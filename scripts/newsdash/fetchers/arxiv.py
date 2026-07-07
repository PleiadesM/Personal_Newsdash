"""arXiv Atom API fetcher. Etiquette per arXiv's API terms: a module-level
throttle keeps ≥3 s between requests, one request per source. No new
announcements on weekends — an empty Saturday is normal, not an error."""

from __future__ import annotations

import calendar
import re
import time
from datetime import datetime, timezone

import feedparser

from ..http import get
from ..models import Item, clip, item_id, strip_html

API = "https://export.arxiv.org/api/query"
THROTTLE_SECONDS = 3.0
_last_call = 0.0

_ARXIV_ID_RE = re.compile(r"abs/([0-9]{4}\.[0-9]{4,5})")


def _throttle() -> None:
    global _last_call
    wait = _last_call + THROTTLE_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def fetch(source, ctx) -> list[Item]:
    _throttle()
    resp = get(ctx.session, API, params={
        "search_query": source.query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": min(source.max_results, 100),
    })
    feed = feedparser.parse(resp.content)
    items: list[Item] = []
    for entry in feed.entries:
        title = re.sub(r"\s+", " ", strip_html(entry.get("title", ""))).strip()
        link = entry.get("link", "")
        parsed = entry.get("published_parsed")
        if not title or not link or not parsed:
            continue
        published = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        abstract = strip_html(entry.get("summary", ""))
        if source.keywords:
            hay = f"{title} {abstract}".casefold()
            if not any(kw.casefold() in hay for kw in source.keywords):
                continue
        match = _ARXIV_ID_RE.search(entry.get("id", "") or link)
        arxiv_id = match.group(1) if match else None
        primary = entry.get("arxiv_primary_category", {}).get("term") or (
            entry.tags[0]["term"] if entry.get("tags") else None
        )
        items.append(Item(
            id=item_id(arxiv_id=arxiv_id, url=link),
            title=title,
            url=link,
            source=source.name,
            source_id=source.id,
            category=source.category,
            section=source.section,
            kind="paper",
            published_at=published,
            summary=clip(abstract),
            lang="en",
            authors=[a.get("name", "") for a in entry.get("authors", [])][:6],
            venue=f"arXiv {primary}" if primary else "arXiv",
            extra={
                "arxiv_id": arxiv_id,
                "abstract_snippet": clip(abstract, 500),
            },
            weight=source.weight,
        ))
    return items
