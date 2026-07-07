#!/usr/bin/env python3
"""Personal Newsdash pipeline orchestrator.

Usage::

    python scripts/build.py --output-dir data [--smoke] [--only CATEGORY]

Phases: load+validate config -> fetch every active source (each isolated;
one failure never kills the build) -> normalize/dedupe/score -> assemble
section payloads -> encrypt per the visibility matrix -> write outputs with
manifest.json last (the frontend's atomic commit point).

Log discipline: on public repos, Actions logs are public. Private-section
lines never print counts, titles, or error detail here.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from newsdash import crypto
from newsdash.config import SECTION_KINDS, ConfigError, load_config
from newsdash.dedupe import dedupe_items
from newsdash.fetchers import FetchContext, get_fetcher
from newsdash.http import make_session
from newsdash.manifest import build_manifest
from newsdash.models import iso_utc
from newsdash.output import read_json, remove_if_exists, write_json
from newsdash.scoring import apply_tags, score_item
from newsdash.status import StatusAccumulator

FUTURE_SLACK_SECONDS = 2 * 3600  # tolerate slightly future-dated feed items
MAX_ITEMS_PER_SECTION = 300
MAX_ARCHIVE_ITEMS = 3000


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Build Personal Newsdash data files")
    ap.add_argument("--output-dir", required=True, help="directory for generated JSON")
    ap.add_argument("--smoke", action="store_true",
                    help="skip all network fetches; emit valid-but-empty outputs")
    ap.add_argument("--only", choices=["open", "private", "optional"],
                    help="fetch only sources of one category (debugging)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--repo-root", default=None, help=argparse.SUPPRESS)  # tests
    return ap.parse_args(argv)


def fail(message: str) -> None:
    print(f"::error::{message}")
    sys.exit(1)


def section_category(sources) -> str:
    cats = {s.category for s in sources}
    if "private" in cats:
        return "private"
    if cats == {"optional"} or ("optional" in cats and "open" not in cats):
        return "optional"
    return "open"


def load_previous_archive(out_dir: Path, passphrase: str | None) -> list[dict]:
    plain = out_dir / "archive.json"
    enc = out_dir / "archive.enc.json"
    try:
        if plain.exists():
            return read_json(plain).get("items", [])
        if enc.exists() and passphrase:
            payload = crypto.decrypt_json(read_json(enc), passphrase, "archive")
            return payload.get("items", [])
    except (crypto.DecryptError, ValueError, KeyError) as exc:
        print(f"[archive] previous archive unreadable ({type(exc).__name__}); starting fresh")
    return []


def main(argv=None) -> None:
    args = parse_args(argv)
    repo_root = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    out_dir = Path(args.output_dir)

    try:
        cfg = load_config(repo_root, env)
    except ConfigError as exc:
        fail(f"config: {exc}")

    now = datetime.now(timezone.utc)
    generated_at = iso_utc(now)
    build_id = now.strftime("%Y%m%dT%H%M%SZ")

    passphrase = env.get("NEWSDASH_PASSPHRASE", "").strip() or None
    private_active = [s for s in cfg.sources if s.category == "private" and s.active]
    if cfg.site.visibility == "private" and not passphrase:
        fail("site visibility is 'private' but the NEWSDASH_PASSPHRASE secret is not set; "
             "refusing to publish plaintext. Add the secret or set visibility to 'public'.")
    if private_active and not passphrase:
        fail("private sources are configured but NEWSDASH_PASSPHRASE is not set; "
             "refusing to write private data as plaintext.")

    if args.only:
        print(f"::warning::--only {args.only} is a debug flag: sections of other "
              "categories will be written as empty/not-configured in this output "
              "dir. Do not point it at the real data/ directory.")

    status = StatusAccumulator()
    ctx = FetchContext(session=make_session(), now=now, env=env,
                       site=cfg.site, repo_root=repo_root, verbose=args.verbose)

    items_by_section: dict[str, list] = {}
    schedule_events: list = []
    schedule_calendars: list[dict] = []
    courses: list[dict] = []

    for source in cfg.sources:
        if args.only and source.category != args.only:
            continue
        if not source.active:
            status.record(source, ok=False, skip_reason=source.skip_reason)
            continue
        if args.smoke:
            status.record(source, ok=True, count=0)
            continue
        try:
            result = get_fetcher(source.type)(source, ctx)
        except Exception as exc:  # noqa: BLE001 — resilience by design
            status.record(source, ok=False, error=exc)
            if source.category == "private":
                print(f"[{source.id}] error: {type(exc).__name__} (detail withheld)")
            else:
                print(f"[{source.id}] error: {type(exc).__name__}: {str(exc)[:160]}")
            continue

        if source.type == "ics":
            schedule_events.extend(result["events"])
            schedule_calendars.extend(result["calendars"])
            status.record(source, ok=True, count=len(result["events"]))
            print(f"[{source.id}] ok (private; detail withheld)")
        elif source.type == "canvas":
            courses.extend(result["courses"])
            status.record(source, ok=True, count=len(result["courses"]))
            print(f"[{source.id}] ok (private; detail withheld)")
        else:
            # feeds are untrusted: only http(s) URLs may become links
            result = [it for it in result
                      if it.url.startswith(("http://", "https://"))]
            items_by_section.setdefault(source.section, []).extend(result)
            status.record(source, ok=True, count=len(result))
            print(f"[{source.id}] ok, {len(result)} items")

    # ---- assemble section payloads --------------------------------------
    win = cfg.site.windows
    encrypt_all = cfg.site.visibility == "private"

    salt = key = crypto_block = None
    if passphrase:
        salt = crypto.new_salt()
        key = crypto.derive_key(passphrase, salt)
        crypto_block = {
            "alg": crypto.ALG,
            "kdf": crypto.kdf_block(salt),
            "check": crypto.make_check_block(key, salt),
        }

    payloads: dict[str, dict] = {}
    manifest_sections: list[dict] = []

    for section in cfg.sections:
        kind = SECTION_KINDS.get(section, "news")
        sources = cfg.sources_for_section(section)
        category = section_category(sources)
        sec_status = status.section_status(section)
        encrypted = encrypt_all or category == "private"

        if kind in ("news", "papers"):
            item_kind = "paper" if kind == "papers" else "news"
            window_hours = (win.papers_days * 24 if item_kind == "paper"
                            else win.news_hours)
            items = items_by_section.get(section, [])
            items = [
                it for it in items
                if (now - it.published_at).total_seconds() <= window_hours * 3600
                and (it.published_at - now).total_seconds() <= FUTURE_SLACK_SECONDS
            ]
            items = dedupe_items(items)
            rules = cfg.tag_rules.get(section, [])
            for it in items:
                apply_tags(it, rules)
                score_item(it, now, cfg.interests_keywords, cfg.interests_boost)
            items.sort(key=lambda it: it.published_at, reverse=True)
            items = items[:MAX_ITEMS_PER_SECTION]
            payloads[section] = {
                "meta": {
                    "generated_at": generated_at,
                    "section": section,
                    "kind": kind,
                    "window_hours": window_hours,
                    "count": len(items),
                    "sources": status.for_section(section),
                },
                "items": [it.to_dict() for it in items],
            }
            count = len(items)
        elif kind == "schedule":
            schedule_events.sort(key=lambda ev: ev.start)
            payloads[section] = {
                "meta": {
                    "generated_at": generated_at,
                    "section": section,
                    "kind": kind,
                    "timezone": cfg.site.timezone,
                    "calendars": schedule_calendars,
                    "sources": status.for_section(section),
                },
                "events": [ev.to_dict() for ev in schedule_events],
            }
            count = len(schedule_events)
        elif kind == "courses":
            payloads[section] = {
                "meta": {
                    "generated_at": generated_at,
                    "section": section,
                    "kind": kind,
                    "sources": status.for_section(section),
                },
                "courses": courses,
            }
            count = len(courses)
        else:  # pragma: no cover — SECTION_KINDS covers v0.1 sections
            continue

        plain_file = out_dir / f"{section}.json"
        enc_file = out_dir / f"{section}.enc.json"
        entry = {
            "id": section,
            "kind": kind,
            "category": category,
            "encrypted": encrypted,
            "status": sec_status,
            "file": None,
        }
        if sec_status == "not_configured":
            remove_if_exists(plain_file)
            remove_if_exists(enc_file)
        elif encrypted:
            # guarded above: encrypted sections imply a passphrase
            write_json(enc_file, crypto.encrypt_json(payloads[section], section, key, salt))
            remove_if_exists(plain_file)
            entry["file"] = enc_file.name
            print(f"[{section}] encrypted -> {enc_file.name}")
        else:
            write_json(plain_file, payloads[section])
            remove_if_exists(enc_file)
            entry["file"] = plain_file.name
            entry["count"] = count
            print(f"[{section}] {count} items -> {plain_file.name}")
        manifest_sections.append(entry)

    # ---- archive (open + optional items only; never private data) -------
    previous = load_previous_archive(out_dir, passphrase)
    archive_map = {d["id"]: d for d in previous if isinstance(d, dict) and "id" in d}
    for section, payload in payloads.items():
        for item in payload.get("items", []):
            archive_map[item["id"]] = item
    cutoff = now.timestamp() - win.archive_days * 86400

    def _fresh(d: dict) -> bool:
        try:
            ts = datetime.strptime(d["published_at"], "%Y-%m-%dT%H:%M:%SZ")
            return ts.replace(tzinfo=timezone.utc).timestamp() >= cutoff
        except (KeyError, ValueError):
            return False

    archive_items = sorted(
        (d for d in archive_map.values() if _fresh(d)),
        key=lambda d: d["published_at"],
        reverse=True,
    )[:MAX_ARCHIVE_ITEMS]
    archive_payload = {
        "meta": {"generated_at": generated_at, "days": win.archive_days,
                 "count": len(archive_items)},
        "items": archive_items,
    }
    if encrypt_all:
        write_json(out_dir / "archive.enc.json",
                   crypto.encrypt_json(archive_payload, "archive", key, salt))
        remove_if_exists(out_dir / "archive.json")
    else:
        write_json(out_dir / "archive.json", archive_payload)
        remove_if_exists(out_dir / "archive.enc.json")

    # ---- source status ---------------------------------------------------
    status_payload = status.public_dict(generated_at)
    if encrypt_all:
        status_file = "source-status.enc.json"
        write_json(out_dir / status_file,
                   crypto.encrypt_json(status_payload, "source-status", key, salt))
        remove_if_exists(out_dir / "source-status.json")
    else:
        status_file = "source-status.json"
        write_json(out_dir / status_file, status_payload)
        remove_if_exists(out_dir / "source-status.enc.json")

    # ---- manifest last (atomic commit point for the frontend) -----------
    overall = "ok"
    if manifest_sections and all(
        s["status"] in ("error", "not_configured") for s in manifest_sections
    ):
        overall = "degraded"
    manifest = build_manifest(
        cfg.site, manifest_sections,
        generated_at=generated_at, build_id=build_id,
        crypto_block=crypto_block, status=overall,
    )
    manifest["source_status_file"] = status_file
    write_json(out_dir / "manifest.json", manifest)
    print(f"[manifest] status={overall} build_id={build_id}")


if __name__ == "__main__":
    main()
