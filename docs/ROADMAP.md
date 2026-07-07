# Roadmap

Personal Newsdash ships small and stays honest. This page is the single place to check
what exists today (v0.1), what is on deck (v0.2), and what will never happen.

House rule: a feature only lands if it stays serverless and keeps the privacy model
intact (see [DATA_CONTRACT.md](DATA_CONTRACT.md)). No exceptions for "just this one".

## v0.1.0 — shipped

- [x] **Serverless pipeline** — GitHub Actions cron → static JSON in `data/` →
      vanilla-JS site on GitHub Pages. No backend, no build step, zero API keys for
      the core loop.
- [x] **Three themes** — `the-type` (typography-first serif, vermillion accent),
      `nyt` (newspaper front page), `bear` (Bear Blog minimalism, auto dark).
- [x] **EN/ZH bilingual** — runtime language toggle, `i18n/{en,zh}.json`.
- [x] **Encryption login** — private sections encrypted with AES-256-GCM
      (PBKDF2-HMAC-SHA256, 600k iterations); entering the passphrase in the browser
      *is* the login. `visibility: "private"` encrypts everything behind a full-page gate.
- [x] **ICS calendars + Canvas courses** — private schedule from Google / Outlook /
      Canvas ICS feeds; Canvas LMS announcements and upcoming assignments with
      submission state.
- [x] **Scholarly fetchers** — `arxiv`, `crossref` (reliable keyless), `openalex`,
      `semanticscholar` (best-effort keyless), with `academic-datavis` and
      `academic-techcomm` presets.
- [x] **Annotations, local-only** — highlight / excerpt / note stored in IndexedDB,
      displayed only after unlock; Clippings view exports Obsidian-friendly Markdown.
- [x] **Issue-ops onboarding** — "Set up my Newsdash" issue form → owner-guarded
      workflow commits your config, dispatches a build, and replies with bilingual
      next steps.
- [x] **Page Skill｜书童Skill** — in-repo maintainer skill for agents
      (interviews you, narrates secrets setup, never touches secret values).

## v0.2 — candidates

Not commitments. Rough priority order. Each item ships only when it clears the house
rule above.

- **Annotation sync** — commit annotations back to the repo *encrypted*, authorized by
  a fine-grained `NEWSDASH_SYNC_PAT` (secret name already reserved). Annotations stay
  unreadable without your passphrase; the PAT is scoped to this one repo.
- **LLM enrichment + ZH item translation** — optional, budget-gated summaries and
  Chinese translations of items via `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
  (reserved). The core pipeline stays LLM-free; this is a bolt-on, off by default.
- **AgentMail email ingestion** — newsletters as a source, via reserved `AGENTMAIL_*`
  secrets, following the ai-news-radar pattern (redacted digests, publish opt-in).
- **Reader-side consumer skill** — install without forking and ask your agent
  "what's on my dash today?" — the analog of radar's `ai-radar` skill, reading this
  site's public JSON (and, with your passphrase, your encrypted sections locally).
- **Story clustering + scoring backtest** — merge multi-source coverage of the same
  event and replay scoring changes against `archive.json`, porting radar's
  v0.6 (story merge) and v0.7 (hot ranking + backtest tool) ideas.
- **Dark variants for `the-type` and `nyt`** — `bear` already auto-darks; the other
  two deserve deliberate dark palettes, not an inverted filter.
- **`deploy-pages` no-commit mode + history-squash workflow** — publish `data/` via
  the Pages artifact API instead of committing it, and a one-click workflow to squash
  the bot-commit history that accumulates in the meantime.
- **OAuth calendar adapters** — Google / Microsoft OAuth as an alternative to secret
  ICS URLs, which regenerate and silently kill your schedule.

## Not planned

Being upfront beats a stale "coming soon":

- **Multi-user auth.** One site, one passphrase, one reader: you. Accounts, roles, and
  sharing flows all imply a server and a trust model this project deliberately does
  not have. Deploy a second Newsdash instead — it's a template.
- **Anything server-side.** No API server, no database, no edge functions, no
  "tiny proxy just for X". Every feature must survive as static files on GitHub Pages
  plus a cron job on GitHub Actions, or it doesn't ship.
