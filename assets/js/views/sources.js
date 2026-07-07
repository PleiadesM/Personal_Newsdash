// Source health table (radar tradition): who's delivering, who's failing,
// who's still waiting for secrets.

import { clear, el } from "../dom.js";
import { t } from "../i18n.js";
import { get } from "../store.js";
import { emptyCard, lockedCard } from "./shared.js";

function statusLabel(entry) {
  if (entry.skip_reason === "disabled") return ["disabled", t("sources.disabled")];
  if (entry.skip_reason === "not_configured") return ["skipped", t("sources.skipped")];
  if (entry.ok) return ["ok", t("sources.ok")];
  return ["failed", `${t("sources.failed")}${entry.error ? ` (${entry.error})` : ""}`];
}

export function render(container) {
  clear(container);
  const { sourceStatus, manifest, unlocked } = get();
  if (!sourceStatus) {
    if (manifest?.source_status_file?.endsWith(".enc.json") && !unlocked) {
      container.appendChild(lockedCard());
    } else {
      container.appendChild(emptyCard());
    }
    return;
  }

  container.appendChild(el("h2", {}, t("sources.title")));

  const rows = sourceStatus.sources || [];
  const table = el("table", { class: "sources-table" },
    el("thead", {}, el("tr", {},
      el("th", {}, t("sources.name")),
      el("th", {}, t("sources.type")),
      el("th", {}, t("sources.category")),
      el("th", {}, t("sources.status")),
      el("th", { class: "num" }, t("sources.items")),
    )),
    el("tbody", {}, rows.map((entry) => {
      const [cls, label] = statusLabel(entry);
      return el("tr", { class: `status-${cls}` },
        el("td", {}, entry.name),
        el("td", {}, entry.type),
        el("td", {}, t(`sources.categories.${entry.category}`)),
        el("td", {}, label),
        el("td", { class: "num" }, entry.skip_reason ? "—" : String(entry.count)),
      );
    })),
  );
  container.appendChild(table);

  const priv = sourceStatus.private_summary;
  if (priv?.total) {
    container.appendChild(el("p", { class: "muted" },
      t("sources.privateSummary", { configured: priv.configured, total: priv.total })));
  }
}
