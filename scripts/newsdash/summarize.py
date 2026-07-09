"""Optional AI daily-brief enrichment. Off by default: skips cleanly, zero
HTTP calls, whenever ``LLM_API_KEY`` is absent, ``LLM_SUMMARY_ENABLED=0``, or
there is nothing to summarize. Server-side only — the deployer's own key,
never a visitor-supplied one (docs/ROADMAP.md's "core pipeline stays
LLM-free; this is a bolt-on" v0.2 reservation).

Generic OpenAI-Chat-Completions-compatible HTTP call (one POST, JSON body,
Bearer auth) so any compatible endpoint works: OpenAI, OpenRouter, Groq,
Together, self-hosted Ollama/vLLM — no provider SDK, no new dependency.
"""

from __future__ import annotations

import json
from typing import Mapping

import requests

LLM_TIMEOUT = 60  # completions run far longer than the DEFAULT_TIMEOUT GETs
MAX_NEWS_ITEMS = 20
MAX_PAPER_ITEMS = 10
SUMMARY_KEYS = ("brief", "news_summary", "papers_summary")
RESPONSE_KEYS = (*SUMMARY_KEYS, "image_query")
LANGS = ("en", "zh")
LANG_NAMES = {"en": "English", "zh": "Simplified Chinese"}

# Reasoning-capable models (DeepSeek reasoner/R1-style, o1-style, etc.) spend
# part of this same budget on a hidden chain-of-thought before ever emitting
# visible content — a low cap can exhaust itself entirely on reasoning and
# come back with finish_reason="length" and an empty `content`. 2000 leaves
# headroom for that without meaningfully changing cost for plain chat models.
MAX_RESPONSE_TOKENS = 2000

# Providers that support strict JSON mode (OpenAI, DeepSeek, and most
# OpenAI-compatible gateways) enforce two things: the literal word "json"
# somewhere in the prompt, and a shown example of the desired shape — both
# satisfied below. Content is still defensively unwrapped in _extract_json
# in case a provider ignores response_format and adds markdown fencing.
SYSTEM_PROMPT = (
    "You write a short daily brief for a personal news dashboard. "
    "You are writing the __LANGUAGE__ edition. Read both the priority-language "
    "items and the cross-language context items, but make the priority-language "
    "items the center of the brief. Use the cross-language items only for "
    "context, contrast, or to mention important developments missing from the "
    "priority-language pool. Write brief, news_summary, and papers_summary in "
    "__LANGUAGE__. Respond with a single json object shaped exactly like this "
    "example (same keys, your own values):\n"
    '{"brief": "1-3 sentences summarizing today across both news and '
    'papers", "news_summary": "1-2 sentences on the news items", '
    '"papers_summary": "1-2 sentences on the papers", "image_query": '
    '"1-2 concrete English nouns for searching a museum collection — a '
    "physical object, tool, animal, place, or historical-era subject "
    "that would plausibly appear in a real museum catalog title, loosely "
    "connected to today's content. No metaphors, no abstract concepts, "
    'no adjectives, no proper nouns — e.g. \'lighthouse\', \'compass '
    "clock', 'steam locomotive' rather than 'stormy geopolitics' or "
    '\'digital revolution\'"}'
)


def _item_lines(items: list[dict], limit: int) -> str:
    lines = []
    for it in items[:limit]:
        title = (it.get("title") or "").strip()
        summary = (it.get("summary") or "").strip()
        source = (it.get("source") or "").strip()
        if not title:
            continue
        lines.append(f"- {title} ({source}): {summary}"[:280])
    return "\n".join(lines) or "(none)"


def _lang_items(items: list[dict], lang: str) -> list[dict]:
    return [it for it in items if (it.get("lang") or "en") == lang]


def _post_chat(base_url: str, api_key: str, model: str, messages: list[dict],
                session: requests.Session, *, json_mode: bool = False) -> str:
    body = {"model": model, "messages": messages, "max_tokens": MAX_RESPONSE_TOKENS}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    resp = session.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json=body,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    choice = resp.json()["choices"][0]
    content = (choice.get("message") or {}).get("content") or ""
    if not content.strip():
        # Surfaces as a clear ValueError instead of a downstream
        # JSONDecodeError("Expecting value: line 1 column 1 (char 0)") when
        # _extract_json is handed "" — see MAX_RESPONSE_TOKENS comment for
        # the usual cause (reasoning models truncated before real content).
        finish_reason = choice.get("finish_reason", "?")
        raise ValueError(f"empty completion content (finish_reason={finish_reason})")
    return content


