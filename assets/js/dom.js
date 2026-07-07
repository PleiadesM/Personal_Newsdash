// Tiny DOM builder. Feed content is untrusted — everything renders through
// textContent, never innerHTML.

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on")) {
      // functions only — a string here would become an inline handler
      if (typeof value === "function") node.addEventListener(key.slice(2), value);
    } else node.setAttribute(key, value);
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children) {
    if (child == null || child === false) continue;
    if (Array.isArray(child)) append(node, child);
    else if (child instanceof Node) node.appendChild(child);
    else node.appendChild(document.createTextNode(String(child)));
  }
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

// Feed/API-controlled URLs must never become javascript:/data: links.
export function safeHref(url) {
  return /^https?:\/\//i.test(url || "") ? url : "#";
}
