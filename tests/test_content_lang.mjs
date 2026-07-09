// Active UI language is also the feed content language.

globalThis.document = {
  documentElement: {
    lang: "en",
    attrs: {},
    setAttribute(name, value) {
      this.attrs[name] = value;
    },
  },
};

const { setLang } = await import("../assets/js/i18n.js");
const {
  contentLang,
  filterItemsForContentLang,
  localizedInsights,
} = await import("../assets/js/content_lang.js");

const items = [
  { id: "en", lang: "en" },
  { id: "zh", lang: "zh" },
  { id: "implicit-en" },
];

setLang("en", { persist: false });
if (contentLang() !== "en") throw new Error("expected English content lang");
if (filterItemsForContentLang(items).map((i) => i.id).join(",") !== "en,implicit-en") {
  throw new Error("English mode should show only English items");
}

setLang("zh", { persist: false });
if (contentLang() !== "zh") throw new Error("expected Chinese content lang");
if (filterItemsForContentLang(items).map((i) => i.id).join(",") !== "zh") {
  throw new Error("Chinese mode should show only Chinese items");
}

const insights = {
  summaries: {
    en: { brief: "EN", news_summary: "EN news", papers_summary: "EN papers" },
    zh: { brief: "ZH", news_summary: "ZH news", papers_summary: "ZH papers" },
  },
  brief: "legacy",
};
if (localizedInsights(insights).brief !== "ZH") {
  throw new Error("Chinese mode should use summaries.zh");
}

setLang("en", { persist: false });
if (localizedInsights({ brief: "legacy" }).brief !== "legacy") {
  throw new Error("English mode should support legacy scalar insights");
}

setLang("zh", { persist: false });
if (localizedInsights({ brief: "legacy" }) !== null) {
  throw new Error("Chinese mode should not render legacy English-only insights");
}

console.log("OK content language helpers");
