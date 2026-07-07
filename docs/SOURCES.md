# Sources — taxonomy, presets, and curation

[中文](SOURCES.zh.md) · Config syntax: [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) · Secrets recipes: [SETUP.md](SETUP.md)

## 1. Three categories, one rule

| Category | Definition | Where its coordinates live |
|---|---|---|
| **Open** | Anyone could fetch it; no credentials | `url` in config — safe to commit |
| **Optional** | Keyless scholarly APIs (rate-limited, not secret) | `query`/`issn` in config |
| **Private** | Fetching requires a capability URL or token | **GitHub Secrets only** — the schema rejects a `url` on private sources |

The rule: *if possessing the address grants access, the address is a
credential and never enters the repo.* Google's "secret iCal address" is the
canonical example.

## 2. Shipped presets

**`ai-news`** (open → news): OpenAI News 1.0 · Google AI Blog 1.0 · DeepMind
Blog 1.0 · Hugging Face Blog 0.9 · Simon Willison 0.9 · MIT Tech Review AI
0.85 · The Verge AI 0.8 · Ars Technica AI 0.8 · Hacker News frontpage 0.7
(keyword-filtered: AI/LLM/GPT/Claude/Gemini/model/agent/machine learning/neural).

**`general-news`** (open → news): BBC World 1.0 · NYT Homepage 1.0 · Guardian
World 0.9 · NPR News 0.9 · BBC 中文 0.8.

**`academic-datavis`** (optional → papers): arXiv `cat:cs.HC OR cat:cs.GR`
1.0 (keyword-filtered to visualization terms) · OpenAlex "information
visualization" 0.9 · Semantic Scholar "data visualization" 0.8.

**`academic-techcomm`** (optional → papers): CrossRef ISSN tracking 1.0 —
*Technical Communication Quarterly* (1057-2252), *J. of Business & Technical
Communication* (1050-6519), *IEEE Trans. Professional Communication*
(0361-1434), *J. of Technical Writing & Communication* (0047-2816), *Written
Communication* (0741-0883) · OpenAlex "technical communication" 0.9 · arXiv
cs.HC writing/docs keywords 0.8.

Academic packs ship **off** by default — tick them in the setup issue or add
them to `presets`.

## 3. Adding a source (copy-paste recipes)

**RSS/Atom** — first choice for anything with a feed:

```json
{ "id": "my_lab_blog", "type": "rss", "section": "news",
  "name": "My Lab Blog", "url": "https://lab.example.edu/feed.xml", "weight": 0.9 }
```

Firehose? Add a title filter: `"keywords": ["visualization", "accessibility"]`.

**OPML** — a whole subscription list. Committed file
(`"path": "feeds/follow.opml"`) or private via the `FOLLOW_OPML_B64` secret
(decoded at build time, never committed).

**feed-json** — another project's public generated feed (a pattern borrowed
from ai-news-radar: consume their output, don't rebuild their crawler):

```json
{ "id": "their_project", "type": "feed-json", "section": "news",
  "name": "Their Radar", "url": "https://raw.githubusercontent.com/them/repo/main/feed.json" }
```

**static-page** — last resort for feedless pages. `query` is a CSS selector
for the links to harvest. Caveat: pages carry no timestamps, so items are
stamped with build time and stay "fresh" while listed.

```json
{ "id": "dept_news", "type": "static-page", "section": "news",
  "name": "Dept news", "url": "https://dept.example.edu/news", "query": "h3 a" }
```

**arXiv** — category and field queries, e.g. `cat:cs.CL`,
`cat:cs.HC AND abs:accessibility`. Built-in 3 s throttle; weekends are quiet
by nature.

**CrossRef** — the journal-tracking workhorse (how `academic-techcomm`
follows journals that never touch arXiv). Recency = when the record was
*created* at CrossRef, which is what "new this week" means for journals:

```json
{ "id": "my_journals", "type": "crossref", "section": "papers",
  "name": "My journals", "issn": ["1057-2252", "0741-0883"], "max_results": 40 }
```

**OpenAlex** — reliable only with `OPENALEX_API_KEY` since their 2026 credits
change; keyless runs are best-effort (0 items when throttled).
**Semantic Scholar** — shared keyless pool, frequently 429s; best-effort by
design. Neither ever fails your build.

**ICS / Canvas** — private; config carries only `secret_ref`. The default
`config/sources.json` already has both entries wired to `ICS_SOURCES_B64` and
`CANVAS_BASE_URL`+`CANVAS_TOKEN`; they activate the moment the secrets exist.
Recipes: [SETUP.md §6–7](SETUP.md).

## 4. Curation discipline (the 伯乐 inheritance)

1. Prefer, in order: official feed → public generated feed → OPML → focused
   static fetcher → **skip**.
2. Judge signal density before adding. A source that posts 50×/day with 2
   items you care about deserves a keyword filter or no seat at all.
3. Probation: add unknown sources at `weight: 0.5`, watch `source-status.json`
   and your own reading behavior for a week, then promote, demote, or drop.
4. Dedupe is your friend: the same story from two sources merges (higher
   weight wins, `also_in` records the rest) — multi-source confirmation is
   visible, not noisy.

## 5. Scoring effects

`score = 0.45·recency + 0.35·interests + 0.20·weight` — so `weight`
separates trusted sources from probationers, and `interests.keywords`
(+ `boost`) lift your topics regardless of source. Tags come from each pack's
`tag_rules` and only apply to that pack's own sources.

## 6. Etiquette

The 2-hourly default cadence is polite to everyone. arXiv gets a built-in 3 s
inter-request delay; set the `CONTACT_MAILTO` variable to join CrossRef's and
OpenAlex's polite pools (better rate limits, and they can reach you instead
of blocking you).
