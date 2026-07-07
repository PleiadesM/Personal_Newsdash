"""Cross-source deduplication: URL canonicalization, title fingerprints,
and DOI/arXiv identity for papers (the same paper reliably arrives from
arXiv, OpenAlex, and Semantic Scholar at once)."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Item

_TRACKING_EXACT = {
    "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "ref", "ref_src",
    "cmpid", "smid", "ncid", "ocid", "igshid", "source",
}
_WORD_STRIP_RE = re.compile(r"[\W_]+", re.UNICODE)


def canonical_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    scheme = "https" if parts.scheme in ("http", "https") else parts.scheme
    host = parts.hostname or ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_EXACT
    ]
    path = parts.path.rstrip("/") or ""
    return urlunsplit((scheme, host, path, urlencode(sorted(query)), ""))


def title_fingerprint(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).casefold()
    return _WORD_STRIP_RE.sub("", text)


def _identity_keys(item: Item) -> list[str]:
    keys: list[str] = []
    doi = item.extra.get("doi")
    if doi:
        keys.append(f"doi:{str(doi).strip().lower()}")
    arxiv = item.extra.get("arxiv_id")
    if arxiv:
        keys.append(f"arxiv:{str(arxiv).strip().lower()}")
    if item.url:
        keys.append(f"url:{canonical_url(item.url)}")
    fp = title_fingerprint(item.title)
    if len(fp) >= 12:  # short fingerprints collide too easily
        keys.append(f"fp:{fp}")
    return keys


def dedupe_items(items: list[Item]) -> list[Item]:
    """Merge duplicates; the higher-weight (then earlier-published) copy wins.

    Losers are recorded in the winner's ``extra["also_in"]`` so multi-source
    confirmation stays visible to the reader.
    """
    ordered = sorted(items, key=lambda it: (-it.weight, it.published_at))
    claimed: dict[str, Item] = {}
    winners: list[Item] = []
    for item in ordered:
        keys = _identity_keys(item)
        winner = next((claimed[k] for k in keys if k in claimed), None)
        if winner is None:
            winners.append(item)
            for k in keys:
                claimed[k] = item
        else:
            if winner.source_id != item.source_id:
                also = winner.extra.setdefault("also_in", [])
                entry = {"source": item.source, "url": item.url}
                if entry not in also:
                    also.append(entry)
            # a duplicate may know identities the winner lacked (e.g. DOI)
            for k in keys:
                claimed.setdefault(k, winner)
    return winners
