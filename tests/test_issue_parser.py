import json
import shutil
from pathlib import Path

import pytest

import apply_issue_setup as ios
from conftest import REPO_ROOT

FIX = Path(__file__).parent / "fixtures" / "issues"


@pytest.fixture
def issue_repo(tmp_path):
    """Throwaway repo with the real config tree (schemas + presets)."""
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copytree(REPO_ROOT / "config", root / "config")
    return root


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_full_form_applies(issue_repo):
    body = (FIX / "setup_full.md").read_text(encoding="utf-8")
    summary, warnings = ios.apply(body, issue_repo)

    site = read_json(issue_repo / "config" / "site.json")
    assert site["default_language"] == "zh"
    assert site["visibility"] == "private"
    assert site["theme"] == "nyt"
    assert site["title"] == "道成的新闻台"
    assert site["timezone"] == "America/Chicago"

    sources = read_json(issue_repo / "config" / "sources.json")
    assert sources["presets"] == ["ai-news", "academic-datavis", "academic-techcomm"]
    ids = [s["id"] for s in sources["sources"]]
    assert "ics_calendars" in ids and "canvas" in ids  # private entries preserved
    customs = [s for s in sources["sources"] if s["id"].startswith("custom_rss_")]
    assert len(customs) == 2
    assert {c["url"] for c in customs} == {
        "https://simonwillison.net/atom/everything/",
        "https://lab.example.edu/feed.xml",
    }
    # Chinese comma splits too
    assert sources["interests"]["keywords"] == [
        "data visualization", "technical communication", "LLM"]
    assert summary["visibility"] == "private"
    assert warnings == []


def test_full_form_is_idempotent(issue_repo):
    body = (FIX / "setup_full.md").read_text(encoding="utf-8")
    ios.apply(body, issue_repo)
    ios.apply(body, issue_repo)
    sources = read_json(issue_repo / "config" / "sources.json")
    customs = [s for s in sources["sources"] if s["id"].startswith("custom_rss_")]
    assert len(customs) == 2  # re-applying replaces, never duplicates


def test_minimal_form_keeps_defaults(issue_repo):
    body = (FIX / "setup_minimal.md").read_text(encoding="utf-8")
    summary, warnings = ios.apply(body, issue_repo)
    site = read_json(issue_repo / "config" / "site.json")
    assert site["title"] == "Personal Newsdash"  # _No response_ keeps existing
    assert site["timezone"] == "UTC"
    assert site["theme"] == "bear"
    sources = read_json(issue_repo / "config" / "sources.json")
    assert sources["presets"] == ["ai-news", "general-news"]  # fallback
    assert any("no packs selected" in w for w in warnings)


def test_malformed_body_with_credential_rejected(issue_repo):
    body = (FIX / "setup_malformed.md").read_text(encoding="utf-8")
    before = (issue_repo / "config" / "site.json").read_text()
    with pytest.raises(ValueError, match="credential"):
        ios.apply(body, issue_repo)
    assert (issue_repo / "config" / "site.json").read_text() == before


def test_missing_ack_rejected(issue_repo):
    body = (FIX / "setup_minimal.md").read_text(encoding="utf-8") \
        .replace("- [x] I understand", "- [ ] I understand")
    with pytest.raises(ValueError, match="[Aa]cknowledgement"):
        ios.apply(body, issue_repo)


def test_success_comment_private_mentions_passphrase():
    summary = {"language": "zh", "visibility": "private", "theme": "nyt",
               "title": "T", "timezone": "UTC", "presets": ["ai-news"],
               "extra_feeds": [], "interests": []}
    comment = ios.success_comment(summary, [], "alice/my-dash")
    assert "NEWSDASH_PASSPHRASE" in comment
    assert "https://alice.github.io/my-dash/" in comment
    assert "settings/secrets/actions/new" in comment
    assert "Page Skill" in comment


def test_form_labels_match_template():
    """The issue form and the parser share heading constants — keep in sync."""
    template = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "setup.yml") \
        .read_text(encoding="utf-8")
    for label in (ios.FIELD_LANGUAGE, ios.FIELD_VISIBILITY, ios.FIELD_THEME,
                  ios.FIELD_TITLE, ios.FIELD_TIMEZONE, ios.FIELD_OPEN_PACKS,
                  ios.FIELD_ACADEMIC_PACKS, ios.FIELD_EXTRA_RSS,
                  ios.FIELD_INTERESTS, ios.FIELD_ACK):
        assert f'label: "{label} ·' in template, f"form label drifted: {label}"
