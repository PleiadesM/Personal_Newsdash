"""Threads · 线索 — LLM keyword aggregation across sources.

One bilingual LLM call per scope surfaces up to ``max_threads`` keyword-themes
that at least two *different* sources touched today. Each thread carries a
cognitively-light bilingual gloss, a "why now" occasion line, a convergence
verdict, and per-source *angles* that the pipeline resolves back to ground
truth (item id / section / source / url / full-text file) so the model can
never fabricate a link — out-of-range refs and single-source threads are
dropped here, not trusted from the model.

Two fully separated scopes:

- ``scope="public"``  — reads only non-private-category payloads.
- ``scope="private"`` — reads only ``category:"private"`` payloads; its output
  is always encrypted by the caller and NEVER written as plaintext. Failure
  logging on this path is detail-free (public Actions logs): exactly
  ``[threads:private] error: <ExceptionTypeName> (detail withheld)``.

Off by default the same way summarize.py is: no ``LLM_API_KEY``,
``LLM_THREADS_ENABLED=0``, an empty pool, or a single-source pool all return
``None`` before any HTTP call.
"""

from __future__ import annotations

from typing import Mapping

import jsonschema
import requests

from .llm import extract_json, post_chat, resolve_endpoint
from .models import clip, strip_html

# Input caps (per bilingual call). News/papers are capped separately for the
# public scope so a busy news day can't crowd papers out of the pool; the
# private pool is a single flat cap.
MAX_INPUT_NEWS = 30
MAX_INPUT_PAPERS = 12
MAX_INPUT_PRIVATE = 30
SUMMARY_CLIP = 200

# Reasoning-capable models (DeepSeek reasoner/R1-style, o1-style) spend part
# of this budget on hidden chain-of-thought before emitting visible content,
# and this call asks for several bilingual threads at once — a bigger payload
# than summarize.py's brief. 4000 leaves headroom so a reasoning model does
# not truncate mid-JSON and come back with finish_reason="length".
THREADS_MAX_TOKENS = 4000

MIN_THREADS = 2  # fewer than this and we fall back to Highlights, not a thin block

KEYWORD_CLIP = 40
GLOSS_CLIP = 240
WHY_NOW_CLIP = 120
PHRASE_MAX_WORDS = 8
PHRASE_ZH_CLIP = 32  # safety clip for the zh angle phrase (prompt asks for ≤16字)

CONVERGENCE_VALUES = {"convergent", "mixed", "divergent"}

_BILINGUAL_SCHEMA = {
    "type": "object",
    "required": ["en", "zh"],
    "properties": {
        "en": {"type": "string"},
        "zh": {"type": "string"},
    },
}

# Validated per-thread (invalid threads are dropped individually, valid ones
# kept) rather than validating the whole response as a unit.
THREAD_SCHEMA = {
    "type": "object",
    "required": ["keyword", "gloss", "why_now", "convergence", "angles"],
    "properties": {
        "keyword": _BILINGUAL_SCHEMA,
        "gloss": _BILINGUAL_SCHEMA,
        "why_now": _BILINGUAL_SCHEMA,
        "convergence": {"type": "string"},
        "relates_to": {"type": "array", "items": {"type": "integer"}},
        "angles": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "required": ["item", "phrase"],
                "properties": {
                    "item": {"type": "integer"},
                    "phrase": _BILINGUAL_SCHEMA,
                },
            },
        },
    },
}

RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["threads"],
    "properties": {
        "threads": {"type": "array", "items": THREAD_SCHEMA},
    },
}

