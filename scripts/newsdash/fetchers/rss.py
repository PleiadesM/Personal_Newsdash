"""RSS/Atom fetcher. Optional ``keywords`` on the source act as a title
filter (e.g. the Hacker News firehose narrowed to AI terms)."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone

import feedparser

from ..http import get
from ..models import Item, clip, detect_lang, item_id, strip_html


def _entry_datetime(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = entry.get(attr)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    return None


def parse_feed_bytes(raw: bytes, source, now: datetime) -> list[Item]:
    feed = feedparser.parse(raw)
    items: list[Item] = []
    for entry in feed.entries[: source.max_results]:
        title = strip_html(entry.get("title", "")).strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        published = _entry_datetime(entry)
        if published is None:
            continue  # undated entries would churn in the 24h window every run
        if source.keywords:
            hay = title.casefold()
            if not any(kw.casefold() in hay for kw in source.keywords):
                continue
        summary = clip(strip_html(entry.get("summary") or entry.get("description") or ""))
        items.append(Item(
            id=item_id(url=link),
            title=title,
            url=link,
            source=source.name,
            source_id=source.id,
            category=source.category,
            section=source.section,
            kind="news",
            published_at=published,
            summary=summary,
            lang=detect_lang(title),
            weight=source.weight,
        ))
    return items


def fetch(source, ctx) -> list[Item]:
    resp = get(ctx.session, source.url)
    return parse_feed_bytes(resp.content, source, ctx.now)
