// Shared feed view for news + papers sections: filter bar, item cards,
// annotation layer. Filter changes re-render only the list, so the search
// input keeps focus.

import { renderAnnotationsIn } from "../annotate.js";
import { clear, el, safeHref } from "../dom.js";
import { fmtDateTime, fmtRelative, t } from "../i18n.js";
import { get } from "../store.js";
import { emptyCard, errorCard, lockedCard, notConfiguredCard } from "./shared.js";

const filters = {}; // sectionId -> { q, source, hours }

export function itemCard(item, sectionId) {
  const isPaper = item.kind === "paper";
  return el("article", {
    class: `item kind-${item.kind}`,
    dataset: { itemId: item.id, sectionId },
    lang: item.lang === "zh" ? "zh-CN" : undefined,
  },
    el("div", { class: "item-meta" },
      el("span", { class: "item-source" }, item.source),
      el("time", {
        datetime: item.published_at,
        title: fmtDateTime(item.published_at, { year: "numeric" }),
      }, fmtRelative(item.published_at)),
      typeof item.score === "number"
        ? el("span", { class: "item-score" }, item.score.toFixed(2)) : null,
    ),
    el("h3", { class: "item-title" },
      el("a", {
        href: safeHref(item.url), target: "_blank", rel: "noopener noreferrer",
        "data-annotatable": "",
      }, item.title),
    ),
    isPaper && (item.authors?.length || item.venue)
      ? el("p", { class: "item-byline" },
          (item.authors || []).join(", "),
          item.venue ? ` · ${item.venue}` : "")
      : null,
    item.summary
      ? el("p", { class: "item-summary", "data-annotatable": "" }, item.summary)
      : null,
    (item.tags?.length || item.extra?.also_in?.length)
      ? el("div", { class: "item-tags" },
          (item.tags || []).map((tag) => el("span", { class: "tag" }, tag)),
          item.extra?.also_in?.length
            ? el("span", { class: "also-in" },
                `${t("feed.alsoIn")}: ${item.extra.also_in.map((s) => s.source).join(", ")}`)
            : null)
      : null,
  );
}

export function render(container, sectionId) {
  clear(container);
  const section = get().sections[sectionId];
  if (!section) return container.appendChild(emptyCard());
  if (section.status === "not_configured") return container.appendChild(notConfiguredCard());
  if (section.status === "locked") return container.appendChild(lockedCard());
  if (section.status === "error" || !section.payload) return container.appendChild(errorCard());

  const items = section.payload.items || [];
  if (!items.length) return container.appendChild(emptyCard());

  const state = filters[sectionId] ||= { q: "", source: "", hours: 0 };
  const sources = [...new Set(items.map((i) => i.source))].sort();

  const list = el("div", { class: "item-list" });
  const count = el("span", { class: "filter-count" });

  const search = el("input", {
    type: "search", class: "filter-search", placeholder: t("feed.search"),
    value: state.q,
    oninput: (e) => { state.q = e.target.value; renderList(); },
  });
  const sourceSel = el("select", {
    class: "filter-source",
    onchange: (e) => { state.source = e.target.value; renderList(); },
  },
    el("option", { value: "" }, t("feed.allSources")),
    sources.map((s) => {
      const opt = el("option", { value: s }, s);
      if (s === state.source) opt.selected = true;
      return opt;
    }),
  );
  const timeSel = el("select", {
    class: "filter-time",
    onchange: (e) => { state.hours = Number(e.target.value); renderList(); },
  },
    [[0, "anyTime"], [6, "last6h"], [24, "last24h"], [72, "last3d"], [168, "last7d"]]
      .map(([hours, key]) => {
        const opt = el("option", { value: hours }, t(`feed.${key}`));
        if (hours === state.hours) opt.selected = true;
        return opt;
      }),
  );

  container.appendChild(el("div", { class: "filter-bar" }, search, sourceSel, timeSel, count));
  container.appendChild(list);

  function renderList() {
    const q = state.q.trim().toLowerCase();
    const cutoff = state.hours ? Date.now() - state.hours * 3600_000 : 0;
    const visible = items.filter((item) =>
      (!q || `${item.title} ${item.summary} ${item.source}`.toLowerCase().includes(q))
      && (!state.source || item.source === state.source)
      && (!cutoff || new Date(item.published_at).getTime() >= cutoff));
    clear(list);
    count.textContent = t("feed.itemCount", { n: visible.length });
    if (!visible.length) {
      list.appendChild(el("p", { class: "muted" }, t("feed.noMatches")));
      return;
    }
    for (const item of visible) list.appendChild(itemCard(item, sectionId));
    renderAnnotationsIn(list);
  }

  renderList();
}
