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
        # Most Smithsonian records have no digitized media at all, so a bare
        # keyword search mostly comes back empty of media entirely — narrow
        # to media-bearing records via `online_media_type:Images` (a
        # documented filter field). There's no confirmed-documented filter
        # field for CC0 specifically (an earlier attempt at "AND
        # media_usage:CC0" was unverified against Smithsonian's own docs and
        # very likely matched nothing, since Open Access's CC0 flag lives at
        # media[].usage.access in the response body, not as an indexed
        # top-level search field) — so widen `rows` instead to improve the
        # odds that at least one of the image-bearing rows happens to carry
        # a CC0 media entry. `_first_cc0_image` is the sole source of truth
        # for the actual CC0 check either way.
        #
        # OR the individual words of a multi-word image_query instead of
        # requiring the literal phrase: seen live returning 0 total matches
        # (not just 0 CC0) for a 3-word LLM-generated phrase like "stormy
        # seas geopolitics" — museum catalog metadata is literal, not
        # poetic, so requiring every word to co-occur is too strict even
        # after summarize.py's prompt was tightened towards concrete nouns.
        terms = image_query.split()
        text_query = f"({' OR '.join(terms)})" if len(terms) > 1 else image_query
        resp = get(session, f"{API_BASE}search",
                   params={"q": f"{text_query} AND online_media_type:Images",
                           "rows": 100, "api_key": api_key})
        body = resp.json().get("response") or {}
        image = _first_cc0_image(body.get("rows") or [])
        if image is None:
            # Distinguishes "ran fine, this phrase just has no CC0 media" —
            # expected, not every image_query will hit — from a real
            # misconfiguration, which raises/logs below instead.
            print(f"[todays-image] no CC0 image for query {image_query!r} "
                  f"({body.get('rowCount', 0)} matches)")
        return image
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        print(f"[todays-image] error: HTTPError ({status})")
        return None
    except Exception as exc:  # noqa: BLE001 — resilience by design
        print(f"[todays-image] error: {type(exc).__name__}: {str(exc)[:200]}")
        return None


def caption_todays_image(image: dict, top_story_title: str, env: Mapping[str, str],
                          session: requests.Session) -> str | None:
    api_key = env.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None
    # `or default`, not `.get(key, default)` — see summarize.py's comment:
    # GitHub Actions emits an empty-string env var, not an absent one, when
    # a referenced `vars.X` doesn't exist in the repo.
    base_url = (env.get("LLM_BASE_URL") or "https://api.openai.com/v1").strip()
    model = (env.get("LLM_MODEL") or "gpt-4o-mini").strip()
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
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        print(f"[todays-image] caption error: HTTPError ({status})")
        return None
    except Exception as exc:  # noqa: BLE001 — resilience by design
        print(f"[todays-image] caption error: {type(exc).__name__}: {str(exc)[:200]}")
        return None
