# Data Contract — pipeline ⇄ frontend

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
    "title": "Personal Newsdash", "subtitle": "",
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
  "source_status_file": "source-status.json"
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
- The AAD binds a ciphertext to its section id: compute it from the section
  you are loading (`newsdash:v1:` + section id), do not trust the envelope's
  `aad` field (it is informational).
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
    "tags": ["model-release"], "lang": "en", "score": 0.73,
    "extra": { "also_in": [ { "source": "…", "url": "…" } ] }
  } ]
}
```

Papers additionally carry `"authors": ["…"]` (≤6), `"venue": "arXiv cs.HC"`,
and `extra.doi` / `extra.arxiv_id` / `extra.abstract_snippet`. Items are
sorted `published_at` descending, capped at 300 per section.

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
here; their detail rides inside the encrypted section metas.
`archive`: `{ meta: { generated_at, days, count }, items: [item…] }` —
open + optional items only, rolling `archive_days`, capped at 3000.

## Privacy invariants (frontend must uphold)

1. Never write decrypted content or the passphrase to storage. The derived
   key bytes may be persisted only behind the explicit "remember on this
   device" opt-in.
2. Annotations UI (highlight/excerpt/note, Clippings) renders only while
   unlocked (`manifest.crypto` present + successful check-block decrypt).
3. Locking wipes the in-memory key, any remembered key, and all decrypted
   section data, then re-renders.
