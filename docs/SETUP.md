# Setup Guide — from zero to your own Newsdash

This is the click-by-click walkthrough. No terminal required for the core path — everything happens in the GitHub web UI. If you get stuck at any step, jump to the [Troubleshooting table](#11-troubleshooting) at the bottom.

**Pick your pace:**

- **Fast lane (10 minutes, zero keys)** → do steps 1–4. You get a live news + papers dashboard with the default packs.
- **Full setup (add ~15 minutes)** → continue with steps 5–8 for private mode, your calendar, and Canvas courses.
- **Lazy lane** → do steps 1–3, then let AI drive steps 4–8 for you ([step 9](#9-let-ai-do-it-for-you)).

---

## 0. What you need

- A **GitHub account** (free is fine).
- About **10 minutes** for the first pass.
- **No API keys.** The default news and academic packs run entirely keyless. Keys and calendar URLs only enter the picture later, if you opt into private sections.

---

## 1. Create your copy

1. On this repository's page, click the green **Use this template** button → **Create a new repository**.
2. Name it whatever you like (e.g. `newsdash`).
3. **Keep it Public.** This matters, so here's why:
   - GitHub Pages hosting is **free only on public repos** — private repos need a paid plan for Pages.
   - Public repos get **unlimited free Actions minutes**; private repos get only 2,000 minutes/month.
   - Worried about privacy? Your privacy does **not** come from repo visibility — it comes from **encryption** ([step 5](#5-private-mode-and-the-passphrase)). Private sections are always encrypted before they're committed, so a public repo never exposes your schedule or courses.
4. Click **Create repository**.

## 2. First build

1. Open the **Actions** tab of your new repo. If you see a banner saying workflows are disabled, click **"I understand my workflows, go ahead and enable them"**.
2. In the left sidebar, click **Update Newsdash**.
3. Click **Run workflow** → **Run workflow** (green button, keep the `main` branch).
4. Wait for the run to go **green** (usually 1–3 minutes). This first build fetches the default news packs and commits the results to the `data/` folder.

After this, the build re-runs itself automatically every 2 hours — no further clicks needed.

## 3. Enable Pages

1. Go to **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Pick branch **`main`** and folder **`/ (root)`**, then **Save**.
4. Your site will be live at:

   ```
   https://<your-username>.github.io/<your-repo>/
   ```

The first deploy takes **1–5 minutes**. After that, each data refresh can lag up to **~10 minutes** behind the build — that's the GitHub Pages CDN cache, not a bug. The site busts the cache automatically on its next load.

> If the page shows an **"awaiting first build"** screen, the pipeline hasn't produced data yet — go back to step 2 and make sure "Update Newsdash" ran green.

## 4. Personalize via the setup issue

You never need to edit JSON by hand. The repo ships an issue form that a bot reads and applies.

1. Go to **Issues → New issue** and pick **"Set up my Newsdash · 配置我的新闻台"**.
2. Fill in the form:

   | Field | What it changes |
   |---|---|
   | **Interface language** | Default UI language, English or Chinese. Readers can still toggle anytime on the page. |
   | **Site visibility** | **Public** = news/papers readable by anyone, personal sections still encrypted. **Private** = the *entire* site is encrypted and opens with a passphrase gate — requires the `NEWSDASH_PASSPHRASE` secret ([step 5](#5-private-mode-and-the-passphrase)). |
   | **Theme** | `the-type` (typography-first serif), `nyt` (newspaper front page), or `bear` (minimal, auto dark mode). |
   | **Site title** | The masthead text (optional). |
   | **Timezone** | IANA name like `America/Chicago` or `Asia/Shanghai` — used for schedule display and day boundaries (optional). |
   | **Open news packs** | Tick **AI news** and/or **General news**. Tick nothing and the bot keeps both defaults. |
   | **Academic packs** | Tick **Data visualization** and/or **Technical communication** — keyless scholarly feeds ([step 8](#8-academic-packs)). |
   | **Extra RSS feeds** | One feed URL per line; each becomes a source in your news section. |
   | **Interest keywords** | Comma-separated; items matching these rank higher in your feed. |
   | **Acknowledgement** | Required checkbox: secrets never go in the issue. |

3. **Submit.** The bot then:
   - updates `config/site.json` and `config/sources.json` and commits the change,
   - triggers a rebuild,
   - **comments back** with your next steps (your Pages URL, a secrets checklist with deep links, and the AI kickoff prompt),
   - **closes the issue** when everything applied cleanly.
4. Made a typo or changed your mind? **Edit the issue body** — the bot re-runs on every edit, even after it's closed.

> ⚠️ **Never paste secrets into the issue** — no passphrase, no calendar URLs, no Canvas tokens. The bot actively scans for credential-looking strings and refuses to apply anything if it finds one. Secrets go in **Settings → Secrets and variables → Actions** (next step). Also note: only issues opened by the **repository owner** are applied — other people's issues on your repo are ignored by design.

## 5. Private mode and the passphrase

One secret turns on encryption for everything personal:

1. Go to **Settings → Secrets and variables → Actions → New repository secret**.
2. Name: `NEWSDASH_PASSPHRASE`
3. Value: **at least 4 random words**, e.g. `maple lantern crater bicycle`. Because the encrypted files are publicly downloadable, a weak passphrase can be brute-forced offline — length beats cleverness here.
4. Click **Add secret**, then re-run **Update Newsdash** (Actions tab) so the new passphrase takes effect.

Things to know:

- **The passphrase is also your login.** When you open your site, entering this passphrase in the browser is what unlocks the encrypted sections. There is no separate account.
- With `visibility: public`, your news/papers stay readable by anyone, while schedule and courses are always encrypted. With `visibility: private`, *every* section is encrypted and the site boots straight to a passphrase gate.
- **Changing the passphrase**: update the secret's value and re-run the workflow — everything is re-encrypted with the new passphrase on the next build. But git remembers: **old ciphertext stays in your repo's history**, still protected only by the *old* passphrase. If the old one may have leaked, treat history as exposed (or squash it — see the maintenance docs).

The full crypto design (AES-256-GCM, PBKDF2, envelope format) is documented in [DATA_CONTRACT.md](DATA_CONTRACT.md).

## 6. Personal schedule (ICS calendars)

Your schedule section reads standard ICS calendar feeds. You collect the URLs, wrap them in one small JSON file, and store it — base64-encoded — as a single secret. The build decrypts nothing on the page until you enter your passphrase.

### 6a. Get your calendar URLs

**Google Calendar**

1. Open [Google Calendar](https://calendar.google.com) on desktop → gear icon → **Settings**.
2. In the left sidebar under **Settings for my calendars**, click your calendar.
3. Scroll to **Integrate calendar** → copy the **"Secret address in iCal format"**.
4. 🔴 **Treat this URL like a password.** Anyone who has it can read your entire calendar. That's exactly why it goes in a secret, never in the repo or an issue.

**Outlook / Office 365**

1. Outlook on the web → **Settings → Calendar → Shared calendars**.
2. Under **Publish a calendar**, choose your calendar and a permission level, click **Publish**.
3. Copy the **ICS** link.

**Canvas calendar** (deadlines as calendar events)

1. In Canvas, open **Calendar** (left global navigation).
2. Bottom-right of the calendar sidebar: click **Calendar feed**.
3. Copy the ICS URL.

### 6b. Build the JSON file

Copy [`examples/ics-sources.example.json`](../examples/ics-sources.example.json) somewhere **outside the repo** (e.g. your Desktop), name it `ics-sources.json`, and fill in your feeds:

```json
[
  { "id": "gcal_personal", "name": "Personal", "url": "https://calendar.google.com/calendar/ical/…/private-…/basic.ics" },
  { "id": "canvas", "name": "Canvas deadlines", "url": "https://canvas.example.edu/feeds/calendars/user_….ics" }
]
```

> 🔴 **Never commit this file.** It contains secret URLs. It lives on your machine only long enough to encode it.

### 6c. Encode and add the secret

In a terminal, from the folder containing the file:

- **macOS**:
  ```bash
  base64 -i ics-sources.json | tr -d "\n"
  ```
- **Linux**:
  ```bash
  base64 -w0 ics-sources.json
  ```
- **Windows (PowerShell)**:
  ```powershell
  [Convert]::ToBase64String([IO.File]::ReadAllBytes("ics-sources.json"))
  ```

Copy the single long line it prints, then add it as a new repository secret named **`ICS_SOURCES_B64`** (Settings → Secrets and variables → Actions → New repository secret).

Finally: the schedule is a **private section, so it also requires `NEWSDASH_PASSPHRASE`** ([step 5](#5-private-mode-and-the-passphrase)) — without it the build has no key to encrypt with and the section shows as not configured. Re-run **Update Newsdash** and your schedule appears behind the unlock.

## 7. Canvas courses

Beyond calendar events, Newsdash can show Canvas **announcements and upcoming assignments** (with whether you've submitted). This uses the Canvas REST API:

1. In Canvas: **Account → Settings** → scroll to **Approved Integrations** → click **+ New Access Token**. Give it a purpose like "newsdash" and generate.
2. Copy the token immediately (Canvas shows it only once).
3. Add two repository secrets:
   - `CANVAS_BASE_URL` — your institution's Canvas root, e.g. `https://canvas.iastate.edu`
   - `CANVAS_TOKEN` — the token you just generated

> ⚠️ **A Canvas access token grants full access to your Canvas account** — grades, messages, everything, not just what Newsdash reads. Rotate it every semester (delete the old token in Canvas, generate a new one, update the secret). Some institutions force tokens to expire; if your courses section suddenly errors, an expired token is the first thing to check.

Like the schedule, courses are a private section: `NEWSDASH_PASSPHRASE` is required.

## 8. Academic packs

Tick **Data visualization** and/or **Technical communication** in the setup issue ([step 4](#4-personalize-via-the-setup-issue)) — no code editing needed. These pull from keyless scholarly APIs, with varying reliability:

| Source | Keyless reliability |
|---|---|
| **arXiv** | ✅ Reliable |
| **CrossRef** | ✅ Reliable |
| **OpenAlex** | ⚠️ Best-effort without a key — since OpenAlex's 2026 move to a credits system, keyless requests often fail. Add an **`OPENALEX_API_KEY`** secret to make it reliable. |
| **Semantic Scholar** | ⚠️ Best-effort — the shared keyless pool is frequently rate-limited. |

One polite thing to do: set the **`CONTACT_MAILTO`** *variable* (note: **Variables tab**, not Secrets — Settings → Secrets and variables → Actions → **Variables** → New repository variable) to your email address. CrossRef and OpenAlex route requests with a contact email into their faster, more reliable "polite pools". It's not a secret; it just identifies your bot as a good citizen.

## 9. Let AI do it for you

If you use Claude Code, Codex, or a similar coding agent, the repo ships a maintainer skill — **Page Skill｜书童Skill** — that automates steps 4–8. Open your repo in the agent and paste:

> Use the Page Skill (书童Skill) in this repo. Interview me about my news sources, academic fields, calendars, and Canvas; update config/ for me; then guide me through adding each GitHub Secret myself. Never ask me to paste secret values into chat, and never commit URLs that contain tokens.

What to expect:

- It **interviews you** — what you read, your field, which calendars and LMS you use.
- It **edits `config/` for you** and validates the result.
- For every secret, it **walks you through adding it yourself** in the GitHub UI: it tells you the exact secret name and where to find the value, but it **never asks you to paste secret values into the chat** and never writes them into files. If an agent ever asks for your actual passphrase or token value, refuse — that's not how this skill works.

## 10. Reading your dashboard

- **Unlock** — if you have encrypted sections, an unlock button asks for your passphrase (the one from `NEWSDASH_PASSPHRASE`). Wrong passphrase is detected instantly, before any data downloads.
- **"Remember on this device"** — optional checkbox at unlock. It stores the derived key in your browser so you skip typing next time. Only use it on a device that is genuinely yours: anyone with access to that browser profile can then read your private sections. Locking the site wipes it.
- **Annotations** — select any text in an article card and choose **Highlight**, **Excerpt**, or **Note**. Everything you save lands in the **Clippings** view, which exports **Obsidian-friendly Markdown**. Annotations are stored locally in your browser (never uploaded) and are **only visible after unlock**.
- **Theme and language** — switch between English/中文 anytime with the language toggle; switch the theme (`the-type` / `nyt` / `bear`) from the page controls or permanently via the setup issue.
- **Print brief** — the print view formats the current dashboard as a clean paper brief; just use your browser's print (⌘P / Ctrl+P).

## 11. Troubleshooting

| Symptom | Likely cause → fix |
|---|---|
| **Build is red** in Actions | Open the failed run's log — the error line tells you which source or secret misbehaved. A `private` site with no `NEWSDASH_PASSPHRASE` refuses to publish by design: add the secret ([step 5](#5-private-mode-and-the-passphrase)) and re-run. |
| **Page looks stale** | The Pages CDN caches ~10 minutes — wait it out, hard-refresh. Still stale? Check [Actions](../../actions) that "Update Newsdash" actually ran green recently. |
| **Schedule is empty / errored** | Google regenerates your "secret address" URL if you ever click *Reset* (or Google resets it for you) — the old URL in your secret then dies. Copy the new secret address, rebuild `ics-sources.json`, re-encode ([step 6c](#6c-encode-and-add-the-secret)), update the `ICS_SOURCES_B64` secret, re-run the workflow. |
| **"Awaiting first build" screen** | The pipeline has never run. Actions tab → Update Newsdash → Run workflow ([step 2](#2-first-build)). |
| **Updates silently stopped** | GitHub **auto-disables cron workflows after 60 days without repo activity**. Actions tab → the workflow shows a "scheduled workflows disabled" banner → click **Enable**. Any commit also resets the clock. |
| **"Wrong passphrase"** | Check spelling, spacing, and case — it must match the secret exactly. Just changed the secret? The site accepts the *new* passphrase only after the next successful "Update Newsdash" run re-encrypts the data. |
| **Private section says "not configured"** | The build ran without that section's secrets. Schedule needs `ICS_SOURCES_B64` **and** `NEWSDASH_PASSPHRASE`; courses need `CANVAS_BASE_URL` + `CANVAS_TOKEN` **and** `NEWSDASH_PASSPHRASE`. Add what's missing, re-run. |

---

Next: how the data files and encryption actually work → [DATA_CONTRACT.md](DATA_CONTRACT.md)