def _extract_json(content: str) -> dict:
    # Defensive unwrap: some OpenAI-compatible providers accept
    # response_format but still wrap output in a ```json fence or add a
    # leading/trailing sentence.
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def _prompt_for_lang(payloads: dict[str, dict], target_lang: str) -> str:
    other_lang = "zh" if target_lang == "en" else "en"
    news_items = payloads.get("news", {}).get("items", [])
    paper_items = payloads.get("papers", {}).get("items", [])
    target = LANG_NAMES[target_lang]
    other = LANG_NAMES[other_lang]
    return (
        f"Priority {target} news:\n"
        f"{_item_lines(_lang_items(news_items, target_lang), MAX_NEWS_ITEMS)}\n\n"
        f"Context from {other} news:\n"
        f"{_item_lines(_lang_items(news_items, other_lang), MAX_NEWS_ITEMS)}\n\n"
        f"Priority {target} papers/research:\n"
        f"{_item_lines(_lang_items(paper_items, target_lang), MAX_PAPER_ITEMS)}\n\n"
        f"Context from {other} papers/research:\n"
        f"{_item_lines(_lang_items(paper_items, other_lang), MAX_PAPER_ITEMS)}"
    )


def _summarize_lang(payloads: dict[str, dict], target_lang: str, base_url: str,
                    api_key: str, model: str, session: requests.Session) -> dict | None:
    try:
        content = _post_chat(
            base_url, api_key, model,
            [{"role": "system",
              "content": SYSTEM_PROMPT.replace(
                  "__LANGUAGE__", LANG_NAMES[target_lang])},
             {"role": "user", "content": _prompt_for_lang(payloads, target_lang)}],
            session, json_mode=True,
        )
        result = _extract_json(content)
        if not all(k in result for k in RESPONSE_KEYS):
            print(f"[llm-summary:{target_lang}] error: response missing keys, "
                  f"got {list(result)}")
            return None
        return {k: result[k] for k in RESPONSE_KEYS}
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        detail = ""
        if exc.response is not None:
            detail = exc.response.text.strip().replace(api_key, "***")[:200]
        print(f"[llm-summary:{target_lang}] error: HTTPError ({status}) {detail}")
        return None
    except Exception as exc:  # noqa: BLE001 — resilience by design
        print(f"[llm-summary:{target_lang}] error: {type(exc).__name__}: "
              f"{str(exc)[:200]}")
        return None


def summarize(payloads: dict[str, dict], env: Mapping[str, str],
              session: requests.Session) -> dict | None:
    api_key = env.get("LLM_API_KEY", "").strip()
    if not api_key or env.get("LLM_SUMMARY_ENABLED") == "0":
        return None

    news_items = payloads.get("news", {}).get("items", [])
    paper_items = payloads.get("papers", {}).get("items", [])
    if not news_items and not paper_items:
        return None

    # `or default`, not `.get(key, default)`: GitHub Actions sets the env var
    # to an empty string (not absent) when a referenced `vars.X` doesn't
    # exist in the repo, and `.get` only falls back on a missing key.
    base_url = (env.get("LLM_BASE_URL") or "https://api.openai.com/v1").strip()
    model = (env.get("LLM_MODEL") or "gpt-4o-mini").strip()

    raw = {
        lang: _summarize_lang(payloads, lang, base_url, api_key, model, session)
        for lang in LANGS
    }
    summaries = {
        lang: {k: result[k] for k in SUMMARY_KEYS}
        for lang, result in raw.items()
        if result
    }
    if not summaries:
        return None
    result = {"summaries": summaries}
    # Backward compatibility for older frontend bundles and cached pages:
    # keep the original top-level fields as the English/default edition.
    fallback_lang = "en" if "en" in summaries else next(iter(summaries))
    result.update(summaries[fallback_lang])
    image_source = raw.get("en") or raw.get(fallback_lang)
    if image_source and image_source.get("image_query"):
        result["image_query"] = image_source["image_query"]
    return result
