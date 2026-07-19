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
| Archive retention | 14 days (cap 3000 items) | `windows.archive_days` |
| Presets on | `ai-news`, `general-news` | `sources.json → presets` |
| Theme / language | `the-type` / `en` | `site.json` |
| Visibility | `public` | `site.json → visibility` |

## 2. `config/site.json`

| Key | Values | Effect |
|---|---|---|
| `title`, `subtitle` | strings | Masthead text + `<title>` |
| `visibility` | `"public"` \| `"private"` | **public**: news/papers plaintext, any private sections always encrypted. **private**: *every* file encrypted; site boots to a passphrase gate; build **fails** if `NEWSDASH_PASSPHRASE` is missing |
| `languages` | subset of `["en","zh"]` | Offered UI languages |
| `default_language` | `"en"` \| `"zh"` | Chrome and content language before the visitor toggles |
| `theme` | `"the-type"` \| `"nyt"` \| `"bear"` | Default theme (visitors can switch; their choice persists per browser) |
| `timezone` | IANA name | Day/window boundaries (display uses the *viewer's* clock) |
| `windows.*` | integers | See overview table; schema enforces sane ranges |

## 3. `config/sources.json`

```jsonc
{
  "presets": ["ai-news", "general-news"],        // packs to activate
  "interests": {
    "keywords": ["data visualization", "LLM"],   // fuels the 0.35 relevance term
    "boost": 0.15                                 // extra credit for any match (0–0.5)
  },
  "sources": [ /* custom sources + preset overrides */ ],
  "tag_rules": [                                  // global rules (unlike pack rules,
    { "tag": "llm", "any": ["LLM", "大模型"] },    // these hit EVERY source of the
    { "tag": "vis", "any": ["chart"], "section": "papers" }  // section; omit `section`
  ]                                               // to target all feed sections
}
```

**Score formula**: `0.45·recency + 0.35·keyword-relevance + 0.20·source-weight`;
recency decays exponentially (half-life 12 h news / 84 h papers). Papers whose
source reports a citation count use
`0.35·recency + 0.25·relevance + 0.15·weight + 0.25·citation-impact` instead
(log-scaled, saturating ≈1000 citations) so the best-cited work ranks first —
the frontend's "Top priority" sort and the Today page use this.

**Override a preset source by id** — same `id` merges field-by-field:

```json
{ "id": "hn_frontpage_ai", "enabled": false }
{ "id": "verge_ai", "weight": 0.4 }
```

**`enabled`**: `true` (always) · `false` (off) · `"auto"` (on iff every env
var named in `secret_ref` is set — key present ⇒ on). Emergency stop for any
source without touching config: set the GitHub *Variable*
`<UPPERCASED_SOURCE_ID>_ENABLED=0` (e.g. `HN_FRONTPAGE_AI_ENABLED=0`).

## 4. Source types

| `type` | Category default | Needs | Notes |
|---|---|---|---|
| `rss` | open | `url` | optional `keywords` title filter; embedded RSS/Atom content becomes an internal full-text reader when substantial |
| `opml` | open | `url` or `path` | `RSS_MAX_FEEDS` caps expansion (default 10) |
| `feed-json` | open | `url` | JSON Feed 1.x or bare array |
| `static-page` | open | `url` (+ `query` CSS selector) | items stamped with build time |
| `arxiv` | optional | `query` | e.g. `cat:cs.HC OR cat:cs.GR`, or `au:"Jane Doe"` |
| `openalex` | optional | `query` and/or `filter` | reliable only with `OPENALEX_API_KEY` |
| `crossref` | optional | `issn` list or `query` | journal tracking; created-date recency |
| `semanticscholar` | optional | `query` | best-effort keyless |

Common fields: `id` (snake_case, unique), `name`, `section`
(`news`/`papers`/`following`/`private`), `weight` (0–1, default
0.8), `max_results` (default 50), `lang` (`"zh"`/`"en"` forces the items'
language; omit to auto-detect per item). The active UI language also filters
visible news/research content: English mode shows only English items, and
Chinese mode shows only Chinese items. The schema **rejects** `url`/`path` on
`category: "private"` sources.

The full-text reader has no config switch in v1. For RSS/Atom sources only,
the pipeline marks an item **Full Text Available** when the feed itself
contains substantial embedded article text; Relevance stores sanitized
plaintext under `data/articles/` and the frontend opens it through
`#/read/<section>/<item_id>`. Summary-only feeds still link to the original
site exactly as before.

### Follow scholars and labs (the `following` section)

Point any source at `section: "following"` and it gets its own nav tab,
grouped by who you follow. The natural fit is `openalex` with a `filter`
instead of a `query` — see `examples/follows.sources.snippet.json` for
copy-paste entries:

```json
{ "id": "follow_jane_doe", "type": "openalex", "section": "following",
  "name": "Jane Doe", "filter": "authorships.author.id:A5023888391" }
```

Find the id by searching the person on <https://openalex.org> — their author
page URL ends in the `A…` id. Labs/institutions use
`authorships.institutions.lineage:I…`. arXiv author queries (`au:"Jane Doe"`)
and lab-blog RSS feeds pointed at the same section work too. All keyless —
the zero-secret build stays green.

### Private URL sources

A source is **private** (`category: "private"`) when fetching it needs a
capability URL or token — the schema **rejects** `url`/`path` on these
entries, so the coordinates never enter the repo. Instead, `secret_ref`
names exactly one GitHub Secret whose *value* is the full capability URL
(must start with `https://`); it is read into memory at build time and
never written to config, logs, or any output file. Supported private
`type`s: `rss`, `feed-json`, `static-page`. `section` defaults to
`"private"` — the frontend renders it as its own locked (🔒) page, gated
behind unlock, and it appears only once you've actually configured one.

```json
{ "id": "my_feed", "category": "private", "type": "rss",
  "section": "private", "name": "My private feed",
  "enabled": "auto", "secret_ref": ["SRC_MY_FEED_URL"] }
```

The secret name must match `^SRC_[A-Z0-9_]+$` (convention: `SRC_<ID>_URL`,
uppercased from the source's `id`). With `enabled: "auto"`, this is exactly
the general `secret_ref` rule from §3: the source is on iff every secret
named in `secret_ref` is present — here that's the one `SRC_<ID>_URL`. Leave
it unset and the source skips cleanly with `skip_reason: "not_configured"`
(zero-secret builds stay green); `validate_config.py` prints a `waiting:
<id> (set secret: SRC_…)` hint. The `<ID>_ENABLED=0` kill switch still
overrides everything, private sources included.

### 4a. Optional AI enrichment (daily brief + Today's Image + Apropos-of-Nothing)

Not a source — a build-time bolt-on, off by default, no config-file
surface at all (every knob is an env var, read the same way
`CONTACT_MAILTO`/`OPENALEX_API_KEY` already are). Server-side only: your
own key, never a visitor-supplied one. The build asks the LLM for separate
English and Chinese summary editions, plus a small image caption call only
when a CC0 image is found. It may also ask the LLM for a deliberately
off-profile public-news query, search GDELT's public DOC API once, and write
a short sourced "Apropos-of-Nothing" card. All of this happens per scheduled
build, never per visitor — budget-gated by design.

| Set this secret… | …to get |
|---|---|
| `LLM_API_KEY` | Language-specific AI daily briefs after the greeting, one-line summaries inside "Top stories" and "Top papers," and an "Apropos-of-Nothing" card at the end of Today that links to one intentionally off-profile public-news item |
| `LLM_API_KEY` **and** `SMITHSONIAN_API_KEY` | The above, plus a "Today's Image" block: a public-domain image from the [Smithsonian Open Access API](https://www.si.edu/openaccess) loosely/creatively matched to the day's content, with a one-sentence AI caption and a source link |

`LLM_API_KEY` targets any OpenAI-Chat-Completions-compatible endpoint
(`{LLM_BASE_URL}/chat/completions`, `Authorization: Bearer`) — OpenAI,
OpenRouter, Groq, Together, self-hosted Ollama/vLLM all work; tune the
endpoint/model with the `LLM_BASE_URL` / `LLM_MODEL` Variables (defaults:
`https://api.openai.com/v1`, `gpt-4o-mini`). `SMITHSONIAN_API_KEY` is free
from <https://api.data.gov/signup/> — one key works across every
api.data.gov API, Smithsonian included.

Hard guarantees:

- Reads only your `news`/`papers` items.
- Apropos-of-Nothing sends only news/papers titles and short summaries to the
  configured LLM, then searches public news through GDELT; visitor browsers
  never contact either service for that card.
- A GDELT rate limit or empty public-news result just omits the
  Apropos-of-Nothing card for that build; it does not fail or degrade the
  dashboard.
- Generates English and Chinese summaries separately. Each summary sees both
  English and Chinese inputs, but prioritizes the active target language.
- **Never** during `--smoke` (no network calls at all), regardless of which
  keys are set.
- Only images the Smithsonian explicitly marks `usage.access: "CC0"` are
  ever shown — a rights-uncertain result is treated as no image.
- Follows the exact same public/private encryption rule as every other
  section: plaintext when `visibility: "public"`, encrypted when
  `visibility: "private"`.
- `LLM_SUMMARY_ENABLED=0` / `TODAYS_IMAGE_ENABLED=0` /
  `APROPOS_OF_NOTHING_ENABLED=0` (Variables) force individual AI features
  off without removing the key.

See `docs/DATA_CONTRACT.md`'s `insights.json` section for the exact payload
shape.

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
| `OPENALEX_API_KEY` | Secret | reliable `openalex` |
| `FOLLOW_OPML_B64` | Secret | private OPML |
| `LLM_API_KEY` | Secret | AI daily brief + per-section summaries + Apropos-of-Nothing (§4a) |
| `SMITHSONIAN_API_KEY` | Secret | Today's Image (§4a); requires `LLM_API_KEY` too |
| `SRC_<ID>_URL` | Secret | Capability URL for one private source (`category: "private"`, `secret_ref`) — see §4 |
| `CONTACT_MAILTO` | Variable | CrossRef/OpenAlex polite pools |
| `<ID>_ENABLED` | Variable | `0` = emergency stop for source `<id>` |
| `RSS_MAX_FEEDS` | Variable | OPML expansion cap |
| `LLM_BASE_URL` / `LLM_MODEL` | Variable | AI endpoint + model (§4a) |
| `LLM_SUMMARY_ENABLED` / `TODAYS_IMAGE_ENABLED` / `APROPOS_OF_NOTHING_ENABLED` | Variable | `0` = emergency stop for an AI feature |

## 7. "I want to change X" quick table

| I want to… | Edit |
|---|---|
| Update more/less often | `update.yml` cron (public repo: `*/30 * * * *` is fine; private repo: mind the 2000 min/month) |
| Longer news window | `site.json → windows.news_hours` |
| Deeper paper lookback | `windows.papers_days` |
| Keep archive longer | `windows.archive_days` |
| Mute one preset feed | `sources.json`: `{ "id": "...", "enabled": false }` |
| Follow a journal | crossref source with its `issn` |
| Follow a scholar/lab | openalex source with `filter` + `section: "following"` (§4) |
| Add topic tags everywhere | top-level `tag_rules` in `sources.json` (§3) |
| Add a private feed | add a config entry (`category: "private"`, `secret_ref`) + set one matching `SRC_<ID>_URL` secret (§4) |
| Mark a feed as Chinese | `"lang": "zh"` on the source |
| Boost my topics | `interests.keywords` (+ `boost`) |
| Turn on AI enrichment | Secret `LLM_API_KEY` (§4a) |
| Add Today's Image | Secret `SMITHSONIAN_API_KEY` (+ `LLM_API_KEY`) (§4a) |
| Stop one source *now* | Variable `<UPPERCASED_SOURCE_ID>_ENABLED=0` |
| Different theme/language default | `site.json → theme` / `default_language` |
| Rename the site | `site.json → title` |

After hand-editing: `python scripts/validate_config.py`, then commit — the
next scheduled run picks it up (or `gh workflow run update.yml`).
