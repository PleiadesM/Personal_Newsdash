// Selection toolbar + TextQuoteSelector anchoring (W3C-style: exact +
// prefix/suffix), per docs/DATA_CONTRACT.md privacy invariants: the whole
// layer is active only while private mode is unlocked.

import { addAnnotation, listAnnotations, newId } from "./annodb.js";
import { el } from "./dom.js";
import { t } from "./i18n.js";
import { get } from "./store.js";

const CONTEXT_LEN = 32;
let toolbar = null;
let pending = null; // { itemId, sectionId, selector, snapshot }
let onSaved = null; // callback so views can refresh their annotation marks

export function setOnSaved(fn) {
  onSaved = fn;
}

export function initAnnotator() {
  document.addEventListener("pointerup", handleSelection);
  document.addEventListener("keyup", (e) => {
    if (e.key === "Escape") hideToolbar();
  });
  document.addEventListener("selectionchange", () => {
    const sel = document.getSelection();
    if (!sel || sel.isCollapsed) hideToolbar();
  });
}

function annotatableFor(node) {
  const element = node instanceof Element ? node : node?.parentElement;
  return element?.closest?.("[data-annotatable]") || null;
}

function handleSelection() {
  if (!get().unlocked) return;
  const sel = document.getSelection();
  if (!sel || sel.isCollapsed || sel.rangeCount === 0) return hideToolbar();
  const range = sel.getRangeAt(0);
  const container = annotatableFor(range.commonAncestorContainer);
  if (!container) return hideToolbar();
  const itemEl = container.closest("[data-item-id]");
  if (!itemEl) return hideToolbar();

  const selector = computeSelector(container, range);
  if (!selector || !selector.exact.trim()) return hideToolbar();

  pending = {
    itemId: itemEl.dataset.itemId,
    sectionId: itemEl.dataset.sectionId,
    selector,
    snapshot: findSnapshot(itemEl.dataset.sectionId, itemEl.dataset.itemId),
  };
  showToolbar(range.getBoundingClientRect());
}

// Map the DOM range to character offsets inside the annotatable element.
function computeSelector(container, range) {
  const full = container.textContent;
  let start = -1;
  let offset = 0;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node === range.startContainer) start = offset + range.startOffset;
    offset += node.textContent.length;
  }
  if (start < 0) return null;
  const exact = range.toString();
  if (!full.slice(start).startsWith(exact.slice(0, 8))) {
    // selection crossed outside this element; fall back to string search
    const idx = full.indexOf(exact);
    if (idx < 0) return null;
    start = idx;
  }
  return {
    exact,
    prefix: full.slice(Math.max(0, start - CONTEXT_LEN), start),
    suffix: full.slice(start + exact.length, start + exact.length + CONTEXT_LEN),
  };
}

function findSnapshot(sectionId, itemId) {
  const section = get().sections[sectionId];
  const items = section?.payload?.items || [];
  const item = items.find((i) => i.id === itemId);
  if (!item) return null;
  return {
    title: item.title, url: item.url, source: item.source,
    published_at: item.published_at, summary: item.summary,
  };
}

function showToolbar(rect) {
  hideToolbar();
  toolbar = el("div", { class: "anno-toolbar", role: "toolbar" },
    el("button", { onclick: () => save("highlight") }, t("annotate.highlight")),
    el("button", { onclick: () => save("excerpt") }, t("annotate.excerpt")),
    el("button", { onclick: () => saveWithNote() }, t("annotate.note")),
  );
  document.getElementById("toolbar-root").appendChild(toolbar);
  const top = window.scrollY + rect.top - toolbar.offsetHeight - 8;
  toolbar.style.top = `${Math.max(window.scrollY + 4, top)}px`;
  toolbar.style.left = `${Math.max(8, window.scrollX + rect.left)}px`;
}

function hideToolbar() {
  toolbar?.remove();
  toolbar = null;
}

async function save(type, note = "") {
  if (!pending) return;
  const now = new Date().toISOString();
  await addAnnotation({
    id: newId(),
    itemId: pending.itemId,
    sectionId: pending.sectionId,
    type,
    quote: pending.selector.exact,
    prefix: pending.selector.prefix,
    suffix: pending.selector.suffix,
    note,
    color: "yellow",
    itemSnapshot: pending.snapshot,
    createdAt: now,
    updatedAt: now,
    schema: 1,
  });
  pending = null;
  hideToolbar();
  document.getSelection()?.removeAllRanges();
  onSaved?.();
}

function saveWithNote() {
  const captured = pending; // survives the selection collapsing
  const root = document.getElementById("modal-root");
  const textarea = el("textarea", {
    class: "note-input", placeholder: t("clippings.notePlaceholder"), rows: 4,
  });
  const dialog = el("div", { class: "modal-backdrop" },
    el("div", { class: "modal", role: "dialog", "aria-modal": "true" },
      el("h3", {}, t("annotate.note")),
      captured?.selector?.exact
        ? el("blockquote", {}, captured.selector.exact) : null,
      textarea,
      el("div", { class: "modal-actions" },
        el("button", { class: "secondary", onclick: close }, t("clippings.cancel")),
        el("button", {
          onclick: async () => {
            pending = captured;
            await save("note", textarea.value.trim());
            close();
          },
        }, t("clippings.save")),
      ),
    ),
  );
  function close() { dialog.remove(); }
  dialog.addEventListener("click", (e) => { if (e.target === dialog) close(); });
  root.appendChild(dialog);
  textarea.focus();
}

// ---- rendering saved highlights back into a view ------------------------

export async function renderAnnotationsIn(viewRoot) {
  if (!get().unlocked) return;
  const all = await listAnnotations();
  if (!all.length) return;
  const byItem = new Map();
  for (const a of all) {
    if (a.type === "highlight" || (a.type === "note" && a.quote)) {
      if (!byItem.has(a.itemId)) byItem.set(a.itemId, []);
      byItem.get(a.itemId).push(a);
    }
  }
  for (const itemEl of viewRoot.querySelectorAll("[data-item-id]")) {
    const annos = byItem.get(itemEl.dataset.itemId);
    if (!annos) continue;
    for (const container of itemEl.querySelectorAll("[data-annotatable]")) {
      for (const anno of annos) markQuote(container, anno);
    }
  }
}

function markQuote(container, anno) {
  const full = container.textContent;
  let idx = -1;
  if (anno.prefix || anno.suffix) {
    const ctx = full.indexOf(anno.prefix + anno.quote + anno.suffix);
    if (ctx >= 0) idx = ctx + anno.prefix.length;
  }
  if (idx < 0) idx = full.indexOf(anno.quote);
  if (idx < 0) return;

  // find the text node containing the whole quote (plain-text renders keep
  // quotes within one node in practice; skip quietly when they don't)
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let offset = 0;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const end = offset + node.textContent.length;
    if (idx >= offset && idx + anno.quote.length <= end) {
      if (node.parentElement?.closest("mark.nd-highlight")) return; // already marked
      const local = idx - offset;
      const target = node.splitText(local);
      target.splitText(anno.quote.length);
      const mark = el("mark", {
        class: `nd-highlight${anno.note ? " has-note" : ""}`,
        title: anno.note || undefined,
        dataset: { annotationId: anno.id },
      });
      target.parentNode.replaceChild(mark, target);
      mark.appendChild(target);
      return;
    }
    offset = end;
  }
}
