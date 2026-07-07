"""OpenAlex /works fetcher. OpenAlex moved to a credits system in 2026 and
now 503s most keyless requests, so: with OPENALEX_API_KEY set, failures are
real errors; without one, 429/503 make this source silently best-effort
(zero items this run) the way Semantic Scholar's shared pool is handled.
CONTACT_MAILTO still joins the polite pool when present."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..http import DEFAULT_TIMEOUT
from ..models import Item, clip, item_id

API = "https://api.openalex.org/works"
SOFT_FAIL_STATUSES = {403, 429, 503}


def _invert_abstract(index: dict | None) -> str:
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, spots in index.items():
        for pos in spots:
            positions.append((pos, word))
    return " ".join(word for _, word in sorted(positions))


def _clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.removeprefix("https://doi.org/").strip() or None


def fetch(source, ctx) -> list[Item]:
    lookback = ctx.site.windows.papers_days * 3  # indexing lags publication
    from_date = (ctx.now - timedelta(days=lookback)).date().isoformat()
    params = {
        "search": source.query,
        "filter": f"from_publication_date:{from_date}",
        "sort": "publication_date:desc",
        "per-page": min(source.max_results, 50),
    }
    mailto = ctx.env.get("CONTACT_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto
    api_key = ctx.env.get("OPENALEX_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key

    resp = ctx.session.get(API, params=params, timeout=DEFAULT_TIMEOUT)
    if resp.status_code in SOFT_FAIL_STATUSES and not api_key:
        return []  # keyless access is best-effort; set OPENALEX_API_KEY to make it reliable
    resp.raise_for_status()
    doc = resp.json()

    items: list[Item] = []
    for work in doc.get("results", []):
        title = (work.get("display_name") or "").strip()
        pub_date = work.get("publication_date")
        if not title or not pub_date:
            continue
        published = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        doi = _clean_doi(work.get("doi"))
        primary = work.get("primary_location") or {}
        url = (primary.get("landing_page_url") or work.get("doi")
               or work.get("id") or "")
        venue = ((primary.get("source") or {}).get("display_name")) or None
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in work.get("authorships", [])
        ][:6]
        abstract = _invert_abstract(work.get("abstract_inverted_index"))
        items.append(Item(
            id=item_id(doi=doi, url=url),
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
            authors=[a for a in authors if a],
            venue=venue,
            extra={"doi": doi, "abstract_snippet": clip(abstract, 500)},
            weight=source.weight,
        ))
    return items
