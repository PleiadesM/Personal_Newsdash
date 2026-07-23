# Data Contract — pipeline ⇄ frontend

[中文](DATA_CONTRACT.zh.md)

This is the single interface document between the Python pipeline
(`scripts/`) and the static frontend (`index.html` + `assets/js/`). If you
change anything here, change both sides and the tests in the same commit.

## Discovery: `data/manifest.json`

Always plaintext (it must be readable before login). Fetch it with
`cache: "no-store"` **and** a `?t=<Date.now()>` query param; fetch every
other data file as `<file>?v=<build_id>` — GitHub Pages' CDN caches for
~10 minutes and the rotating `build_id` defeats it deterministically.

```jsonc
{
  "schema_version": 1,
  "app": "personal-newsdash",
  "app_version": "0.1.0",
  "status": "ok",                      // "ok" | "awaiting_first_build" | "degraded"
  "generated_at": "2026-07-06T18:17:03Z",
  "build_id": "20260706T181703Z",
  "site": {
    "title": "Relevance", "subtitle": "",
    "languages": ["en", "zh"], "default_language": "en",
    "theme": "the-type",               // "the-type" | "nyt" | "bear"
    "timezone": "America/Chicago",
    "visibility": "public",            // "public" | "private"
    "ranking": {                       // homepage Highlights knobs; absent on manifests built before this key
      "highlights": true,              // show the mixed Highlights block
      "max_per_source": 2              // per-source diversity cap (int ≥ 1)
    }
  },
  "crypto": {                          // present iff a passphrase is configured
    "alg": "AES-256-GCM",
    "kdf": { "name": "PBKDF2", "hash": "SHA-256",
             "iterations": 600000, "salt": "<b64 16B>" },
    "check": { "aad": "newsdash:v1:check",
               "nonce": "<b64 12B>", "ct": "<b64>" }
  },
  "sections": [
    { "id": "news", "kind": "news", "category": "open",
      "file": "news.json", "encrypted": false, "count": 142, "status": "ok" },
    { "id": "papers", "kind": "papers", "category": "optional",
      "file": "papers.json", "encrypted": false, "count": 37, "status": "ok" },
    { "id": "ai", "kind": "news", "category": "open",           // custom section with metadata
      "file": "ai.json", "encrypted": false, "count": 12, "status": "ok",
      "label": { "en": "AI", "zh": "AI 前沿" } }                 // optional; present iff config gave one
  ],
  "source_status_file": "source-status.json",
  "insights_file": "insights.json",       // AI brief/summaries/image/apropos; null if absent
  "threads_file": "threads.json",         // public Threads · 线索; null if absent/disabled
  "threads_private_file": null,           // private-scope Threads (opt-in); null if absent
  "ai_summary": { "enabled": true }        // was LLM_API_KEY configured this run?
}
```

Rules:

- `status: "awaiting_first_build"` → the pipeline has never run; render the
  onboarding screen (enable Actions / Pages instructions).
- Section `status`: `ok` | `degraded` (some sources failed) | `error` (all
  active sources failed) | `not_configured` (secrets absent → render a
  bilingual setup-hint card; `file` is `null`).
- Encrypted sections omit `count` and carry no display detail — everything
  descriptive lives inside the encrypted payload's `meta`.
- `visibility: "private"` → every section (plus `source_status_file` and the
  archive) is encrypted and the app boots to a full-page login gate.
- `site.ranking` drives the homepage **Highlights** block. When it is absent
  (older manifest) or `highlights` is `false`, the frontend renders no
  Highlights block at all; otherwise it pools loaded `news`/`papers`-kind
  sections, caps each source at `max_per_source` (min 1, default 2), shows ≤ 10
  items, and still hides itself if fewer than 3 survive.
