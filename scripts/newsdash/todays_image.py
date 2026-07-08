"""Optional "Today's Image" enrichment: a public-domain image loosely tied
to today's news/papers, via the Smithsonian Open Access API
(https://api.si.edu/openaccess/api/v1.0/), with a one-sentence AI caption.

Off by default: skips cleanly, zero HTTP calls, whenever
``SMITHSONIAN_API_KEY`` is absent, ``TODAYS_IMAGE_ENABLED=0``, or the LLM
summarizer didn't produce an ``image_query`` (this feature rides on top of
``summarize()`` — see docs/CONFIG_REFERENCE.md).

Rights discipline: only images carrying an explicit ``usage.access ==
"CC0"`` media entry are ever surfaced. If no row in the search results has
one, this returns ``None`` — never a rights-uncertain image.
"""

from __future__ import annotations

from typing import Mapping

import requests

from .http import get

API_BASE = "https://api.si.edu/openaccess/api/v1.0/"
CAPTION_TIMEOUT = 30
CAPTION_MAX_LEN = 240


def _first_cc0_image(rows: list[dict]) -> dict | None:
    for row in rows:
        dnr = (row.get("content") or {}).get("descriptiveNonRepeating") or {}
        media_list = ((dnr.get("online_media") or {}).get("media")) or []
        for media in media_list:
            if ((media.get("usage") or {}).get("access")) == "CC0":
                return {
                    "image_url": media.get("content") or media.get("thumbnail"),
                    "thumbnail_url": media.get("thumbnail"),
                    "title": (dnr.get("title") or {}).get("content", ""),
                    "source_name": dnr.get("data_source", "Smithsonian"),
                    "source_url": dnr.get("record_link"),
                }
    return None


def find_todays_image(image_query: str, env: Mapping[str, str],
                       session: requests.Session) -> dict | None:
    api_key = env.get("SMITHSONIAN_API_KEY", "").strip()
    if not api_key or env.get("TODAYS_IMAGE_ENABLED") == "0" or not image_query:
        return None
    try:
        resp = get(session, f"{API_BASE}search",
                   params={"q": image_query, "rows": 10, "api_key": api_key})
        rows = (resp.json().get("response") or {}).get("rows") or []
        return _first_cc0_image(rows)
    except Exception as exc:  # noqa: BLE001 — resilience by design
        print(f"[todays-image] error: {type(exc).__name__}")
        return None


def caption_todays_image(image: dict, top_story_title: str, env: Mapping[str, str],
                          session: requests.Session) -> str | None:
    api_key = env.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = env.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    model = env.get("LLM_MODEL", "gpt-4o-mini").strip()
    prompt = (
        "In one short sentence, explain a loose, creative connection "
        f'between the public domain image "{image.get("title", "")}" and '
        f'today\'s top story: "{top_story_title}". Reply with only the '
        "sentence, no preamble."
    )
    try:
        resp = session.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=CAPTION_TIMEOUT,
        )
        resp.raise_for_status()
        caption = resp.json()["choices"][0]["message"]["content"].strip()
        return caption[:CAPTION_MAX_LEN] or None
    except Exception as exc:  # noqa: BLE001 — resilience by design
        print(f"[todays-image] caption error: {type(exc).__name__}")
        return None
