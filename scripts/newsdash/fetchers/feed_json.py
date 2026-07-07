"""JSON feed fetcher: JSON Feed 1.x documents and the bare-array feeds that
GitHub-actions-generated projects commonly publish (radar's
"GitHub project feed" pattern — consume the public output, don't rebuild
the crawler)."""

from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as dateparser

from ..http import get
from ..models import Item, clip, detect_lang, item_id, strip_html


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = dateparser.parse(str(value))
    except (ValueError, OverflowError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fetch(source, ctx) -> list[Item]:
    doc = get(ctx.session, source.url).json()
    entries = doc.get("items", []) if isinstance(doc, dict) else doc
    items: list[Item] = []
    for entry in entries[: source.max_results]:
        if not isinstance(entry, dict):
            continue
        title = strip_html(entry.get("title", "")).strip()
        link = (entry.get("url") or entry.get("link") or entry.get("external_url") or "").strip()
        published = _parse_date(
            entry.get("date_published") or entry.get("published_at")
            or entry.get("date") or entry.get("pubDate")
        )
        if not title or not link or published is None:
            continue
        if source.keywords:
            hay = title.casefold()
            if not any(kw.casefold() in hay for kw in source.keywords):
                continue
        summary = clip(strip_html(
            entry.get("summary") or entry.get("content_text")
            or entry.get("content_html") or entry.get("description") or ""
        ))
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
