// Shared feed view for news / papers / following sections: filter bar
// (search, source, time window), tag chips, Newest/Top sort,
// timeline day headers, group-by-source mode, favorite stars, NEW badges,
// annotation layer. Filter changes re-render only the list, so the search
// input keeps focus.

import { renderAnnotationsIn } from "../annotate.js";
import { addFavorite, favoriteIdSet, removeFavorite } from "../annodb.js";
import { filterItemsForContentLang } from "../content_lang.js";
import { clear, el, safeHref } from "../dom.js";
import { fmtDate, fmtDateTime, fmtRelative, t } from "../i18n.js";
import { get, prefs } from "../store.js";
import { emptyCard, errorCard, lockedCard, notConfiguredCard } from "./shared.js";

const filters = {}; // sectionId -> { q, source, hours, tag }
let renderToken = 0; // drops stale async renders on fast route changes

function localDayKey(iso) {
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function dayLabel(key) {
  if (key === localDayKey(new Date().toISOString())) return t("today.today");
  if (key === localDayKey(new Date(Date.now() - 86400_000).toISOString())) {
    return t("today.yesterday");
  }
  return fmtDate(key);
}

export async function toggleFavorite(item, sectionId, favs, btn) {
  if (favs.has(item.id)) {
    await removeFavorite(item.id);
    favs.delete(item.id);
  } else {
    await addFavorite({
      itemId: item.id,
      sectionId,
      itemSnapshot: {
        title: item.title, url: item.url, source: item.source,
        published_at: item.published_at, summary: item.summary,
        kind: item.kind, venue: item.venue || null,
      },
      createdAt: new Date().toISOString(),
      schema: 1,
    });
    favs.add(item.id);
  }
  const active = favs.has(item.id);
  btn.classList.toggle("active", active);
  btn.textContent = active ? "★" : "☆";
  btn.title = active ? t("fav.remove") : t("fav.add");
  btn.setAttribute("aria-pressed", String(active));
}

export function itemLinkAttrs(item, sectionId) {
  if (item.full_text_file) {
    return { href: `#/read/${sectionId}/${item.id}` };
  }
  return {
    href: safeHref(item.url),
    target: "_blank",
    rel: "noopener noreferrer",
  };
}

// opts: { favs: Set|null (unlocked only), newSince: ISO|null }
export function itemCard(item, sectionId, opts = {}) {
  const isPaper = item.kind === "paper";
  const citations = item.extra?.citations;
  const isNew = opts.newSince && item.published_at > opts.newSince;
  const starred = opts.favs?.has(item.id);
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
      isNew ? el("span", { class: "new-badge" }, t("feed.newBadge")) : null,
      item.full_text_available
        ? el("span", { class: "full-text-badge" }, t("feed.fullTextAvailable"))
        : null,
      typeof citations === "number" && citations > 0
        ? el("span", { class: "cite-badge" }, t("feed.citations", { n: citations }))
        : null,
      typeof item.score === "number"
        ? el("span", { class: "item-score" }, item.score.toFixed(2)) : null,
      opts.favs
        ? el("button", {
            class: `fav-star${starred ? " active" : ""}`,
            title: starred ? t("fav.remove") : t("fav.add"),
            "aria-pressed": String(Boolean(starred)),
            onclick: (e) => toggleFavorite(item, sectionId, opts.favs, e.currentTarget),
          }, starred ? "★" : "☆")
        : null,
    ),
    el("h3", { class: "item-title" },
      el("a", {
        ...itemLinkAttrs(item, sectionId),
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
    (item.tags?.length || item.extra?.also_in?.length || item.full_text_available)
      ? el("div", { class: "item-tags" },
          (item.tags || []).map((tag) => el("span", { class: "tag" }, tag)),
          item.extra?.also_in?.length
            ? el("span", { class: "also-in" },
                `${t("feed.alsoIn")}: ${item.extra.also_in.map((s) => s.source).join(", ")}`)
            : null,
          item.full_text_available
            ? el("a", {
                class: "original-link",
                href: safeHref(item.url),
                target: "_blank",
                rel: "noopener noreferrer",
              }, t("feed.original"))
            : null)
      : null,
  );
}

function segmented(options, active, onPick) {
  const wrap = el("div", { class: "seg", role: "group" });
  for (const [value, label] of options) {
    const btn = el("button", {
      type: "button",
      class: value === active ? "active" : "",
      onclick: () => onPick(value),
    }, label);
    btn.dataset.value = value;
    wrap.appendChild(btn);
  }
  return wrap;
}

function setActive(wrap, value) {
  wrap.querySelectorAll("button").forEach((b) =>
    b.classList.toggle("active", b.dataset.value === value));
}

export async function render(container, sectionId) {
  const token = ++renderToken;
  const section = get().sections[sectionId];
  const favs = get().unlocked ? await favoriteIdSet() : null;
  if (token !== renderToken) return; // superseded by a newer render
  clear(container);
  if (!section) return container.appendChild(emptyCard());
  if (section.status === "not_configured") return container.appendChild(notConfiguredCard());
  if (section.status === "locked") return container.appendChild(lockedCard());
  if (section.status === "error" || !section.payload) return container.appendChild(errorCard());

  const items = filterItemsForContentLang(section.payload.items || []);
  if (!items.length) return container.appendChild(emptyCard());

  // NEW badges mark items published since the previous visit to this section.
  const newSince = prefs.read(`seen.${sectionId}`);
  prefs.write(`seen.${sectionId}`, new Date().toISOString());

  const state = filters[sectionId] ||= { q: "", source: "", hours: 0, tag: "" };
  delete state.lang; // old in-memory filter state from pre-locale filtering
  const sources = [...new Set(items.map((i) => i.source))].sort();
  if (state.source && !sources.includes(state.source)) state.source = "";
  const isPapersKind = items.some((i) => i.kind === "paper");
  // papers-kind sections rank impact first; news reads chronologically;
  // "following" groups by the followed scholar/lab by default
  let sort = prefs.read(`sort.${sectionId}`, isPapersKind ? "top" : "new");
  let group = prefs.read(`group.${sectionId}`,
    sectionId === "following" ? "source" : "none");

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

  const sortSeg = segmented(
    [["new", t("feed.sortNewest")], ["top", t("feed.sortTop")]], sort,
    (value) => {
      sort = value;
      prefs.write(`sort.${sectionId}`, value);
      setActive(sortSeg, value);
      renderList();
    });
  const groupSeg = sources.length > 1
    ? segmented(
        [["none", t("feed.groupNone")], ["source", t("feed.groupBySource")]], group,
        (value) => {
          group = value;
          prefs.write(`group.${sectionId}`, value);
          setActive(groupSeg, value);
          renderList();
        })
    : null;
  // tag chips: the section's most frequent tags, click to filter
  const tagCounts = new Map();
  for (const item of items) {
    for (const tag of item.tags || []) {
      tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
    }
  }
  if (state.tag && !tagCounts.has(state.tag)) state.tag = "";
  const topTags = [...tagCounts.entries()]
    .sort((a, b) => b[1] - a[1]).slice(0, 14);
  let tagRow = null;
  if (topTags.length) {
    tagRow = el("div", { class: "tag-row" },
      el("button", {
        type: "button",
        class: `tag-chip${state.tag === "" ? " active" : ""}`,
        dataset: { tag: "" },
        onclick: () => pickTag(""),
      }, t("feed.allTags")),
      topTags.map(([tag, n]) => el("button", {
        type: "button",
        class: `tag-chip${state.tag === tag ? " active" : ""}`,
        dataset: { tag },
        onclick: () => pickTag(tag),
      }, tag, el("span", { class: "n" }, String(n)))),
    );
  }
  function pickTag(tag) {
    state.tag = state.tag === tag ? "" : tag;
    tagRow.querySelectorAll(".tag-chip").forEach((c) =>
      c.classList.toggle("active", c.dataset.tag === state.tag));
    renderList();
  }

  container.appendChild(el("div", { class: "filter-bar" }, search, sourceSel, timeSel, count));
  container.appendChild(el("div", { class: "feed-controls" },
    sortSeg, groupSeg));
  if (tagRow) container.appendChild(tagRow);
  container.appendChild(list);

  const cardOpts = { favs, newSince };

  function renderFlat(visible) {
    let currentDay = null;
    for (const item of visible) {
      if (sort === "new" && group === "none") {
        const day = localDayKey(item.published_at);
        if (day !== currentDay) {
          list.appendChild(el("h3", { class: "feed-day-label" }, dayLabel(day)));
          currentDay = day;
        }
      }
      list.appendChild(itemCard(item, sectionId, cardOpts));
    }
  }

  function renderGrouped(visible) {
    const groups = new Map();
    for (const item of visible) {
      if (!groups.has(item.source)) groups.set(item.source, []);
      groups.get(item.source).push(item);
    }
    const ordered = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
    for (const [source, groupItems] of ordered) {
      list.appendChild(el("h3", { class: "feed-group-label" },
        source, el("span", { class: "n" }, ` · ${groupItems.length}`)));
      for (const item of groupItems) list.appendChild(itemCard(item, sectionId, cardOpts));
    }
  }

  function renderList() {
    const q = state.q.trim().toLowerCase();
    const cutoff = state.hours ? Date.now() - state.hours * 3600_000 : 0;
    const visible = items.filter((item) =>
      (!q || `${item.title} ${item.summary} ${item.source}`.toLowerCase().includes(q))
      && (!state.source || item.source === state.source)
      && (!state.tag || (item.tags || []).includes(state.tag))
      && (!cutoff || new Date(item.published_at).getTime() >= cutoff));
    if (sort === "top") visible.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    clear(list);
    count.textContent = t("feed.itemCount", { n: visible.length });
    if (!visible.length) {
      list.appendChild(el("p", { class: "muted" }, t("feed.noMatches")));
      return;
    }
    if (group === "source") renderGrouped(visible);
    else renderFlat(visible);
    renderAnnotationsIn(list);
  }

  renderList();
}
