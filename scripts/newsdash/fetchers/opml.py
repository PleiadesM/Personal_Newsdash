"""OPML fetcher: expand an OPML file (local ``path`` or remote ``url``) into
RSS sub-fetches. Radar-compatible private-subscription route: the workflow
decodes FOLLOW_OPML_B64 into feeds/follow.opml, which never gets committed."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace

from ..http import get
from ..models import Item
from . import rss

DEFAULT_MAX_FEEDS = 10


def _outlines(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    feeds = []
    for node in root.iter("outline"):
        xml_url = node.get("xmlUrl")
        if xml_url:
            feeds.append({
                "url": xml_url,
                "name": node.get("title") or node.get("text") or xml_url,
            })
    return feeds


def fetch(source, ctx) -> list[Item]:
    if source.url:
        raw = get(ctx.session, source.url).content
    else:
        opml_path = (ctx.repo_root / source.path) if ctx.repo_root else source.path
        with open(opml_path, "rb") as fh:
            raw = fh.read()

    max_feeds = int(ctx.env.get("RSS_MAX_FEEDS", DEFAULT_MAX_FEEDS))
    items: list[Item] = []
    for idx, feed in enumerate(_outlines(raw)[:max_feeds]):
        sub = replace(source, id=f"{source.id}_{idx}", name=feed["name"],
                      url=feed["url"], path=None)
        try:
            sub_items = rss.fetch(sub, ctx)
        except Exception:  # noqa: BLE001 — one dead feed must not kill the OPML
            continue
        for item in sub_items:
            item.source_id = source.id  # status/filters group under the OPML source
        items.extend(sub_items)
    return items
