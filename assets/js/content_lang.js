// Content-language helpers. The interface language now also selects which
// news/research items and AI summaries are visible.

import { getLang } from "./i18n.js";

export function contentLang() {
  return getLang() === "zh" ? "zh" : "en";
}

export function itemMatchesContentLang(item) {
  return (item?.lang || "en") === contentLang();
}

export function filterItemsForContentLang(items) {
  return (items || []).filter(itemMatchesContentLang);
}

export function localizedInsights(insights) {
  if (!insights) return null;
  const lang = contentLang();
  return insights.summaries?.[lang]
    || (lang === "en"
      ? {
          brief: insights.brief,
          news_summary: insights.news_summary,
          papers_summary: insights.papers_summary,
        }
      : null);
}
