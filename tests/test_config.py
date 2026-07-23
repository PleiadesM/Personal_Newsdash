import pytest

from newsdash.config import ConfigError, load_config


def test_default_repo_config_loads(repo_root):
    cfg = load_config(repo_root, env={})
    assert cfg.site.visibility == "public"
    ids = {s.id for s in cfg.sources}
    assert "openai_blog" in ids  # from ai-news preset
    assert "bbc_world" in ids  # from general-news preset
    assert "news" in cfg.sections


def test_private_sources_wait_for_secrets(make_repo):
    root = make_repo(sources={"schema_version": 1, "presets": [], "sources": [
        {"id": "private_papers", "category": "private", "type": "openalex",
         "section": "research", "name": "Private", "query": "cat:cs.HC",
         "secret_ref": ["PRIVATE_FEED_TOKEN"], "enabled": "auto"},
    ]})
    cfg = load_config(root, env={})
    src = next(s for s in cfg.sources if s.id == "private_papers")
    assert not src.active
    assert src.skip_reason == "not_configured"


def test_auto_resolves_when_secrets_present(make_repo):
    root = make_repo(sources={"schema_version": 1, "presets": [], "sources": [
        {"id": "private_papers", "category": "private", "type": "openalex",
         "section": "research", "name": "Private", "query": "cat:cs.HC",
         "secret_ref": ["PRIVATE_FEED_TOKEN"], "enabled": "auto"},
    ]})
    cfg = load_config(root, env={"PRIVATE_FEED_TOKEN": "tok"})
    assert next(s for s in cfg.sources if s.id == "private_papers").active


def test_kill_switch(make_repo):
    root = make_repo(sources={"schema_version": 1, "presets": [], "sources": [
        {"id": "private_papers", "category": "private", "type": "openalex",
         "section": "research", "name": "Private", "query": "cat:cs.HC",
         "secret_ref": ["PRIVATE_FEED_TOKEN"], "enabled": "auto"},
    ]})
    env = {"PRIVATE_FEED_TOKEN": "tok", "PRIVATE_PAPERS_ENABLED": "0"}
    cfg = load_config(root, env=env)
    src = next(s for s in cfg.sources if s.id == "private_papers")
    assert not src.active and src.skip_reason == "disabled"


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
        "sources": [{"id": "leaky", "category": "private", "type": "rss",
                     "section": "research", "url": "https://cal.example/secret.xml",
                     "secret_ref": ["X_B64"]}],
    })
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_unknown_preset_rejected(make_repo):
    root = make_repo(sources={"schema_version": 1, "presets": ["nope"], "sources": []})
    with pytest.raises(ConfigError):
        load_config(root, env={})


def _site(**overrides):
    base = {
        "schema_version": 1, "title": "T", "visibility": "public",
        "languages": ["en"], "default_language": "en",
        "theme": "bear", "timezone": "UTC",
    }
    base.update(overrides)
    return base


def test_ranking_defaults_when_absent(make_repo):
    root = make_repo(site=_site())
    cfg = load_config(root, env={})
    assert cfg.site.ranking.highlights is True
    assert cfg.site.ranking.max_per_source == 2


def test_ranking_explicit_values_parse(make_repo):
    root = make_repo(site=_site(ranking={"highlights": False, "max_per_source": 4}))
    cfg = load_config(root, env={})
    assert cfg.site.ranking.highlights is False
    assert cfg.site.ranking.max_per_source == 4


def test_ranking_max_per_source_zero_rejected(make_repo):
    root = make_repo(site=_site(ranking={"max_per_source": 0}))
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_ranking_unknown_key_rejected(make_repo):
    root = make_repo(site=_site(ranking={"bogus": True}))
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


def test_source_lang_parsed(repo_root):
    cfg = load_config(repo_root, env={})
    zhongwen = next(s for s in cfg.sources if s.id == "bbc_zhongwen")
    assert zhongwen.lang == "zh"
    bbc = next(s for s in cfg.sources if s.id == "bbc_world")
    assert bbc.lang is None  # unset -> per-item detection


def test_openalex_filter_replaces_query(make_repo):
    """Follows: an openalex source may carry filter instead of query."""
    root = make_repo(sources={
        "schema_version": 1, "presets": [],
        "sources": [{"id": "follow_x", "type": "openalex", "section": "following",
                     "filter": "authorships.author.id:A5023888391"}],
    })
    cfg = load_config(root, env={})
    src = next(s for s in cfg.sources if s.id == "follow_x")
    assert src.active and src.filter.endswith("A5023888391")
    assert "following" in cfg.sections


