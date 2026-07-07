"""Focused static-page fetcher for sources with no feed at all.

The source's ``query`` field is a CSS selector for the link elements to
harvest (default ``a``). Static pages carry no timestamps, so items are
stamped with the build time; they stay listed while they stay on the page.
Prefer a real RSS/Atom feed whenever one exists — this fetcher is the
last resort, as in ai-news-radar."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..http import get
from ..models import Item, detect_lang, item_id, strip_html

MAX_LINKS = 30


def fetch(source, ctx) -> list[Item]:
    resp = get(ctx.session, source.url)
    soup = BeautifulSoup(resp.text, "html.parser")
    selector = source.query or "a"
    items: list[Item] = []
    seen: set[str] = set()
    for node in soup.select(selector)[: MAX_LINKS * 3]:
        anchor = node if node.name == "a" else node.find("a")
        if anchor is None or not anchor.get("href"):
            continue
        title = strip_html(anchor.get_text(" ", strip=True) or node.get_text(" ", strip=True))
        link = urljoin(source.url, anchor["href"])
        if not title or len(title) < 8 or link in seen:
            continue
        if source.keywords:
            hay = title.casefold()
            if not any(kw.casefold() in hay for kw in source.keywords):
                continue
        seen.add(link)
        items.append(Item(
            id=item_id(url=link),
            title=title,
            url=link,
            source=source.name,
            source_id=source.id,
            category=source.category,
            section=source.section,
            kind="news",
            published_at=ctx.now,
            summary="",
            lang=detect_lang(title),
            weight=source.weight,
        ))
        if len(items) >= min(source.max_results, MAX_LINKS):
            break
    return items
