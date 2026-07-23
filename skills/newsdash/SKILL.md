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

## Guided setup — the Source Studio workflow

For a deployer who has cloned the repo and is working with you (Claude Code,
Codex, …), prefer this hands-on, four-step flow over a chat questionnaire. Each
step is one turn; pause for the user between them.

1. **Source Studio** — run `python scripts/build_source_studio.py` to generate a
   local, gitignored HTML editor. The user curates sources there (add/remove,
   public/private, friendly kinds, weights) and Saves a `sources.plan.json`; you
   apply it. Full protocol: `references/source-studio.md`.
2. **Test & report** — health-check each source and show the results + weight /
   dedupe recommendations, then add sources by description.
3. **Priority** — interview the user's interests, then tune `interests` +
   per-source `weight` and diversify the homepage.
4. **Categories** — propose a set of named nav tabs (sections), assign sources
   to them, and give each a friendly bilingual label.

### Step 1 — Source Studio

Generate it, tell the user to open `newsdash-studio/source-studio.html`, edit,
and Save / Copy the plan. Then apply it per `references/source-studio.md`: run
every `url` past the capability-URL gate (`scripts/discover_source.py`), write
`plan.sources` into `config/sources.json` (preserving `interests`/`tag_rules`),
set `presets`, and `python scripts/validate_config.py`. **A private source in
the plan carries a `secret_ref` name and never a `url`** — keep it that way.

### Step 2 — Test & report

Health-check the planned sources and show the user the result:

```bash
python scripts/discover_source.py report --plan newsdash-studio/sources.plan.json
python scripts/build_source_report.py
```

The first writes `newsdash-studio/source-report.json` (per-source status,
freshness/cadence, a recommended weight, duplicate overlaps); the second renders
`newsdash-studio/source-report.html` — a freshness chart + a table with a
plain-language recommendation per source. The report references sources by name
only and **never prints a URL**, so it is safe to share. Walk the user through it:

- **ok** — healthy; keep. If the recommended weight differs from the planned one, offer to adjust.
- **empty / unhealthy** — parses with no recent items, or failed to fetch; verify the URL or drop it.
- **capability** — an "open" source whose URL looks like a credential; move it to a
  private source (`secret_ref`), never store the URL. (The Studio blocks this, but a hand-edited plan can trip it.)
- **private / api** — not health-checked locally (private URLs live in Secrets; scholarly APIs depend on the service).
- **duplicates** — two sources share a host or ISSN; drop or merge one.

Apply the keep/drop/weight decisions to `config/sources.json`, re-run
`validate_config.py`. Then **add sources by description**: when the user says
"follow X" or "add this blog", use `scripts/discover_source.py probe <url>` +
`references/source-intake.md` to find and vet the feed, then slot it in.

### Step 3 — Priority & homepage variety

Now make the ranking feel like the owner's. Interview them per
`references/priority-interview.md` — read `scripts/newsdash/scoring.py` first so
your promises match the real formula (recency + keyword relevance + weight).
The interview maps their answers onto four knobs:

- `interests.keywords` + `interests.boost` in `config/sources.json` — what
  topics lift an item (boost `0.0`–`0.5`, default `0.15`).
- per-source `weight` (`0`–`1`) — a steady thumb on the scale for trusted
  feeds; override preset weights by id, never edit the pack.
- `ranking` in `config/site.json` — homepage variety. `{"highlights": true,
  "max_per_source": 2}`: `highlights` toggles the mixed top-of-page Highlights
  block; `max_per_source` (minimum `1`) caps how many items one feed may
  contribute so no single source hogs the front page.

Apply, then validate + smoke build and sanity-read the ordering:

```bash
python scripts/validate_config.py
python scripts/build.py --output-dir /tmp/nd --smoke
```

Because `--smoke` feeds are empty, also eyeball a live build (or the deployed
`data/news.json`) to confirm the owner's keywords and trusted sources actually
surface. Full protocol and the answers→config mapping table live in
`references/priority-interview.md`.

### Step 4 — Categories (custom tabs)

Finally, give the dashboard its shape. Cluster the existing sources into a
handful of named nav tabs (sections), reusing the Studio's per-source `section`
assignment from step 1, and give each tab a friendly **bilingual** label so the
nav reads "AI 前沿" rather than a raw `ai` id. Custom sections already build and
route — this step only adds their metadata.

Propose 4–7 tabs (the built-ins `news`/`papers` stay), show the owner a table of
tab id, en/zh label, and which sources move in, then apply: set `section` on the
moving sources in `config/sources.json`, and add a `sections[]` block to
`config/site.json`:

