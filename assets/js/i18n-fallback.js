// GENERATED from i18n/en.json — do not edit by hand.
// Regenerate: python3 scripts/gen_i18n_fallback.py
// Purpose: the network copies of i18n/*.json can fail behind a flaky
// CDN; this embedded English dictionary guarantees the chrome never
// renders raw keys like "app.tagline". Parity with en.json is pinned
// by tests/test_i18n_fallback.mjs.

export const FALLBACK_EN = {
  "app": {
    "tagline": "Your news and your papers — one page.",
    "updated": "Updated {time}",
    "loading": "Loading…",
    "empty": "Nothing here yet.",
    "error": "Something went wrong loading this section.",
    "notConfigured": "This section isn't set up yet.",
    "notConfiguredHint": "Add the required secrets in your repository settings, then wait for the next update. See the setup guide.",
    "setupGuide": "Setup guide",
    "schemeToDark": "Switch to dark mode",
    "schemeToLight": "Switch to light mode",
    "noscript": "Relevance needs JavaScript to render your dashboard. 及君需要启用 JavaScript 才能显示。"
  },
  "nav": {
    "today": "Today",
    "news": "News",
    "papers": "Papers",
    "following": "Following",
    "private": "🔒 Private",
    "clippings": "Clippings",
    "settings": "Settings"
  },
  "onboarding": {
    "title": "Almost there — one build away",
    "body": "This dashboard hasn't produced its first data snapshot yet. If you just deployed, do the following:",
    "step1": "Enable GitHub Actions for your repository (Actions tab → enable workflows).",
    "step2": "Run the “Update Relevance” workflow once (Actions → Update Relevance → Run workflow), or wait for the schedule.",
    "step3": "Enable GitHub Pages (Settings → Pages → deploy from branch, main / root).",
    "step4": "Open the “Set up my Relevance” issue in your repository to choose sources, theme, language, and privacy.",
    "refresh": "Refresh"
  },
  "tutorial": {
    "title": "Welcome to Relevance",
    "s1Title": "Congratulations — your site is live! 🎉",
    "s1Body": "This is Relevance, your own serverless news · research dashboard. It refreshes itself on a schedule — there's no server to run. Let's finish customizing it in three quick steps.",
    "s2Title": "① Set up your site",
    "s2Body": "Open a “Set up my Relevance” issue in your repository to choose your language, theme, starter sources, and whether the site is public or private. A bot applies your choices and rebuilds.",
    "s2Action": "Open the setup issue →",
    "s3Title": "② Add your keys",
    "s3Body": "Some features need secrets: a passphrase (NEWSDASH_PASSPHRASE) to unlock private mode, and optional API keys for AI summaries. Add them under Settings → Secrets and variables → Actions.",
    "s3Action": "Open repository secrets →",
    "s3Note": "Never paste a secret or a private feed URL into an issue — issues are public. A secret's value belongs only in Settings.",
    "s4Title": "③ Customize with your coding agent",
    "s4Body": "Clone the repo locally, open Claude Code, Codex, or another coding agent, and run the Page Skill. It guides you through curating sources, testing them, tuning priority, and organizing them into tabs.",
    "s4Action": "Read the skill guide →",
    "s5Title": "You're all set",
    "s5Body": "Reopen this guide any time from Settings → About. Enjoy your dashboard!",
    "next": "Next",
    "back": "Back",
    "done": "Done",
    "skip": "Skip",
    "noRepoNote": "Open your repository on GitHub to do this — your site is on a custom domain, so we can't link to it directly."
  },
  "login": {
    "title": "Private mode",
    "prompt": "Enter your passphrase to unlock private sections and notes.",
    "placeholder": "Passphrase",
    "unlock": "Unlock",
    "wrong": "Wrong passphrase. Please try again.",
    "remember": "Remember on this device",
    "rememberNote": "Stores the derived key (not your passphrase) in this browser. Skip this on shared computers.",
    "lock": "Lock",
    "locked": "Locked",
    "unlocked": "Unlocked",
    "gateTitle": "This dashboard is private",
    "gateBody": "All content is encrypted. Enter the passphrase to read.",
    "noCrypto": "Private mode isn't configured. Set the NEWSDASH_PASSPHRASE secret to enable private sections and notes."
  },
  "today": {
    "greetings": {
      "dawn": [
        "Up before the headlines.",
        "First light, first lines.",
        "The day is still in draft."
      ],
      "morning": [
        "Morning — the world kept notes while you slept.",
        "A fresh page. Begin anywhere.",
        "Good morning. The ink is still fresh."
      ],
      "midday": [
        "Midday — the news is still warm.",
        "Noon. A good hour to look up.",
        "Half the day, whole of the world."
      ],
      "afternoon": [
        "Afternoon light, long stories, short reads.",
        "The afternoon knows what the morning suspected.",
        "Slow hours. Read one thing well."
      ],
      "evening": [
        "Evening — time to gather the day's threads.",
        "The day files its last dispatches.",
        "Dusk. The headlines soften."
      ],
      "night": [
        "Late hours. Read gently.",
        "The world runs on night shift now.",
        "Tomorrow is already typesetting."
      ]
    },
    "today": "Today",
    "yesterday": "Yesterday",
    "highlights": "Highlights",
    "topStories": "Top stories",
    "latestPapers": "Top papers",
    "lockedBlock": "Unlock to see this.",
    "more": "More →",
    "aiSummaryLabel": "AI summary",
    "todaysImage": "Today's Image",
    "imageSource": "Source:",
    "todaysFeed": "Today's Feed",
    "featured": "Featured",
    "photoOfTheDay": "Photo of the Day",
    "aproposTitle": "Apropos-of-Nothing",
    "aproposKicker": "Not for you, probably",
    "aproposSource": "Source",
    "threads": "Threads",
    "threadsWhyNow": "Why now —",
    "threadsTouches": "touches:",
    "threadConvergent": "convergent",
    "threadMixed": "mixed",
    "threadDivergent": "divergent"
  },
  "overview": {
    "newToday": "New today",
    "items": "Items",
    "sourcesOk": "Sources OK",
    "languages": "Languages",
    "favorites": "Favorites",
    "articles": "articles",
    "sources": "sources",
    "topics": "topics"
  },
  "feed": {
    "search": "Search…",
    "allSources": "All sources",
    "anyTime": "Any time",
    "last6h": "Last 6 hours",
    "last24h": "Last 24 hours",
    "last3d": "Last 3 days",
    "last7d": "Last 7 days",
    "itemCount": "{n} items",
    "alsoIn": "Also reported by",
    "noMatches": "No items match your filters.",
    "sortNewest": "Newest",
    "sortTop": "Top priority",
    "langAll": "All languages",
    "langZh": "中文",
    "langEn": "English",
    "groupBySource": "By source",
    "groupNone": "Timeline",
    "citations": "{n} citations",
    "newBadge": "NEW",
    "allTags": "All tags",
    "fullTextAvailable": "Full Text Available",
    "original": "Original"
  },
  "reader": {
    "back": "Back to feed",
    "unavailable": "Full text unavailable",
    "unavailableBody": "This item does not include embedded full text in the current feed snapshot.",
    "stale": "Reader file unavailable",
    "staleBody": "This article may have rolled out of the latest generated data. Open the original source instead."
  },
  "fav": {
    "title": "Favorites",
    "empty": "No favorites yet. Click the ☆ on any item to save it here.",
    "searchPlaceholder": "Search favorites…",
    "add": "Add to favorites",
    "remove": "Remove from favorites",
    "lockedHint": "Unlock private mode to see your favorites."
  },
  "clippings": {
    "title": "Clippings",
    "empty": "No highlights, excerpts, or notes yet. Select text in any item to start.",
    "searchPlaceholder": "Search clippings…",
    "all": "All",
    "highlights": "Highlights",
    "excerpts": "Excerpts",
    "notes": "Notes",
    "tabs": {
      "favorites": "Favorites",
      "notes": "Notes"
    },
    "export": "Export Markdown",
    "delete": "Delete",
    "editNote": "Edit note",
    "notePlaceholder": "Write a note…",
    "save": "Save",
    "cancel": "Cancel",
    "deleted": "Deleted.",
    "lockedHint": "Unlock private mode to see your clippings."
  },
  "annotate": {
    "highlight": "Highlight",
    "excerpt": "Excerpt",
    "note": "Note",
    "saved": "Saved to clippings.",
    "unlockHint": "Unlock to annotate"
  },
  "sources": {
    "title": "Source health",
    "name": "Source",
    "type": "Type",
    "category": "Category",
    "status": "Status",
    "items": "Items",
    "ok": "OK",
    "failed": "Failed",
    "skipped": "Awaiting secrets",
    "disabled": "Disabled",
    "fullText": "Full text",
    "fullTextCount": "{n}",
    "privateSummary": "{configured} of {total} private sources configured",
    "categories": {
      "open": "Open",
      "optional": "Optional",
      "private": "Private"
    },
    "add": {
      "title": "Add a source",
      "kind": {
        "rss": "RSS / Page",
        "scholar": "Scholar",
        "journal": "Journal",
        "private": "Private feed"
      },
      "ph": {
        "rss": "Page or feed URL",
        "scholar": "Scholar name",
        "journal": "Journal name or ISSN",
        "private": "Feed nickname — never the URL"
      },
      "promptLabel": "Paste this to Claude (Page Skill):",
      "copy": "Copy",
      "copied": "Copied ✓",
      "issueLink": "…or add it via a GitHub issue",
      "privateWarning": "Never paste the feed's URL or token into chat or issues — issues are public. Only the secret's NAME goes in config; the value goes into the repo's Settings → Secrets.",
      "prompt": {
        "rss": "Use the Page Skill (skills/newsdash) in this repo. Add this page or feed as an open source: {input}. Autodiscover the feed if needed, check its health, propose the config snippet, validate, and commit.",
        "scholar": "Use the Page Skill (skills/newsdash) in this repo. Follow the scholar {input}: find their OpenAlex author ID and add an openalex source (filter authorships.author.id:…) in the 'following' section, then validate and commit.",
        "journal": "Use the Page Skill (skills/newsdash) in this repo. Track the journal {input} via Crossref: verify the ISSN and add a crossref source in the 'papers' section, then validate and commit.",
        "private": "Use the Page Skill (skills/newsdash) in this repo. I have a private feed ({input}) that needs a capability URL. Add it as a private source (category 'private', section 'private', enabled 'auto', secret_ref ['SRC_<ID>_URL']) WITHOUT asking me to paste the URL into chat, config, or issues; then guide me through adding the GitHub Secret myself and verifying the next build."
      }
    }
  },
  "settings": {
    "title": "Settings",
    "tabs": {
      "general": "General",
      "sources": "Sources"
    },
    "theme": "Theme",
    "themes": {
      "the-type": "The Type",
      "nyt": "Newsprint",
      "bear": "Bear"
    },
    "appearance": "Appearance",
    "schemes": {
      "light": "Light",
      "dark": "Dark",
      "auto": "Auto"
    },
    "language": "Language",
    "privacy": "Private mode",
    "print": "Print today's brief",
    "aiSummary": "AI summary",
    "aiSummaryConfigured": "Configured — an AI daily brief, Today's Image, and Apropos-of-Nothing may appear on the Today page.",
    "aiSummaryNotConfigured": "Not configured. The dashboard owner can add an LLM_API_KEY secret to enable an AI daily brief and Apropos-of-Nothing.",
    "about": "About",
    "aboutBody": "Relevance — a serverless, self-hosted news · research dashboard. Data updates via GitHub Actions; private sections are AES-256 encrypted and decrypted only in your browser.",
    "version": "Version"
  }
};
