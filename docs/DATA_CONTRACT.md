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
    "visibility": "public"             // "public" | "private"
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
    { "id": "schedule", "kind": "schedule", "category": "private",
      "file": "schedule.enc.json", "encrypted": true, "status": "ok" }
  ],
  "source_status_file": "source-status.json",
  "insights_file": "insights.json",       // AI brief/summaries/image; null if absent
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
  insights uses `newsdash:v1:insights`, and full-text article files use
  `newsdash:v1:article:<section_id>:<item_id>`. Compute this locally; do not
  trust the envelope's `aad` field (it is informational).
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

### `schedule` (kind: schedule)

```jsonc
{
  "meta": { "generated_at": "…Z", "section": "schedule", "kind": "schedule",
            "timezone": "America/Chicago",
            "calendars": [ { "id": "gcal_personal", "name": "Personal",
                             "ok": true, "count": 12 } ],
            "sources": [ /* full private status detail lives here */ ] },
  "events": [ {
    "id": "…", "calendar_id": "gcal_personal", "calendar": "Personal",
    "title": "Advisor meeting",
    "start": "2026-07-07T14:00:00-05:00",   // ISO-8601 with site-tz offset
    "end": "2026-07-07T15:00:00-05:00",     // or null
    "all_day": false,                        // all-day: start/end are "YYYY-MM-DD"
    "location": "Ross 203", "url": null,
    "status": "confirmed", "recurring": true
  } ]
}
```

Events are RRULE-expanded occurrences within
`[today − schedule_past_days, today + schedule_horizon_days]`, sorted by
`start`.

### `courses` (kind: courses)

```jsonc
{
  "meta": { "generated_at": "…Z", "section": "courses", "kind": "courses",
            "sources": [ /* full private detail */ ] },
  "courses": [ {
    "id": 118234, "code": "ENGL 5920C", "name": "…", "url": "https://canvas…",
    "announcements": [ { "id": 99, "title": "…", "url": "…",
                         "posted_at": "2026-07-05T16:00:00Z",
                         "snippet": "plaintext ≤240 chars" } ],
    "upcoming": [ { "id": 555, "type": "assignment", "title": "…",
                    "due_at": "2026-07-10T04:59:00Z", "points_possible": 20,
                    "url": "…", "submitted": false } ]
  } ]
}
```

### `source-status.json` / `archive.json`

`source-status`: `{ generated_at, sources: [entry…], private_summary:
{ total, configured } }` — private sources appear **only** in the aggregate
here; their detail rides inside the encrypted section metas. Public source
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
items — never schedule/courses. Follows `encrypt_all` exactly like any
other section.

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
5. The AI daily brief and Today's Image are build-time enrichment, not
   runtime calls — no visitor's browser ever contacts the LLM endpoint.
   Today's Image *is* hotlinked from Smithsonian's CDN at view time
   (`referrerpolicy="no-referrer"`); the AI-generated text has no runtime
   third-party contact at all, baked fully into `insights.json`/`.enc.json`
   at build time.
