// Manifest-driven data loading with cache-busting (docs/DATA_CONTRACT.md).
// GitHub Pages' CDN caches ~10 min: the manifest is fetched no-store with a
// timestamp param; every data file is fetched as file?v=<build_id>.

import { get, set } from "./store.js";
import { decryptEnvelope } from "./crypto.js";

export async function loadManifest() {
  const resp = await fetch(`data/manifest.json?t=${Date.now()}`, { cache: "no-store" });
  if (!resp.ok) throw new Error(`manifest fetch failed: ${resp.status}`);
  return resp.json();
}

async function fetchData(file, buildId) {
  const resp = await fetch(`data/${file}?v=${encodeURIComponent(buildId || "0")}`);
  if (!resp.ok) throw new Error(`fetch ${file}: ${resp.status}`);
  return resp.json();
}

// Load one section into store.sections[id]:
//   { entry, status: "ok"|"locked"|"error"|"not_configured", payload|null }
async function loadSection(entry, manifest, key) {
  if (entry.status === "not_configured" || !entry.file) {
    return { entry, status: "not_configured", payload: null };
  }
  try {
    const doc = await fetchData(entry.file, manifest.build_id);
    if (!entry.encrypted) return { entry, status: "ok", payload: doc };
    if (!key) return { entry, status: "locked", payload: null };
    const payload = await decryptEnvelope(doc, key, entry.id);
    return { entry, status: "ok", payload };
  } catch (err) {
    console.error(`section ${entry.id}:`, err);
    return { entry, status: "error", payload: null };
  }
}

async function loadSourceStatus(manifest, key) {
  const file = manifest.source_status_file;
  if (!file) return null;
  try {
    const doc = await fetchData(file, manifest.build_id);
    if (!file.endsWith(".enc.json")) return doc;
    if (!key) return null;
    return await decryptEnvelope(doc, key, "source-status");
  } catch (err) {
    console.error("source-status:", err);
    return null;
  }
}

// (Re)load all sections. Called at boot and again after unlock/lock.
export async function loadAllSections() {
  const { manifest, cryptoKey } = get();
  if (!manifest || !Array.isArray(manifest.sections)) return;
  const [results, sourceStatus] = await Promise.all([
    Promise.all(manifest.sections.map((e) => loadSection(e, manifest, cryptoKey))),
    loadSourceStatus(manifest, cryptoKey),
  ]);
  const sections = {};
  for (const r of results) sections[r.entry.id] = r;
  set({ sections, sourceStatus });
}

export function dropDecrypted() {
  const { manifest } = get();
  const sections = {};
  for (const [id, sec] of Object.entries(get().sections)) {
    sections[id] = sec.entry.encrypted
      ? { entry: sec.entry, status: sec.entry.file ? "locked" : "not_configured", payload: null }
      : sec;
  }
  const sourceStatus = manifest?.source_status_file?.endsWith(".enc.json")
    ? null : get().sourceStatus;
  set({ sections, sourceStatus });
}
