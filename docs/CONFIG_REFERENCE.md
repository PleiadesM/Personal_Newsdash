# Config Reference — "I want to change X → edit Y"

[中文](CONFIG_REFERENCE.zh.md) · Applies to `config/*.json`, `config/presets/*.json`, `.github/workflows/update.yml`.

**Core principle** (inherited from ai-news-radar): keys live in **Secrets**;
tuning lives in **config files**; GitHub Variables exist only as **kill
switches**. Everything below is plain JSON, validated by the schemas in
`config/schema/` — `python scripts/validate_config.py` tells you exactly
what's wrong.

## 1. One-minute overview (defaults as shipped)

| Dimension | Default | Where |
|---|---|---|
| Update frequency | every 2 h (`17 */2 * * *`) | `update.yml` cron line |
| News window | 24 h | `site.json → windows.news_hours` |
| Papers window | 7 days | `windows.papers_days` |
| Schedule window | −1 d … +14 d | `windows.schedule_past_days` / `schedule_horizon_days` |
| Courses horizon | 30 days | `windows.courses_horizon_days` |
| Archive retention | 14 days (cap 3000 items) | `windows.archive_days` |
| Presets on | `ai-news`, `general-news` | `sources.json → presets` |
| Theme / language | `the-type` / `en` | `site.json` |
| Visibility | `public` | `site.json → visibility` |

## 2. `config/site.json`

| Key | Values | Effect |
|---|---|---|
| `title`, `subtitle` | strings | Masthead text + `<title>` |
| `visibility` | `"public"` \| `"private"` | **public**: news/papers plaintext, schedule/courses always encrypted. **private**: *every* file encrypted; site boots to a passphrase gate; build **fails** if `NEWSDASH_PASSPHRASE` is missing |
| `languages` | subset of `["en","zh"]` | Offered UI languages |
| `default_language` | `"en"` \| `"zh"` | Chrome language before the visitor toggles |
| `theme` | `"the-type"` \| `"nyt"` \| `"bear"` | Default theme (visitors can switch; their choice persists per browser) |
| `timezone` | IANA name | Schedule windowing + event offsets (display uses the *viewer's* clock) |
| `windows.*` | integers | See overview table; schema enforces sane ranges |

## 3. `config/sources.json`

```jsonc
{
  "presets": ["ai-news", "general-news"],        // packs to activate
  "interests": {
    "keywords": ["data visualization", "LLM"],   // fuels the 0.35 relevance term
    "boost": 0.15                                 // extra credit for any match (0–0.5)
  },
  "sources": [ /* custom sources + preset overrides */ ]
}
```

**Score formula**: `0.45·recency + 0.35·keyword-relevance + 0.20·source-weight`;
recency decays exponentially (half-life 12 h news / 84 h papers). Events and
courses are never scored — they stay time-ordered.

**Override a preset source by id** — same `id` merges field-by-field:

```json
{ "id": "hn_frontpage_ai", "enabled": false }
{ "id": "verge_ai", "weight": 0.4 }
```

**`enabled`**: `true` (always) · `false` (off) · `"auto"` (on iff every env
var named in `secret_ref` is set — key present ⇒ on). Emergency stop for any
source without touching config: set the GitHub *Variable*
`<UPPERCASED_SOURCE_ID>_ENABLED=0` (e.g. `CANVAS_ENABLED=0`).

## 4. Source types

| `type` | Category default | Needs | Notes |
|---|---|---|---|
| `rss` | open | `url` | optional `keywords` title filter |
| `opml` | open | `url` or `path` | `RSS_MAX_FEEDS` caps expansion (default 10) |
| `feed-json` | open | `url` | JSON Feed 1.x or bare array |
| `static-page` | open | `url` (+ `query` CSS selector) | items stamped with build time |
| `arxiv` | optional | `query` | e.g. `cat:cs.HC OR cat:cs.GR` |
| `openalex` | optional | `query` | reliable only with `OPENALEX_API_KEY` |
| `crossref` | optional | `issn` list or `query` | journal tracking; created-date recency |
| `semanticscholar` | optional | `query` | best-effort keyless |
| `ics` | private | `secret_ref` | URLs live in `ICS_SOURCES_B64` — **never** in config |
| `canvas` | private | `secret_ref` | `CANVAS_BASE_URL` + `CANVAS_TOKEN` |

Common fields: `id` (snake_case, unique), `name`, `section`
(`news`/`papers`/`schedule`/`courses`), `weight` (0–1, default 0.8),
`max_results` (default 50). The schema **rejects** `url`/`path` on
`category: "private"` sources.

## 5. Preset packs (`config/presets/<id>.json`)

```json
{
  "id": "academic-hci",
  "name": { "en": "Academic · HCI", "zh": "学术 · 人机交互" },
  "category": "optional",
  "section": "papers",
  "sources": [
    { "id": "arxiv_hci", "type": "arxiv", "name": "arXiv cs.HC",
      "query": "cat:cs.HC", "max_results": 60, "weight": 1.0 }
  ],
  "tag_rules": [
    { "tag": "eval-study", "any": ["user study", "participants"] }
  ]
}
```

Activate it by adding `"academic-hci"` to `presets` in `sources.json`.
`tag_rules` only tag items from **that pack's own sources** — an ai-news rule
never fires on a BBC story.

## 6. Secrets & variables master table

| Name | Kind | Needed by |
|---|---|---|
| `NEWSDASH_PASSPHRASE` | Secret | any encryption (private sections; everything when `visibility:"private"`) |
| `ICS_SOURCES_B64` | Secret | `ics` sources |
| `CANVAS_BASE_URL`, `CANVAS_TOKEN` | Secret | `canvas` source |
| `OPENALEX_API_KEY` | Secret | reliable `openalex` |
| `FOLLOW_OPML_B64` | Secret | private OPML |
| `CONTACT_MAILTO` | Variable | CrossRef/OpenAlex polite pools |
| `<ID>_ENABLED` | Variable | `0` = emergency stop for source `<id>` |
| `RSS_MAX_FEEDS` | Variable | OPML expansion cap |

## 7. "I want to change X" quick table

| I want to… | Edit |
|---|---|
| Update more/less often | `update.yml` cron (public repo: `*/30 * * * *` is fine; private repo: mind the 2000 min/month) |
| Longer news window | `site.json → windows.news_hours` |
| Deeper paper lookback | `windows.papers_days` |
| Keep archive longer | `windows.archive_days` |
| Mute one preset feed | `sources.json`: `{ "id": "...", "enabled": false }` |
| Follow a journal | crossref source with its `issn` |
| Boost my topics | `interests.keywords` (+ `boost`) |
| Stop Canvas *now* | Variable `CANVAS_ENABLED=0` |
| Different theme/language default | `site.json → theme` / `default_language` |
| Rename the site | `site.json → title` |

After hand-editing: `python scripts/validate_config.py`, then commit — the
next scheduled run picks it up (or `gh workflow run update.yml`).
