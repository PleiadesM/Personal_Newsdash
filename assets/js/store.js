// Tiny app state store. Views read via get(); mutations go through set()
// which notifies subscribers (used by the header chrome). The main view
// re-renders explicitly on route change / data arrival, not reactively —
// keeps text selection stable while annotating.

const state = {
  manifest: null,
  sections: {},        // id -> { entry, status, payload|null, locked }
  sourceStatus: null,  // decoded source-status payload or null
  insights: null,      // decoded insights payload (AI brief/summaries/image) or null
  threads: null,       // { public: payload|null, private: payload|null } — AI "Threads · 线索"
  unlocked: false,
  cryptoKey: null,     // in-memory CryptoKey while unlocked
  lang: "en",
  theme: "the-type",
  route: { name: "today", param: null },
};

const listeners = new Set();

export function get() {
  return state;
}

export function set(patch) {
  Object.assign(state, patch);
  for (const fn of listeners) fn(state);
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export const prefs = {
  read(key, fallback = null) {
    try {
      const v = localStorage.getItem(`nd.${key}`);
      return v === null ? fallback : v;
    } catch { return fallback; }
  },
  write(key, value) {
    try {
      if (value === null) localStorage.removeItem(`nd.${key}`);
      else localStorage.setItem(`nd.${key}`, value);
    } catch { /* private browsing: fine, prefs just don't persist */ }
  },
};
