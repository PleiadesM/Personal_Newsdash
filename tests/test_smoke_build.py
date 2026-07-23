import json
from datetime import datetime, timezone
from email.utils import format_datetime

import pytest
import responses

import build as build_mod
from newsdash import crypto

CHAT_URL = "https://api.openai.com/v1/chat/completions"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def llm_completion(**fields):
    payload = {
        "brief": "EN brief",
        "news_summary": "EN news",
        "papers_summary": "EN papers",
        "image_query": "clockwork automatons",
    }
    payload.update(fields)
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


def apropos_query_completion():
    return {"choices": [{"message": {"content": json.dumps({
        "topic": "competitive pumpkin growing",
        "search_terms": ["pumpkin championship", "giant pumpkin"],
        "why_irrelevant": "Far from this dashboard's usual feed.",
    })}}]}


def apropos_summary_completion():
    return {"choices": [{"message": {"content": json.dumps({
        "choice": 1,
        "summaries": {
            "en": {
                "summary": "A giant pumpkin contest picked a new winner.",
                "why_irrelevant": "A cheerful detour from the usual feed.",
            },
            "zh": {
                "summary": "一场巨型南瓜比赛选出了新冠军。",
                "why_irrelevant": "这是一条轻松的题外话。",
            },
        },
    })}}]}


def gdelt_apropos_response():
    return {"articles": [{
        "title": "Giant pumpkin champion breaks local record",
        "url": "https://example.org/pumpkin",
        "domain": "example.org",
        "seendate": "20260708100000",
    }]}


def rss_with_full_text(url="https://a.example/story"):
    pub = format_datetime(datetime.now(timezone.utc), usegmt=True)
    body = " ".join(f"fulltext-{i}" for i in range(140))
    return f"""<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>T</title>
<item><title>Full story</title><link>{url}</link>
<pubDate>{pub}</pubDate>
<description>Short summary</description>
<content:encoded><![CDATA[<article><p>{body}</p></article>]]></content:encoded>
</item></channel></rss>"""


def simple_rss(title, url):
    pub = format_datetime(datetime.now(timezone.utc), usegmt=True)
    return f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>{title}</title><link>{url}</link>
