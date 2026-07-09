// Internal full-text reader for RSS/Atom entries that shipped embedded
// content in the feed. Bodies are generated as plaintext and rendered
// through textContent, never as HTML.

import { renderAnnotationsIn } from "../annotate.js";
import { itemMatchesContentLang } from "../content_lang.js";
import { loadArticle } from "../data.js";
import { clear, el, safeHref } from "../dom.js";
import { fmtDateTime, fmtRelative, t } from "../i18n.js";
import { get } from "../store.js";
import { errorCard, lockedCard } from "./shared.js";

function itemFor(sectionId, itemId) {
  const section = get().sections[sectionId];
  if (!section) return { status: "missing", item: null };
  if (section.status === "locked") return { status: "locked", item: null };
  if (section.status !== "ok") return { status: "error", item: null };
  const item = (section.payload?.items || [])
    .find((candidate) => candidate.id === itemId && itemMatchesContentLang(candidate));
  return item ? { status: "ok", item } : { status: "missing", item: null };
}

function paragraphs(text) {
  const blocks = String(text || "")
    .split(/\n{2,}/)
    .map((block) => block.replace(/\s+/g, " ").trim())
    .filter(Boolean);
  return blocks.length ? blocks : [""];
}

function readerShell(item, body) {
  return el("article", {
    class: `reader-article kind-${item.kind}`,
    dataset: { itemId: item.id, sectionId: item.section },
    lang: item.lang === "zh" ? "zh-CN" : undefined,
  },
    el("a", { class: "reader-back", href: `#/${item.section}` }, t("reader.back")),
    el("div", { class: "item-meta reader-meta" },
      el("span", { class: "item-source" }, item.source),
      el("time", {
        datetime: item.published_at,
        title: fmtDateTime(item.published_at, { year: "numeric" }),
      }, fmtRelative(item.published_at)),
      el("span", { class: "full-text-badge" }, t("feed.fullTextAvailable")),
    ),
    el("h1", { class: "reader-title", "data-annotatable": "" }, item.title),
    item.summary
      ? el("p", { class: "reader-summary", "data-annotatable": "" }, item.summary)
      : null,
    el("p", { class: "reader-actions" },
      el("a", {
        href: safeHref(item.url), target: "_blank", rel: "noopener noreferrer",
      }, t("feed.original")),
    ),
    el("div", { class: "reader-body", "data-annotatable": "" },
      paragraphs(body).map((para) => el("p", {}, para))),
  );
}

export async function render(container, sectionId, itemId) {
  clear(container);
  const { status, item } = itemFor(sectionId, itemId);
  if (status === "locked") return container.appendChild(lockedCard());
  if (status !== "ok" || !item) return container.appendChild(errorCard());
  if (!item.full_text_file) {
    return container.appendChild(el("div", { class: "state-card" },
      el("h2", {}, t("reader.unavailable")),
      el("p", { class: "muted" }, t("reader.unavailableBody")),
      el("p", {},
        el("a", {
          href: safeHref(item.url), target: "_blank", rel: "noopener noreferrer",
        }, t("feed.original"))),
    ));
  }

  container.appendChild(el("p", { class: "muted" }, t("app.loading")));
  const article = await loadArticle(item);
  clear(container);
  if (article.status === "locked") return container.appendChild(lockedCard());
  if (article.status !== "ok" || !article.payload?.full_text) {
    return container.appendChild(el("div", { class: "state-card" },
      el("h2", {}, t("reader.stale")),
      el("p", { class: "muted" }, t("reader.staleBody")),
      el("p", {},
        el("a", {
          href: safeHref(item.url), target: "_blank", rel: "noopener noreferrer",
        }, t("feed.original"))),
    ));
  }

  container.appendChild(readerShell(item, article.payload.full_text));
  renderAnnotationsIn(container);
}
