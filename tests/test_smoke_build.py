import json

import pytest

import build as build_mod
from newsdash import crypto


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


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
