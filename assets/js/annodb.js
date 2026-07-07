// Annotation storage: IndexedDB first, localStorage fallback (iOS private
// browsing). Records carry an itemSnapshot so clippings outlive the rolling
// feed window, and a schema field so v0.2 sync needs no migration.
//
// Record shape:
// { id, itemId, sectionId, type: "highlight"|"excerpt"|"note",
//   quote, prefix, suffix, note, color,
//   itemSnapshot: { title, url, source, published_at, summary },
//   createdAt, updatedAt, schema: 1 }

const DB_NAME = "newsdash";
const DB_VERSION = 1;
const STORE = "annotations";
const LS_KEY = "nd.annotations";

let dbPromise = null;
let useFallback = false;

function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    let request;
    try {
      request = indexedDB.open(DB_NAME, DB_VERSION);
    } catch (err) {
      reject(err);
      return;
    }
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("itemId", "itemId");
        store.createIndex("createdAt", "createdAt");
        store.createIndex("type", "type");
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  }).catch((err) => {
    console.warn("IndexedDB unavailable, falling back to localStorage:", err);
    useFallback = true;
    return null;
  });
  return dbPromise;
}

function lsRead() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); }
  catch { return []; }
}

function lsWrite(list) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(list)); }
  catch (err) { console.warn("annotation save failed:", err); }
}

async function withStore(mode, fn) {
  const db = await openDb();
  if (useFallback || !db) return null;
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const result = fn(tx.objectStore(STORE));
    tx.oncomplete = () => resolve(result?.result ?? result);
    tx.onerror = () => reject(tx.error);
  });
}

export function newId() {
  return crypto.randomUUID ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function addAnnotation(record) {
  await openDb();
  if (useFallback) {
    const list = lsRead();
    list.push(record);
    lsWrite(list);
    return record;
  }
  await withStore("readwrite", (store) => store.put(record));
  return record;
}

export async function updateAnnotation(id, patch) {
  await openDb();
  if (useFallback) {
    const list = lsRead();
    const idx = list.findIndex((r) => r.id === id);
    if (idx >= 0) {
      list[idx] = { ...list[idx], ...patch, updatedAt: new Date().toISOString() };
      lsWrite(list);
    }
    return;
  }
  const existing = await withStore("readonly", (store) => store.get(id));
  if (existing) {
    await withStore("readwrite", (store) => store.put(
      { ...existing, ...patch, updatedAt: new Date().toISOString() }));
  }
}

export async function deleteAnnotation(id) {
  await openDb();
  if (useFallback) {
    lsWrite(lsRead().filter((r) => r.id !== id));
    return;
  }
  await withStore("readwrite", (store) => store.delete(id));
}

export async function listAnnotations() {
  await openDb();
  const list = useFallback
    ? lsRead()
    : (await withStore("readonly", (store) => store.getAll())) || [];
  return list.sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
}

export async function listForItem(itemId) {
  const all = await listAnnotations();
  return all.filter((r) => r.itemId === itemId);
}

// Obsidian-friendly Markdown export, grouped by day.
export function exportMarkdown(annotations) {
  const lines = ["# Newsdash clippings", ""];
  let currentDay = null;
  const sorted = [...annotations].sort(
    (a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
  for (const a of sorted) {
    const day = (a.createdAt || "").slice(0, 10) || "undated";
    if (day !== currentDay) {
      lines.push(`## ${day}`, "");
      currentDay = day;
    }
    const snap = a.itemSnapshot || {};
    const label = { highlight: "Highlight", excerpt: "Excerpt", note: "Note" }[a.type] || a.type;
    lines.push(`### ${label} — [${snap.title || "untitled"}](${snap.url || ""})`);
    if (snap.source || snap.published_at) {
      lines.push(`*${[snap.source, snap.published_at].filter(Boolean).join(" · ")}*`);
    }
    if (a.quote) lines.push("", `> ${a.quote.replaceAll("\n", "\n> ")}`);
    if (a.note) lines.push("", a.note);
    lines.push("");
  }
  return lines.join("\n");
}