```json
"sections": [
  { "id": "ai", "label": { "en": "AI", "zh": "AI 前沿" }, "order": 1, "kind": "news" }
]
```

`order` and `kind` are optional (`kind` is a custom-sections-only news-/
papers-rendering override — rejected on built-ins); `label` needs at least one
of en/zh. Validate + smoke build and confirm `manifest.sections[].label`:

```bash
python scripts/validate_config.py
python scripts/build.py --output-dir /tmp/nd --smoke
```

Labels are **public plaintext** in the manifest (readable before login) — never
put private or secret info in them, and keep private sources in the `private`
section. Full clustering guidance, the proposal format, and the rules live in
`references/categories.md`.

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

### Enable Threads

"Threads · 线索" is the LLM keyword-aggregation block that replaces the
homepage Highlights block; it needs `LLM_API_KEY` before it does anything.

1. **Narrate the secret setup**: `LLM_API_KEY` (same secret the AI daily
   brief already uses — no new secret if it's already configured), plus
   Variables `LLM_BASE_URL` / `LLM_MODEL` for the endpoint (defaults:
   `https://api.openai.com/v1` / `gpt-4o-mini`; the owner's DeepSeek setup is
   `https://api.deepseek.com/v1` / `deepseek-chat`). Never ask for or handle
   the key value.
2. **Optional tuning** in `config/site.json → threads`: `enabled` (default
   `true` — nothing to change unless the user wants it off),
   `max_threads` (2–6, default 6), and `include_private` (default `false` —
   flip only with explicit user consent; it sends private-section titles and
   summaries to the configured LLM endpoint, see `docs/CONFIG_REFERENCE.md`
   §2c).
3. **Run the update workflow**: `gh workflow run update.yml && gh run
   watch`.
4. **Verify**: `manifest.threads_file` is non-null (public scope ran); if
   `include_private` was turned on, `manifest.threads_private_file` is also
   non-null. If the LLM endpoint errors or returns too few threads, both
   stay `null` and the site quietly falls back to Highlights — that is
   expected graceful degradation, not a bug.

**Kill switch**: repo Variable `LLM_THREADS_ENABLED=0` turns Threads off
without touching the key or `site.json`.

### Wire a private career section

A worked example of adding a custom private section and pointing Threads'
private scope at it — follow the general private-source protocol above,
plus:

1. **Config shape** in `config/sources.json`: private sources with
   `category: "private"`, `secret_ref: ["SRC_<ID>_URL"]` per source (e.g.
   `SRC_CAREER_HIGHEREDJOBS_URL`), pointed at a custom section — add that
   section's metadata (`id`, bilingual `label`) to `config/site.json →
   sections[]` (§2b of `docs/CONFIG_REFERENCE.md`). No `url`/`path` in the
   repo — the schema rejects them on private sources.
2. **Consent flag**: if the user wants this section's items fed into
   Threads, that requires flipping `site.json → threads.include_private:
   true` — narrate the consent note from `docs/CONFIG_REFERENCE.md` §2c
   before doing it (private titles/summaries leave the build for the
   configured LLM endpoint).
3. **Narrate each secret** per `references/secrets-setup.md` — the exact
   name, the settings page, that the value is the full `https://` feed URL.
   Never ask for or handle the value; the owner creates the Secrets
   themselves.
4. **Verify** after the next build: the new section's `.enc.json` file
   (e.g. `career.enc.json`) appears and decrypts under unlock; if
   `include_private` is on, `threads-private.enc.json` also appears. Before
   secrets are set, `python scripts/validate_config.py` prints a `waiting:
   <id> (set secret: SRC_…)` hint for each — that's the expected
   zero-secret-green state, not an error.

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

## Update frequency

How often Actions rebuilds the site is controlled by the **repo Variable
`NEWSDASH_UPDATE_FREQ`** — not by config files. Three values:

- `2h` (default; also when unset/empty) — every 2 h, ≈ 900 Actions min/month
- `3x` — 05:17 / 13:17 / 21:17 UTC, ≈ 225 min/month
- `daily` — 13:17 UTC, ≈ 75 min/month (at ~2.5 min/run)

`update.yml` defines all three crons; a job-level `if:` runs only the one that
matches the Variable and skips the rest **before any runner starts** (zero
billed minutes). Private repos get 2000 free min/month — pick `3x` or `daily`.

Set it three ways: the **setup Issue form** (Update frequency dropdown, applied
by the bot); the CLI — `gh variable set NEWSDASH_UPDATE_FREQ --body "3x"`; or
the UI — Settings → Secrets and variables → Actions → Variables. A manual
`workflow_dispatch` run (`gh workflow run update.yml`) always builds regardless
of the Variable.

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
