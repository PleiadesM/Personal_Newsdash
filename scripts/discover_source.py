#!/usr/bin/env python3
"""Source-discovery helper: identify and evaluate feeds before adding them.

A maintainer aide for the "add a source" workflow. Given a site URL it finds
the RSS/Atom feed, checks that the feed actually parses and is fresh, and emits
a ready-to-paste ``config/sources.json`` snippet. It can also expand an OPML
export and flag duplicates against the already-configured sources.

Design: all network I/O lives in a thin CLI layer; the interesting logic is a
handful of pure functions (``is_capability_url``, ``autodiscover_feeds``,
``probe_feed``, ``opml_feeds``, ``find_duplicates``) that take bytes/objects and
return data, so the whole thing is unit-testable with no network.

SAFETY: a capability URL (a credential — e.g. a calendar ICS link with a secret
token in it) must never be probed, printed, or logged. ``probe`` refuses such a
URL up front, before any network call, and exits 3 without ever echoing it. Such
feeds belong in a PRIVATE source (category "private", secret_ref
["SRC_<ID>_URL"]) whose capability URL lives in a GitHub Secret, never in config.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlsplit, parse_qsl

# The package lives under scripts/; make it importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from newsdash.config import Config, SourceConfig, load_config  # noqa: E402
from newsdash.fetchers.rss import parse_feed_bytes  # noqa: E402
from newsdash.http import get, make_session  # noqa: E402

# --------------------------------------------------------------------------- #
# Capability-URL heuristics
#
# Kept as module constants so both the tests and the maintainer skill can refer
# to the exact same list. If a URL trips ANY of these it is treated as a
# credential: refuse to probe, tell the user to classify it PRIVATE, never echo.
# --------------------------------------------------------------------------- #

# Query-string parameter NAMES (lowercased, matched by SUBSTRING) that carry
# secrets. Substring match so "access_token", "api_key", "apikey", "x-hmac",
# "auth_sig", "X-Amz-Signature" all trip via one of these fragments.
CAPABILITY_QUERY_PARAMS = (
    "token", "key", "secret", "sig", "signature", "auth", "hmac", "credential",
)

# Any query-param name starting with one of these prefixes is a presigned
# request. "x-amz-" covers the whole AWS SigV4 family (X-Amz-Signature,
# X-Amz-Credential, X-Amz-Security-Token, X-Amz-Date, X-Amz-Expires, ...).
CAPABILITY_QUERY_PARAM_PREFIXES = ("x-amz-",)

# Path substrings (matched case-insensitively) typical of private/calendar URLs.
# ".ics" and "/ical/" catch calendar capability links (Google/Outlook/Apple).
CAPABILITY_PATH_MARKERS = ("/private/", "/ical/", ".ics")

# Opaque-token regex: a run of base64url characters. Applied with a length
# threshold (lowered from 24 to 16 so shorter real tokens are still caught):
#   - query values & fragment values: >= 16 chars is enough on its own.
#   - path segments: >= 16 chars AND the segment has a digit OR mixed case, so
#     ordinary long lowercase slugs ("the-quick-brown-fox-jumps") are NOT
#     flagged while real tokens ("AbCdEf0123456789AbCd") are. (Heuristic; a
#     lowercase-only, digitless 16+ slug is assumed to be a human-readable slug.)
OPAQUE_TOKEN_MIN_LEN = 16
CAPABILITY_OPAQUE_TOKEN = re.compile(r"[A-Za-z0-9_-]{%d,}" % OPAQUE_TOKEN_MIN_LEN)

# JWT: the canonical header prefix "eyJ" (base64url of '{"'), or 2-3 dot-joined
# base64url parts of plausible length. Caught in path segments and in query /
# fragment values.
JWT_PREFIX = "eyJ"
_JWT_PART = r"[A-Za-z0-9_-]{8,}"
CAPABILITY_JWT = re.compile(r"%s(\.%s){1,2}" % (_JWT_PART, _JWT_PART))

# Hostnames known to serve capability-bearing feeds/calendars/webhooks.
# Substring match (host contains marker):
CAPABILITY_HOST_MARKERS = (
    "calendar.google.com", "outlook.office365.com", "outlook.live.com",
    "hooks.slack.com", "caldav.icloud.com", "caldav.fastmail.com", "p.ical",
)

# Suffix match (host ends with suffix): any subdomain of these.
# ".slack.com" covers hooks.slack.com and any other *.slack.com webhook host.
CAPABILITY_HOST_SUFFIXES = (".slack.com",)

# Regex host patterns (fullmatch). Presigned S3 hosts in both layouts —
# path-style (s3.amazonaws.com / s3.<region>.amazonaws.com) and virtual-hosted
# (bucket.s3.amazonaws.com / bucket.s3.<region>.amazonaws.com) — plus Apple
# CalDAV shards (p42-caldav.icloud.com).
CAPABILITY_HOST_PATTERNS = (
    re.compile(r"s3(\.[a-z0-9-]+)?\.amazonaws\.com"),          # path-style
    re.compile(r".+\.s3(\.[a-z0-9-]+)?\.amazonaws\.com"),      # virtual-hosted
    re.compile(r"p\d+-caldav\.icloud\.com"),
)

# YouTube feed URLs carry an opaque-but-PUBLIC channel/user/list id (e.g.
# channel_id=UCabcdefghijklmnopqrstuv, a 24-char value). Those id params are
# allowlisted on youtube.com so a plain YouTube feed URL is not mistaken for a
# capability. DECISION: allowlist (rather than accept the refusal) because
# YouTube feeds are common and the id is public, not a secret. Any OTHER param,
# or a token in the path/fragment, still trips the gate.
YOUTUBE_HOST = "youtube.com"
YOUTUBE_PUBLIC_ID_PARAMS = ("channel_id", "user", "list", "playlist_id")


def _has_digit_or_mixed_case(s: str) -> bool:
    if any(c.isdigit() for c in s):
        return True
    return any(c.islower() for c in s) and any(c.isupper() for c in s)


def _looks_like_jwt(value: str) -> bool:
    if not value:
        return False
    if value.startswith(JWT_PREFIX):
        return True
    return bool(CAPABILITY_JWT.fullmatch(value))


def _is_opaque_value(value: str) -> bool:
    """Opaque-token test for a query value or fragment value (>= min length)."""
    return bool(CAPABILITY_OPAQUE_TOKEN.fullmatch(value))


def _is_opaque_path_segment(segment: str) -> bool:
    """Opaque-token test for a path segment (length + digit-or-mixed-case)."""
    return (bool(CAPABILITY_OPAQUE_TOKEN.fullmatch(segment))
            and _has_digit_or_mixed_case(segment))


def _query_name_is_capability(name: str) -> bool:
    lname = name.lower()
    if any(lname.startswith(p) for p in CAPABILITY_QUERY_PARAM_PREFIXES):
        return True
    return any(marker in lname for marker in CAPABILITY_QUERY_PARAMS)


def is_capability_url(url: str) -> bool:
    """True if the URL looks like a credential (capability URL) we must refuse.

    Heuristic and deliberately conservative: a false positive only asks the user
    to double-check; a false negative could leak a secret into logs. Checks, in
    order: userinfo, host markers/suffixes/patterns, path markers, path segments
    (JWT / opaque token), query names, query values (JWT / opaque, minus the
    YouTube public-id allowlist), then the fragment (raw and key=value pairs).
    """
    if not url:
        return False
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path or ""
    path_lower = path.lower()

    # Userinfo (user:pass@host) always signals an embedded credential.
    if parts.username or parts.password:
        return True

    # Host: substring markers, subdomain suffixes, regex patterns.
    for marker in CAPABILITY_HOST_MARKERS:
        if marker in host:
            return True
    for suffix in CAPABILITY_HOST_SUFFIXES:
        if host.endswith(suffix):
            return True
    for pattern in CAPABILITY_HOST_PATTERNS:
        if pattern.fullmatch(host):
            return True

    # Path substrings, then per-segment token/JWT checks.
    for marker in CAPABILITY_PATH_MARKERS:
        if marker in path_lower:
            return True
    for segment in path.split("/"):
        if not segment:
            continue
        if _looks_like_jwt(segment) or _is_opaque_path_segment(segment):
            return True

    is_youtube = host == YOUTUBE_HOST or host.endswith("." + YOUTUBE_HOST)

    # Query string: parameter names, then values.
    for name, value in parse_qsl(parts.query, keep_blank_values=True):
        if _query_name_is_capability(name):
            return True
        # Public YouTube id params carry an opaque-but-public value: skip them.
        if is_youtube and name.lower() in YOUTUBE_PUBLIC_ID_PARAMS:
            continue
        if _looks_like_jwt(value) or _is_opaque_value(value):
            return True

    # Fragment: check it raw (bare token) and parsed as key=value pairs
    # (e.g. #access_token=... , the OAuth implicit-flow shape).
    frag = parts.fragment or ""
    if frag:
        if _looks_like_jwt(frag) or _is_opaque_value(frag):
            return True
        for name, value in parse_qsl(frag, keep_blank_values=True):
            if _query_name_is_capability(name):
                return True
            if _looks_like_jwt(value) or _is_opaque_value(value):
                return True

    return False


# Shown when refusing. MUST NOT interpolate the URL.
CAPABILITY_REFUSAL = (
    "Refusing to probe: this looks like a capability URL (it carries a "
    "secret token). Do NOT paste or probe it.\n"
    "Classify this feed as PRIVATE instead:\n"
    '  - category "private"\n'
    '  - secret_ref ["SRC_<ID>_URL"]  (put the real URL in that GitHub Secret)\n'
    "Private sources carry no url in config; the capability URL stays in Secrets."
)

# Shown when a single discovered/OPML feed is dropped. MUST NOT interpolate the
# URL — callers pair it with a feed TITLE or "untitled #<n>", never the URL.
CAPABILITY_DROP_MESSAGE = (
    "skipped: looks like a capability URL — classify as private (see SRC_<ID>_URL)"
)


# --------------------------------------------------------------------------- #
# RSS autodiscovery (stdlib html.parser only — no bs4 dependency)
# --------------------------------------------------------------------------- #

_FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/feed+json")


class _FeedLinkParser(HTMLParser):
    """Collect href of <link rel="alternate" type="application/rss+xml">."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        rel = a.get("rel", "").lower()
        typ = a.get("type", "").lower()
        href = a.get("href", "").strip()
        if not href:
            return
        # Feed <link>s are rel="alternate" with a feed content type.
        if "alternate" in rel.split() and typ in _FEED_TYPES:
            self.hrefs.append(href)