- A section entry's optional `label: {en?, zh?}` (from `config/site.json`'s
  `sections[]`) is the friendly nav-tab name. The frontend resolves the display
  name `label[activeLang] → label.en → label.zh`, and — when no usable `label`
  is present — falls back to the i18n key `nav.<id>`, then the raw id. Labels
  are public plaintext, emitted even on private sites (readable before login),
  so they must never carry private detail.
- A section's `kind` may be overridden by `sections[]` metadata for **custom
  sections only** (the config layer rejects a `kind` override on the built-ins
  `news`/`papers`/`following`/`private`). Section entries are ordered by their
  metadata `order` (stable sort; entries without `order` follow the ordered
  ones in config order).
- `id: "private"` is a first-class `kind: "news"` section fed by
  `category: "private"` sources (see `docs/CONFIG_REFERENCE.md`'s "Private
  URL sources"). It appears in `sections[]` only once at least one private
  source is configured, and — regardless of the site's own
  `visibility` — is **always** `encrypted: true` and omits `count` exactly
  like any other encrypted section; a public site with a private feed
  configured still ships that one section as ciphertext behind the same
  login gate.

## Encryption envelope (`*.enc.json`)

One JSON object per file:

```jsonc
{ "v": 1, "alg": "AES-256-GCM",
  "kdf": { "name": "PBKDF2", "hash": "SHA-256",
           "iterations": 600000, "salt": "<b64 16B>" },
  "aad": "newsdash:v1:<section_id>",
  "nonce": "<b64 12B>",
  "ct": "<b64: ciphertext || 16B GCM tag>" }
```

- Key = PBKDF2-HMAC-SHA256(NFC-normalized passphrase, salt, 600 000 iters,
  32 bytes). **Normalize the passphrase with `.normalize("NFC")` before
  encoding** — Python does the same, and CJK/composed-accent passphrases
  break across platforms otherwise.
- One salt (and thus one derived key) per pipeline run; every file gets a
  fresh random nonce. Derive once per session, decrypt N files.
- The AAD binds a ciphertext to what you are loading: section files use
  `newsdash:v1:` + section id, source status uses `newsdash:v1:source-status`,
  insights uses `newsdash:v1:insights`, public Threads uses
  `newsdash:v1:threads`, private-scope Threads uses
  `newsdash:v1:threads-private`, and full-text article files use
  `newsdash:v1:article:<section_id>:<item_id>`. Compute this locally; do not
  trust the envelope's `aad` field (it is informational). (Envelope
  parameters themselves are unchanged by Threads — no `v` bump.)
- Verify the passphrase against `manifest.crypto.check` (plaintext is the
  ASCII string `newsdash:ok`, AAD `newsdash:v1:check`) *before* downloading
  data files — instant wrong-passphrase UX.

Reference decrypt (this exact code is tested in
`tests/test_crypto_webcrypto.mjs` against a Python-encrypted vector):

```js
const te = new TextEncoder();
const km = await crypto.subtle.importKey(
  "raw", te.encode(passphrase.normalize("NFC")), { name: "PBKDF2" }, false, ["deriveKey"]);
const key = await crypto.subtle.deriveKey(
  { name: "PBKDF2", salt: b64d(env.kdf.salt), iterations: env.kdf.iterations, hash: "SHA-256" },
  km, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
const pt = await crypto.subtle.decrypt(
  { name: "AES-GCM", iv: b64d(env.nonce), additionalData: te.encode(`newsdash:v1:${sectionId}`) },
  key, b64d(env.ct));
```

Do not change any parameter without bumping `v` and updating
`scripts/newsdash/crypto.py`, `assets/js/crypto.js`, this file, and both
crypto tests together.

## Section payloads

### `news` / `papers` (kind: news, papers)

