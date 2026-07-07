"""Semantic Scholar Graph API fetcher (keyless shared pool). Best-effort by
policy: a 429 from the shared pool returns zero items with a note instead of
an exception, so the papers section never degrades just because S2 is busy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..http import DEFAULT_TIMEOUT
from ..models import Item, clip, item_id

API = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,url,publicationDate,venue,authors,externalIds"


def fetch(source, ctx) -> list[Item]:
    from_date = (ctx.now - timedelta(days=ctx.site.windows.papers_days * 3)).date()
    resp = ctx.session.get(API, params={
        "query": source.query,
        "limit": min(source.max_results, 100),
        "fields": FIELDS,
        "publicationDateOrYear": f"{from_date.isoformat()}:",
    }, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 429:
        return []  # shared keyless pool is saturated; try again next run
    resp.raise_for_status()

    items: list[Item] = []
    for paper in resp.json().get("data", []):
        title = (paper.get("title") or "").strip()
        pub_date = paper.get("publicationDate")
        if not title or not pub_date:
            continue
        try:
            published = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        external = paper.get("externalIds") or {}
        doi = (external.get("DOI") or "").lower() or None
        arxiv_id = external.get("ArXiv")
        url = paper.get("url") or (f"https://doi.org/{doi}" if doi else "")
        if not url:
            continue
        abstract = paper.get("abstract") or ""
        items.append(Item(
            id=item_id(doi=doi, arxiv_id=arxiv_id, url=url),
            title=title,
            url=url,
            source=source.name,
            source_id=source.id,
            category=source.category,
            section=source.section,
            kind="paper",
            published_at=published,
            summary=clip(abstract),
            lang="en",
            authors=[a.get("name", "") for a in (paper.get("authors") or [])][:6],
            venue=paper.get("venue") or None,
            extra={"doi": doi, "arxiv_id": arxiv_id,
                   "abstract_snippet": clip(abstract, 500)},
            weight=source.weight,
        ))
    return items
