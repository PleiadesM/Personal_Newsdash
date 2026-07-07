import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from newsdash.config import SiteConfig, SourceConfig, Windows  # noqa: E402
from newsdash.fetchers import FetchContext  # noqa: E402
from newsdash.http import make_session  # noqa: E402

FIXED_NOW = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def make_ctx():
    def _make(env=None, tz="America/Chicago", now=FIXED_NOW):
        site = SiteConfig(
            title="Test", subtitle="", visibility="public",
            languages=["en"], default_language="en", theme="bear",
            timezone=tz, windows=Windows(),
        )
        return FetchContext(session=make_session(), now=now, env=env or {},
                            site=site, repo_root=REPO_ROOT)
    return _make


@pytest.fixture
def make_source():
    def _make(**kwargs):
        defaults = dict(id="src", category="open", type="rss",
                        section="news", name="Src", weight=0.9)
        defaults.update(kwargs)
        return SourceConfig(**defaults)
    return _make


@pytest.fixture
def make_repo(tmp_path):
    """Build a throwaway repo layout with the real schemas and custom config."""

    def _make(site: dict | None = None, sources: dict | None = None,
              presets: dict[str, dict] | None = None) -> Path:
        root = tmp_path / "repo"
        (root / "config" / "presets").mkdir(parents=True, exist_ok=True)
        shutil.copytree(REPO_ROOT / "config" / "schema", root / "config" / "schema",
                        dirs_exist_ok=True)
        site = site or {
            "schema_version": 1, "title": "Test Dash", "visibility": "public",
            "languages": ["en", "zh"], "default_language": "en",
            "theme": "bear", "timezone": "UTC",
        }
        sources = sources or {"schema_version": 1, "presets": [], "sources": []}
        (root / "config" / "site.json").write_text(json.dumps(site), encoding="utf-8")
        (root / "config" / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
        for pid, pack in (presets or {}).items():
            (root / "config" / "presets" / f"{pid}.json").write_text(
                json.dumps(pack), encoding="utf-8")
        return root

    return _make
