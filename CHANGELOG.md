# Changelog

All notable changes to Relevance (及君) are documented here.
The version number lives in `scripts/newsdash/__init__.py` (`__version__`),
is emitted into `data/manifest.json` as `app_version`, and is shown on the
site under **Settings → About**. Bump it and add an entry here whenever a
round of significant changes lands. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver
(minor = feature round, patch = fixes).

## [0.3.0] — 2026-07-23

Threads · 线索 round.

### Added
- **Threads · 线索** — a build-time LLM keyword-aggregation block that
  replaces the client-computed Highlights block: up to `threads.max_threads`
  bilingual keyword-themes where at least two different sources converge
  today, each with a cognitively light gloss, a "why now" occasion line, a
  convergence verdict, and per-source angles that link back to the
  underlying items. One bilingual LLM call per scope; works with any
  OpenAI-compatible endpoint; gracefully falls back to Highlights whenever
  it's off, keyless, or the model returns too few threads.
- **Private-scope Threads** behind `threads.include_private` (default
  `false`, explicit consent) — a fully separated call over
  `category: "private"` input only, written encrypted-only to
  `threads-private.enc.json` (AAD `newsdash:v1:threads-private`); no
  plaintext variant exists regardless of site visibility. Ships dormant in
  this template (`threads.include_private: false`, no private sections
  configured) — custom private-section wiring exercised end-to-end.
- **Shared `scripts/newsdash/llm.py` client** — extracted from
  `summarize.py`'s OpenAI-compatible post/parse helpers, now shared by
  `summarize.py`, `apropos.py`, `todays_image.py`, and `threads.py`.
- **`LLM_THREADS_ENABLED` kill switch** (Variable) — turns Threads off
  without touching `LLM_API_KEY` or `site.json`.

### Fixed / Security
- **Archive plaintext leak (pre-existing)** — the rolling `archive.json`
  build loop did not filter by category, so once a private section existed
  on a `visibility: "public"` site, its items would have been archived into
  the *plaintext* archive alongside open/optional items. The loop now
  explicitly skips `category: "private"` sections before folding items into
  the archive map.

### Docs
- New `docs/THREADS_DESIGN.md` design note (Tamarkin's *Apropos of
  Something* + Latour's "Visualisation and Cognition").

## [0.2.0] — 2026-07-21

Onboarding & scheduling round.

### Added
- **First-deploy tutorial** — a one-time 5-slide setup checklist greets the
  first successful load, deep-linking to the deployer's own Issue form,
  Actions secrets page, and skill README; reopenable from Settings → About.
- **Guided 4-step skill workflow** (`skills/newsdash/SKILL.md` → "Guided
  setup"): ① Source Studio, a local gitignored HTML editor that hands the
  agent a source plan; ② Test & report, per-source health/freshness checks
  rendered as a chart; ③ Priority, an interview mapped onto
  `interests.*`/`weight` plus the new `ranking` knob; ④ Categories, custom
  nav tabs via `sections[]` metadata.
- **Homepage Highlights block** — top-scored items pooled across loaded
  sections with a per-source diversity cap (`site.json → ranking`:
  `highlights`, `max_per_source`).
- **Custom nav tabs** — `site.json → sections[]` gives custom sections
  bilingual labels, ordering, and a custom-only `kind` override.
- **Configurable update frequency** — `NEWSDASH_UPDATE_FREQ` repo variable
  (`2h` default / `3x` / `daily`) throttles the Actions cron at zero cost
  for skipped runs; settable from the setup Issue form or the skill.
  Recommended for private repos, which have limited free Actions minutes.

### Changed
- `docs/CONFIG_REFERENCE.md` / `docs/DATA_CONTRACT.md` document the new
  `ranking` and `sections[]` keys and manifest fields.

## [0.1.0] — 2026-07-19

Baseline: the Relevance template as of the 2026-07 restructure — rebrand
from "Personal Newsdash", tab merges (Clippings, unified Settings), the
private-source pipeline (`SRC_<ID>_URL`, AES-256-GCM envelope), source
discovery tooling (`scripts/discover_source.py`) and the Page Skill｜书童
maintainer skill.
