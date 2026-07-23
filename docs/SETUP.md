# Setup Guide — from zero to your own Relevance

This is the click-by-click walkthrough. No terminal required for the core path — everything happens in the GitHub web UI. If you get stuck at any step, jump to the [Troubleshooting table](#9-troubleshooting) at the bottom.

**Pick your pace:**

- **Fast lane (10 minutes, zero keys)** → do steps 1–4. You get a live news + papers dashboard with the default packs.
- **Full setup (add ~10 minutes)** → continue with steps 5–6 for private mode and academic packs.
- **Lazy lane** → do steps 1–3, then let AI drive the rest for you ([step 7](#7-let-ai-do-it-for-you)).

---

## 0. What you need

- A **GitHub account** (free is fine).
- About **10 minutes** for the first pass.
- **No API keys.** The default news and academic packs run entirely keyless. Keys only enter the picture later, if you opt into private mode or AI features.

---

## 1. Create your copy

1. On this repository's page, click the green **Use this template** button → **Create a new repository**.
2. Name it whatever you like (e.g. `relevance`).
3. **Keep it Public.** This matters, so here's why:
   - GitHub Pages hosting is **free only on public repos** — private repos need a paid plan for Pages.
   - Public repos get **unlimited free Actions minutes**; private repos get only 2,000 minutes/month.
   - Worried about privacy? Your privacy does **not** come from repo visibility — it comes from **encryption** ([step 5](#5-private-mode-and-the-passphrase)). Private sections are always encrypted before they're committed, so a public repo never exposes them.
4. Click **Create repository**.

## 2. First build

1. Open the **Actions** tab of your new repo. If you see a banner saying workflows are disabled, click **"I understand my workflows, go ahead and enable them"**.
2. In the left sidebar, click **Update Relevance**.
3. Click **Run workflow** → **Run workflow** (green button, keep the `main` branch).
4. Wait for the run to go **green** (usually 1–3 minutes). This first build fetches the default news packs and commits the results to the `data/` folder.

After this, the build re-runs itself automatically every 2 hours — no further clicks needed.

**Want it to run less often?** The cadence is a repo Variable, `NEWSDASH_UPDATE_FREQ`: `2h` (default, ≈ 900 Actions min/month), `3x` a day (≈ 225), or `daily` (≈ 75), at ~2.5 min/run. On a **private** repo (only 2,000 free min/month) pick `3x` or `daily` to stay well under. You can set it right in the setup form ([step 4](#4-personalize-via-the-setup-issue)), or later at Settings → Secrets and variables → Actions → Variables. A manual **Run workflow** always rebuilds regardless.

## 3. Enable Pages

1. Go to **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Pick branch **`main`** and folder **`/ (root)`**, then **Save**.
4. Your site will be live at:

   ```
   https://<your-username>.github.io/<your-repo>/
   ```

The first deploy takes **1–5 minutes**. After that, each data refresh can lag up to **~10 minutes** behind the build — that's the GitHub Pages CDN cache, not a bug. The site busts the cache automatically on its next load.

> If the page shows an **"awaiting first build"** screen, the pipeline hasn't produced data yet — go back to step 2 and make sure "Update Relevance" ran green.

### 3a. Custom domain (optional)

If you point your own domain at the site (Settings → Pages → **Custom domain**),
GitHub commits a `CNAME` file to the repo root — **keep it**. Then set DNS at
your registrar so the domain resolves **straight to GitHub Pages**, not to a
registrar CDN/parking service:

- **Apex** (`example.com`) → four `A` records:
  `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
  (and/or the matching `AAAA` records from GitHub's docs).
- **`www` subdomain** → one `CNAME` → `<your-username>.github.io`
  (your username **exactly** — a typo silently breaks it).
- **Turn off** any registrar "CDN"/"parking"/proxy on the domain (e.g.
  Namecheap **Supersonic CDN**). Those sit in front of your real origin and
  return **502** because GitHub Pages isn't wired up as their origin.

DNS changes take minutes to hours to propagate; verify with
`dig +short example.com` (should show the GitHub IPs above).

## 4. Personalize via the setup issue

You never need to edit JSON by hand. The repo ships an issue form that a bot reads and applies.

1. Go to **Issues → New issue** and pick **"Set up my Relevance · 配置我的及君"**.
2. Fill in the form:

   | Field | What it changes |
   |---|---|
   | **Interface language** | Default UI language, English or Chinese. Readers can still toggle anytime on the page. |
   | **Site visibility** | **Public** = news/papers readable by anyone, personal sections still encrypted. **Private** = the *entire* site is encrypted and opens with a passphrase gate — requires the `NEWSDASH_PASSPHRASE` secret ([step 5](#5-private-mode-and-the-passphrase)). |
   | **Theme** | `the-type` (typography-first serif), `nyt` (newspaper front page), or `bear` (minimal, compact). All three ship a designed dark variant. |
   | **Site title** | The masthead text (optional). |
   | **Timezone** | IANA name like `America/Chicago` or `Asia/Shanghai` — used for day boundaries (optional). |
   | **Open news packs** | Tick **AI news** and/or **General news**. Tick nothing and the bot keeps both defaults. |
   | **Academic packs** | Tick **Data visualization** and/or **Technical communication** — keyless scholarly feeds ([step 6](#6-academic-packs)). |
   | **Extra RSS feeds** | One feed URL per line; each becomes a source in your news section. |
   | **Interest keywords** | Comma-separated; items matching these rank higher in your feed. |
   | **Acknowledgement** | Required checkbox: secrets never go in the issue. |

3. **Submit.** The bot then:
   - updates `config/site.json` and `config/sources.json` and commits the change,
   - triggers a rebuild,
   - **comments back** with your next steps (your Pages URL, a secrets checklist with deep links, and the AI kickoff prompt),
   - **closes the issue** when everything applied cleanly.
4. Made a typo or changed your mind? **Edit the issue body** — the bot re-runs on every edit, even after it's closed.

> ⚠️ **Never paste secrets into the issue** — no passphrase, no tokens. The bot actively scans for credential-looking strings and refuses to apply anything if it finds one. Secrets go in **Settings → Secrets and variables → Actions** (next step). Also note: only issues opened by the **repository owner** are applied — other people's issues on your repo are ignored by design.

## 5. Private mode and the passphrase

One secret turns on encryption for everything personal:

1. Go to **Settings → Secrets and variables → Actions → New repository secret**.
2. Name: `NEWSDASH_PASSPHRASE`
3. Value: **at least 4 random words**, e.g. `maple lantern crater bicycle`. Because the encrypted files are publicly downloadable, a weak passphrase can be brute-forced offline — length beats cleverness here.
4. Click **Add secret**, then re-run **Update Relevance** (Actions tab) so the new passphrase takes effect.

Things to know:

- **The passphrase is also your login.** When you open your site, entering this passphrase in the browser is what unlocks the encrypted sections. There is no separate account.
- With `visibility: public`, your news/papers stay readable by anyone, while any private sections are always encrypted. With `visibility: private`, *every* section is encrypted and the site boots straight to a passphrase gate.
- **Changing the passphrase**: update the secret's value and re-run the workflow — everything is re-encrypted with the new passphrase on the next build. But git remembers: **old ciphertext stays in your repo's history**, still protected only by the *old* passphrase. If the old one may have leaked, treat history as exposed (or squash it — see the maintenance docs).

The full crypto design (AES-256-GCM, PBKDF2, envelope format) is documented in [DATA_CONTRACT.md](DATA_CONTRACT.md).

## 6. Academic packs

Tick **Data visualization** and/or **Technical communication** in the setup issue ([step 4](#4-personalize-via-the-setup-issue)) — no code editing needed. These pull from keyless scholarly APIs, with varying reliability:

| Source | Keyless reliability |
|---|---|
| **arXiv** | ✅ Reliable |
| **CrossRef** | ✅ Reliable |
| **OpenAlex** | ⚠️ Best-effort without a key — since OpenAlex's 2026 move to a credits system, keyless requests often fail. Add an **`OPENALEX_API_KEY`** secret to make it reliable. |
| **Semantic Scholar** | ⚠️ Best-effort — the shared keyless pool is frequently rate-limited. |

One polite thing to do: set the **`CONTACT_MAILTO`** *variable* (note: **Variables tab**, not Secrets — Settings → Secrets and variables → Actions → **Variables** → New repository variable) to your email address. CrossRef and OpenAlex route requests with a contact email into their faster, more reliable "polite pools". It's not a secret; it just identifies your bot as a good citizen.

### 6a. AI daily brief + Today's Image + Apropos-of-Nothing (optional)

Off by default — nothing changes until you add a key. Once you do, the Today page gets an AI-written daily brief, a one-line summary inside "Top stories" and "Top papers," and an "Apropos-of-Nothing" card at the end: one intentionally off-profile public-news item with a short AI summary and source link. With a second key, it also gets a "Today's Image" block: a public-domain image loosely matched to the day's content, with a one-sentence AI caption.

**Get an LLM key.** `LLM_API_KEY` works with any OpenAI-Chat-Completions-compatible provider — pick whichever you already have an account with:

| Provider | `LLM_BASE_URL` | `LLM_MODEL` example |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` (default — you can omit this variable) | `gpt-4o-mini` (default) |
| DeepSeek | `https://api.deepseek.com` | `deepseek-v4-flash` |
| OpenRouter | `https://openrouter.ai/api/v1` | any model slug it lists |
| Groq | `https://api.groq.com/openai/v1` | any model it lists |

1. Get an API key from your chosen provider's own dashboard.
2. Add it as a repository secret: **Settings → Secrets and variables → Actions → New repository secret**, name **`LLM_API_KEY`**.
3. If you're not using OpenAI, also add two repository **variables** (Variables tab, not Secrets) — **`LLM_BASE_URL`** and **`LLM_MODEL`** — with the values from the table above.
4. Re-run **Update Relevance**. Within one build, a brief should appear on the Today page.

**Add Today's Image (optional, needs the LLM key above too).** Images come from the [Smithsonian Open Access API](https://www.si.edu/openaccess) — official, documented, and only ever CC0-licensed (truly rights-free) images are shown.

1. Go to <https://api.data.gov/signup/> and fill in your name + email — no institutional affiliation or approval needed, it's a casual free-tier signup like any other API. A key arrives by email in seconds.
2. Add it as a repository secret named **`SMITHSONIAN_API_KEY`**.
3. Re-run **Update Relevance**.

These features only ever read your `news`/`papers` item titles and short summaries — never your passphrase or full-text article bodies — and skip silently (no error, no cost) if something's temporarily unreachable. `Settings` on your live site shows whether this is "configured." Full details, kill switches (`LLM_SUMMARY_ENABLED=0` / `TODAYS_IMAGE_ENABLED=0` / `APROPOS_OF_NOTHING_ENABLED=0`), and the privacy/egress model: [CONFIG_REFERENCE.md §4a](CONFIG_REFERENCE.md#4a-optional-ai-enrichment-daily-brief--todays-image--apropos-of-nothing) and [SECURITY_MODEL.md §3a](SECURITY_MODEL.md#3a-optional-ai-enrichment-egress-off-by-default).

## 7. Let AI do it for you

If you use Claude Code, Codex, or a similar coding agent, the repo ships a maintainer skill — **Page Skill｜书童Skill** — that automates steps 4–6. Open your repo in the agent and paste:

> Use the Page Skill (书童Skill) in this repo. Interview me about my news sources and academic fields; update config/ for me; then guide me through adding each GitHub Secret myself. Never ask me to paste secret values into chat, and never commit URLs that contain tokens.

What to expect:

- It **interviews you** — what you read and your field.
- It **edits `config/` for you** and validates the result.
- For every secret, it **walks you through adding it yourself** in the GitHub UI: it tells you the exact secret name and where to find the value, but it **never asks you to paste secret values into the chat** and never writes them into files. If an agent ever asks for your actual passphrase or token value, refuse — that's not how this skill works.

## 8. Reading your dashboard

- **Unlock** — if you have encrypted sections, an unlock button asks for your passphrase (the one from `NEWSDASH_PASSPHRASE`). Wrong passphrase is detected instantly, before any data downloads.
- **"Remember on this device"** — optional checkbox at unlock. It stores the derived key in your browser so you skip typing next time. Only use it on a device that is genuinely yours: anyone with access to that browser profile can then read your private sections. Locking the site wipes it.
- **Annotations** — select any text in an article card and choose **Highlight**, **Excerpt**, or **Note**. Everything you save lands in the **Clippings** view, which exports **Obsidian-friendly Markdown**. Annotations are stored locally in your browser (never uploaded) and are **only visible after unlock**.
- **Theme and language** — switch between English/中文 anytime with the language toggle; switch the theme (`the-type` / `nyt` / `bear`) from the page controls or permanently via the setup issue.
- **Print brief** — the print view formats the current dashboard as a clean paper brief; just use your browser's print (⌘P / Ctrl+P).

## 9. Troubleshooting

| Symptom | Likely cause → fix |
|---|---|
| **Build is red** in Actions | Open the failed run's log — the error line tells you which source or secret misbehaved. A `private` site with no `NEWSDASH_PASSPHRASE` refuses to publish by design: add the secret ([step 5](#5-private-mode-and-the-passphrase)) and re-run. |
| **Page looks stale** | The Pages CDN caches ~10 minutes — wait it out, hard-refresh. Still stale? Check [Actions](../../actions) that "Update Relevance" actually ran green recently. |
| **502 / "trouble connecting"** on a custom domain | Your registrar's CDN/parking (e.g. Namecheap Supersonic CDN) is intercepting the domain and can't reach GitHub as its origin. Fix DNS per [step 3a](#3a-custom-domain-optional): apex `A` records → GitHub's four IPs, `www` `CNAME` → `<username>.github.io` (check for typos), disable the registrar CDN. The site always stays reachable at the raw `https://<username>.github.io/<repo>/` URL meanwhile. |
| **"Awaiting first build" screen** | The pipeline has never run. Actions tab → Update Relevance → Run workflow ([step 2](#2-first-build)). |
| **Updates silently stopped** | GitHub **auto-disables cron workflows after 60 days without repo activity**. Actions tab → the workflow shows a "scheduled workflows disabled" banner → click **Enable**. Any commit also resets the clock. |
| **"Wrong passphrase"** | Check spelling, spacing, and case — it must match the secret exactly. Just changed the secret? The site accepts the *new* passphrase only after the next successful "Update Relevance" run re-encrypts the data. |
| **Private section says "not configured"** | The build ran without that section's secrets. A private section needs its own secret(s) **and** `NEWSDASH_PASSPHRASE`. Add what's missing, re-run. |
| **AI brief / Today's Image / Apropos-of-Nothing doesn't appear** | Check `Settings` on your live site — it reports whether `LLM_API_KEY` is configured at all. If it says configured but nothing shows: confirm `LLM_BASE_URL`/`LLM_MODEL` actually match your provider ([step 6a](#6a-ai-daily-brief--todays-image--apropos-of-nothing-optional)); check the latest Actions run's log for `[llm-summary] error: …` or `[apropos-of-nothing:*] error: …`. Today's Image and Apropos-of-Nothing can legitimately be absent on a given run if their public searches find no suitable sourced result. |

---

Next: how the data files and encryption actually work → [DATA_CONTRACT.md](DATA_CONTRACT.md)
