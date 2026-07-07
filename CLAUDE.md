# CLAUDE.md

Personal Newsdash: serverless news · schedule · research dashboard template —
Python pipeline on Actions cron → static JSON in `data/` → vanilla-JS site on
GitHub Pages. Private sections are AES-256-GCM encrypted; the passphrase is the login.

## First reads

- `README.md` — product + architecture overview
- `skills/newsdash/SKILL.md` — the Page Skill｜书童Skill (maintainer workflows; follow it for any source/config/secrets task)
- `docs/DATA_CONTRACT.md` — pipeline ⇄ frontend interface (manifest, payload schemas, crypto envelope)
- `docs/CONFIG_REFERENCE.md` — every config key; "change X → edit Y"

## Validate

```bash
python -m pytest -q                                    # unit tests (offline)
python scripts/validate_config.py                      # config schema + semantics
python scripts/build.py --output-dir /tmp/nd --smoke   # no-network end-to-end
node tests/test_crypto_webcrypto.mjs                   # crypto envelope cross-check
```

## Hard rules

- Never commit or log: the passphrase, tokens, ICS URLs (they are credentials),
  decoded `ICS_SOURCES_B64`, or decrypted private payloads. Actions logs on
  public repos are public — never print private counts/titles/details.
- Never weaken crypto parameters (`scripts/newsdash/crypto.py`) or add a
  plaintext fallback for private sections. The envelope is pinned by
  `tests/test_crypto_webcrypto.mjs`.
- Never remove the owner guard in `.github/workflows/setup-from-issue.yml`,
  nor the schema rule forbidding `url`/`path` on private sources.
- Keep the zero-secret build green: new sources must skip cleanly when their
  secrets are absent (`enabled: "auto"` + `secret_ref`).
- `data/` is bot-owned output — don't hand-edit it.
