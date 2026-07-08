---
name: newsdash
description: "Use when working on Personal Newsdash, Page Skill, 书童Skill, 个人新闻台: setting up or personalizing a deployment (set up my newsdash / 配置我的新闻台), adding news/calendar/course/paper sources, guiding GitHub Secrets, fixing a stale dashboard, themes, GitHub Actions, or GitHub Pages deployment."
---

# Page Skill｜书童Skill

The maintainer-side skill for Personal Newsdash. The 书童 (page) is a scholar's
study attendant: minds the schedule, fetches the readings, sorts the
correspondence — and never reads the master's sealed letters. That last part
is the point: **this skill narrates secrets setup; it never touches secret
values.**

## First Reads

When this skill triggers inside the repo, read these first (as needed):

- `README.md` — product overview, source taxonomy, quick start.
- `docs/SETUP.md` — the click-by-click onboarding path users follow.
- `docs/CONFIG_REFERENCE.md` — every config key; "change X → edit Y".
- `docs/DATA_CONTRACT.md` — pipeline ⇄ frontend interface. Read before
  touching `scripts/` or `assets/js/`.
- `docs/SECURITY_MODEL.md` — threat model and invariants.
- `docs/SOURCES.md` + `references/source-intake.md` — when the user proposes
  a new source.
- `references/secrets-setup.md` — when credentials come up.
- `references/crypto-notes.md` — before touching anything crypto-adjacent.
- `config/site.json`, `config/sources.json`, `config/presets/*.json` — current state.

## Onboarding interview

When a user asks you to set up or personalize their Newsdash, interview them
in this order (one topic at a time, don't dump a questionnaire):

1. **Visibility first.** Explain the trade-off in one paragraph: *public* =
   news/papers readable by anyone, schedule/courses always encrypted;
   *private* = everything encrypted, site opens with a passphrase gate.
   Either way the repo stays public and privacy comes from encryption —
   "a private site is an encrypted public site."
2. **Language, theme, timezone, title** (`the-type` / `nyt` / `bear`; IANA timezone).
3. **Open packs** — `ai-news`, `general-news` — plus any custom RSS/blog feeds.
4. **Academic fields** — map to `academic-datavis` / `academic-techcomm`, or
   craft new sources for other fields: arXiv category queries (`cat:cs.CL`),
   CrossRef ISSN tracking for journals. Add their interest keywords.
5. **Private sources** — which calendars (Google / Outlook / Canvas ICS)?
   Which LMS (Canvas base URL)?

Then apply it via ONE of:

- **The setup issue** (preferred for beginners): tell them to open
  *Issues → "Set up my Newsdash · 配置我的新闻台"* and what to pick — the
  owner-guarded workflow applies it and comments next steps; or
- **Direct edit**: modify `config/site.json` / `config/sources.json`, run
  `python scripts/validate_config.py`, and commit.

## Secrets guidance protocol — narrate, never touch

For every secret, give the user: the exact page
(`https://github.com/<owner>/<repo>/settings/secrets/actions/new`), the exact
secret **name**, how to produce the **value in their own terminal**, and how
to verify afterwards. Recipes live in `references/secrets-setup.md`.

Verification loop after they add a secret:

```bash
gh workflow run update.yml && gh run watch
# then confirm the section flipped from "not_configured" to "ok":
curl -s https://<owner>.github.io/<repo>/data/manifest.json | python3 -m json.tool
```

**If the user pastes a real credential into the chat: do not echo it, do not
store it, do not use it. Tell them to rotate it immediately** (pasted-into-a-
logged-context counts as leaked), then continue with the narrate-only flow.

**`LLM_API_KEY` / `SMITHSONIAN_API_KEY`** (optional AI daily brief + Today's
Image) aren't a source — recipe in `references/secrets-setup.md`. Verify by
checking `manifest.json`'s `ai_summary.enabled` flips to `true` (not a
section, so the usual "not_configured → ok" check doesn't apply); an
`insights_file` may still legitimately be `null` on a given run if there's
nothing to summarize yet. Flag before narrating: this is the only feature
that sends any user content to a third-party endpoint of the user's choice.

## Evaluate a new source

Decision order (radar's 伯乐 spirit): official RSS/Atom > public generated
feed (another project's committed JSON/feed output) > OPML > focused
static-page fetcher > skip. Judge signal density before adding; when unsure,
add with a low `weight` and review `source-status.json` after a week.
Per-type intake rules and config snippets: `references/source-intake.md`.

Classification is category-first: does fetching it require a capability URL,
cookie, or token? Then it is **private** — `secret_ref` only, never a `url`
in config (the schema enforces this). Scholarly APIs → **optional**.
Everything else → **open**.

## Validate

```bash
python -m pytest -q
python scripts/validate_config.py
python scripts/build.py --output-dir /tmp/nd-test --smoke
node tests/test_crypto_webcrypto.mjs
```

For a live check: `gh workflow run update.yml && gh run watch`, then reload
the site (data can lag ~10 min behind the Pages CDN).

## Safety rules (hard block)

- Never commit or log: the passphrase, Canvas tokens, ICS URLs (capability
  URLs **are** credentials), decoded `ICS_SOURCES_B64`, `.env` values, or
  decrypted private payloads.
- Never print decrypted schedule/courses content into CI logs, PR bodies, or
  issue comments. Public repos have public logs. Local decryption via
  `scripts/encrypt_tool.py decrypt` only at the user's explicit request,
  output to their terminal only.
- Never weaken crypto parameters (AES-256-GCM, PBKDF2-SHA256 600k iterations,
  16-byte salt, 12-byte nonce, NFC normalization) and never add a plaintext
  fallback for private sections. The envelope is pinned by
  `tests/test_crypto_webcrypto.mjs` — if that test fails, stop.
- Never remove the owner guard in `.github/workflows/setup-from-issue.yml`.
- Never relax the schema rule forbidding `url`/`path` on private sources.
- Keep the zero-secret build green: every new source must skip cleanly when
  its secrets are absent (`enabled: "auto"` + `secret_ref`).
- `data/` is bot-owned output; never hand-edit it.