# JSON-mode requirement (same pattern as summarize.py): the literal word
# "json" plus a shown example of the exact shape. "__MAX_THREADS__" is
# substituted per call.
SYSTEM_PROMPT = (
    "You are the thread editor for a personal news dashboard. You are given a "
    "numbered list of today's items across several sources. Find up to "
    "__MAX_THREADS__ keyword-themes where AT LEAST TWO DIFFERENT SOURCES land "
    "on the same topic today — a theme only one source touches is not a "
    "thread. For each thread write: a short bilingual keyword (en + zh); a "
    "cognitively light gloss of 1-2 sentences, plain and possibly a little "
    "poetic, that a tired reader can absorb at a glance (en + zh); a one-line "
    "'why now' note naming today's occasion for the theme (en + zh); and, for "
    "every supporting item, an angle {\"item\": <the number from the list>, "
    "\"phrase\": {\"en\": \"how THAT source frames the theme, <=8 words\", "
    "\"zh\": \"<=16 characters\"}}. Reference items only by their number; do "
    "not invent items. Give each thread a convergence verdict: 'convergent' "
    "when the sources agree, 'mixed' when they partly diverge, 'divergent' "
    "when they clash. Optionally add relates_to: the numbers of OTHER threads "
    "in this same answer that connect to this one. Respond with a single json "
    "object shaped exactly like this example (same keys, your own values):\n"
    '{"threads": [{"keyword": {"en": "compute sovereignty", "zh": "算力主权"}, '
    '"gloss": {"en": "Nations race to own the chips that own the future.", '
    '"zh": "各国竞相掌握决定未来的芯片。"}, "why_now": {"en": "Two new export '
    'rules landed today.", "zh": "今日出台两项新出口规定。"}, "convergence": '
    '"mixed", "relates_to": [2], "angles": [{"item": 1, "phrase": {"en": '
    '"frames it as security", "zh": "视为安全议题"}}, {"item": 4, "phrase": '
    '{"en": "frames it as trade", "zh": "视为贸易议题"}}]}]}'
)


def _pool_items(payloads: dict[str, dict], scope: str) -> list[dict]:
    """Flatten payload items, sort by score desc, cap, and return an ordered
    list whose position (index + 1) is the number the prompt shows the model."""
    pooled: list[tuple[str, dict]] = []
    for payload in payloads.values():
        kind = (payload.get("meta") or {}).get("kind", "news")
        for it in payload.get("items", []):
            pooled.append((kind, it))
    pooled.sort(key=lambda pair: pair[1].get("score") or 0, reverse=True)

    if scope == "private":
        return [it for _, it in pooled][:MAX_INPUT_PRIVATE]

    items: list[dict] = []
    counts = {"news": 0, "papers": 0}
    for kind, it in pooled:
        bucket = "papers" if kind == "papers" else "news"
        cap = MAX_INPUT_PAPERS if bucket == "papers" else MAX_INPUT_NEWS
        if counts[bucket] < cap:
            items.append(it)
            counts[bucket] += 1
    return items


def _prompt_lines(items: list[dict]) -> str:
    lines = []
    for i, it in enumerate(items, start=1):
        title = strip_html(it.get("title") or "").strip()
        source = strip_html(it.get("source") or "").strip()
        kind = it.get("kind") or "news"
        summary = clip(strip_html(it.get("summary") or ""), SUMMARY_CLIP)
        lines.append(f"[{i}] {title} ({source}) [{kind}]: {summary}")
    return "\n".join(lines)


def _clip_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def _bilingual(raw, clip_len: int) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "en": clip(strip_html(str(raw.get("en") or "")), clip_len),
        "zh": clip(strip_html(str(raw.get("zh") or "")), clip_len),
    }


def _normalize_thread(raw: dict, items: list[dict]) -> dict | None:
    """Resolve the model's numeric refs against ground truth and sanitize
    every model-authored string. Returns ``None`` for a thread that, after
    dropping out-of-range refs and deduping by resolved item, does not link
    at least two distinct sources."""
    n = len(items)
    seen_item_ids: set[str] = set()
    source_ids: set[str] = set()
    angles: list[dict] = []
    for a in raw.get("angles", []):
        if not isinstance(a, dict):
            continue
        ref = a.get("item")
        if not isinstance(ref, int) or isinstance(ref, bool) or ref < 1 or ref > n:
            continue
        item = items[ref - 1]
        item_id = item.get("id") or ""
        if item_id in seen_item_ids:
            continue
        seen_item_ids.add(item_id)
        source_ids.add(item.get("source_id") or item.get("source") or "")
        phrase = a.get("phrase") if isinstance(a.get("phrase"), dict) else {}
        angle = {
            "item_id": item_id,
            "section": item.get("section") or "",
            "source": strip_html(str(item.get("source") or "")).strip(),
            "phrase": {
                "en": _clip_words(
                    strip_html(str(phrase.get("en") or "")).strip(),
                    PHRASE_MAX_WORDS),
                "zh": clip(strip_html(str(phrase.get("zh") or "")).strip(),
                           PHRASE_ZH_CLIP),
            },
            "url": item.get("url") or "",
        }
        # Only carry an in-app reader link when the resolved item actually has
        # a full-text file — never fabricated from model output.
        if item.get("full_text_file"):
            angle["full_text_file"] = item["full_text_file"]
        angles.append(angle)

    if len(source_ids) < 2:
        return None

    convergence = raw.get("convergence")
    if convergence not in CONVERGENCE_VALUES:
        convergence = "mixed"

    return {
        "keyword": _bilingual(raw.get("keyword"), KEYWORD_CLIP),
        "gloss": _bilingual(raw.get("gloss"), GLOSS_CLIP),
        "why_now": _bilingual(raw.get("why_now"), WHY_NOW_CLIP),
        "convergence": convergence,
        "angles": angles,
        # 1-based response positions of related threads; resolved to ids by
        # _link_relates once every surviving thread has an id.
        "_relates": [r for r in (raw.get("relates_to") or [])
                     if isinstance(r, int) and not isinstance(r, bool)],
    }


