// App bootstrap: manifest load -> theme/i18n -> (onboarding | private gate |
// dashboard) -> hash routing. Unlock flow per docs/DATA_CONTRACT.md: derive
// key once, verify against the manifest check block, decrypt sections.

import { initAnnotator, setOnSaved, renderAnnotationsIn } from "./annotate.js";
import * as ndCrypto from "./crypto.js";
import { dropDecrypted, loadAllSections, loadManifest } from "./data.js";
import { clear, el } from "./dom.js";
import { fmtDateTime, initI18n, t } from "./i18n.js";
import { applyScheme, initScheme, resolvedScheme, updateThemeColorMeta } from "./scheme.js";
import { get, prefs, set } from "./store.js";
import * as clippingsView from "./views/clippings.js";
import * as feedView from "./views/feed.js";
import * as readerView from "./views/reader.js";
import * as settingsView from "./views/settings.js";
import { fixDocLinks, sectionLabel } from "./views/shared.js";
import * as todayView from "./views/today.js";
import { showTutorial, tutorialSeen } from "./tutorial.js";

const SECTION_ORDER = ["news", "papers", "following", "private"];
const viewEl = () => document.getElementById("view");

// ---- routing -------------------------------------------------------------

// Old top-level routes now live as tabs; redirect (replaceState so the
// back button isn't polluted with the dead route).
const LEGACY = { favorites: "clippings/favorites", sources: "settings/sources" };

function parseRoute() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (LEGACY[hash]) {
    history.replaceState(null, "", `#/${LEGACY[hash]}`);
    return LEGACY[hash];
  }
  return hash || "today";
}

function routes() {
  const manifest = get().manifest;
  const sectionIds = (manifest?.sections || []).map((s) => s.id);
  const list = ["today"];
  for (const id of SECTION_ORDER) if (sectionIds.includes(id)) list.push(id);
  for (const id of sectionIds) if (!list.includes(id)) list.push(id);
  list.push("clippings", "settings");
  return list;
}

function renderView() {
  const route = parseRoute();
  const container = viewEl();
  const sections = get().sections;
  // subroutes (clippings/notes, settings/sources) keep the parent nav
  // item highlighted.
  document.querySelectorAll("#nav a").forEach((a) =>
    a.classList.toggle("active", a.dataset.route === route.split("/")[0]));

  if (route.startsWith("read/")) {
    const [, sectionId, itemId] = route.split("/");
    readerView.render(container, sectionId, itemId);
  } else {
    const [page, tab] = route.split("/");
    if (page === "clippings") clippingsView.render(container, tab);
    else if (page === "settings") settingsView.render(container, tab);
    else if (sections[page]) feedView.render(container, page);
    else todayView.render(container);
  }

  fixDocLinks(container);
  container.focus({ preventScroll: true });
}

// ---- header chrome -------------------------------------------------------

// the-type is the only theme with a typography-first look that needs
// non-system fonts; nyt/bear stay on the "system fonts only" guarantee
// (assets/styles.css header comment) since this never runs for them.
function ensureTheTypeFonts() {
  if (document.documentElement.dataset.theme !== "the-type") return;
  if (document.getElementById("the-type-fonts")) return;
  document.head.append(
    el("link", { rel: "preconnect", href: "https://fonts.googleapis.com" }),
    el("link", { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "" }),
    el("link", {
      id: "the-type-fonts", rel: "stylesheet",
      href: "https://fonts.googleapis.com/css2?"
        + "family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400"
        + "&family=Noto+Serif+SC:wght@400;500;600;700"
        + "&family=Noto+Sans+SC:wght@300;400;500"
        + "&family=IBM+Plex+Mono:wght@400;500"
        + "&display=swap",
    }),
  );
}

// The product wordmark localizes to 及君 in Chinese mode — but only when the
// deployer kept the default title. A custom site title is shown verbatim.
function brandTitle() {
  const title = get().manifest?.site?.title;
  const lang = document.documentElement.getAttribute("data-lang") || "en";
  if (!title || title === "Relevance") return lang === "zh" ? "及君" : "Relevance";
  return title;
}