def autodiscover_feeds(html: bytes | str, base: str) -> list[str]:
    """Return resolved feed URLs declared in page ``html`` via <link> tags.

    Relative hrefs are resolved against ``base``. Order preserved, deduped.
    """
    if isinstance(html, bytes):
        html = html.decode("utf-8", "replace")
    parser = _FeedLinkParser()
    parser.feed(html)
    seen: list[str] = []
    for href in parser.hrefs:
        resolved = urljoin(base, href)
        if resolved not in seen:
            seen.append(resolved)
    return seen


# Common feed locations to try when a page declares no <link> feeds.
COMMON_FEED_PATHS = ("/feed", "/rss", "/atom.xml", "/feed.xml", "/index.xml", "/rss.xml")


def common_path_candidates(base: str) -> list[str]:
    """Candidate feed URLs formed by appending well-known paths to ``base``."""
    parts = urlsplit(base)
    root = f"{parts.scheme}://{parts.netloc}"
    return [root + path for path in COMMON_FEED_PATHS]


# --------------------------------------------------------------------------- #
# Feed health / freshness
# --------------------------------------------------------------------------- #

def recommend_weight(cadence_per_week: float | None) -> float:
    """Starting weight: brisk feeds (>=1 item/week) 0.8, sparser ones 0.5."""
    if cadence_per_week is not None and cadence_per_week >= 1.0:
        return 0.8
    return 0.5


