# Secrets setup recipes (narrate these — never handle values)

All secrets go to: `https://github.com/<owner>/<repo>/settings/secrets/actions/new`
Variables go to the *Variables* tab on the same page.

## NEWSDASH_PASSPHRASE

- Recommend ≥ 4 random words (e.g. diceware). It is both the encryption key
  source and the site login. There is **no recovery**: lost passphrase =
  private history in git stays sealed.
- Rotation: update the secret → `gh workflow run update.yml`. Old ciphertext
  remains in git history (see SECURITY_MODEL §rotation).

## ICS_SOURCES_B64 (personal schedule)

1. User copies `examples/ics-sources.example.json` to a **local, uncommitted**
   file and fills in real calendar URLs:
   - Google: *Calendar Settings → your calendar → "Secret address in iCal format"*
   - Outlook: *Settings → Calendar → Shared calendars → Publish a calendar → ICS*
   - Canvas: *Calendar → "Calendar feed" (bottom right)*
2. Encode **in their own terminal**:
   - macOS: `base64 -i ics-sources.json | tr -d '\n'`
   - Linux: `base64 -w0 ics-sources.json`
   - Windows PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("ics-sources.json"))`
3. Paste the output as the secret value; delete the local file afterwards.
4. Remind: these URLs are credentials. If one leaks, regenerate it at the
   provider (Google: "Reset" next to the secret address).

## CANVAS_BASE_URL + CANVAS_TOKEN (courses)

- Base URL: the school's Canvas origin, e.g. `https://canvas.iastate.edu` (no path).
- Token: *Canvas → Account → Settings → "+ New Access Token"*. Warn: tokens
  grant **full account access**; suggest an expiry date and rotating each
  semester.

## Optional

- `OPENALEX_API_KEY` (secret) — makes the OpenAlex fetcher reliable.
- `FOLLOW_OPML_B64` (secret) — base64 of a private OPML file.
- `CONTACT_MAILTO` (variable) — any email; joins CrossRef/OpenAlex polite pools.
- `ICS_CALENDARS_ENABLED=0` / `CANVAS_ENABLED=0` (variables) — emergency stops.

## Verify after each secret

```bash
gh workflow run update.yml && gh run watch
curl -s https://<owner>.github.io/<repo>/data/manifest.json | python3 -m json.tool
# the section's "status" flips from "not_configured" to "ok"
```

Sources with `enabled: "auto"` turn on the moment every env var in their
`secret_ref` exists — no config edit needed.
