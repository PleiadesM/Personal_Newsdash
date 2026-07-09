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


def test_smoke_zero_secret(tmp_path, monkeypatch, repo_root):
    for var in ("NEWSDASH_PASSPHRASE", "ICS_SOURCES_B64", "CANVAS_BASE_URL",
                "CANVAS_TOKEN", "LLM_API_KEY", "SMITHSONIAN_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    out = tmp_path / "data"
    build_mod.main(["--output-dir", str(out), "--smoke"])

    manifest = read(out / "manifest.json")
    assert manifest["status"] == "ok"
    assert manifest["site"]["visibility"] == "public"
    assert "crypto" not in manifest

    by_id = {s["id"]: s for s in manifest["sections"]}
    assert by_id["news"]["file"] == "news.json"
    assert by_id["news"]["encrypted"] is False
    assert by_id["schedule"]["status"] == "not_configured"
    assert by_id["schedule"]["file"] is None
    assert not (out / "schedule.enc.json").exists()
    assert not (out / "schedule.json").exists()

    news = read(out / "news.json")
    assert news["items"] == []
    assert (out / "source-status.json").exists()
    assert (out / "archive.json").exists()
    assert manifest["insights_file"] is None
    assert manifest["ai_summary"] == {"enabled": False}


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


def test_smoke_with_private_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWSDASH_PASSPHRASE", "correct horse battery staple")
    monkeypatch.setenv("ICS_SOURCES_B64", "W10=")
    monkeypatch.setenv("CANVAS_BASE_URL", "https://canvas.example.edu")
    monkeypatch.setenv("CANVAS_TOKEN", "dummy")
    out = tmp_path / "data"
    build_mod.main(["--output-dir", str(out), "--smoke"])

    manifest = read(out / "manifest.json")
    assert manifest["crypto"]["kdf"]["iterations"] == crypto.PBKDF2_ITERATIONS
    by_id = {s["id"]: s for s in manifest["sections"]}
    assert by_id["schedule"]["file"] == "schedule.enc.json"
    assert by_id["schedule"]["encrypted"] is True
    assert "count" not in by_id["schedule"]
    assert not (out / "schedule.json").exists(), "plaintext private file must never exist"
    assert not (out / "courses.json").exists()

    env = read(out / "schedule.enc.json")
    payload = crypto.decrypt_json(env, "correct horse battery staple", "schedule")
    assert payload["events"] == []

    check = manifest["crypto"]["check"]
    full = {"v": 1, "alg": crypto.ALG, "kdf": manifest["crypto"]["kdf"], **check}
    assert crypto.decrypt_envelope(full, "correct horse battery staple", "check") \
        == crypto.CHECK_PLAINTEXT


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
    insights = read(out / "insights.json")
    assert insights["summaries"]["en"] == {
        "brief": "EN brief", "news_summary": "EN news", "papers_summary": "EN papers",
    }
    assert insights["summaries"]["zh"] == {
        "brief": "中文简报", "news_summary": "中文新闻", "papers_summary": "中文论文",
    }
    assert insights["brief"] == "EN brief"
    assert "image_query" not in insights


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
