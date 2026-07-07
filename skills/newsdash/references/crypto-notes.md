# Crypto notes (operational summary)

Source of truth: `docs/DATA_CONTRACT.md` (envelope + manifest contract) and
`scripts/newsdash/crypto.py` (implementation). This page is the checklist.

## The envelope (do not change without bumping `v`)

- AES-256-GCM; key = PBKDF2-HMAC-SHA256(**NFC-normalized** passphrase,
  16-byte salt, **600 000** iterations, 32 bytes).
- One salt (⇒ one derived key) per pipeline run; fresh random 12-byte nonce
  per file; GCM tag appended to ciphertext (WebCrypto convention).
- AAD binds each file to its section: `newsdash:v1:<section_id>` — computed
  by the reader from the section being loaded, never trusted from the file.
- Manifest `crypto.check` block: `"newsdash:ok"` encrypted under AAD
  `newsdash:v1:check` → instant wrong-passphrase UX before downloading data.
- Any parameter change requires, in ONE commit: `scripts/newsdash/crypto.py`,
  `assets/js/crypto.js`, `docs/DATA_CONTRACT.md`, `tests/test_crypto.py`,
  and a regenerated `tests/fixtures/crypto-vector.json` — then
  `node tests/test_crypto_webcrypto.mjs` must pass. If it fails, stop.

## Never log / never commit

- The passphrase (only ever in the `NEWSDASH_PASSPHRASE` env/secret).
- Decrypted payloads — not in CI logs, PR bodies, issue comments, or files.
  `scripts/encrypt_tool.py decrypt` is for the user's own terminal only.
- ICS URLs and the decoded `ICS_SOURCES_B64` JSON (in-process only).
- Private-source error detail: reduce to exception class names
  (requests errors embed URLs — see `scripts/newsdash/status.py`).

## Invariants to preserve when editing the pipeline

- `visibility: "private"` + missing passphrase ⇒ **build fails loudly**
  (never silently publish plaintext).
- Private sources configured + missing passphrase ⇒ build fails loudly.
- `schedule`/`courses` payloads must never exist as plaintext files —
  CI's guard job greps for exactly that.
- The archive only ever contains open + optional items.
- Build logs never print private counts, titles, or calendar names.
