# Source intake — per-type rules

Decision order: **official RSS/Atom > public generated feed > OPML > focused
static fetcher > skip.** Category first: needs a capability URL / token /
cookie ⇒ `private` (secret_ref only). Scholarly API ⇒ `optional`. Else `open`.

| Type | Required fields | Intake checks | Notes |
|---|---|---|---|
| `rss` | `url` | Fetch it once; entries have dates? titles? | Add `keywords` to filter firehoses (see the HN entry in `config/presets/ai-news.json`) |
| `opml` | `url` or `path` | Feed count ≤ `RSS_MAX_FEEDS` (default 10) | Private subscriptions → `FOLLOW_OPML_B64` secret, decoded to `feeds/follow.opml` at build time; never commit the real file |
| `feed-json` | `url` | JSON Feed 1.x or a bare array with `title`/`url`/date fields | The "consume another project's public output" pattern (from ai-news-radar) — don't rebuild their crawler |
| `static-page` | `url` (+ `query` = CSS selector) | Links stable? Titles ≥ 8 chars? | Last resort. Items are stamped with build time (pages carry no dates) — they stay "fresh" while listed |
| `arxiv` | `query` | Valid search query (`cat:cs.HC OR cat:cs.GR`) | 3 s throttle built in; quiet on weekends — not an error |
| `crossref` | `issn` (list) or `query` | ISSN format `1234-5678`; check the journal actually registers with CrossRef | Recency = record *created* date (right for slow journals); 30 s timeout — CrossRef is slow |
| `openalex` | `query` | — | Best-effort keyless since the 2026 credits change; reliable only with `OPENALEX_API_KEY` |
| `semanticscholar` | `query` | — | Shared keyless pool, 429s often; best-effort by design |
| `ics` | `secret_ref: ["ICS_SOURCES_B64"]` | Never accept a calendar URL into config — it's a credential | URLs live in the secret's JSON payload (`examples/ics-sources.example.json`) |
| `canvas` | `secret_ref: ["CANVAS_BASE_URL", "CANVAS_TOKEN"]` | — | REST: active courses → announcements → upcoming assignments w/ submission state |

Every source: unique snake_case `id`, human `name`, `section`
(`news`/`papers`/`schedule`/`courses`), `weight` 0–1 (feeds the 0.20 score
term), `max_results`. New source of unknown quality → `weight: 0.5`, watch
`source-status.json` for a week, then promote or drop (伯乐 discipline).

Disable or reweight a preset source without copying the pack: add
`{"id": "<same-id>", "enabled": false}` (or `"weight": 0.3`) to `sources[]`.
