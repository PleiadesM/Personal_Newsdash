#!/usr/bin/env python3
"""Relevance pipeline orchestrator.

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
import math
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from newsdash import crypto
from newsdash.apropos import find_apropos_of_nothing
from newsdash.config import SECTION_KINDS, ConfigError, load_config
from newsdash.dedupe import dedupe_items
from newsdash.fetchers import FetchContext, get_fetcher
from newsdash.http import make_session
from newsdash.manifest import build_manifest
from newsdash.models import iso_utc
from newsdash.output import read_json, remove_if_exists, write_json
from newsdash.scoring import apply_tags, score_item
from newsdash.status import StatusAccumulator
from newsdash.summarize import summarize
from newsdash.threads import generate_threads
from newsdash.todays_image import caption_todays_image, find_todays_image

FUTURE_SLACK_SECONDS = 2 * 3600  # tolerate slightly future-dated feed items
MAX_ITEMS_PER_SECTION = 300
MAX_ARCHIVE_ITEMS = 3000
ARTICLE_ROOT = "articles"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Build Relevance data files")
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


def article_section_id(section: str, item_id: str) -> str:
    return f"article:{section}:{item_id}"


def article_file_name(section: str, item_id: str, encrypted: bool) -> str:
    suffix = ".enc.json" if encrypted else ".json"
    return f"{ARTICLE_ROOT}/{section}/{item_id}{suffix}"


def archive_item(item: dict) -> dict:
    """Keep the rolling archive summary-only; article files are per build."""
    d = dict(item)
    d.pop("full_text_available", None)
    d.pop("full_text_file", None)
    return d


def write_article_file(
    out_dir: Path,
    *,
    section: str,
    item,
    generated_at: str,
    encrypted: bool,
    key: bytes | None,
    salt: bytes | None,
) -> None:
    item.full_text_file = article_file_name(section, item.id, encrypted)
    payload = {
        "meta": {
            "generated_at": generated_at,
            "section": section,
            "item_id": item.id,
            "source": item.source,
            "source_id": item.source_id,
        },
        "item": item.to_dict(),
        "full_text": item.full_text,
    }
    path = out_dir / item.full_text_file
    if encrypted:
        write_json(path, crypto.encrypt_json(
            payload, article_section_id(section, item.id), key, salt))
    else:
        write_json(path, payload)


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

        # feeds are untrusted: only http(s) URLs may become links
        result = [it for it in result
                  if it.url.startswith(("http://", "https://"))]
        # a declared source language beats per-item detection (fetchers
        # only see titles, which are too short for reliable detection)
        if source.lang in ("zh", "en"):
            for it in result:
                it.lang = source.lang
        items_by_section.setdefault(source.section, []).extend(result)
        status.record(
            source,
            ok=True,
            count=len(result),
            full_text_count=sum(1 for it in result if getattr(it, "full_text", "")),
        )
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
    section_categories: dict[str, str] = {}
    manifest_sections: list[dict] = []
    section_meta = {m.id: m for m in cfg.site.sections}
    shutil.rmtree(out_dir / ARTICLE_ROOT, ignore_errors=True)

    for section in cfg.sections:
        meta = section_meta.get(section)
        # A metadata kind override applies to custom sections only (the config
        # semantic check forbids it for built-ins), so it can never redirect
        # the private-section pipeline.
        kind = meta.kind if (meta and meta.kind) else SECTION_KINDS.get(section, "news")
        sources = cfg.sources_for_section(section)
        category = section_category(sources)
        section_categories[section] = category
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
            for it in items:
                if it.full_text:
                    write_article_file(
                        out_dir,
                        section=section,
                        item=it,
                        generated_at=generated_at,
                        encrypted=encrypted,
                        key=key,
                        salt=salt,
                    )
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
        if meta and meta.label:
            entry["label"] = dict(meta.label)
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

    # Order nav tabs by section metadata `order`; entries without one keep
    # their current relative position after ordered ones (stable sort).
    manifest_sections.sort(
        key=lambda e: (section_meta[e["id"]].order
                       if section_meta.get(e["id"])
                       and section_meta[e["id"]].order is not None
                       else math.inf))

    # ---- AI daily brief + Today's Image + Apropos-of-Nothing ------------
    # Bolt-on enrichment per docs/ROADMAP.md: reads only news/papers
    # payloads, never runs during --smoke, and follows encrypt_all exactly
    # like every other section.
    insights_file = None
    if not args.smoke:
        insights = {}
        summary = summarize(payloads, env, ctx.session)
        if summary:
            image = find_todays_image(summary.get("image_query", ""), env, ctx.session)
            if image:
                top_story = (payloads.get("news", {}).get("items") or [{}])[0]
                caption = caption_todays_image(
                    image, top_story.get("title", ""), env, ctx.session)
                if caption:
                    summary["todays_image"] = {**image, "caption": caption}
            summary.pop("image_query", None)
            insights.update(summary)

        apropos = find_apropos_of_nothing(payloads, env, ctx.session)
        if apropos:
            insights["apropos_of_nothing"] = apropos

        if insights:
            insights_plain = out_dir / "insights.json"
            insights_enc = out_dir / "insights.enc.json"
            if encrypt_all:
                write_json(insights_enc,
                           crypto.encrypt_json(insights, "insights", key, salt))
                remove_if_exists(insights_plain)
                insights_file = insights_enc.name
            else:
                write_json(insights_plain,
                           {"meta": {"generated_at": generated_at}, **insights})
                remove_if_exists(insights_enc)
                insights_file = insights_plain.name
            print(f"[insights] -> {insights_file}")

    # ---- Threads · 线索 (LLM keyword aggregation) -----------------------
    # Two isolated scopes, one bilingual call each. Public reads only
    # non-private-category payloads; private (opt-in) reads only
    # category:"private" payloads and is written encrypted-only, never as
    # plaintext. Never runs during --smoke. Log discipline on the private
    # path lives in threads.generate_threads (detail-free errors); the only
    # two lines this block prints for the private scope are the allowed
    # "[threads:private] written" on success and nothing on a skip.
    threads_file = None
    threads_private_file = None
    threads_plain = out_dir / "threads.json"
    threads_enc = out_dir / "threads.enc.json"
    threads_private_enc = out_dir / "threads-private.enc.json"
    if not args.smoke and cfg.site.threads.enabled:
        public_payloads = {
            s: p for s, p in payloads.items()
            if section_categories.get(s) != "private"
        }
        result = generate_threads(
            public_payloads, env, ctx.session,
            scope="public", max_threads=cfg.site.threads.max_threads)
        if result:
            payload = {
                "meta": {"generated_at": generated_at, "scope": "public",
                         "count": len(result["threads"])},
                "threads": result["threads"],
            }
            if encrypt_all:
                write_json(threads_enc,
                           crypto.encrypt_json(payload, "threads", key, salt))
                threads_file = threads_enc.name
            else:
                write_json(threads_plain, payload)
                threads_file = threads_plain.name
            print(f"[threads] -> {threads_file}")

        # Private scope is opt-in AND requires a key (guarded above: a
        # passphrase is present whenever a private section is active).
        if cfg.site.threads.include_private and key is not None:
            private_payloads = {
                s: p for s, p in payloads.items()
                if section_categories.get(s) == "private"
            }
            result = generate_threads(
                private_payloads, env, ctx.session,
                scope="private", max_threads=cfg.site.threads.max_threads)
            if result:
                payload = {
                    "meta": {"generated_at": generated_at, "scope": "private",
                             "count": len(result["threads"])},
                    "threads": result["threads"],
                }
                write_json(threads_private_enc, crypto.encrypt_json(
                    payload, "threads-private", key, salt))
                threads_private_file = threads_private_enc.name
                print("[threads:private] written")

    # Stale-file hygiene: any of the three variants not written this run must
    # not survive from a previous build in the output dir.
    if threads_file != threads_plain.name:
        remove_if_exists(threads_plain)
    if threads_file != threads_enc.name:
        remove_if_exists(threads_enc)
    if threads_private_file is None:
        remove_if_exists(threads_private_enc)

    # ---- archive (open + optional items only; never private data) -------
    previous = load_previous_archive(out_dir, passphrase)
    archive_map = {
        d["id"]: archive_item(d)
        for d in previous
        if isinstance(d, dict) and "id" in d
    }
    for section, payload in payloads.items():
        # Never let private-category items into the archive: it is written as
        # plaintext archive.json whenever site visibility is "public" (only a
        # private *section* is active), so mixing them in would leak private
        # titles/summaries in cleartext. Honors this block's stated contract.
        if section_categories.get(section) == "private":
            continue
        for item in payload.get("items", []):
            archive_map[item["id"]] = archive_item(item)
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
    manifest["insights_file"] = insights_file
    # Nullable existence flags, set like insights_file. A non-null private
    # field reveals only that private threads exist — the same disclosure
    # class as the private entry already in sections[].
    manifest["threads_file"] = threads_file
    manifest["threads_private_file"] = threads_private_file
    manifest["ai_summary"] = {
        "enabled": bool(env.get("LLM_API_KEY", "").strip())
        and env.get("LLM_SUMMARY_ENABLED") != "0"
    }
    write_json(out_dir / "manifest.json", manifest)
    print(f"[manifest] status={overall} build_id={build_id}")


if __name__ == "__main__":
    main()