def _probe_source() -> SourceConfig:
    # A permissive source so parse_feed_bytes keeps every dated entry it finds.
    return SourceConfig(id="probe", category="open", type="rss", section="news",
                        name="probe", max_results=500, weight=0.8)


def probe_feed(raw: bytes, now: datetime) -> dict:
    """Parse a feed and report health stats. Never raises; never fabricates.

    Returns a dict with ``ok`` plus, when ok, ``title``/``count``/``newest``/
    ``oldest``/``cadence_per_week``/``weight``. ``count`` is dated entries only
    (undated entries are dropped by the pipeline, so they cannot be scheduled).
    """
    try:
        items = parse_feed_bytes(raw, _probe_source(), now)
    except Exception as exc:  # noqa: BLE001 — a broken feed is a normal outcome
        return {"ok": False, "error": f"feed did not parse ({type(exc).__name__})"}

    title = _feed_title(raw)
    if not items:
        return {"ok": False, "error": "no dated entries", "title": title, "count": 0}

    dates = sorted(i.published_at for i in items)
    newest, oldest = dates[-1], dates[0]
    span_weeks = (newest - oldest).total_seconds() / (7 * 86400)
    cadence = (len(items) / span_weeks) if span_weeks > 0 else None
    return {
        "ok": True,
        "title": title,
        "count": len(items),
        "newest": newest,
        "oldest": oldest,
        "cadence_per_week": round(cadence, 2) if cadence is not None else None,
        "weight": recommend_weight(cadence),
    }


