// Bilingual UI strings. Both dictionaries load once at boot; switching
// language is synchronous after that. Content items stay in their source
// language — only the chrome translates.

import { prefs } from "./store.js";

const dicts = { en: null, zh: null };
let current = "en";

export async function initI18n(preferred) {
  const results = await Promise.all(
    ["en", "zh"].map((l) =>
      fetch(`i18n/${l}.json`, { cache: "no-cache" }).then((r) => r.json())
        .catch(() => ({}))),
  );
  dicts.en = results[0];
  dicts.zh = results[1];
  setLang(preferred || "en", { persist: false });
}

export function getLang() {
  return current;
}

export function setLang(lang, { persist = true } = {}) {
  current = lang === "zh" ? "zh" : "en";
  document.documentElement.lang = current === "zh" ? "zh-CN" : "en";
  document.documentElement.setAttribute("data-lang", current);
  if (persist) prefs.write("lang", current);
}

function lookup(dict, key) {
  let node = dict;
  for (const part of key.split(".")) {
    if (node == null || typeof node !== "object") return undefined;
    node = node[part];
  }
  return typeof node === "string" ? node : undefined;
}

export function t(key, vars) {
  let text = lookup(dicts[current] || {}, key)
    ?? lookup(dicts.en || {}, key)
    ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.replaceAll(`{${k}}`, String(v));
    }
  }
  return text;
}

const locale = () => (current === "zh" ? "zh-CN" : "en-US");

export function fmtDateTime(iso, opts = {}) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat(locale(), {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    ...opts,
  }).format(d);
}

export function fmtDate(iso, opts = {}) {
  // date-only strings must not shift across timezones
  const d = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T12:00:00`) : new Date(iso);
  return new Intl.DateTimeFormat(locale(), {
    weekday: "short", month: "short", day: "numeric", ...opts,
  }).format(d);
}

export function fmtTime(iso) {
  return new Intl.DateTimeFormat(locale(), {
    hour: "numeric", minute: "2-digit",
  }).format(new Date(iso));
}

export function fmtRelative(iso, now = Date.now()) {
  const diffSec = (new Date(iso).getTime() - now) / 1000;
  const rtf = new Intl.RelativeTimeFormat(locale(), { numeric: "auto" });
  const abs = Math.abs(diffSec);
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
  return rtf.format(Math.round(diffSec / 86400), "day");
}
