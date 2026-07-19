---
name: newsdash
description: "Use when working on Relevance, Page Skill, 书童Skill, 及君: setting up or personalizing a deployment (set up my relevance / 配置我的及君), adding news/paper sources, guiding GitHub Secrets, fixing a stale dashboard, themes, GitHub Actions, or GitHub Pages deployment."
---

# Page Skill｜书童Skill

The maintainer-side skill for Relevance. The 书童 (page) is a scholar's
study attendant: fetches the readings, sorts the correspondence — and never
reads the master's sealed letters. That last part
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

When a user asks you to set up or personalize their Relevance, interview them
in this order (one topic at a time, don't dump a questionnaire):

1. **Visibility first.** Explain the trade-off in one paragraph: *public* =
   news/papers readable by anyone, any private sections always encrypted;
   *private* = everything encrypted, site opens with a passphrase gate.
   Either way the repo stays public and privacy comes from encryption —
   "a private site is an encrypted public site."
2. **Language, theme, timezone, title** (`the-type` / `nyt` / `bear`; IANA timezone).
3. **Open packs** — `ai-news`, `general-news` — plus any custom RSS/blog feeds.
4. **Academic fields** — map to `academic-datavis` / `academic-techcomm`, or
   craft new sources for other fields: arXiv category queries (`cat:cs.CL`),
   CrossRef ISSN tracking for journals. Add their interest keywords.

Then apply it via ONE of:

- **The setup issue** (preferred for beginners): tell them to open
  *Issues → "Set up my Relevance · 配置我的及君"* and what to pick — the
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

**`LLM_API_KEY` / `SMITHSONIAN_API_KEY`** (optional AI daily brief,
Apropos-of-Nothing, and Today's Image) aren't a source — recipe in
`references/secrets-setup.md`. Verify by checking `manifest.json`'s
`ai_summary.enabled` flips to `true` (not a section, so the usual
"not_configured → ok" check doesn't apply); an `insights_file` may still
legitimately be `null` on a given run if there's nothing to summarize yet or
the public searches do not find a suitable sourced result. Flag before
narrating: this is the only feature that sends any user content to a
third-party endpoint of the user's choice.

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

When the user brings a **topic, a web page, or an OPML export** instead of a
ready feed URL, don't guess — reach for `scripts/discover_source.py`
(Discovery, below) to find and vet the feed first.

## Manage sources

The ongoing side of source work: knowing what's configured, reading its
health, and adding / editing / retiring / migrating entries. Recipes and
API cookbooks live in `references/source-intake.md`.

### List / audit what's configured

Config lives in two places that merge at build time: `config/sources.json`
(the user's own `sources[]` + `presets[]`) and `config/presets/*.json` (the
packs). Never read only one — a source can be a preset entry, an override of
a preset entry, or a fully custom entry.

For the *resolved* active/waiting picture, run the validator — it does the
merge and the secret-presence check for you:

```bash
python scripts/validate_config.py
```

It prints a per-category rollup (`open` / `optional` / `private`, each as
`N sources (A active, W awaiting secrets)`), then one
`waiting: <id> (set secret: SRC_…)` line per private source whose
`SRC_<ID>_URL` secret is still absent. Names only, never values — safe to
paste into an issue or a public log.

### Health triage (`data/source-status.json`)

`source-status.json` is bot-owned build output (don't hand-edit it). Read the
local copy after a build, or the deployed
`https://<owner>.github.io/<repo>/data/source-status.json` — but note that
under `visibility: "private"` the deployed copy is itself encrypted, so read
the freshly built local file instead. Each **public** source is one entry;
private sources appear **only** as the aggregate `private_summary`
`{ total, configured }` (never a per-source entry, name, count, or error).

Triage each public entry from `ok` (bool) + `error` + `skip_reason`
(`skip_reason` is `null`, `"disabled"`, or `"not_configured"` — there is no
per-source `status` string):

| Entry state | Reading | Action |
|---|---|---|
| `ok: true` | healthy | leave it |
| `ok: false`, `skip_reason: null`, `error` set | fetch failed this build | note the `error` class; a one-off (timeout, 5xx, weekend-quiet arXiv) needs nothing — persistent > 1 week ⇒ lower `weight` or set `enabled: false` |
| `skip_reason: "not_configured"` | required secret absent | run the secrets protocol below (private sources) or add the missing key |
| `skip_reason: "disabled"` | intentionally off (`enabled:false` or `<ID>_ENABLED=0`) | leave unless the user wants it back |

For **private** sources you get no per-source health in public output by
design — only `private_summary.configured` (the count with their
`SRC_<ID>_URL` present). Per-source private detail rides inside the encrypted
`private` section's `meta`; read it only by decrypting locally, only at the
user's explicit request, per the Safety rules — never into a log or comment.

### Add / edit / remove

Two paths, same schema:

- **Direct edit** — edit `config/sources.json`, run
  `python scripts/validate_config.py`, then commit. Fastest when you're
  already in the repo.
- **The add-source issue** — *Issues → "Add or edit a source · 添加或编辑信源"*
  (label `newsdash-source`), applied by `scripts/apply_issue_setup.py`
  (exit `0` = applied, `2` = rejected, with a bilingual comment either way).
  Preferred when the user isn't editing files directly. Its leak guards are
  load-bearing — see the private protocol below.

**Preset sources are never edited inside the pack.** To disable or reweight a
`config/presets/*.json` entry, override it from `sources[]` by id:
`{"id": "<same-id>", "enabled": false}` or `{"id": "<same-id>", "weight":
0.3}` (any field overrides the pack's). Editing the pack file diverges you
from upstream and breaks the override contract.

### Migrate between sections

Move a source to a different tab by changing its `section`
(`news`/`papers`/`following`/`private`). Two things to know:

- `tag_rules` follow the section, and NEW-badge seen-state is keyed by
  **source id** — a rename resets the badge, a section change does not.
- **Category never changes in a migration.** A source that needs a credential
  stays `category: "private"` no matter which `section` it renders in —
  "needs a credential" is a property of the source, not the tab. The issue
  flow *enforces* this: `apply_issue_setup.py` refuses to flip an existing
  private source's category off `"private"` (its capability URL lives in a
  Secret that must be rotated first), and refuses any URL/query/ISSN aimed at
  an existing private source, treating it as a leaked value.

### Add a private URL source (protocol)

Order matters — config entry first, secret second:

1. **Write the config entry** in `config/sources.json`: `category: "private"`,
   `type` one of `rss`/`feed-json`/`static-page`, `enabled: "auto"`,
   `secret_ref: ["SRC_<ID>_URL"]`, `section: "private"` (default). No `url`,
   no `path` — the schema rejects them on private sources.
2. **Narrate the secret setup** per `references/secrets-setup.md`
   (`SRC_<ID>_URL`): the exact name, the settings page, that the value is the
   full `https://` capability URL. Never ask for or handle the value.
3. **Verify** after the next build: `private_summary.configured` increments by
   one, and the 🔒 Private tab appears (only once ≥ 1 private source is
   configured) behind the unlock gate.

**If a capability URL ever lands in chat or an issue body: it is leaked.**
Do not echo, store, or use it — tell the user to rotate it immediately (see
Safety rules), then continue narrate-only.

### Discovery — topic / page / OPML in, feed out

When the user hasn't handed you a feed URL, use `scripts/discover_source.py`
(full examples in `references/source-intake.md`). **Always `dupcheck` before
adding.**

```bash
python scripts/discover_source.py probe <page-or-feed-url>   # autodiscover + health, prints a config snippet
python scripts/discover_source.py probe --opml <file>        # list an OPML's feeds, deduped, snippets for new ones
python scripts/discover_source.py dupcheck <url-or-issn>      # overlap vs merged config (host / ISSN / id)
```

`probe` recommends a `weight` from freshness (≥ 1 item/week → `0.8`, sparser
→ `0.5`) and **refuses** a URL that looks like a capability link (token / key /
sig params, private-calendar paths) with exit code `3` and a "classify as
private, do not probe" message — that's the signal to switch to the private
protocol above, not to work around it.

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

- Never commit or log: the passphrase, source capability URLs / tokens
  (they **are** credentials), `.env` values, or decrypted private payloads.
- Never print decrypted private-section content into CI logs, PR bodies, or
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