def _feed_title(raw: bytes) -> str:
    import feedparser  # local import: heavy, and only needed for the title
    parsed = feedparser.parse(raw)
    return (parsed.feed.get("title") or "").strip()


# --------------------------------------------------------------------------- #
# OPML parsing
# --------------------------------------------------------------------------- #

def opml_feeds(xml_bytes: bytes) -> list[dict]:
    """Return ``[{title, xmlUrl}]`` for every feed outline in an OPML document."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_bytes)
    feeds: list[dict] = []
    for node in root.iter("outline"):
        xml_url = node.get("xmlUrl")
        if xml_url:
            feeds.append({
                "title": node.get("title") or node.get("text") or xml_url,
                "xmlUrl": xml_url,
            })
    return feeds


# --------------------------------------------------------------------------- #
# Slugs, hosts, duplicate detection
# --------------------------------------------------------------------------- #

# Registrable-domain approximation without a new dependency (no tldextract):
# strip a leading www and keep the last two labels, plus a small set of
# two-level public suffixes so co.uk-style hosts collapse correctly.
_TWO_LEVEL_TLDS = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "org.au", "net.au",
    "co.jp", "co.nz", "com.cn", "co.in", "com.br", "co.kr",
}


def registrable_host(url: str) -> str:
    """Best-effort registrable domain for ``url`` (lowercased, no www, no port)."""
    host = (urlsplit(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    last_two = ".".join(labels[-2:])
    last_three = ".".join(labels[-3:])
    if last_two in _TWO_LEVEL_TLDS and len(labels) >= 3:
        return last_three
    return last_two


_ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dxX]$")


def looks_like_issn(value: str) -> bool:
    return bool(_ISSN_RE.match(value.strip()))


def slugify(text: str, *, fallback: str = "source") -> str:
    """Lowercase alnum slug with underscores, suitable for a source id."""
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return (slug or fallback)[:48].strip("_") or fallback


def slug_for(*, title: str = "", url: str = "") -> str:
    """Preferred source id: from feed title, else from the registrable host."""
    if title.strip():
        return slugify(title)
    if url:
        host = registrable_host(url)
        return slugify(host.split(".")[0] if host else url)
    return "source"


def find_duplicates(candidate: dict, config: Config) -> list[dict]:
    """Report how ``candidate`` overlaps existing sources in ``config``.

    ``candidate`` keys (all optional): ``url``, ``issn`` (list or str), ``id``.
    Returns a list of ``{kind, source_id, detail}`` where kind is one of
    "host" | "issn" | "id". Empty list means genuinely new.
    """
    collisions: list[dict] = []

    cand_host = registrable_host(candidate["url"]) if candidate.get("url") else ""
    raw_issn = candidate.get("issn") or []
    cand_issns = {raw_issn} if isinstance(raw_issn, str) else set(raw_issn)
    cand_issns = {s.strip().lower() for s in cand_issns if s}
    cand_id = (candidate.get("id") or "").strip()

    for src in config.sources:
        if cand_host and src.url and registrable_host(src.url) == cand_host:
            collisions.append({"kind": "host", "source_id": src.id, "detail": cand_host})
        if cand_issns and src.issn:
            shared = cand_issns & {s.lower() for s in src.issn}
            if shared:
                collisions.append({"kind": "issn", "source_id": src.id,
                                   "detail": ", ".join(sorted(shared))})
        if cand_id and src.id == cand_id:
            collisions.append({"kind": "id", "source_id": src.id, "detail": cand_id})

    return collisions


# --------------------------------------------------------------------------- #
# Snippet building
# --------------------------------------------------------------------------- #

def build_snippet(*, source_id: str, url: str, name: str, weight: float) -> dict:
    """A ready-to-paste config/sources.json entry for an open RSS feed."""
    return {
        "id": source_id,
        "category": "open",
        "type": "rss",
        "section": "news",
        "name": name or source_id,
        "url": url,
        "weight": weight,
    }


# --------------------------------------------------------------------------- #
# Network layer (thin; monkeypatched in tests)
# --------------------------------------------------------------------------- #

_SESSION = None


def _session():
    """Lazily create one shared HTTP session. Tests monkeypatch this."""
    global _SESSION
    if _SESSION is None:
        _SESSION = make_session()
    return _SESSION


def _fetch(url: str) -> bytes | None:
    try:
        return get(_session(), url).content
    except Exception:  # noqa: BLE001 — a missing/broken candidate is expected
        return None


# --------------------------------------------------------------------------- #
# CLI commands
# --------------------------------------------------------------------------- #

def _summarize_probe(feed_url: str, stats: dict) -> str:
    if not stats.get("ok"):
        return f"  {feed_url}\n    UNHEALTHY: {stats.get('error', 'unknown')}"
    return (
        f"  {feed_url}\n"
        f"    title:   {stats['title'] or '(untitled)'}\n"
        f"    entries: {stats['count']} dated\n"
        f"    newest:  {stats['newest'].date()}   oldest: {stats['oldest'].date()}\n"
        f"    cadence: "
        + (f"{stats['cadence_per_week']}/week" if stats['cadence_per_week'] is not None
           else "unknown (too few dated entries)")
        + f"   -> suggested weight {stats['weight']}"
    )


def cmd_probe_url(url: str, *, as_json: bool, now: datetime) -> int:
    # SAFETY GATE — before any network call or output that could echo the URL.
    if is_capability_url(url):
        print(CAPABILITY_REFUSAL, file=sys.stderr)
        return 3

    page = _fetch(url)
    candidates: list[str] = []
    if page is not None:
        candidates = autodiscover_feeds(page, url)
    discovery = "autodiscovery"
    if not candidates:
        candidates = common_path_candidates(url)
        discovery = "common-path probing"

    # SAFETY GATE #2 — gate every discovered candidate BEFORE it is fetched,
    # printed, or snippeted. Autodiscovered <link> hrefs and common-path guesses
    # are attacker-influenced input just like the top-level URL, so a tokened
    # candidate must be dropped without a network call and without echoing it.
    safe_candidates: list[str] = []
    dropped: list[int] = []
    for idx, feed_url in enumerate(candidates, 1):
        if is_capability_url(feed_url):
            dropped.append(idx)
            continue
        safe_candidates.append(feed_url)

    results: list[dict] = []
    for feed_url in safe_candidates:
        raw = _fetch(feed_url)
        if raw is None:
            results.append({"url": feed_url, "stats": {"ok": False, "error": "fetch failed"}})
            continue
        results.append({"url": feed_url, "stats": probe_feed(raw, now)})

    healthy = [r for r in results if r["stats"].get("ok")]
    best = max(healthy, key=lambda r: (r["stats"]["cadence_per_week"] or 0), default=None)

    snippet = None
    if best is not None:
        s = best["stats"]
        snippet = build_snippet(
            source_id=slug_for(title=s["title"], url=best["url"]),
            url=best["url"], name=s["title"], weight=s["weight"],
        )

    if as_json:
        print(json.dumps({
            "discovery": discovery,
            "candidates": [r["url"] for r in results],
            "dropped_capability": len(dropped),
            "snippet": snippet,
            "healthy": bool(healthy),
        }, indent=2))
        return 0 if snippet else 1

    print(f"Feed discovery via {discovery}: {len(candidates)} candidate(s).")
    if dropped:
        print(f"NOTE: dropped {len(dropped)} candidate feed(s) that look like "
              f"capability URLs (not fetched):", file=sys.stderr)
        for n in dropped:
            print(f"  untitled #{n}: {CAPABILITY_DROP_MESSAGE}", file=sys.stderr)
    for r in results:
        print(_summarize_probe(r["url"], r["stats"]))
    if snippet is None:
        print("\nNo healthy feed found. Nothing to paste — check the URL by hand.")
        return 1
    print("\nReady-to-paste config/sources.json entry:")
    print(json.dumps(snippet, indent=2, ensure_ascii=False))
    return 0


def _safe_feed_label(feed: dict, n: int) -> str:
    """A display label for a feed that can NEVER leak its URL.

    ``opml_feeds`` falls back to the xmlUrl when an outline has no title/text, so
    a titleless capability feed would otherwise echo its own URL. Guard: use the
    title only when it is a real title — not equal to the URL and not itself a
    URL — otherwise fall back to "untitled #<n>".
    """
    title = (feed.get("title") or "").strip()
    url = feed.get("xmlUrl") or ""
    if not title or title == url or title.lower().startswith(("http://", "https://")):
        return f"untitled #{n}"
    return title


def cmd_probe_opml(opml_path: Path, *, repo_root: Path, max_feeds: int,
                   as_json: bool) -> int:
    raw = opml_path.read_bytes()
    feeds = opml_feeds(raw)
    config = load_config(repo_root)

    # SAFETY GATE — drop capability URLs BEFORE dedup/snippet/print. Each xmlUrl
    # is untrusted input; a tripped one is excluded and reported by title only
    # (never the URL) via _safe_feed_label.
    cap_dropped: list[str] = []
    gated: list[dict] = []
    for n, feed in enumerate(feeds, 1):
        if is_capability_url(feed["xmlUrl"]):
            cap_dropped.append(_safe_feed_label(feed, n))
            continue
        gated.append(feed)

    fresh: list[dict] = []
    known = 0
    for feed in gated:
        url = feed["xmlUrl"]
        candidate = {"url": url, "id": slug_for(title=feed["title"], url=url)}
        if find_duplicates(candidate, config):
            known += 1
            continue
        fresh.append(feed)

    total_new = len(fresh)
    dropped = 0
    if total_new > max_feeds:
        dropped = total_new - max_feeds
        fresh = fresh[:max_feeds]

    snippets = [
        build_snippet(source_id=slug_for(title=f["title"], url=f["xmlUrl"]),
                      url=f["xmlUrl"], name=f["title"], weight=0.8)
        for f in fresh
    ]

    if cap_dropped:
        # Report capability-URL drops by title only — never the URL.
        print(f"NOTE: dropped {len(cap_dropped)} feed(s) that look like capability "
              f"URLs (excluded from output):", file=sys.stderr)
        for label in cap_dropped:
            print(f"  {label}: {CAPABILITY_DROP_MESSAGE}", file=sys.stderr)

    if dropped:
        # Never silently cap: always say how many were left out.
        print(f"NOTE: {total_new} new feeds found; emitting {max_feeds}, "
              f"dropped {dropped} (raise --max or RSS_MAX_FEEDS to include them).",
              file=sys.stderr)

    if as_json:
        print(json.dumps({
            "total_in_opml": len(feeds),
            "dropped_capability": len(cap_dropped),
            "already_configured": known,
            "new": total_new,
            "emitted": len(snippets),
            "dropped": dropped,
            "snippets": snippets,
        }, indent=2, ensure_ascii=False))
        return 0

    print(f"OPML: {len(feeds)} feeds, {len(cap_dropped)} capability (skipped), "
          f"{known} already configured, {total_new} new, emitting {len(snippets)}.")
    if snippets:
        print(json.dumps({"sources": snippets}, indent=2, ensure_ascii=False))
    return 0


def cmd_dupcheck(target: str, *, repo_root: Path, as_json: bool) -> int:
    config = load_config(repo_root)
    if looks_like_issn(target):
        candidate = {"issn": [target]}
    else:
        candidate = {"url": target, "id": slug_for(url=target)}
    collisions = find_duplicates(candidate, config)

    if as_json:
        print(json.dumps({"collisions": collisions}, indent=2))
        return 1 if collisions else 0

    if not collisions:
        print("No overlap with existing sources — looks new.")
        return 0
    print(f"Overlaps with {len(collisions)} existing source(s):")
    for c in collisions:
        print(f"  [{c['kind']}] source '{c['source_id']}' ({c['detail']})")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="discover_source.py",
        description="Identify and evaluate feeds before adding them as sources.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(),
                        help="repo root holding config/ (default: cwd)")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="emit machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p_probe = sub.add_parser("probe", help="find & health-check a site's feed")
    p_probe.add_argument("url", nargs="?", help="site or feed URL to probe")
    p_probe.add_argument("--opml", type=Path, help="expand an OPML file instead")
    p_probe.add_argument("--max", type=int, default=None,
                         help="max feeds to emit from OPML (default 50 / RSS_MAX_FEEDS)")

    p_dup = sub.add_parser("dupcheck", help="check a URL or ISSN against config")
    p_dup.add_argument("target", help="feed URL or ISSN")

    return parser


def main(argv: list[str] | None = None) -> int:
    import os
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc)

    if args.command == "probe":
        if args.opml:
            max_feeds = args.max
            if max_feeds is None:
                max_feeds = int(os.environ.get("RSS_MAX_FEEDS", 50))
            return cmd_probe_opml(args.opml, repo_root=args.repo_root,
                                  max_feeds=max_feeds, as_json=args.as_json)
        if not args.url:
            print("probe: provide a URL or --opml FILE", file=sys.stderr)
            return 2
        return cmd_probe_url(args.url, as_json=args.as_json, now=now)

    if args.command == "dupcheck":
        return cmd_dupcheck(args.target, repo_root=args.repo_root,
                            as_json=args.as_json)

    return 2  # unreachable: subparser is required


if __name__ == "__main__":
    raise SystemExit(main())