def test_openalex_without_query_or_filter_rejected(make_repo):
    root = make_repo(sources={
        "schema_version": 1, "presets": [],
        "sources": [{"id": "oa_bare", "type": "openalex", "section": "papers"}],
    })
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_top_level_tag_rules_apply_to_feed_sections(make_repo):
    root = make_repo(sources={
        "schema_version": 1, "presets": [],
        "sources": [
            {"id": "feed_a", "type": "rss", "section": "news",
             "url": "https://a.example/feed.xml"},
            {"id": "arxiv_b", "type": "arxiv", "section": "papers", "query": "cat:cs.HC"},
        ],
        "tag_rules": [
            {"tag": "llm", "any": ["LLM"]},
            {"tag": "vis-only", "any": ["chart"], "section": "papers"},
        ],
    })
    cfg = load_config(root, env={})
    news_tags = [r.tag for r in cfg.tag_rules["news"]]
    papers_tags = [r.tag for r in cfg.tag_rules["papers"]]
    assert "llm" in news_tags and "llm" in papers_tags
    assert "vis-only" in papers_tags and "vis-only" not in news_tags
    # global rules are unscoped, unlike pack rules
    assert all(r.source_ids is None for r in cfg.tag_rules["news"])


# ---- threads (Threads · 线索 config) ------------------------------------


def test_threads_defaults_when_absent(make_repo):
    root = make_repo(site=_site())
    cfg = load_config(root, env={})
    assert cfg.site.threads.enabled is True
    assert cfg.site.threads.max_threads == 6
    assert cfg.site.threads.include_private is False


def test_threads_explicit_values_parse(make_repo):
    root = make_repo(site=_site(threads={
        "enabled": False, "max_threads": 3, "include_private": True}))
    cfg = load_config(root, env={})
    assert cfg.site.threads.enabled is False
    assert cfg.site.threads.max_threads == 3
    assert cfg.site.threads.include_private is True


def test_threads_max_threads_above_bound_rejected(make_repo):
    root = make_repo(site=_site(threads={"max_threads": 7}))
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_threads_max_threads_below_bound_rejected(make_repo):
    root = make_repo(site=_site(threads={"max_threads": 1}))
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_threads_unknown_key_rejected(make_repo):
    root = make_repo(site=_site(threads={"bogus": True}))
    with pytest.raises(ConfigError):
        load_config(root, env={})


# ---- section metadata (custom nav tabs) ---------------------------------


def test_sections_metadata_absent_defaults_empty(make_repo):
    root = make_repo(site=_site())
    cfg = load_config(root, env={})
    assert cfg.site.sections == []


def test_sections_metadata_parses(make_repo):
    root = make_repo(site=_site(sections=[
        {"id": "ai", "label": {"en": "AI", "zh": "AI 前沿"},
         "order": 1, "kind": "news"},
        {"id": "climate", "label": {"en": "Climate"}},
    ]))
    cfg = load_config(root, env={})
    by_id = {m.id: m for m in cfg.site.sections}
    assert by_id["ai"].label == {"en": "AI", "zh": "AI 前沿"}
    assert by_id["ai"].order == 1
    assert by_id["ai"].kind == "news"
    assert by_id["climate"].order is None and by_id["climate"].kind is None


def test_sections_metadata_duplicate_id_rejected(make_repo):
    root = make_repo(site=_site(sections=[
        {"id": "ai", "label": {"en": "AI"}},
        {"id": "ai", "label": {"en": "AI again"}},
    ]))
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_sections_metadata_kind_override_on_builtin_rejected(make_repo):
    root = make_repo(site=_site(sections=[
        {"id": "news", "label": {"en": "News"}, "kind": "news"},
    ]))
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_sections_metadata_empty_label_rejected(make_repo):
    root = make_repo(site=_site(sections=[{"id": "ai", "label": {}}]))
    with pytest.raises(ConfigError):
        load_config(root, env={})


def test_sections_metadata_bad_id_pattern_rejected(make_repo):
    root = make_repo(site=_site(sections=[
        {"id": "A!", "label": {"en": "Bad"}},
    ]))
    with pytest.raises(ConfigError):
        load_config(root, env={})
