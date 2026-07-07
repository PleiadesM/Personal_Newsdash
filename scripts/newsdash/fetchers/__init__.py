"""Fetcher registry: source ``type`` string -> fetch callable.

Every fetcher shares one interface (radar-compatible, config-driven)::

    fetch(source: SourceConfig, ctx: FetchContext)
        -> list[Item]                      # news / paper fetchers
        -> {"events": [...], "calendars": [...]}   # ics
        -> {"courses": [...]}              # canvas

Modules import lazily so a missing optional dependency only breaks the
source that needs it, never the whole build."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Mapping

import requests

from ..config import SiteConfig

_MODULES = {
    "rss": "newsdash.fetchers.rss",
    "opml": "newsdash.fetchers.opml",
    "feed-json": "newsdash.fetchers.feed_json",
    "static-page": "newsdash.fetchers.static_page",
    "arxiv": "newsdash.fetchers.arxiv",
    "openalex": "newsdash.fetchers.openalex",
    "crossref": "newsdash.fetchers.crossref",
    "semanticscholar": "newsdash.fetchers.semanticscholar",
    "ics": "newsdash.fetchers.ics",
    "canvas": "newsdash.fetchers.canvas",
}


@dataclass
class FetchContext:
    session: requests.Session
    now: datetime  # timezone-aware UTC
    env: Mapping[str, str]
    site: SiteConfig
    repo_root: Path | None = None
    verbose: bool = False


def get_fetcher(source_type: str):
    module_path = _MODULES.get(source_type)
    if module_path is None:
        raise KeyError(f"no fetcher registered for source type {source_type!r}")
    return import_module(module_path).fetch
