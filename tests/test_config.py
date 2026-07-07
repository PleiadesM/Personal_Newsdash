import pytest

from newsdash.config import ConfigError, load_config


def test_default_repo_config_loads(repo_root):
    cfg = load_config(repo_root, env={})
    assert cfg.site.visibility == "public"
    ids = {s.id for s in cfg.sources}
    assert "openai_blog" in ids  # from ai-news preset
    assert "bbc_world" in ids  # from general-news preset
    assert "ics_calendars" in ids and "canvas" in ids
    assert set(cfg.sections) >= {"news", "schedule", "courses"}


def test_private_sources_wait_for_secrets(repo_root):
    cfg = load_config(repo_root, env={})
    ics = next(s for s in cfg.sources if s.id == "ics_calendars")
    assert not ics.active
    assert ics.skip_reason == "not_configured"


def test_auto_resolves_when_secrets_present(repo_root):
    env = {"ICS_SOURCES_B64": "eyJ4IjogMX0=", "CANVAS_BASE_URL": "https://c.example",
           "CANVAS_TOKEN": "tok"}
    cfg = load_config(repo_root, env=env)
    assert next(s for s in cfg.sources if s.id == "ics_calendars").active
    assert next(s for s in cfg.sources if s.id == "canvas").active


def test_kill_switch(repo_root):
    env = {"CANVAS_BASE_URL": "https://c.example", "CANVAS_TOKEN": "tok",
           "CANVAS_ENABLED": "0"}
    cfg = load_config(repo_root, env=env)
    canvas = next(s for s in cfg.sources if s.id == "canvas")
    assert not canvas.active and canvas.skip_reason == "disabled"


def test_override_preset_source_by_id(make_repo):
    pack = {
        "id": "mini", "name": {"en": "Mini", "zh": "迷你"},
        "category": "open", "section": "news",
        "sources": [{"id": "feed_a", "type": "rss", "name": "Feed A",
                     "url": "https://a.example/feed.xml", "weight": 0.5}],
    }
    root = make_repo(sources={
        "schema_version": 1, "presets": ["mini"],
        "sources": [{"id": "feed_a", "enabled": False, "weight": 0.1}],
    }, presets={"mini": pack})
    cfg = load_config(root, env={})
    feed = next(s for s in cfg.sources if s.id == "feed_a")
    assert feed.enabled is False and not feed.active
    assert feed.weight == 0.1
    assert feed.preset == "mini"


def test_private_source_with_url_rejected(make_repo):
    root = make_repo(sources={
        "schema_version": 1, "presets": [],
        "sources": [{"id": "leaky", "category": "private", "type": "ics",
                     "section": "schedule", "url": "https://cal.example/secret.ics",
                     "secret_ref": ["X_B64"]}],
    })
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_unknown_preset_rejected(make_repo):
    root = make_repo(sources={"schema_version": 1, "presets": ["nope"], "sources": []})
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_bad_theme_rejected(make_repo):
    root = make_repo(site={
        "schema_version": 1, "title": "T", "visibility": "public",
        "languages": ["en"], "default_language": "en",
        "theme": "comic-sans", "timezone": "UTC",
    })
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_category_defaults_by_type(make_repo):
    root = make_repo(sources={
        "schema_version": 1, "presets": [],
        "sources": [{"id": "ax", "type": "arxiv", "section": "papers",
                     "query": "cat:cs.HC"}],
    })
    cfg = load_config(root, env={})
    assert next(s for s in cfg.sources if s.id == "ax").category == "optional"


def test_missing_url_for_rss_rejected(make_repo):
    root = make_repo(sources={
        "schema_version": 1, "presets": [],
        "sources": [{"id": "nourl", "type": "rss", "section": "news"}],
    })
    with pytest.raises(ConfigError):
        load_config(root, env={})
