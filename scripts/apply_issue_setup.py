#!/usr/bin/env python3
"""Issue-ops onboarding: parse the "Set up my Newsdash" issue-form body,
rewrite config/site.json + config/sources.json, and emit the bilingual
comment the workflow posts back.

The heading labels in .github/ISSUE_TEMPLATE/setup.yml are the contract:
this parser keys on the English part of each label (before " ·").
tests/test_issue_parser.py enforces the pairing.

Usage:
    python scripts/apply_issue_setup.py --body-file body.md \
        --comment-out comment.md --repo owner/name [--repo-root PATH]

Exit codes: 0 = applied; 2 = rejected (comment-out still written).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from newsdash.config import ConfigError, load_config

NO_RESPONSE = "_No response_"

FIELD_LANGUAGE = "Interface language"
FIELD_VISIBILITY = "Site visibility"
FIELD_THEME = "Theme"
FIELD_TITLE = "Site title"
FIELD_TIMEZONE = "Timezone"
FIELD_OPEN_PACKS = "Open news packs"
FIELD_ACADEMIC_PACKS = "Academic packs"
FIELD_EXTRA_RSS = "Extra RSS feeds"
FIELD_INTERESTS = "Interest keywords"
FIELD_ACK = "Acknowledgement"

OPEN_PACK_MAP = [("AI news", "ai-news"), ("General news", "general-news")]
ACADEMIC_PACK_MAP = [("Data visualization", "academic-datavis"),
                     ("Technical communication", "academic-techcomm")]

CUSTOM_RSS_PREFIX = "custom_rss_"

SECRET_PATTERN = re.compile(
    r"(github_pat_|ghp_[A-Za-z0-9]{20,}|/calendar/ical/.+/private|Bearer\s+[A-Za-z0-9._-]{20,})",
    re.IGNORECASE,
)


def parse_form(body: str) -> dict[str, str]:
    """Issue-form bodies render as '### Label\\n\\nvalue' blocks."""
    fields: dict[str, str] = {}
    current = None
    lines: list[str] = []
    for line in body.splitlines():
        match = re.match(r"^###\s+(.*)$", line)
        if match:
            if current is not None:
                fields[current] = "\n".join(lines).strip()
            heading = match.group(1).strip()
            current = heading.split("·")[0].strip()  # English part is the key
            lines = []
        elif current is not None:
            lines.append(line)
    if current is not None:
        fields[current] = "\n".join(lines).strip()
    return fields


def field(fields: dict[str, str], key: str) -> str:
    value = fields.get(key, "").strip()
    return "" if value == NO_RESPONSE else value


def checked_labels(raw: str) -> list[str]:
    return [m.group(1).strip()
            for m in re.finditer(r"^- \[[xX]\] (.+)$", raw, re.MULTILINE)]


def slug_for_feed(url: str, taken: set[str]) -> str:
    host = (urlsplit(url).hostname or "feed").lower()
    base = CUSTOM_RSS_PREFIX + re.sub(r"[^a-z0-9]+", "_", host).strip("_")[:40]
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}_{n}", n + 1
    taken.add(slug)
    return slug


def apply(body: str, repo_root: Path) -> tuple[dict, list[str]]:
    """Mutate config files from the parsed form; returns (summary, warnings)."""
    fields = parse_form(body)
    warnings: list[str] = []

    if SECRET_PATTERN.search(body):
        raise ValueError(
            "The issue body contains something that looks like a credential. "
            "Nothing was applied — please edit the issue to remove it, and "
            "rotate that credential if it was real."
        )
    if "[x]" not in fields.get(FIELD_ACK, "").lower():
        raise ValueError("The acknowledgement checkbox is required.")

    site_path = repo_root / "config" / "site.json"
    sources_path = repo_root / "config" / "sources.json"
    site = json.loads(site_path.read_text(encoding="utf-8"))
    sources = json.loads(sources_path.read_text(encoding="utf-8"))

    # site.json -----------------------------------------------------------
    lang_raw = field(fields, FIELD_LANGUAGE)
    if lang_raw:
        site["default_language"] = "zh" if lang_raw.startswith("中文") else "en"

    vis_raw = field(fields, FIELD_VISIBILITY)
    if vis_raw:
        site["visibility"] = "private" if vis_raw.startswith("Private") else "public"

    theme_raw = field(fields, FIELD_THEME)
    if theme_raw:
        theme = theme_raw.split("—")[0].split(" ")[0].strip()
        if theme in ("the-type", "nyt", "bear"):
            site["theme"] = theme
        else:
            warnings.append(f"unknown theme {theme!r} ignored")

    title = field(fields, FIELD_TITLE)
    if title:
        site["title"] = title[:120]

    tz = field(fields, FIELD_TIMEZONE)
    if tz:
        try:
            ZoneInfo(tz)
            site["timezone"] = tz
        except Exception:
            warnings.append(f"unknown timezone {tz!r} ignored (kept {site['timezone']!r})")

    # sources.json --------------------------------------------------------
    presets: list[str] = []
    open_checked = checked_labels(fields.get(FIELD_OPEN_PACKS, ""))
    for label_prefix, preset_id in OPEN_PACK_MAP:
        if any(label.startswith(label_prefix) for label in open_checked):
            presets.append(preset_id)
    academic_checked = checked_labels(fields.get(FIELD_ACADEMIC_PACKS, ""))
    for label_prefix, preset_id in ACADEMIC_PACK_MAP:
        if any(label.startswith(label_prefix) for label in academic_checked):
            presets.append(preset_id)
    if not presets:
        presets = ["ai-news", "general-news"]
        warnings.append("no packs selected; kept the default ai-news + general-news")
    sources["presets"] = presets

    interests_raw = field(fields, FIELD_INTERESTS)
    if interests_raw:
        keywords = [k.strip() for k in re.split(r"[,，]", interests_raw) if k.strip()]
        sources.setdefault("interests", {})["keywords"] = keywords[:20]

    kept = [s for s in sources.get("sources", [])
            if not s.get("id", "").startswith(CUSTOM_RSS_PREFIX)]
    taken = {s.get("id", "") for s in kept}
    extra_urls = [u.strip() for u in field(fields, FIELD_EXTRA_RSS).splitlines()
                  if u.strip()]
    added_feeds = []
    for url in extra_urls[:20]:
        if not re.match(r"^https?://", url):
            warnings.append(f"skipped non-http feed line: {url[:60]!r}")
            continue
        slug = slug_for_feed(url, taken)
        kept.append({
            "id": slug, "category": "open", "type": "rss", "section": "news",
            "name": urlsplit(url).hostname or slug, "url": url, "weight": 0.8,
        })
        added_feeds.append(url)
    sources["sources"] = kept

    original_site = site_path.read_text(encoding="utf-8")
    original_sources = sources_path.read_text(encoding="utf-8")
    site_path.write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    sources_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    # final gate: the merged config must still validate; restore on failure so
    # a rejected form never leaves half-applied config behind
    try:
        load_config(repo_root, env={})
    except ConfigError as exc:
        site_path.write_text(original_site, encoding="utf-8")
        sources_path.write_text(original_sources, encoding="utf-8")
        raise ValueError(f"resulting config failed validation: {exc}") from exc

    summary = {
        "language": site["default_language"],
        "visibility": site["visibility"],
        "theme": site["theme"],
        "title": site["title"],
        "timezone": site["timezone"],
        "presets": presets,
        "extra_feeds": added_feeds,
        "interests": sources.get("interests", {}).get("keywords", []),
    }
    return summary, warnings


def success_comment(summary: dict, warnings: list[str], repo: str) -> str:
    owner, _, name = repo.partition("/")
    site_url = f"https://{owner}.github.io/{name}/"
    private = summary["visibility"] == "private"
    lines = [
        "## ✅ Preferences applied · 配置已应用", "",
        f"- **Theme · 主题**: `{summary['theme']}`",
        f"- **Language · 语言**: `{summary['language']}`",
        f"- **Visibility · 可见性**: `{summary['visibility']}`",
        f"- **Timezone · 时区**: `{summary['timezone']}`",
        f"- **Packs · 信源包**: {', '.join(f'`{p}`' for p in summary['presets'])}",
    ]
    if summary["extra_feeds"]:
        lines.append(f"- **Extra feeds · 自定义订阅**: {len(summary['extra_feeds'])} added")
    if summary["interests"]:
        lines.append(f"- **Interests · 兴趣词**: {', '.join(summary['interests'][:8])}")
    if warnings:
        lines += ["", "### ⚠️ Notes"] + [f"- {w}" for w in warnings]

    lines += [
        "",
        "A rebuild is running: "
        f"[Actions → Update Newsdash](https://github.com/{repo}/actions/workflows/update.yml)",
        "",
        "## Next steps · 后续步骤", "",
        f"1. **Enable GitHub Pages** (once): [Settings → Pages](https://github.com/{repo}/settings/pages)"
        " → *Deploy from a branch* → `main` / `/ (root)`."
        f" Your site · 你的网站: {site_url}",
    ]
    step = 2
    if private:
        lines += [
            f"{step}. 🔴 **REQUIRED — add the `NEWSDASH_PASSPHRASE` secret** "
            f"([add secret](https://github.com/{repo}/settings/secrets/actions/new)). "
            "Your site is set to *private*: without the passphrase the build refuses to publish. "
            "Pick ≥4 random words and keep them safe — the passphrase is also your login. "
            "私密模式必需：请添加口令 Secret（≥4 个随机单词），它同时也是你的登录口令。",
        ]
        step += 1
    lines += [
        f"{step}. **Personal schedule (optional)** — add `ICS_SOURCES_B64` "
        f"([add secret](https://github.com/{repo}/settings/secrets/actions/new)): "
        "copy `examples/ics-sources.example.json`, fill in your calendar ICS URLs "
        "(Google: *Settings → Secret address in iCal format*; Outlook: *Publish calendar*; "
        "Canvas: *Calendar → Calendar feed*), then in your own terminal: "
        "`base64 -i ics-sources.json | tr -d '\\n'` and paste the output as the secret value. "
        "Also add `NEWSDASH_PASSPHRASE` if you haven't — private sections require it.",
        f"{step + 1}. **Canvas courses (optional)** — add `CANVAS_BASE_URL` "
        "(e.g. `https://canvas.youruniversity.edu`) and `CANVAS_TOKEN` "
        "(Canvas → Account → Settings → *+ New Access Token*).",
        f"{step + 2}. **Or let AI walk you through it** — open this repo in Claude Code / Codex and paste: "
        "更推荐让 AI 带你配置——在 Claude Code 里粘贴：",
        "",
        "   > Use the Page Skill (书童Skill) in this repo. Interview me about my news sources, "
        "academic fields, calendars, and Canvas; update config/ for me; then guide me through "
        "adding each GitHub Secret myself. Never ask me to paste secret values into chat, and "
        "never commit URLs that contain tokens.",
        "",
        "Full walkthrough · 完整教程: "
        f"[docs/SETUP.md](https://github.com/{repo}/blob/main/docs/SETUP.md) · "
        f"[中文](https://github.com/{repo}/blob/main/docs/SETUP.zh.md)",
    ]
    return "\n".join(lines) + "\n"


def error_comment(message: str) -> str:
    return (
        "## ❌ Setup not applied · 配置未应用\n\n"
        f"{message}\n\n"
        "Edit this issue to fix the problem — the bot re-runs on every edit. "
        "修改本 Issue 后机器人会自动重试。\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--comment-out", required=True)
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()

    repo_root = Path(args.repo_root) if args.repo_root \
        else Path(__file__).resolve().parent.parent
    body = Path(args.body_file).read_text(encoding="utf-8")

    try:
        summary, warnings = apply(body, repo_root)
    except (ValueError, ConfigError, json.JSONDecodeError) as exc:
        Path(args.comment_out).write_text(error_comment(str(exc)), encoding="utf-8")
        print(f"::error::setup rejected: {exc}")
        sys.exit(2)

    Path(args.comment_out).write_text(
        success_comment(summary, warnings, args.repo), encoding="utf-8")
    print(f"applied: {json.dumps(summary, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
