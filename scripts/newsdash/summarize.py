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
RESPONSE_KEYS = ("brief", "news_summary", "papers_summary", "image_query")

SYSTEM_PROMPT = (
    "You write a short daily brief for a personal news dashboard. "
    "Reply with ONLY a JSON object (no markdown, no code fence) with "
    'exactly these keys: "brief" (1-3 sentences summarizing today across '
    'both news and papers), "news_summary" (1-2 sentences on the news '
    'items), "papers_summary" (1-2 sentences on the papers), "image_query" '
    "(a short, loose, creative 2-4 word phrase for searching a public "
    "domain art/photo archive for an image thematically connected to "
    "today's content — favor evocative general themes over proper nouns)."
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


def _post_chat(base_url: str, api_key: str, model: str, messages: list[dict],
                session: requests.Session) -> str:
    resp = session.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json={"model": model, "messages": messages},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def summarize(payloads: dict[str, dict], env: Mapping[str, str],
              session: requests.Session) -> dict | None:
    api_key = env.get("LLM_API_KEY", "").strip()
    if not api_key or env.get("LLM_SUMMARY_ENABLED") == "0":
        return None

    news_items = payloads.get("news", {}).get("items", [])
    paper_items = payloads.get("papers", {}).get("items", [])
    if not news_items and not paper_items:
        return None

    base_url = env.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    model = env.get("LLM_MODEL", "gpt-4o-mini").strip()

    prompt = (
        f"Today's top news:\n{_item_lines(news_items, MAX_NEWS_ITEMS)}\n\n"
        f"Today's top papers:\n{_item_lines(paper_items, MAX_PAPER_ITEMS)}"
    )

    try:
        content = _post_chat(
            base_url, api_key, model,
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": prompt}],
            session,
        )
        result = json.loads(content)
        if not all(k in result for k in RESPONSE_KEYS):
            return None
        return {k: result[k] for k in RESPONSE_KEYS}
    except Exception as exc:  # noqa: BLE001 — resilience by design
        print(f"[llm-summary] error: {type(exc).__name__}")
        return None
