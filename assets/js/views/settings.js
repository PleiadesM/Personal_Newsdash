// Settings: theme, language, private-mode lock state, print, about.

import { clear, el } from "../dom.js";
import { getLang, setLang, t } from "../i18n.js";
import { get, prefs } from "../store.js";

const THEMES = ["the-type", "nyt", "bear"];

export function render(container) {
  clear(container);
  const { manifest, unlocked } = get();

  container.appendChild(el("h2", {}, t("settings.title")));

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
    ),
  ));
}
