"""CrossRef /works fetcher. Two modes: journal tracking via ``issn`` (one
request per ISSN, newest records first — how the techcomm preset follows
journals that never touch arXiv) and free-text ``query``. Recency is judged
by CrossRef's ``created`` date (when the record appeared), which is what
"new this week" means for slow-moving journals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..http import get
from ..models import Item, clip, item_id, strip_html

API = "https://api.crossref.org/works"
TIMEOUT = 30  # CrossRef can be slow


def _work_datetime(work: dict) -> datetime | None:
    created = (work.get("created") or {}).get("date-time")
    if not created:
        return None
    try:
        return datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _work_to_item(work: dict, source) -> Item | None:
    titles = work.get("title") or []
    title = strip_html(titles[0]).strip() if titles else ""
    doi = (work.get("DOI") or "").strip().lower() or None
    published = _work_datetime(work)
    if not title or not doi or published is None:
        return None
    url = work.get("URL") or f"https://doi.org/{doi}"
    containers = work.get("container-title") or []
    venue = containers[0] if containers else None
    authors = [
        " ".join(filter(None, [a.get("given"), a.get("family")]))
        for a in (work.get("author") or [])
    ][:6]
    abstract = strip_html(work.get("abstract") or "")
    return Item(
        id=item_id(doi=doi),
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
    )


def fetch(source, ctx) -> list[Item]:
    lookback = ctx.site.windows.papers_days * 4  # journal records trickle in
    from_date = (ctx.now - timedelta(days=lookback)).date().isoformat()
    mailto = ctx.env.get("CONTACT_MAILTO", "").strip()

    requests_params: list[dict] = []
    if source.issn:
        rows = max(10, source.max_results // len(source.issn))
        for issn in source.issn:
            requests_params.append({
                "filter": f"issn:{issn},from-created-date:{from_date}",
                "rows": rows, "sort": "created", "order": "desc",
            })
    else:
        requests_params.append({
            "query": source.query,
            "filter": f"from-created-date:{from_date}",
            "rows": min(source.max_results, 50), "sort": "created", "order": "desc",
        })

    items: list[Item] = []
    for params in requests_params:
        if mailto:
            params["mailto"] = mailto
        doc = get(ctx.session, API, params=params, timeout=TIMEOUT).json()
        for work in (doc.get("message") or {}).get("items", []):
            item = _work_to_item(work, source)
            if item is not None:
                items.append(item)
    return items
