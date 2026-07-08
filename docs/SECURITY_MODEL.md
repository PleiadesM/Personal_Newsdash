# Security Model

[中文](SECURITY_MODEL.zh.md) · Implementation: `scripts/newsdash/crypto.py` · Contract: [DATA_CONTRACT.md](DATA_CONTRACT.md)

> **TL;DR — what you get and what you don't**
>
> Protected: the **contents** of private sections (schedule, courses — and
> everything, in private mode) and your annotations' visibility.
> Not protected: **metadata** — file sizes, update cadence, commit times, and
> *whether* a section is configured.
>
> **A private site is an encrypted public site — not a private repo.**
> GitHub Pages is always publicly reachable on free plans; your privacy comes
> from cryptography, not from access control.

## 1. Encryption spec

Every `*.enc.json` file is one envelope:

```json
{ "v": 1, "alg": "AES-256-GCM",
  "kdf": { "name": "PBKDF2", "hash": "SHA-256", "iterations": 600000, "salt": "<b64 16B>" },
  "aad": "newsdash:v1:<section_id>", "nonce": "<b64 12B>",
  "ct": "<b64 ciphertext||16B GCM tag>" }
```

- Key = PBKDF2-HMAC-SHA256 over the **NFC-normalized** passphrase — CJK and
  composed-accent passphrases derive identically on every platform.
- One salt (⇒ one key derivation, ~0.5 s) per pipeline run; a fresh random
  nonce per file — AES-GCM's intended usage.
- The AAD binds ciphertext to its section id: `courses.enc.json` content can
  never be served to the reader as `schedule`.
- `manifest.crypto.check` holds `"newsdash:ok"` encrypted under
  `newsdash:v1:check`, so the browser can verify a passphrase in under a
  second *before* downloading data. It gives an attacker nothing a data file
  wouldn't (same KDF cost per guess).
- The format is pinned by a cross-language test: Node's WebCrypto decrypts a
  Python-encrypted vector in CI (`tests/test_crypto_webcrypto.mjs`).

## 2. Threat analysis

| Adversary | Outcome |
|---|---|
| Casual visitor / search crawler on your Pages URL | Sees open sections (public mode) or a login gate (private mode); private payloads are ciphertext |
| Someone who clones the repo | Same — ciphertext plus git history of ciphertext |
| **Offline brute-force against your passphrase** | **The real threat.** Ciphertext is public; PBKDF2-600k makes each guess ~0.3 s on commodity hardware, but that only *slows* a dictionary attack. A weak passphrase ("hunter2") falls; ≥ 4 random words (≈ 50+ bits) does not. This is the single most important user decision |
| Drive-by setup issue on your public repo | The apply workflow runs **only** for issues authored by the repository owner; the body reaches the parser via env→file (no shell/template interpolation); a credential-pattern scanner rejects bodies that look like they contain secrets |
| Malicious PR | CI never exposes secrets to fork PRs (GitHub default); the guard job also greps for plaintext private files and token-like strings |
| Compromised Actions runner | Sees the secrets for that run — the same trust boundary as any CI system. Mitigation: scope-limited tokens (Canvas), rotation habits |
| XSS via a malicious feed | The frontend never renders feed content as HTML — a `textContent`-only DOM builder (`assets/js/dom.js`); item URLs are restricted to `http(s)` before becoming links |

## 3. What never leaves where

- **ICS calendar URLs are credentials** (capability URLs). They exist only
  inside the `ICS_SOURCES_B64` secret, are decoded in-process, and are never
  written to disk. Error reporting for private sources is reduced to
  exception **class names** — `requests` errors can echo full URLs.
- The Canvas token is sent per-request and never set on the shared HTTP
  session other fetchers reuse.
- Build logs print no private counts, titles, or calendar names — on a
  public repo, **Actions logs are public**.
- `source-status.json` shows private sources only as an aggregate
  (`configured n of m`); their detail rides inside the encrypted payloads.

### 3a. Optional AI enrichment egress (off by default)

Two distinct data flows, only present if you've added `LLM_API_KEY`
and/or `SMITHSONIAN_API_KEY` — see `docs/CONFIG_REFERENCE.md` §4a:

- **Build-time (server → LLM endpoint).** Once per scheduled build, the
  pipeline may send your `news`/`papers` items' **titles and short
  summaries only** to your configured LLM endpoint — never full item
  bodies, never schedule or courses content, never the passphrase. This is
  the *only* code path in the whole pipeline that calls out to a third
  party you don't control the identity of (every other fetcher targets a
  named, fixed API). The resulting text is baked into
  `insights.json`/`.enc.json` at build time; no visitor's browser ever
  contacts the LLM endpoint.
- **Runtime (visitor's browser → Smithsonian CDN).** If Today's Image
  renders, the `<img>` tag is hotlinked directly from Smithsonian's image
  CDN (`ids.si.edu`) — the **first** runtime third-party asset load this
  dashboard has ever made from a reader's browser (every other asset is
  served from your own Pages domain). Mitigated with
  `referrerpolicy="no-referrer"` on the tag, but the request itself
  (source IP, timing) is still visible to Smithsonian like any hotlinked
  image anywhere on the web.

Both features are off unless you explicitly add the relevant secret, and
both fail silently (skip, never crash the build) if the endpoint is
unreachable or misbehaves.

## 4. Browser side

- The derived key lives in memory. **"Remember on this device"** (opt-in)
  stores the derived key bytes — never the passphrase — in `localStorage`;
  anyone with that browser profile can then unlock. Skip it on shared machines.
- **Lock** wipes the in-memory key, the remembered key, and all decrypted
  section data, then re-renders.
- Annotations live in IndexedDB on your device and render only while
  unlocked. In v0.1 they are **unencrypted at rest locally** (your own
  browser profile); encrypted sync is a v0.2 item.

## 5. Rotation & incident recipes

| Situation | Do this |
|---|---|
| Rotate the passphrase | Update `NEWSDASH_PASSPHRASE` → run *Update Newsdash*. New ciphertext everywhere. **Git history still holds old ciphertext** decryptable by the old passphrase — either accept that or purge history (`git filter-repo --path data --invert-paths`, then force-push and re-run) |
| Canvas token leaked / semester ended | Canvas → Account → Settings → delete token, create a new one, update the secret |
| Google secret iCal URL leaked | Google Calendar settings → *Reset* the secret address, rebuild `ICS_SOURCES_B64` |
| You pasted a secret into an issue/chat/log | Treat it as leaked: rotate it now. The setup-issue scanner tries to catch this, but rotation is the only real fix |
| Lost passphrase | There is **no recovery**. Set a new one; future data re-encrypts; old ciphertext in history stays sealed forever |

## 6. Residual risks & non-goals

- Metadata leakage (sizes, cadence, configured sections) — accepted, documented.
- The Pages URL is guessable (`<user>.github.io/<repo>`); private mode shows
  a gate, not a 404.
- No key escrow or recovery, by design.
- No multi-user auth, roles, or sharing — this is a one-person dashboard.
  If you need real access control, GitHub Enterprise's access-controlled
  Pages or a private host is the tool.
