// Color scheme (light/dark) with an Auto mode that follows the OS. Distinct
// from `theme` (the-type/nyt/bear): a scheme change is a pure CSS-custom-
// property swap — no re-render — so it can cross-fade. The resolved scheme is
// stamped on <html data-scheme>; the FOUC guard in index.html stamps it once
// before first paint, and this module keeps it in sync afterward, drives the
// fade, and syncs <meta name="theme-color"> to the active background.

import { prefs } from "./store.js";

const SCHEMES = ["light", "dark", "auto"];
const FADE_MS = 400;
const darkQuery = () => window.matchMedia("(prefers-color-scheme: dark)");
const reducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// The stored preference (light|dark|auto), defaulting to auto.
export function schemePref() {
  const p = prefs.read("scheme", "auto");
  return SCHEMES.includes(p) ? p : "auto";
}

// The concrete scheme in effect (light|dark): auto resolves via matchMedia.
export function resolvedScheme(pref = schemePref()) {
  if (pref === "light" || pref === "dark") return pref;
  return darkQuery().matches ? "dark" : "light";
}

// Point the browser chrome (mobile URL bar, etc.) at the active --bg token.
// Read after the scheme is stamped so the computed value reflects it.
export function updateThemeColorMeta() {
  const meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) return;
  const bg = getComputedStyle(document.documentElement)
    .getPropertyValue("--bg").trim();
  if (bg) meta.setAttribute("content", bg);
}

let fadeTimer = null;

// Persist the preference, resolve it, and stamp the result on <html>. When the
// resolved scheme actually changes, cross-fade the token swap (unless
// reduced-motion is on) via a one-shot html.scheme-fade class, then dispatch
// nd:schemechange so the header/settings chrome can resync.
export function applyScheme(pref, { persist = true, fade = true } = {}) {
  if (!SCHEMES.includes(pref)) pref = "auto";
  if (persist) prefs.write("scheme", pref);

  const root = document.documentElement;
  const next = resolvedScheme(pref);
  const changed = root.dataset.scheme !== next;

  if (changed && fade && !reducedMotion()) {
    root.classList.add("scheme-fade");
    // Commit the class before the token swap so the transition catches it.
    void root.offsetWidth;
    clearTimeout(fadeTimer);
    fadeTimer = setTimeout(() => root.classList.remove("scheme-fade"), FADE_MS);
  }

  root.dataset.scheme = next;
  updateThemeColorMeta();
  document.dispatchEvent(new CustomEvent("nd:schemechange",
    { detail: { pref, resolved: next } }));
}

// Boot-time: adopt the stored preference without persisting or fading (the
// FOUC guard already stamped the correct scheme), then follow the OS live —
// those auto-mode flips DO fade.
export function initScheme() {
  applyScheme(schemePref(), { persist: false, fade: false });
  darkQuery().addEventListener("change", () => {
    if (schemePref() === "auto") {
      applyScheme("auto", { persist: false, fade: true });
    }
  });
}