<pubDate>{pub}</pubDate><description>{title} — summary</description></item>
</channel></rss>"""


def basic_thread(items=(1, 2), keyword=None):
    return {
        "keyword": keyword or {"en": "kw", "zh": "关键"},
        "gloss": {"en": "a gloss", "zh": "释义"},
        "why_now": {"en": "now", "zh": "此刻"},
        "convergence": "convergent",
        "angles": [{"item": n, "phrase": {"en": "angle", "zh": "角度"}}
                   for n in items],
    }


def threads_completion(threads=None):
    threads = threads if threads is not None else [basic_thread(), basic_thread()]
    return {"choices": [{"message":
            {"content": json.dumps({"threads": threads})}}]}


def test_smoke_zero_secret(tmp_path, monkeypatch, repo_root):
    for var in ("NEWSDASH_PASSPHRASE", "LLM_API_KEY", "SMITHSONIAN_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    out = tmp_path / "data"
    build_mod.main(["--output-dir", str(out), "--smoke"])

    manifest = read(out / "manifest.json")
    assert manifest["status"] == "ok"
    assert manifest["site"]["visibility"] == "public"
    assert manifest["site"]["ranking"] == {"highlights": True, "max_per_source": 2}
    assert "crypto" not in manifest

    by_id = {s["id"]: s for s in manifest["sections"]}
    assert by_id["news"]["file"] == "news.json"
    assert by_id["news"]["encrypted"] is False

    news = read(out / "news.json")
    assert news["items"] == []
    assert (out / "source-status.json").exists()
    assert (out / "archive.json").exists()
    assert manifest["insights_file"] is None
    assert manifest["ai_summary"] == {"enabled": False}
    # Threads never run during --smoke: nullable fields present-and-null, no files
    assert manifest["threads_file"] is None
    assert manifest["threads_private_file"] is None
    assert not (out / "threads.json").exists()
    assert not (out / "threads.enc.json").exists()
    assert not (out / "threads-private.enc.json").exists()


def test_smoke_never_calls_llm_or_smithsonian_even_with_keys_set(tmp_path, monkeypatch):
    # --smoke promises "skip all network fetches" — this must hold even when
    # both optional enrichment secrets are present in the environment.
    monkeypatch.setenv("LLM_API_KEY", "sk-should-not-be-used")
    monkeypatch.setenv("SMITHSONIAN_API_KEY", "dg-should-not-be-used")
    out = tmp_path / "data"
    build_mod.main(["--output-dir", str(out), "--smoke"])

    manifest = read(out / "manifest.json")
    assert manifest["insights_file"] is None
    assert manifest["ai_summary"] == {"enabled": True}  # key present -> "configured"
    assert not (out / "insights.json").exists()
    assert not (out / "insights.enc.json").exists()
    # --smoke must not call the LLM for threads either, even with a key set
    assert manifest["threads_file"] is None
    assert manifest["threads_private_file"] is None
    assert not (out / "threads.json").exists()


def test_smoke_with_private_secrets(tmp_path, monkeypatch, make_repo):
    monkeypatch.setenv("NEWSDASH_PASSPHRASE", "correct horse battery staple")
    monkeypatch.setenv("PRIVATE_FEED_TOKEN", "dummy")
    root = make_repo(sources={"schema_version": 1, "presets": [], "sources": [
        {"id": "private_papers", "category": "private", "type": "openalex",
         "section": "research", "name": "Private", "query": "cat:cs.HC",
         "secret_ref": ["PRIVATE_FEED_TOKEN"], "enabled": "auto"},
    ]})
    out = tmp_path / "data"
    build_mod.main(["--output-dir", str(out), "--smoke", "--repo-root", str(root)])

    manifest = read(out / "manifest.json")
    assert manifest["crypto"]["kdf"]["iterations"] == crypto.PBKDF2_ITERATIONS
    by_id = {s["id"]: s for s in manifest["sections"]}
    assert by_id["research"]["file"] == "research.enc.json"
    assert by_id["research"]["encrypted"] is True
    assert "count" not in by_id["research"]
    assert not (out / "research.json").exists(), "plaintext private file must never exist"

    env = read(out / "research.enc.json")
    payload = crypto.decrypt_json(env, "correct horse battery staple", "research")
    assert payload["items"] == []

    check = manifest["crypto"]["check"]
    full = {"v": 1, "alg": crypto.ALG, "kdf": manifest["crypto"]["kdf"], **check}
    assert crypto.decrypt_envelope(full, "correct horse battery staple", "check") \
        == crypto.CHECK_PLAINTEXT


PRIVATE_CAP_URL = "https://feeds.example/cap/deadbeef0123"


def _private_rss_repo(make_repo):
    return make_repo(sources={"schema_version": 1, "presets": [], "sources": [
        {"id": "src_x", "category": "private", "type": "rss",
         "section": "private", "name": "X",
         "secret_ref": ["SRC_X_URL"], "enabled": "auto"},
    ]})


def _assert_url_absent_from_output(out):
    """Byte-scan every file under the output dir for the capability URL."""
    needle = PRIVATE_CAP_URL.encode("utf-8")
    scanned = 0
    for path in out.rglob("*"):
        if path.is_file():
            assert needle not in path.read_bytes(), f"URL leaked into {path.name}"
            scanned += 1
    assert scanned > 0


def test_smoke_private_rss_encrypts_and_never_leaks_url(tmp_path, monkeypatch, make_repo):
    monkeypatch.setenv("NEWSDASH_PASSPHRASE", "correct horse battery staple")
    monkeypatch.setenv("SRC_X_URL", PRIVATE_CAP_URL)
    out = tmp_path / "data"
    build_mod.main(["--output-dir", str(out), "--smoke",
                    "--repo-root", str(_private_rss_repo(make_repo))])

    manifest = read(out / "manifest.json")
    by_id = {s["id"]: s for s in manifest["sections"]}
    assert by_id["private"]["file"] == "private.enc.json"
    assert by_id["private"]["encrypted"] is True
    assert (out / "private.enc.json").exists()
    assert not (out / "private.json").exists()
    # The resolved capability URL lives only in build-process memory; --smoke
    # never fetches it and nothing may write it to any output file.
    _assert_url_absent_from_output(out)


def test_smoke_private_rss_zero_secret_skips_green(tmp_path, monkeypatch, make_repo):
    # Same config, but the SRC_X_URL secret is absent: the build must stay green
    # (exit 0) with the source skipped, not fail.
    monkeypatch.delenv("SRC_X_URL", raising=False)
    monkeypatch.delenv("NEWSDASH_PASSPHRASE", raising=False)
    out = tmp_path / "data"
    build_mod.main(["--output-dir", str(out), "--smoke",
                    "--repo-root", str(_private_rss_repo(make_repo))])

    manifest = read(out / "manifest.json")
    by_id = {s["id"]: s for s in manifest["sections"]}
    assert by_id["private"]["status"] == "not_configured"
    # no passphrase needed because no private source is active
    assert not (out / "private.enc.json").exists()
    status = read(out / "source-status.json")
    assert status["private_summary"] == {"total": 1, "configured": 0}


def test_private_visibility_requires_passphrase(tmp_path, monkeypatch, make_repo):
    monkeypatch.delenv("NEWSDASH_PASSPHRASE", raising=False)
    root = make_repo(site={
        "schema_version": 1, "title": "T", "visibility": "private",
        "languages": ["en"], "default_language": "en",
        "theme": "bear", "timezone": "UTC",
    })
    with pytest.raises(SystemExit):
        build_mod.main(["--output-dir", str(tmp_path / "d"), "--smoke",
                        "--repo-root", str(root)])


def test_private_visibility_encrypts_everything(tmp_path, monkeypatch, make_repo):
    monkeypatch.setenv("NEWSDASH_PASSPHRASE", "four random words here")
    root = make_repo(
        site={"schema_version": 1, "title": "T", "visibility": "private",
              "languages": ["en"], "default_language": "en",
              "theme": "bear", "timezone": "UTC"},
        sources={"schema_version": 1, "presets": [], "sources": [
            {"id": "feed_a", "type": "rss", "section": "news",
             "name": "A", "url": "https://a.example/feed.xml"}]},
    )
    out = tmp_path / "d"
    build_mod.main(["--output-dir", str(out), "--smoke", "--repo-root", str(root)])
    manifest = read(out / "manifest.json")
    by_id = {s["id"]: s for s in manifest["sections"]}
    assert by_id["news"]["file"] == "news.enc.json"
    assert manifest["source_status_file"] == "source-status.enc.json"
    assert not (out / "news.json").exists()
    assert (out / "archive.enc.json").exists()


def test_smoke_custom_section_carries_label_kind_and_orders(tmp_path, monkeypatch, make_repo):
    # A custom section ("ai") with site.json metadata: the manifest entry must
    # carry the bilingual label + the overridden kind, and ordered entries must
    # sort ahead of unordered ones.
    monkeypatch.delenv("NEWSDASH_PASSPHRASE", raising=False)
    root = make_repo(
        site={
            "schema_version": 1, "title": "T", "visibility": "public",
            "languages": ["en", "zh"], "default_language": "en",
            "theme": "bear", "timezone": "UTC",
            "sections": [
                {"id": "ai", "label": {"en": "AI", "zh": "AI 前沿"},
                 "order": 1, "kind": "news"},
            ],
        },
        sources={"schema_version": 1, "presets": [], "sources": [
            {"id": "world", "type": "rss", "section": "news",
             "name": "World", "url": "https://a.example/feed.xml"},
            {"id": "ai_feed", "type": "rss", "section": "ai",
             "name": "AI Feed", "url": "https://b.example/feed.xml"},
        ]},
    )
    out = tmp_path / "data"
    build_mod.main(["--output-dir", str(out), "--smoke", "--repo-root", str(root)])

    manifest = read(out / "manifest.json")
    by_id = {s["id"]: s for s in manifest["sections"]}
    assert by_id["ai"]["label"] == {"en": "AI", "zh": "AI 前沿"}
    assert by_id["ai"]["kind"] == "news"
    # built-in "news" section stays label-free
    assert "label" not in by_id["news"]
    # the ordered section (order=1) sorts ahead of the unordered "news"
    ids = [s["id"] for s in manifest["sections"]]
    assert ids.index("ai") < ids.index("news")


@responses.activate
def test_build_writes_bilingual_insights(tmp_path, monkeypatch, make_repo):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.delenv("SMITHSONIAN_API_KEY", raising=False)
    responses.get(
        "https://a.example/feed.xml",
        body=rss_with_full_text("https://a.example/en-story"),
    )
    responses.get(
        "https://b.example/feed.xml",
        body=rss_with_full_text("https://b.example/zh-story"),
    )
    responses.post(CHAT_URL, json=llm_completion())
    responses.post(CHAT_URL, json=llm_completion(
        brief="中文简报",
        news_summary="中文新闻",
        papers_summary="中文论文",
        image_query="compass clock",
    ))
    responses.post(CHAT_URL, json=apropos_query_completion())
    responses.get("https://api.gdeltproject.org/api/v2/doc/doc",
                  json=gdelt_apropos_response())
    responses.post(CHAT_URL, json=apropos_summary_completion())
    # Threads runs last in the enrichment block (after summarize en/zh + apropos)
    responses.post(CHAT_URL, json=threads_completion())
    root = make_repo(sources={"schema_version": 1, "presets": [], "sources": [
        {"id": "feed_en", "type": "rss", "section": "news",
         "name": "A", "url": "https://a.example/feed.xml", "lang": "en"},
        {"id": "feed_zh", "type": "rss", "section": "news",
         "name": "B", "url": "https://b.example/feed.xml", "lang": "zh"},
    ]})
    out = tmp_path / "d"
    build_mod.main(["--output-dir", str(out), "--repo-root", str(root)])

    manifest = read(out / "manifest.json")
    assert manifest["insights_file"] == "insights.json"
    assert manifest["threads_file"] == "threads.json"
    assert manifest["threads_private_file"] is None
    threads = read(out / "threads.json")
    assert threads["meta"]["scope"] == "public"
    assert len(threads["threads"]) == 2
    assert threads["threads"][0]["id"] == "t1"
    insights = read(out / "insights.json")
    assert insights["summaries"]["en"] == {
        "brief": "EN brief", "news_summary": "EN news", "papers_summary": "EN papers",
    }
    assert insights["summaries"]["zh"] == {
        "brief": "中文简报", "news_summary": "中文新闻", "papers_summary": "中文论文",
    }
    assert insights["brief"] == "EN brief"
    assert "image_query" not in insights
    assert insights["apropos_of_nothing"]["source"]["url"] == "https://example.org/pumpkin"
    assert insights["apropos_of_nothing"]["summaries"]["zh"]["summary"].startswith("一场")


@responses.activate
def test_rss_full_text_generates_article_file_and_status(tmp_path, monkeypatch, make_repo):
    monkeypatch.delenv("NEWSDASH_PASSPHRASE", raising=False)
    responses.get("https://a.example/feed.xml", body=rss_with_full_text())
    root = make_repo(sources={"schema_version": 1, "presets": [], "sources": [
        {"id": "feed_a", "type": "rss", "section": "news",
         "name": "A", "url": "https://a.example/feed.xml"},
    ]})
    out = tmp_path / "d"
    build_mod.main(["--output-dir", str(out), "--repo-root", str(root)])

    news = read(out / "news.json")
    item = news["items"][0]
    assert item["full_text_available"] is True
    assert item["full_text_file"].startswith("articles/news/")
    assert item["full_text_file"].endswith(".json")
    article = read(out / item["full_text_file"])
    assert article["item"]["id"] == item["id"]
    assert article["full_text"].startswith("fulltext-0")

    status = read(out / "source-status.json")
    assert status["sources"][0]["full_text_count"] == 1

    archive = read(out / "archive.json")
    archived = archive["items"][0]
    assert "full_text_available" not in archived
    assert "full_text_file" not in archived


@responses.activate
def test_private_visibility_encrypts_article_files(tmp_path, monkeypatch, make_repo):
    passphrase = "four random words here"
    monkeypatch.setenv("NEWSDASH_PASSPHRASE", passphrase)
    responses.get("https://a.example/feed.xml", body=rss_with_full_text())
    root = make_repo(
        site={"schema_version": 1, "title": "T", "visibility": "private",
              "languages": ["en"], "default_language": "en",
              "theme": "bear", "timezone": "UTC"},
        sources={"schema_version": 1, "presets": [], "sources": [
            {"id": "feed_a", "type": "rss", "section": "news",
             "name": "A", "url": "https://a.example/feed.xml"},
        ]},
    )
    out = tmp_path / "d"
    build_mod.main(["--output-dir", str(out), "--repo-root", str(root)])

    news = crypto.decrypt_json(read(out / "news.enc.json"), passphrase, "news")
    item = news["items"][0]
    assert item["full_text_available"] is True
    assert item["full_text_file"].startswith("articles/news/")
    assert item["full_text_file"].endswith(".enc.json")

    article = crypto.decrypt_json(
        read(out / item["full_text_file"]),
        passphrase,
        f"article:news:{item['id']}",
    )
    assert article["item"]["id"] == item["id"]
    assert article["full_text"].startswith("fulltext-0")

    status = crypto.decrypt_json(
        read(out / "source-status.enc.json"), passphrase, "source-status")
    assert status["sources"][0]["full_text_count"] == 1


# ---- Threads · 线索 build integration -----------------------------------

PRIVATE_MARKER = "ZZMARKERPRIVATECAREER"


def _threads_repo(make_repo, *, include_private, visibility="public"):
    """Two public news feeds + two private career feeds; LLM summary/apropos
    disabled so the only LLM calls a build makes are the threads call(s)."""
    return make_repo(
        site={
            "schema_version": 1, "title": "T", "visibility": visibility,
            "languages": ["en", "zh"], "default_language": "en",
            "theme": "bear", "timezone": "UTC",
            "sections": [{"id": "career", "label": {"en": "Career", "zh": "求职"}}],
            "threads": {"enabled": True, "max_threads": 6,
                        "include_private": include_private},
        },
        sources={"schema_version": 1, "presets": [], "sources": [
            {"id": "pub_a", "type": "rss", "section": "news",
             "name": "PubA", "url": "https://pa.example/feed.xml"},
            {"id": "pub_b", "type": "rss", "section": "news",
             "name": "PubB", "url": "https://pb.example/feed.xml"},
            {"id": "career_a", "category": "private", "type": "rss",
             "section": "career", "name": "CareerA",
             "secret_ref": ["SRC_CAREER_A_URL"], "enabled": "auto"},
            {"id": "career_b", "category": "private", "type": "rss",
             "section": "career", "name": "CareerB",
             "secret_ref": ["SRC_CAREER_B_URL"], "enabled": "auto"},
        ]},
    )


def _threads_env(monkeypatch, *, passphrase=None):
    # Kill summary + apropos + today's image so only the threads call(s) hit
    # the LLM; keep threads on with a key present.
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_SUMMARY_ENABLED", "0")
    monkeypatch.delenv("SMITHSONIAN_API_KEY", raising=False)
    if passphrase:
        monkeypatch.setenv("NEWSDASH_PASSPHRASE", passphrase)
    else:
        monkeypatch.delenv("NEWSDASH_PASSPHRASE", raising=False)


def _mock_threads_feeds(private=True):
    responses.get("https://pa.example/feed.xml",
                  body=simple_rss("Public story A", "https://pa.example/a"))
    responses.get("https://pb.example/feed.xml",
                  body=simple_rss("Public story B", "https://pb.example/b"))
    if private:
        responses.get("https://feeds.example/cap/aaaa",
                      body=simple_rss(PRIVATE_MARKER, "https://jobs.example/1"))
        responses.get("https://feeds.example/cap/bbbb",
                      body=simple_rss("Career posting two", "https://jobs.example/2"))


@responses.activate
def test_threads_opt_in_private_encrypts_and_isolates(tmp_path, monkeypatch, make_repo):
    passphrase = "correct horse battery staple"
    _threads_env(monkeypatch, passphrase=passphrase)
    monkeypatch.setenv("SRC_CAREER_A_URL", "https://feeds.example/cap/aaaa")
    monkeypatch.setenv("SRC_CAREER_B_URL", "https://feeds.example/cap/bbbb")
    _mock_threads_feeds()
    # public threads call first, then the private one (build order)
    responses.post(CHAT_URL, json=threads_completion())
    responses.post(CHAT_URL, json=threads_completion())

    out = tmp_path / "d"
    build_mod.main(["--output-dir", str(out), "--repo-root",
                    str(_threads_repo(make_repo, include_private=True))])

    manifest = read(out / "manifest.json")
    assert manifest["threads_file"] == "threads.json"
    assert manifest["threads_private_file"] == "threads-private.enc.json"

    # private threads decrypt only under their own AAD; no plaintext variant
    assert not (out / "threads-private.json").exists()
    payload = crypto.decrypt_json(
        read(out / "threads-private.enc.json"), passphrase, "threads-private")
    assert payload["meta"]["scope"] == "private"
    assert payload["threads"][0]["id"] == "p1"

    # the private marker title is byte-absent from every plaintext file
    needle = PRIVATE_MARKER.encode("utf-8")
    scanned = 0
    for path in out.rglob("*"):
        if path.is_file() and not path.name.endswith(".enc.json"):
            assert needle not in path.read_bytes(), f"marker leaked into {path.name}"
            scanned += 1
    assert scanned > 0

    # the private title reaches only the private LLM request, never the public
    def body_text(call):
        b = call.request.body
        return b.decode("utf-8") if isinstance(b, bytes) else b
    assert PRIVATE_MARKER not in body_text(responses.calls[-2])
    assert PRIVATE_MARKER in body_text(responses.calls[-1])


@responses.activate
def test_threads_private_default_off_makes_no_private_call(tmp_path, monkeypatch, make_repo):
    passphrase = "correct horse battery staple"
    _threads_env(monkeypatch, passphrase=passphrase)
    monkeypatch.setenv("SRC_CAREER_A_URL", "https://feeds.example/cap/aaaa")
    monkeypatch.setenv("SRC_CAREER_B_URL", "https://feeds.example/cap/bbbb")
    _mock_threads_feeds()
    responses.post(CHAT_URL, json=threads_completion())  # public only

    out = tmp_path / "d"
    build_mod.main(["--output-dir", str(out), "--repo-root",
                    str(_threads_repo(make_repo, include_private=False))])

    manifest = read(out / "manifest.json")
    assert manifest["threads_file"] == "threads.json"
    assert manifest["threads_private_file"] is None
    assert not (out / "threads-private.enc.json").exists()
    # exactly one LLM call — the public threads call — was made
    assert sum(1 for c in responses.calls if c.request.url == CHAT_URL) == 1


@responses.activate
def test_threads_private_visibility_encrypts_public_threads(tmp_path, monkeypatch, make_repo):
    passphrase = "four random words here"
    _threads_env(monkeypatch, passphrase=passphrase)
    responses.get("https://pa.example/feed.xml",
                  body=simple_rss("Public story A", "https://pa.example/a"))
    responses.get("https://pb.example/feed.xml",
                  body=simple_rss("Public story B", "https://pb.example/b"))
    responses.post(CHAT_URL, json=threads_completion())

    root = make_repo(
        site={"schema_version": 1, "title": "T", "visibility": "private",
              "languages": ["en", "zh"], "default_language": "en",
              "theme": "bear", "timezone": "UTC",
              "threads": {"enabled": True}},
        sources={"schema_version": 1, "presets": [], "sources": [
            {"id": "pub_a", "type": "rss", "section": "news",
             "name": "PubA", "url": "https://pa.example/feed.xml"},
            {"id": "pub_b", "type": "rss", "section": "news",
             "name": "PubB", "url": "https://pb.example/feed.xml"},
        ]},
    )
    out = tmp_path / "d"
    build_mod.main(["--output-dir", str(out), "--repo-root", str(root)])

    manifest = read(out / "manifest.json")
    assert manifest["threads_file"] == "threads.enc.json"
    assert not (out / "threads.json").exists()
    payload = crypto.decrypt_json(
        read(out / "threads.enc.json"), passphrase, "threads")
    assert payload["meta"]["scope"] == "public"


@responses.activate
def test_threads_http_error_leaves_no_file_and_clears_stale(tmp_path, monkeypatch, make_repo):
    _threads_env(monkeypatch)  # no passphrase; public only
    responses.get("https://pa.example/feed.xml",
                  body=simple_rss("Public story A", "https://pa.example/a"))
    responses.get("https://pb.example/feed.xml",
                  body=simple_rss("Public story B", "https://pb.example/b"))
    responses.post(CHAT_URL, status=500)

    out = tmp_path / "d"
    out.mkdir(parents=True)
    (out / "threads.json").write_text('{"stale": true}', encoding="utf-8")  # prior build

    root = make_repo(
        site={"schema_version": 1, "title": "T", "visibility": "public",
              "languages": ["en", "zh"], "default_language": "en",
              "theme": "bear", "timezone": "UTC", "threads": {"enabled": True}},
        sources={"schema_version": 1, "presets": [], "sources": [
            {"id": "pub_a", "type": "rss", "section": "news",
             "name": "PubA", "url": "https://pa.example/feed.xml"},
            {"id": "pub_b", "type": "rss", "section": "news",
             "name": "PubB", "url": "https://pb.example/feed.xml"},
        ]},
    )
    build_mod.main(["--output-dir", str(out), "--repo-root", str(root)])

    manifest = read(out / "manifest.json")
    assert manifest["status"] == "ok"  # a threads failure never fails the build
    assert manifest["threads_file"] is None
    assert manifest["threads_private_file"] is None
    assert not (out / "threads.json").exists(), "stale threads.json must be swept"
