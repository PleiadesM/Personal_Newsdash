// Clippings library: every highlight, excerpt, and note — searchable,
// editable, exportable as Obsidian-friendly Markdown. Visible only while
// private mode is unlocked (the requirement: annotations show after login).

import { deleteAnnotation, exportMarkdown, listAnnotations, updateAnnotation } from "../annodb.js";
import { clear, el, safeHref } from "../dom.js";
import { fmtDateTime, t } from "../i18n.js";
import { get } from "../store.js";
import { lockedCard } from "./shared.js";

const state = { q: "", type: "" };

export async function render(container) {
  clear(container);
  if (!get().unlocked) {
    container.appendChild(el("p", { class: "muted" }, t("clippings.lockedHint")));
    container.appendChild(lockedCard());
    return;
  }

  const annotations = await listAnnotations();
  const list = el("div", { class: "clippings-list" });

  const search = el("input", {
    type: "search", class: "filter-search",
    placeholder: t("clippings.searchPlaceholder"), value: state.q,
    oninput: (e) => { state.q = e.target.value; renderList(); },
  });
  const typeSel = el("select", {
    onchange: (e) => { state.type = e.target.value; renderList(); },
  },
    [["", "all"], ["highlight", "highlights"], ["excerpt", "excerpts"], ["note", "notes"]]
      .map(([value, key]) => {
        const opt = el("option", { value }, t(`clippings.${key}`));
        if (value === state.type) opt.selected = true;
        return opt;
      }),
  );
  const exportBtn = el("button", {
    class: "secondary",
    onclick: () => {
      const md = exportMarkdown(annotations);
      const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
      const a = el("a", {
        href: URL.createObjectURL(blob),
        download: `newsdash-clippings-${new Date().toISOString().slice(0, 10)}.md`,
      });
      a.click();
      URL.revokeObjectURL(a.href);
    },
  }, t("clippings.export"));

  container.appendChild(el("div", { class: "filter-bar" }, search, typeSel, exportBtn));
  container.appendChild(list);

  function entryCard(anno) {
    const snap = anno.itemSnapshot || {};
    const card = el("article", { class: `clipping type-${anno.type}` },
      el("div", { class: "clipping-meta" },
        el("span", { class: `tag tag-${anno.type}` }, t(`clippings.${anno.type}s`)),
        el("span", { class: "muted" }, fmtDateTime(anno.createdAt, { year: "numeric" })),
      ),
      snap.title
        ? el("p", { class: "clipping-source" },
            el("a", { href: safeHref(snap.url), target: "_blank", rel: "noopener" }, snap.title),
            snap.source ? ` · ${snap.source}` : "")
        : null,
      anno.quote ? el("blockquote", {}, anno.quote) : null,
    );
    const noteP = el("p", { class: "clipping-note" }, anno.note || "");
    if (anno.note) card.appendChild(noteP);

    card.appendChild(el("div", { class: "clipping-actions" },
      el("button", {
        class: "linklike",
        onclick: () => editNote(card, anno, noteP),
      }, t("clippings.editNote")),
      el("button", {
        class: "linklike danger",
        onclick: async () => {
          await deleteAnnotation(anno.id);
          const idx = annotations.indexOf(anno);
          if (idx >= 0) annotations.splice(idx, 1);
          renderList();
        },
      }, t("clippings.delete")),
    ));
    return card;
  }

  function editNote(card, anno, noteP) {
    const textarea = el("textarea", {
      class: "note-input", rows: 3,
      placeholder: t("clippings.notePlaceholder"),
    });
    textarea.value = anno.note || "";
    const actions = el("div", { class: "modal-actions" },
      el("button", { class: "secondary", onclick: () => editor.remove() }, t("clippings.cancel")),
      el("button", {
        onclick: async () => {
          anno.note = textarea.value.trim();
          await updateAnnotation(anno.id, { note: anno.note });
          renderList();
        },
      }, t("clippings.save")),
    );
    const editor = el("div", { class: "note-editor" }, textarea, actions);
    card.appendChild(editor);
    textarea.focus();
  }

  function renderList() {
    clear(list);
    const q = state.q.trim().toLowerCase();
    const visible = annotations.filter((anno) =>
      (!state.type || anno.type === state.type)
      && (!q || `${anno.quote} ${anno.note} ${anno.itemSnapshot?.title || ""}`
        .toLowerCase().includes(q)));
    if (!visible.length) {
      list.appendChild(el("p", { class: "muted" }, t("clippings.empty")));
      return;
    }
    for (const anno of visible) list.appendChild(entryCard(anno));
  }

  renderList();
}
