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

Every source: unique snake_case `id`, human `name`, `section`
(`news`/`papers`/`following`/`private`), `weight` 0–1 (feeds the 0.20 score
term), `max_results`. New source of unknown quality → `weight: 0.5`, watch
`source-status.json` for a week, then promote or drop (伯乐 discipline).

Disable or reweight a preset source without copying the pack: add
`{"id": "<same-id>", "enabled": false}` (or `"weight": 0.3`) to `sources[]`.

## Discovery recipes

When the user brings a **topic, a page, or an OPML** instead of a feed URL,
find and vet the feed before writing config. **Rule: `dupcheck` before every
add** — a duplicate host/ISSN/id silently double-weights a source.

### `scripts/discover_source.py`

```bash
# Probe an HTML page: RSS autodiscovery (+ common feed paths), health &
# freshness check. Prints a ready config snippet with a recommended weight.
python scripts/discover_source.py probe https://example.org/blog
```

Expected output: a JSON/config snippet for the discovered feed, with `weight`
set from freshness — **≥ 1 item/week → `0.8`, sparser → `0.5`**. Paste it into
`config/sources.json` (after `dupcheck`), then `validate_config.py`.

```bash
# Expand an OPML export: list its feeds, drop any already in the merged
# config, emit a snippet for each genuinely new feed.
python scripts/discover_source.py probe --opml ~/Downloads/subscriptions.opml
```

```bash
# Overlap check against the merged config (same host, same ISSN, id collision).
python scripts/discover_source.py dupcheck https://example.org/feed.xml
python scripts/discover_source.py dupcheck 1234-5678
```

**Safety behaviour — capability URLs.** `probe` **refuses** a top-level URL
that looks like a capability link with **exit code `3`** and a "classify as
private, do not probe" message. It also gates **every candidate it discovers**
— autodiscovered `<link>` feeds and every OPML `xmlUrl` — *before* fetching or
printing them: a tripped candidate is **dropped and reported by title** (or
`untitled #<n>`) with the same message, and its URL/token is **never echoed**
to stdout or stderr. That is not an error to work around: such a source is
`category: "private"` — switch to the private-source protocol (config entry +
`SRC_<ID>_URL` secret, see `SKILL.md` → Manage sources and
`secrets-setup.md`). Never re-run `probe` on such a URL, and never paste its
value anywhere.

The heuristic lives in module-level constants in `scripts/discover_source.py`
(`CAPABILITY_QUERY_PARAMS`, `CAPABILITY_QUERY_PARAM_PREFIXES`,
`CAPABILITY_PATH_MARKERS`, `CAPABILITY_OPAQUE_TOKEN`, `CAPABILITY_HOST_MARKERS`,
`CAPABILITY_HOST_SUFFIXES`, `CAPABILITY_HOST_PATTERNS`). It flags: secret-ish
query-param **names** (substring match: token/key/secret/sig/signature/auth/
hmac/credential, plus any `x-amz-*` presigned param); opaque **values** in
query strings and the URL **fragment** (≥16 base64url chars), incl.
`#access_token=…`; **userinfo** (`user:pass@…`); **JWTs** (`eyJ…` or dotted
base64url); long opaque **path segments** (≥16 chars with a digit or mixed
case — plain lowercase slugs are allowed); and capability **hosts** (Google/
Outlook/iCloud/Fastmail calendars, `*.slack.com` webhooks, presigned S3). A
plain YouTube feed (`?channel_id=UC…`) is **allowlisted** on `youtube.com`
because that id is public, not a secret.

### Scholarly-ID lookups (for `openalex` / `crossref` / `arxiv` entries)

These are public, keyless GET requests you can run to fill in a source's
`filter` / `query` / `issn` correctly.

**OpenAlex — follow an author.** Resolve the person to their `A…` id, then use
it in an `authorships.author.id:` filter:

```bash
curl -s 'https://api.openalex.org/authors?search=Jane%20Doe' | python3 -m json.tool
# → pick the right result's "id": ".../A5023888391"
#   config: { "type": "openalex", "section": "following",
#             "filter": "authorships.author.id:A5023888391" }
```

**OpenAlex — follow a venue/journal.** Resolve the source to its `S…` id, then
filter on `primary_location.source.id:`:

```bash
curl -s 'https://api.openalex.org/sources?search=Nature%20Communications' | python3 -m json.tool
# → "id": ".../S…"   config filter: primary_location.source.id:S…
```

**Crossref — verify a journal registers before adding it.** A `crossref`
source is only worth adding if the ISSN actually resolves:

```bash
curl -s 'https://api.crossref.org/journals/1234-5678' | python3 -m json.tool
# 200 with a "message.title" → registered; 404 → don't add it as crossref
```

Join the polite pool by setting the `CONTACT_MAILTO` variable (see
`secrets-setup.md`) — it makes CrossRef/OpenAlex faster and more reliable.

**arXiv — category + author queries.** `arxiv` sources take a `query` in the
arXiv search syntax: `cat:cs.CL` (one category), `cat:cs.HC OR cat:cs.GR`
(several), `au:"Jane Doe"` (author), or a combination. The full category
taxonomy (all the `cs.*`, `stat.*`, `eess.*`, etc. codes) is at
<https://arxiv.org/category_taxonomy>. arXiv is quiet on weekends — an empty
build then is not a failure.