def _link_relates(threads: list[dict], positions: list[int]) -> None:
    """Map each surviving thread's 1-based response positions to assigned ids,
    dropping self-references and dangling refs (positions that did not
    survive)."""
    pos_to_id = {pos: t["id"] for t, pos in zip(threads, positions)}
    for t in threads:
        linked: list[str] = []
        seen: set[str] = set()
        for r in t.pop("_relates", []):
            target = pos_to_id.get(r)
            if target and target != t["id"] and target not in seen:
                seen.add(target)
                linked.append(target)
        t["relates_to"] = linked


def _log_error(scope: str, exc: Exception, api_key: str) -> None:
    if scope == "private":
        # Public Actions logs: never a title, count, status, or body.
        print(f"[threads:private] error: {type(exc).__name__} (detail withheld)")
        return
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        detail = exc.response.text.strip().replace(api_key, "***")[:200]
        print(f"[threads:public] error: HTTPError ({status}) {detail}")
    else:
        detail = str(exc)[:200].replace(api_key, "***")
        print(f"[threads:public] error: {type(exc).__name__}: {detail}")


def generate_threads(payloads: dict[str, dict], env: Mapping[str, str],
                     session: requests.Session, *, scope: str,
                     max_threads: int = 6) -> dict | None:
    api_key = env.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None
    if env.get("LLM_THREADS_ENABLED") == "0":
        return None

    items = _pool_items(payloads, scope)
    if not items:
        return None
    distinct = {(it.get("source_id") or it.get("source") or "") for it in items}
    if len(distinct) < 2:
        # A thread needs two different sources; a single-source pool can't
        # produce one, so skip the call entirely (zero HTTP).
        return None

    base_url, model = resolve_endpoint(env)
    try:
        content = post_chat(
            base_url, api_key, model,
            [{"role": "system",
              "content": SYSTEM_PROMPT.replace("__MAX_THREADS__", str(max_threads))},
             {"role": "user", "content": _prompt_lines(items)}],
            session, json_mode=True, max_tokens=THREADS_MAX_TOKENS,
        )
        data = extract_json(content)
    except Exception as exc:  # noqa: BLE001 — enrichment must not fail builds
        _log_error(scope, exc, api_key)
        return None

    raw_threads = data.get("threads") if isinstance(data, dict) else None
    if not isinstance(raw_threads, list):
        return None

    validator = jsonschema.Draft202012Validator(THREAD_SCHEMA)
    threads: list[dict] = []
    positions: list[int] = []
    for pos, raw in enumerate(raw_threads, start=1):
        if not isinstance(raw, dict) or not validator.is_valid(raw):
            continue
        thread = _normalize_thread(raw, items)
        if thread is None:
            continue
        threads.append(thread)
        positions.append(pos)
        if len(threads) >= max_threads:
            break

    if len(threads) < MIN_THREADS:
        return None

    prefix = "p" if scope == "private" else "t"
    for i, thread in enumerate(threads, start=1):
        thread["id"] = f"{prefix}{i}"
    _link_relates(threads, positions)
    return {"scope": scope, "threads": threads}