```jsonc
{
  "meta": { "generated_at": "…Z", "section": "news", "kind": "news",
            "window_hours": 24, "count": 142,
            "sources": [ { "id": "openai_blog", "name": "OpenAI News",
                           "category": "open", "section": "news", "type": "rss",
                           "ok": true, "count": 3, "error": null,
                           "skip_reason": null } ] },
  "items": [ {
    "id": "a1b2c3d4e5f60708",          // sha1_16 of DOI > arXiv id > canonical URL
    "title": "…", "url": "https://…",
    "source": "OpenAI News", "source_id": "openai_blog",
    "category": "open", "section": "news", "kind": "news",
    "published_at": "2026-07-06T12:34:00Z",
    "summary": "plaintext, ≤300 chars",
    "full_text_available": true,          // present only when RSS/Atom embedded content qualified
    "full_text_file": "articles/news/a1b2c3d4e5f60708.json",
    "tags": ["model-release"], "lang": "en", "score": 0.73,
    "extra": { "also_in": [ { "source": "…", "url": "…" } ] }
  } ]
}
```

Papers additionally carry `"authors": ["…"]` (≤6), `"venue": "arXiv cs.HC"`,
and `extra.doi` / `extra.arxiv_id` / `extra.abstract_snippet`. When the
upstream API reports a citation count, papers also carry
`extra.citations` (int ≥ 0); its presence switches the item to the
citation-aware score blend (see `scripts/newsdash/scoring.py`) and the
frontend renders a citations badge. Items are sorted `published_at`
descending, capped at 300 per section.

The `following` section (scholars/labs tracking) is `kind: "papers"` and
uses this same payload shape; the frontend groups it by source by default.

`item.lang` is `"zh"` or `"en"`: forced by the source's config `lang` when
declared, else detected per item. The frontend treats the active UI language
as the content language for `news`, `papers`, `following`, Today feed blocks,
and the full-text reader: English mode renders only `lang: "en"` items;
Chinese mode renders only `lang: "zh"` items.

RSS/Atom entries that include substantial embedded full content (for example
Atom `content` or RSS `content:encoded`) additionally carry
`full_text_available: true` and `full_text_file`. The pipeline stores only
sanitized plaintext, never upstream HTML, and never fetches article pages for
this v1 reader. `full_text_file` points to a generated sibling under
`data/articles/<section>/<item_id>.json` when plaintext, or `.enc.json` when
`visibility: "private"`.

Full-text article files are loaded on demand by `#/read/<section>/<item_id>`:

```jsonc
{
  "meta": { "generated_at": "…Z", "section": "news",
            "item_id": "a1b2c3d4e5f60708",
            "source": "OpenAI News", "source_id": "openai_blog" },
  "item": { /* same summary item shape, including full_text_file */ },
  "full_text": "sanitized plaintext body, capped at 50,000 chars"
}
```

In private visibility the article payload uses the same envelope parameters
as other encrypted files, with AAD
`newsdash:v1:article:<section_id>:<item_id>`. Article files are per-build
generated data; the rolling archive deliberately strips `full_text_available`
and `full_text_file` so it cannot point at stale article files.

### `source-status.json` / `archive.json`

`source-status`: `{ generated_at, sources: [entry…], private_summary:
{ total, configured } }` — private sources appear **only** in the aggregate
here (never a per-source entry, never a name, count, or error for a private
source); their detail rides inside the encrypted `private` section's own
`meta`. Public source
entries include `full_text_count` (integer, usually `0`) for the current
build, so the frontend can mark sources that produced at least one embedded
full-text RSS item.
`archive`: `{ meta: { generated_at, days, count }, items: [item…] }` —
open + optional items only, rolling `archive_days`, capped at 3000. Archive
items are summary-only and omit `full_text_available` / `full_text_file`.

### `insights.json` / `insights.enc.json` — optional AI enrichment

