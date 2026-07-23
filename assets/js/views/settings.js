// Settings: theme, language, private-mode lock state, print, about.

import { clear, el } from "../dom.js";
import { getLang, setLang, t } from "../i18n.js";
import { applyScheme, schemePref } from "../scheme.js";
import { get, prefs } from "../store.js";
import { tabBar } from "./shared.js";
import * as sourcesView from "./sources.js";

const THEMES = ["the-type", "nyt", "bear"];
const SCHEMES = ["light", "dark", "auto"];

// Keep the Appearance chips reflecting the PREF (Auto stays active under auto),
// even when the scheme changes from the header toggle or a live OS flip. The
// scheme swap is a pure CSS-var change (no nd:rerender), so nothing re-renders
// settings for us — this listener, registered once, resyncs the active chip in
// place. No-ops when the settings view isn't mounted.
document.addEventListener("nd:schemechange", () => {
  const pref = schemePref();
  document.querySelectorAll(".scheme-chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.scheme === pref);
  });
});

export function render(container, tab = "general") {
  if (tab !== "sources") tab = "general"; // unknown tab -> default
  clear(container);
  container.appendChild(el("h2", {}, t("settings.title")));
  container.appendChild(tabBar("settings", [
    ["general", t("settings.tabs.general")],
    ["sources", t("settings.tabs.sources")],
  ], tab));
  const body = el("div", { class: "tab-body" });
  container.appendChild(body);

  if (tab === "sources") sourcesView.render(body);
  else renderGeneral(body);
}

function renderGeneral(container) {
  const { manifest, unlocked } = get();

  // theme
  container.appendChild(el("section", { class: "settings-group" },
    el("h3", {}, t("settings.theme")),
    el("div", { class: "theme-picker" }, THEMES.map((theme) => {
      const active = document.documentElement.dataset.theme === theme;
      return el("button", {
        class: `theme-chip${active ? " active" : ""}`,
        dataset: { theme },
        onclick: () => {
          document.documentElement.dataset.theme = theme;
          prefs.write("theme", theme);
          // the-type's Today layout is structurally different (not just
          // CSS), so a full rerender is needed; this also re-renders
          // settings itself (refreshing the active theme chip).
          document.dispatchEvent(new CustomEvent("nd:rerender"));
        },
      }, t(`settings.themes.${theme}`));
    })),
  ));

  // appearance (color scheme): light / dark / auto. Chips reflect the PREF,
  // not the resolved scheme, so Auto stays highlighted under a dark OS. Each
  // click is a pure CSS-var swap (applyScheme cross-fades) — deliberately NO
  // nd:rerender, which would rebuild the DOM and defeat the fade.
  container.appendChild(el("section", { class: "settings-group" },
    el("h3", {}, t("settings.appearance")),
    el("div", { class: "theme-picker" }, SCHEMES.map((scheme) => {
      const active = schemePref() === scheme;
      return el("button", {
        class: `theme-chip scheme-chip${active ? " active" : ""}`,
        dataset: { scheme },
        onclick: () => applyScheme(scheme),
      }, t(`settings.schemes.${scheme}`));
    })),
  ));

  // language
  container.appendChild(el("section", { class: "settings-group" },
    el("h3", {}, t("settings.language")),
    el("div", { class: "theme-picker" }, [["en", "English"], ["zh", "中文"]].map(([lang, label]) =>
      el("button", {
        class: `theme-chip${getLang() === lang ? " active" : ""}`,
        onclick: () => {
          setLang(lang);
          document.dispatchEvent(new CustomEvent("nd:rerender"));
        },
      }, label)),
    ),
  ));

  // private mode
  const privacy = el("section", { class: "settings-group" },
    el("h3", {}, t("settings.privacy")));
  if (!manifest?.crypto) {
    privacy.appendChild(el("p", { class: "muted" }, t("login.noCrypto")));
  } else if (unlocked) {
    privacy.appendChild(el("p", {}, `✓ ${t("login.unlocked")}`));
    privacy.appendChild(el("button", {
      class: "secondary",
      onclick: () => document.dispatchEvent(new CustomEvent("nd:lock")),
    }, t("login.lock")));
  } else {
    privacy.appendChild(el("p", { class: "muted" }, `🔒 ${t("login.locked")}`));
    privacy.appendChild(el("button", {
      onclick: () => document.dispatchEvent(new CustomEvent("nd:unlock-request")),
    }, t("login.unlock")));
  }
  container.appendChild(privacy);

  // AI summary (informational only — the key lives in GitHub Secrets;
  // narrated, never entered here, per skills/newsdash/SKILL.md).
  const aiConfigured = Boolean(manifest?.ai_summary?.enabled);
  container.appendChild(el("section", { class: "settings-group" },
    el("h3", {}, t("settings.aiSummary")),
    el("p", { class: "muted" },
      aiConfigured
        ? `✓ ${t("settings.aiSummaryConfigured")}`
        : t("settings.aiSummaryNotConfigured")),
  ));

  // print
  container.appendChild(el("section", { class: "settings-group" },
    el("button", {
      class: "secondary",
      onclick: () => {
        window.location.hash = "#/today";
        setTimeout(() => window.print(), 150);
      },
    }, t("settings.print")),
  ));

  // about
  container.appendChild(el("section", { class: "settings-group about" },
    el("h3", {}, t("settings.about")),
    el("p", { class: "muted" }, t("settings.aboutBody")),
    el("p", { class: "muted" },
      `${t("settings.version")}: ${manifest?.app_version || "?"} · `,
      el("a", { href: "https://github.com", target: "_blank", rel: "noopener",
                dataset: { repoDoc: "README.md" } }, "GitHub"),
      " · ",
      el("a", { href: "#", class: "reopen-tutorial",
                onclick: (e) => {
                  e.preventDefault();
                  document.dispatchEvent(new CustomEvent("nd:show-tutorial"));
                } }, t("app.setupGuide")),
    ),
  ));
}