function renderHeader() {
  ensureTheTypeFonts();
  const { manifest, unlocked } = get();
  const brand = brandTitle();
  document.getElementById("site-title-link").textContent = brand;
  document.getElementById("site-subtitle").textContent =
    manifest?.site?.subtitle || t("app.tagline");
  document.title = brand;

  const updated = document.getElementById("updated-at");
  updated.textContent = manifest?.generated_at
    ? t("app.updated", { time: fmtDateTime(manifest.generated_at) }) : "";

  const lockBtn = document.getElementById("lock-btn");
  if (manifest?.crypto) {
    lockBtn.hidden = false;
    lockBtn.textContent = unlocked ? "🔓" : "🔒";
    lockBtn.title = unlocked ? t("login.lock") : t("login.unlock");
    lockBtn.setAttribute("aria-label", lockBtn.title);
  } else {
    lockBtn.hidden = true;
  }

  const langBtn = document.getElementById("lang-toggle");
  const lang = document.documentElement.getAttribute("data-lang") || "en";
  langBtn.textContent = lang === "zh" ? "EN" : "中文";

  const nav = document.getElementById("nav");
  clear(nav);
  for (const route of routes()) {
    nav.appendChild(el("a", { href: `#/${route}`, dataset: { route } },
      sectionLabel(route)));
  }

  // Scheme toggle glyph/label track the resolved scheme; theme switches also
  // change --bg, so refresh the meta theme-color here too.
  updateSchemeToggle();
  updateThemeColorMeta();
}

// Header ☀/☾ quick-toggle: glyph reflects the RESOLVED scheme, the label names
// the action (switch to the other one). Kept in sync via nd:schemechange.
function updateSchemeToggle() {
  const btn = document.getElementById("scheme-toggle");
  if (!btn) return;
  const dark = resolvedScheme() === "dark";
  btn.textContent = dark ? "☾" : "☀";
  const title = dark ? t("app.schemeToLight") : t("app.schemeToDark");
  btn.title = title;
  btn.setAttribute("aria-label", title);
}

function renderAll() {
  renderHeader();
  renderView();
}

// First-run only: show the setup tutorial once the site is live and readable
// (never over the awaiting-build screen or the private gate). Callers invoke
// this after content has rendered; the "seen" flag makes it a one-time popup.
function maybeShowTutorial() {
  if (tutorialSeen() || isGated()) return;
  const { manifest } = get();
  if (!manifest || manifest.status === "awaiting_first_build") return;
  showTutorial();
}

// ---- unlock / lock -------------------------------------------------------

async function tryRememberedKey() {
  const manifest = get().manifest;
  if (!manifest?.crypto) return false;
  const stored = prefs.read("key");
  if (!stored) return false;
  try {
    const key = await ndCrypto.importKeyBytes(ndCrypto.b64decode(stored));
    if (await ndCrypto.verifyCheck(manifest.crypto, key)) {
      set({ cryptoKey: key, unlocked: true });
      return true;
    }
  } catch { /* stale key, fall through */ }
  prefs.write("key", null);
  return false;
}

function showUnlockModal() {
  const manifest = get().manifest;
  if (!manifest?.crypto || get().unlocked) return;
  const root = document.getElementById("modal-root");
  clear(root);

  const input = el("input", {
    type: "password", class: "pass-input", placeholder: t("login.placeholder"),
    autocomplete: "current-password",
  });
  const remember = el("input", { type: "checkbox", id: "remember-key" });
  const error = el("p", { class: "login-error", role: "alert", hidden: "" });
  const unlockBtn = el("button", { class: "unlock-btn" }, t("login.unlock"));

  const modal = el("div", { class: "modal-backdrop" },
    el("div", { class: "modal login-modal", role: "dialog", "aria-modal": "true" },
      el("h3", {}, t("login.title")),
      el("p", { class: "muted" }, t("login.prompt")),
      el("form", {
        onsubmit: async (e) => {
          e.preventDefault();
          unlockBtn.disabled = true;
          unlockBtn.textContent = "…";
          const ok = await unlock(input.value, remember.checked);
          if (!ok) {
            error.hidden = false;
            error.textContent = t("login.wrong");
            modal.querySelector(".modal").classList.add("shake");
            setTimeout(() => modal.querySelector(".modal").classList.remove("shake"), 400);
            unlockBtn.disabled = false;
            unlockBtn.textContent = t("login.unlock");
            input.select();
          } else {
            close();
          }
        },
      },
        input,
        el("label", { class: "remember-row" }, remember, ` ${t("login.remember")}`),
        el("p", { class: "muted small" }, t("login.rememberNote")),
        error,
        el("div", { class: "modal-actions" },
          el("button", {
            type: "button", class: "secondary",
            onclick: () => close(),
          }, t("clippings.cancel")),
          unlockBtn,
        ),
      ),
    ),
  );
  function close() { modal.remove(); }
  modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
  modal.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  root.appendChild(modal);
  input.focus();
}