Not a manifest *section* (see `manifest.insights_file` above) — a sibling
file so it never gets an automatic nav tab. Absent (`insights_file: null`)
unless `LLM_API_KEY` is configured; even then it may legitimately be absent
on a given run (nothing to summarize yet, or a transient upstream failure —
distinguish "configured" (`manifest.ai_summary.enabled`) from "has content
this run" (`insights_file` non-null)). Built only from `news`/`papers`
items — never full-text article bodies. Follows
`encrypt_all` exactly like any other section.

```jsonc
{
  "meta": { "generated_at": "…Z" },       // omitted inside the encrypted envelope's plaintext; see below
  "summaries": {
    "en": {
      "brief": "1-3 English sentences across news + papers",
      "news_summary": "1-2 English sentences on today's news",
      "papers_summary": "1-2 English sentences on today's papers"
    },
    "zh": {
      "brief": "1-3 Chinese sentences across news + papers",
      "news_summary": "1-2 Chinese sentences on today's news",
      "papers_summary": "1-2 Chinese sentences on today's papers"
    }
  },
  "brief": "English/default compatibility copy of summaries.en.brief",
  "news_summary": "English/default compatibility copy of summaries.en.news_summary",
  "papers_summary": "English/default compatibility copy of summaries.en.papers_summary",
  "todays_image": {                        // omitted entirely if no CC0 image was found this run
    "image_url": "https://ids.si.edu/…",
    "thumbnail_url": "https://ids.si.edu/…",
    "title": "Automaton Clock",
    "source_name": "Cooper Hewitt, Smithsonian Design Museum",
    "source_url": "https://www.si.edu/object/…",
    "caption": "One AI-generated sentence connecting the image to today's top story"
  },
  "apropos_of_nothing": {                  // omitted if no off-profile item was found this run
    "topic": "competitive pumpkin growing",
    "query": "(\"pumpkin championship\" OR \"giant pumpkin\")",
    "summaries": {
      "en": {
        "summary": "One short AI summary of the chosen irrelevant item.",
        "why_irrelevant": "One short note on why this is outside the feed."
      },
      "zh": {
        "summary": "One short Simplified Chinese summary.",
        "why_irrelevant": "One short Simplified Chinese note."
      }
    },
    "source": {
      "title": "Giant pumpkin champion breaks local record",
      "url": "https://example.org/pumpkin",
      "name": "example.org",
      "published_at": "2026-07-08T10:00:00Z"
    }
  }
}
```

The LLM generates `summaries.en` and `summaries.zh` as separate calls. Each
call reads both English and Chinese `news`/`papers` items, but prioritizes
the target language's items and writes in that target language. The frontend
selects `summaries[active_language]`; the top-level scalar fields are kept as
an English/default fallback for older cached clients.

All summary/image-caption text fields are content, not chrome — rendered raw,
never passed through `i18n.js`'s `t()`. `todays_image` only ever carries an
image with an explicit Smithsonian
`usage.access: "CC0"` media entry (`scripts/newsdash/todays_image.py`) —
rights-uncertain results are never surfaced.

`apropos_of_nothing` is a build-time echo-chamber break. The configured LLM
first sees only `news`/`papers` titles and short summaries and proposes
benign off-profile search terms. The pipeline then searches public news via
the GDELT DOC API (`mode=artlist`, `format=json`, one week), and the LLM
writes a short bilingual card for one sourced result. If GDELT is rate-limited
or no sourced result is available, the field is omitted for that build. No
visitor browser ever contacts GDELT or the LLM endpoint for this block.

### `threads.json` / `threads.enc.json` / `threads-private.enc.json` — optional AI enrichment

Not a manifest *section* — sibling files pointed to by `manifest.threads_file`
/ `manifest.threads_private_file` (see above), so neither gets an automatic
nav tab. **Threads · 线索** replaces the client-computed Highlights block with
an LLM-generated set of keyword-themes that at least two different sources
touched today, each with a bilingual gloss, a "why now" occasion line, a
convergence verdict, and per-source angles that link back to ground-truth
items. Built only when `site.json → threads.enabled` (default `true`) and
`LLM_API_KEY` is configured; never runs during `--smoke`; one bilingual LLM
call per scope.

Two fully separated scopes:

- **public** — input is `open`/`optional`-category sections only. Written as
  `threads.json` or, when `visibility: "private"`, `threads.enc.json` (AAD
  `newsdash:v1:threads`).
- **private** — opt-in via `threads.include_private` (default `false`);
  input is `category: "private"` sections only. Always written encrypted,
  regardless of site visibility, as `threads-private.enc.json` (AAD
  `newsdash:v1:threads-private`) — there is no plaintext variant. Runs only
  when `include_private`, a passphrase, and `LLM_API_KEY` are all present.

```jsonc
{
  "meta": { "generated_at": "…Z", "scope": "public", "count": 5 },
  "threads": [ {
      "id": "t1",                           // "t1"…"tN" (public) or "p1"…"pN" (private) — never collide
      "keyword": { "en": "compute sovereignty", "zh": "算力主权" },
      "gloss":   { "en": "1–2 light sentences, may be poetic", "zh": "…" },   // ≤240 chars/lang
      "why_now": { "en": "one-line occasion note", "zh": "…" },               // ≤120 chars/lang
      "convergence": "convergent",          // "convergent" | "mixed" | "divergent" (invalid model output coerced to "mixed")
      "relates_to": ["t3"],                 // other thread ids from this same build; may be []
      "angles": [ {                         // ≥2 entries, resolved against ≥2 distinct sources
          "item_id": "…", "section": "news", "source": "…",
          "phrase": { "en": "≤8 words", "zh": "≤16 characters" },
          "url": "https://…",
          "full_text_file": "articles/news/….json"   // present iff the resolved item has an in-app reader file
      } ]
  } ]
}
```

The private variant is identical in shape with `"scope": "private"` and
thread ids `p1…pN`.

**Anti-hallucination referencing:** the prompt numbers pooled items
`[1]…[N]`; the model returns angles as integer refs; the pipeline resolves
every ref against ground truth and fills in `item_id`, `section`, `source`,
`url`, `full_text_file` itself — the model never supplies these directly.
Out-of-range refs are dropped, and a thread whose surviving angles resolve to
fewer than 2 distinct sources is dropped entirely (never trusted from the
model). Threads are capped at `threads.max_threads` (2–6, default 6).

**Frontend fallback rule:** Threads replaces Highlights. When
`threads_file` is `null`, the file fails to load, or the loaded payload has
no threads, the frontend renders the existing Highlights block per
`site.ranking` instead.

## Privacy invariants (frontend must uphold)

1. Never write decrypted content or the passphrase to storage. The derived
   key bytes may be persisted only behind the explicit "remember on this
   device" opt-in.
2. Annotations UI (highlight/excerpt/note, Clippings) and the Favorites UI
   (stars, Favorites view) render only while unlocked (`manifest.crypto`
   present + successful check-block decrypt). Both live in local storage
   (IndexedDB `newsdash` db: `annotations` + `favorites` stores) and never
   leave the device.
3. Locking wipes the in-memory key, any remembered key, and all decrypted
   section data, then re-renders.
4. The numeric overview strip is computed client-side from already-loaded
   sections — private counts must never be added to plaintext files for it.
5. The AI daily brief, Today's Image, and Apropos-of-Nothing are build-time enrichment, not
   runtime calls — no visitor's browser ever contacts the LLM endpoint.
   Today's Image *is* hotlinked from Smithsonian's CDN at view time
   (`referrerpolicy="no-referrer"`); the AI-generated text has no runtime
   third-party contact at all, baked fully into `insights.json`/`.enc.json`
   at build time.
6. Private-scope Threads render only while unlocked (`manifest.crypto`
   present + successful check-block decrypt) — the same gate as any other
   encrypted section. Public Threads are built exclusively from
   non-private-category input and never derive from private-section data,
   even when a private section is active on the same site.
7. Thread `angles` are deliberately exempt from the content-language filter
   applied elsewhere to `news`/`papers`/`following`/Today feed blocks —
   cross-language convergence (a theme two sources touch in different
   languages) is the point of the feature. Do not "fix" this by filtering
   angles to the active UI language.