async function unlock(passphrase, remember) {
  const manifest = get().manifest;
  try {
    const bytes = await ndCrypto.deriveKeyBytes(passphrase, manifest.crypto.kdf);
    const key = await ndCrypto.importKeyBytes(bytes);
    if (!(await ndCrypto.verifyCheck(manifest.crypto, key))) return false;
    if (remember) prefs.write("key", ndCrypto.b64encode(bytes));
    set({ cryptoKey: key, unlocked: true });
    await loadAllSections();
    renderAll();
    maybeShowTutorial();
    return true;
  } catch (err) {
    console.error("unlock failed:", err);
    return false;
  }
}

function lock() {
  prefs.write("key", null);
  set({ cryptoKey: null, unlocked: false });
  dropDecrypted();
  renderAll();
}

// ---- special screens -----------------------------------------------------

function renderOnboarding() {
  const container = viewEl();
  clear(container);
  container.appendChild(el("div", { class: "onboarding" },
    el("h2", {}, t("onboarding.title")),
    el("p", {}, t("onboarding.body")),
    el("ol", {},
      el("li", {}, t("onboarding.step1")),
      el("li", {}, t("onboarding.step2")),
      el("li", {}, t("onboarding.step3")),
      el("li", {}, t("onboarding.step4")),
    ),
    el("p", {},
      el("a", { class: "doc-link", target: "_blank", rel: "noopener",
                href: "https://github.com", dataset: { repoDoc: "docs/SETUP.md" } },
        t("app.setupGuide")),
    ),
    el("button", { onclick: () => window.location.reload() }, t("onboarding.refresh")),
  ));
  fixDocLinks(container);
}

function renderPrivateGate() {
  const container = viewEl();
  clear(container);
  container.appendChild(el("div", { class: "private-gate" },
    el("h2", {}, `🔒 ${t("login.gateTitle")}`),
    el("p", { class: "muted" }, t("login.gateBody")),
    el("button", { onclick: showUnlockModal }, t("login.unlock")),
  ));
}

// ---- boot ----------------------------------------------------------------

async function boot() {
  let manifest = null;
  try {
    manifest = await loadManifest();
  } catch (err) {
    console.error(err);
  }
  set({ manifest });

  const theme = prefs.read("theme", manifest?.site?.theme || "the-type");
  document.documentElement.dataset.theme = theme;
  initScheme();
  await initI18n(prefs.read("lang", manifest?.site?.default_language || "en"));

  initAnnotator();
  setOnSaved(() => renderAnnotationsIn(viewEl()));

  document.getElementById("lang-toggle").addEventListener("click", () => {
    const next = (document.documentElement.getAttribute("data-lang") || "en") === "zh"
      ? "en" : "zh";
    import("./i18n.js").then(({ setLang }) => {
      setLang(next);
      renderCurrent();
    });
  });
  document.getElementById("scheme-toggle").addEventListener("click", () => {
    applyScheme(resolvedScheme() === "dark" ? "light" : "dark");
  });
  document.getElementById("lock-btn").addEventListener("click", () => {
    if (get().unlocked) lock();
    else showUnlockModal();
  });
  document.addEventListener("nd:unlock-request", showUnlockModal);
  document.addEventListener("nd:lock", lock);
  document.addEventListener("nd:rerender", renderCurrent);
  document.addEventListener("nd:schemechange", updateSchemeToggle);
  document.addEventListener("nd:show-tutorial", showTutorial);
  window.addEventListener("hashchange", renderCurrent);

  await tryRememberedKey();
  await refreshContent();
}

function isGated() {
  const { manifest, unlocked } = get();
  return manifest?.site?.visibility === "private" && !unlocked;
}

async function refreshContent() {
  const { manifest } = get();
  if (!manifest || manifest.status === "awaiting_first_build") {
    renderHeader();
    renderOnboarding();
    return;
  }
  if (isGated()) {
    renderHeader();
    renderPrivateGate();
    return;
  }
  await loadAllSections();
  renderAll();
  maybeShowTutorial();
}

function renderCurrent() {
  const { manifest } = get();
  if (!manifest || manifest.status === "awaiting_first_build") {
    renderHeader();
    renderOnboarding();
    return;
  }
  if (isGated()) {
    renderHeader();
    renderPrivateGate();
    return;
  }
  renderAll();
}

boot();
