// The Today view: a morning brief — numeric overview strip, top stories by
// score, top papers, followed scholars. Locked private blocks render a lock
// placeholder instead of leaking that they're empty.

import { renderAnnotationsIn } from "../annotate.js";
import { favoriteIdSet } from "../annodb.js";
import { filterItemsForContentLang, localizedApropos, localizedInsights } from "../content_lang.js";
import { clear, el, safeHref } from "../dom.js";
import { fmtDate, fmtDateTime, fmtRelative, getLang, t } from "../i18n.js";
import { get } from "../store.js";
import { itemCard, itemLinkAttrs, toggleFavorite } from "./feed.js";
import { emptyCard, sectionLabel } from "./shared.js";

function isTheType() {
  return document.documentElement.dataset.theme === "the-type";
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return t("today.greetingMorning");
  if (hour < 18) return t("today.greetingAfternoon");
  return t("today.greetingEvening");
}

function block(title, route, ...children) {
  return el("section", { class: "today-block" },
    el("header", { class: "block-header" },
      el("h2", {}, title),
      route ? el("a", { class: "block-more", href: `#/${route}` }, t("today.more")) : null,
    ),
    ...children,
  );
}

function localDay(iso) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso;
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function storiesBlock(cardOpts) {
  const section = get().sections.news;
  if (!section || section.status !== "ok") return null;
  const top = filterItemsForContentLang(section.payload?.items || [])
    .sort((a, b) => b.score - a.score).slice(0, 6);
  if (!top.length) return null;
  const summary = localizedInsights(get().insights)?.news_summary;
  return block(t("today.topStories"), "news",
    summary ? el("p", { class: "ai-summary-line" }, summary) : null,
    el("div", { class: "story-grid" }, top.map((item) => itemCard(item, "news", cardOpts))));
}

function papersBlock(cardOpts) {
  const section = get().sections.papers;
  if (!section || section.status !== "ok") return null;
  // priority order: the best-scored (recency · relevance · citations) first
  const top = filterItemsForContentLang(section.payload?.items || [])
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 5);
  if (!top.length) return null;
  const summary = localizedInsights(get().insights)?.papers_summary;
  return block(t("today.latestPapers"), "papers",
    summary ? el("p", { class: "ai-summary-line" }, summary) : null,
    top.map((item) => itemCard(item, "papers", cardOpts)));
}

// AI-generated: a public-domain image (Smithsonian Open Access, CC0-only)
// loosely tied to today's content, with a one-sentence AI caption. Absent
// unless LLM_API_KEY + SMITHSONIAN_API_KEY are both configured server-side
// and a CC0 match was found this run — see docs/CONFIG_REFERENCE.md.
function todaysImageBlock() {
  const image = get().insights?.todays_image;
  if (!image) return null;
  return block(t("today.todaysImage"), null,
    el("figure", { class: "todays-image" },
      el("img", {
        src: safeHref(image.image_url), alt: image.title || "",
        loading: "lazy", referrerpolicy: "no-referrer",
      }),
      el("figcaption", {},
        el("p", { class: "todays-image-caption" }, image.caption),
        el("p", { class: "todays-image-source muted" },
          `${t("today.imageSource")} `,
          el("a", {
            href: safeHref(image.source_url), target: "_blank", rel: "noopener",
          }, image.title ? `${image.title} — ${image.source_name}` : image.source_name),
        ),
      ),
    ),
  );
}

function aproposOfNothingBlock() {
  const apropos = get().insights?.apropos_of_nothing;
  const text = localizedApropos(apropos);
  const source = apropos?.source;
  if (!text?.summary || !source?.url) return null;
  const sourceMeta = [
    source.name,
    source.published_at ? fmtDate(source.published_at) : null,
  ].filter(Boolean).join(" · ");
  return el("section", { class: "apropos-card", tabindex: "0" },
    el("div", { class: "apropos-kicker" }, t("today.aproposKicker")),
    el("div", { class: "apropos-body" },
      el("div", { class: "apropos-copy" },
        el("h2", { class: "apropos-title" }, t("today.aproposTitle")),
        apropos.topic ? el("p", { class: "apropos-topic" }, apropos.topic) : null,
        el("p", { class: "apropos-summary" }, text.summary),
        text.why_irrelevant
          ? el("p", { class: "apropos-why" }, text.why_irrelevant)
          : null,
      ),
      el("a", {
        class: "apropos-source",
        href: safeHref(source.url),
        target: "_blank",
        rel: "noopener noreferrer",
      },
        el("span", { class: "apropos-source-label" }, t("today.aproposSource")),
        el("span", { class: "apropos-source-title" }, source.title || source.url),
        sourceMeta ? el("span", { class: "apropos-source-meta" }, sourceMeta) : null,
      ),
    ),
  );
}

function followingBlock(cardOpts) {
  const section = get().sections.following;
  if (!section || section.status !== "ok") return null;
  const top = filterItemsForContentLang(section.payload?.items || [])
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 5);
  if (!top.length) return null;
  return block(sectionLabel("following"), "following",
    top.map((item) => itemCard(item, "following", cardOpts)));
}

// A config-driven mixed "Highlights" block: the highest-scored items pooled
// across every LOADED content section, with a per-source diversity cap so no
// single feed dominates. Driven by manifest.site.ranking (Stage D); renders
// nothing when highlights are off or there isn't enough variety. Gathers only
// status==="ok" sections (the locked/private guard) — never touches sections
// that aren't unlocked and loaded.
function highlightsBlock(cardOpts) {
  const ranking = get().manifest?.site?.ranking;
  if (!ranking || !ranking.highlights) return null;
  const maxPerSource = Math.max(1, ranking.max_per_source ?? 2);

  const pool = Object.values(get().sections)
    .filter((s) => s.status === "ok" && Array.isArray(s.payload?.items)
      && (s.entry?.kind === "news" || s.entry?.kind === "papers"))
    .flatMap((s) => filterItemsForContentLang(s.payload.items))
    .slice()
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

  const perSource = new Map();
  const picked = [];
  for (const item of pool) {
    if (picked.length >= 10) break;
    const key = item.source_id || item.source || "";
    const used = perSource.get(key) || 0;
    if (used >= maxPerSource) continue;
    perSource.set(key, used + 1);
    picked.push(item);
  }
  if (picked.length < 3) return null;

  return block(t("today.highlights"), null,
    el("div", { class: "story-grid" },
      picked.map((item) => itemCard(item, item.section || "news", cardOpts))));
}

// ---- AI "Threads · 线索" ---------------------------------------------------
// LLM-aggregated keywords across sources, each a bilingual foothold with
// per-source "return ticket" angles, a convergence glyph, a "why now"
// occasion line, and inter-thread links — replaces highlightsBlock() when
// present (graceful fallback otherwise). All thread text is untrusted LLM
// output: it renders only through el()/textContent, never innerHTML, and the
// glyph is static path data (never LLM-derived).

// Bilingual field picker: active UI/content language → en → zh → "".
function pickLang(bi) {
  if (!bi) return "";
  const lang = getLang();
  return bi[lang] || bi.en || bi.zh || "";
}

// 16×16 inline convergence glyph. SVG is built with createElementNS (el() is
// HTML-only). stroke="currentColor", static path data ONLY — never any
// LLM-derived text inside the SVG. Wrapped in a span carrying an accessible
// i18n title.
function convergenceGlyph(kind) {
  const SVG = "http://www.w3.org/2000/svg";
  // Path data per variant. All strokes read left → right toward the right edge.
  const paths = {
    // three strokes meeting toward a single right-edge point
    convergent: ["M1 3 L15 8", "M1 8 L15 8", "M1 13 L15 8"],
    // two meeting at the point + one crossing away from it
    mixed: ["M1 3 L15 8", "M1 13 L15 8", "M1 8 L15 2"],
    // three fanning out from a single left-edge point
    divergent: ["M1 8 L15 3", "M1 8 L15 8", "M1 8 L15 13"],
  };
  const variant = paths[kind] ? kind : "mixed";
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  svg.setAttribute("fill", "none");
  svg.setAttribute("aria-hidden", "true");
  for (const d of paths[variant]) {
    const p = document.createElementNS(SVG, "path");
    p.setAttribute("d", d);
    p.setAttribute("stroke", "currentColor");
    p.setAttribute("stroke-width", "1.25");
    p.setAttribute("stroke-linecap", "round");
    svg.appendChild(p);
  }
  const titleKey = {
    convergent: "today.threadConvergent",
    mixed: "today.threadMixed",
    divergent: "today.threadDivergent",
  }[variant];
  const span = el("span", { class: "thread-glyph", title: t(titleKey) });
  span.appendChild(svg);
  return span;
}

// One angle row: a two-way "return ticket". If full_text_file is present the
// link goes to the in-app reader (#/read/<section>/<item_id>); otherwise it
// opens the original in a new tab. Source and phrase are LLM/feed text →
// textContent only.
function angleRow(angle) {
  const link = angle.full_text_file
    ? el("a", { href: `#/read/${angle.section}/${angle.item_id}` })
    : el("a", { href: safeHref(angle.url), target: "_blank", rel: "noopener noreferrer" });
  link.appendChild(el("span", { class: "thread-angle-source" }, angle.source));
  link.appendChild(document.createTextNode(" — "));
  link.appendChild(el("span", { class: "thread-angle-phrase" }, pickLang(angle.phrase)));
  return el("li", { class: "thread-angle" }, link);
}

// One thread card. `list` is the full payload thread list (for resolving
// relates_to ids to their keyword labels). Angles are deliberately NOT run
// through filterItemsForContentLang — cross-language convergence is the point
// of the feature.
function threadCard(thread, isPrivate, list) {
  const card = el("article", {
    class: `thread-card${isPrivate ? " thread-card-private" : ""}`,
    dataset: { threadId: thread.id },
  },
    el("h3", { class: "thread-keyword" },
      pickLang(thread.keyword),
      convergenceGlyph(thread.convergence),
    ),
    el("p", { class: "thread-gloss" }, pickLang(thread.gloss)),
  );
  const whyNow = pickLang(thread.why_now);
  if (whyNow) {
    card.appendChild(el("p", { class: "thread-whynow" },
      el("span", { class: "thread-whynow-label" }, t("today.threadsWhyNow") + " "),
      whyNow));
  }
  const angles = (thread.angles || []).map(angleRow);
  if (angles.length) card.appendChild(el("ul", { class: "thread-angles" }, angles));

  const related = (thread.relates_to || [])
    .map((id) => list.find((x) => x.id === id))
    .filter(Boolean);
  if (related.length) {
    const touches = el("div", { class: "thread-touches" },
      el("span", { class: "thread-touches-label" }, t("today.threadsTouches") + " "));
    related.forEach((target, i) => {
      if (i) touches.appendChild(document.createTextNode(" · "));
      touches.appendChild(el("span", {
        class: "thread-touch",
        role: "button",
        tabindex: "0",
        onclick: () => scrollToThread(target.id),
        onkeydown: (e) => {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); scrollToThread(target.id); }
        },
      }, pickLang(target.keyword)));
    });
    card.appendChild(touches);
  }
  return card;
}

function scrollToThread(id) {
  const target = document.querySelector(`[data-thread-id="${CSS.escape(id)}"]`);
  if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
}

// The Threads block: public threads always; private-scope threads only while
// unlocked (no teaser when locked). Null when empty → caller falls back to
// highlightsBlock().
function threadsBlock() {
  const threads = get().threads;
  if (!threads) return null;
  const list = (threads.public?.threads || [])
    .concat(get().unlocked ? (threads.private?.threads || []) : []);
  if (!list.length) return null;
  const privateIds = new Set((threads.private?.threads || []).map((x) => x.id));
  const cards = list.map((thT) => threadCard(thT, privateIds.has(thT.id), list));
  return block(t("today.threads"), null, el("div", { class: "threads-grid" }, cards));
}

// AI-News-Radar-style numeric overview: fresh count, totals, source health,
// language split, favorites. Computed client-side from loaded sections so
// encrypted-section counts never leak into public files.
function overviewStrip(favCount) {
  const { sections, sourceStatus, unlocked } = get();
  const feedItems = Object.values(sections)
    .filter((s) => s.status === "ok" && Array.isArray(s.payload?.items))
    .flatMap((s) => filterItemsForContentLang(s.payload.items));
  if (!feedItems.length) return null;

  const todayKey = localDay(new Date().toISOString());
  const newToday = feedItems.filter((i) => localDay(i.published_at) === todayKey).length;

  const tile = (value, label) => el("div", { class: "stat-tile" },
    el("span", { class: "stat-num" }, value),
    el("span", { class: "stat-label" }, label));

  const active = (sourceStatus?.sources || []).filter((s) => !s.skip_reason);
  const tiles = [
    tile(String(newToday), t("overview.newToday")),
    tile(String(feedItems.length), t("overview.items")),
    active.length
      ? tile(`${active.filter((s) => s.ok).length}/${active.length}`, t("overview.sourcesOk"))
      : null,
    unlocked && favCount != null
      ? el("a", { class: "stat-tile", href: "#/clippings/favorites" },
          el("span", { class: "stat-num" }, `★ ${favCount}`),
          el("span", { class: "stat-label" }, t("overview.favorites")))
      : null,
  ];
  return el("div", { class: "overview-strip" }, tiles);
}

// ---- the-type theme: hero + numbered-feed Today layout --------------------
// A structurally different Today layout for the-type only (see
// assets/themes/the-type.css); nyt/bear keep the masthead+overview-strip
// layout below untouched.

function heroDateParts() {
  const now = new Date();
  const locale = getLang() === "zh" ? "zh-CN" : "en-US";
  return {
    weekday: new Intl.DateTimeFormat(locale, { weekday: "long" }).format(now),
    mainDate: new Intl.DateTimeFormat(locale, { month: "long", day: "numeric" }).format(now),
    subDate: new Intl.DateTimeFormat(locale, { year: "numeric", month: "long", day: "numeric" }).format(now),
  };
}

function heroImageBlock(image) {
  return el("div", { class: "hero-image" },
    el("img", {
      src: safeHref(image.image_url), alt: image.title || "",
      loading: "lazy", referrerpolicy: "no-referrer",
    }),
    el("div", { class: "hero-image-caption" },
      el("span", { class: "hero-image-kicker" }, t("today.photoOfTheDay")),
      el("p", { class: "hero-image-text" },
        `${image.caption} · `,
        el("a", {
          href: safeHref(image.source_url), target: "_blank", rel: "noopener",
        }, image.title ? `${image.title} — ${image.source_name}` : image.source_name),
      ),
    ),
  );
}

// Distinct from overviewStrip()'s numeric strip (nyt/bear): the hero pills
// surface a simpler cut — how much ran through the feed today — matching
// the mockup, computed the same client-side way (no private-count leaks).
function statsPills() {
  const feedItems = Object.values(get().sections)
    .filter((s) => s.status === "ok" && Array.isArray(s.payload?.items))
    .flatMap((s) => filterItemsForContentLang(s.payload.items));
  if (!feedItems.length) return null;
  const sourceCount = new Set(feedItems.map((i) => i.source)).size;
  const topicCount = new Set(feedItems.flatMap((i) => i.tags || [])).size;
  const tile = (value, label) => el("div", { class: "stat-tile" },
    el("span", { class: "stat-num" }, String(value)),
    el("span", { class: "stat-label" }, label));
  return el("div", { class: "stats-pills" },
    tile(feedItems.length, t("overview.articles")),
    tile(sourceCount, t("overview.sources")),
    topicCount ? tile(topicCount, t("overview.topics")) : null,
  );
}

function heroGrid() {
  const image = get().insights?.todays_image;
  const brief = localizedInsights(get().insights)?.brief;
  const stats = statsPills();
  if (!image && !brief && !stats) return null;
  const right = (brief || stats)
    ? el("div", { class: "hero-right" },
        brief ? el("div", { class: "hero-summary" },
          el("div", { class: "hero-summary-label" }, t("today.aiSummaryLabel")),
          el("p", { class: "hero-summary-text" }, brief),
        ) : null,
        stats,
      )
    : null;
  const children = [image ? heroImageBlock(image) : null, right].filter(Boolean);
  return children.length ? el("div", { class: "hero-grid" }, children) : null;
}

function featuredArticleCard(item, favs) {
  const starred = favs?.has(item.id);
  return el("article", {
    class: `item featured-article kind-${item.kind}`,
    dataset: { itemId: item.id, sectionId: "news" },
    lang: item.lang === "zh" ? "zh-CN" : undefined,
  },
    el("div", { class: "item-meta" },
      el("span", { class: "featured-label" }, t("today.featured")),
      el("span", { class: "item-source" }, item.source),
      el("time", {
        datetime: item.published_at,
        title: fmtDateTime(item.published_at, { year: "numeric" }),
      }, fmtRelative(item.published_at)),
      item.full_text_available
        ? el("span", { class: "full-text-badge" }, t("feed.fullTextAvailable"))
        : null,
      typeof item.score === "number"
        ? el("span", { class: "item-score" }, item.score.toFixed(2)) : null,
      favs
        ? el("button", {
            class: `fav-star${starred ? " active" : ""}`,
            title: starred ? t("fav.remove") : t("fav.add"),
            "aria-pressed": String(Boolean(starred)),
            onclick: (e) => toggleFavorite(item, "news", favs, e.currentTarget),
          }, starred ? "★" : "☆")
        : null,
    ),
    el("h2", { class: "item-title" },
      el("a", {
        ...itemLinkAttrs(item, "news"),
        "data-annotatable": "",
      }, item.title),
    ),
    item.summary ? el("p", { class: "item-summary", "data-annotatable": "" }, item.summary) : null,
    item.full_text_available
      ? el("div", { class: "item-tags" },
          el("a", {
            class: "original-link",
            href: safeHref(item.url),
            target: "_blank",
            rel: "noopener noreferrer",
          }, t("feed.original")))
      : null,
  );
}

function theTypeFeedSection(favs) {
  const section = get().sections.news;
  if (!section || section.status !== "ok") return null;
  const top = filterItemsForContentLang(section.payload?.items || [])
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 6);
  if (!top.length) return null;
  const [featured, ...rest] = top;
  const cardOpts = { favs };
  return el("div", { class: "the-type-feed" },
    el("h2", { class: "feed-section-header" }, t("today.todaysFeed")),
    featuredArticleCard(featured, favs),
    rest.length
      ? el("div", { class: "item-list" }, rest.map((item) => itemCard(item, "news", cardOpts)))
      : null,
  );
}

function renderTheType(container, favs) {
  const { weekday, mainDate, subDate } = heroDateParts();
  const hero = el("div", { class: "hero-section nd-fadein" },
    el("div", { class: "hero-date-row" },
      el("div", {},
        el("div", { class: "hero-weekday" }, weekday),
        el("div", { class: "hero-date" }, mainDate),
        el("div", { class: "hero-date-sub" }, subDate),
      ),
      el("div", { class: "hero-greeting" },
        el("span", { class: "hero-greeting-dot" }),
        el("span", { class: "hero-greeting-text" }, greeting()),
      ),
    ),
  );
  const grid = heroGrid();
  if (grid) hero.appendChild(grid);
  container.appendChild(hero);

  const highlights = threadsBlock() || highlightsBlock({ favs });
  if (highlights) {
    highlights.classList.add("nd-fadein", "nd-fadein-d1");
    container.appendChild(highlights);
  }

  const feedSection = theTypeFeedSection(favs);
  if (feedSection) {
    feedSection.classList.add("nd-fadein", "nd-fadein-d1");
    container.appendChild(feedSection);
  }

  const cardOpts = { favs };
  const restBlocks = [papersBlock(cardOpts), followingBlock(cardOpts)]
    .filter(Boolean);
  const apropos = aproposOfNothingBlock();
  if (restBlocks.length) {
    container.appendChild(el("div", { class: "today-grid nd-fadein nd-fadein-d2" }, restBlocks));
  } else if (!grid && !feedSection && !apropos) {
    container.appendChild(emptyCard());
  }
  if (apropos) {
    apropos.classList.add("nd-fadein", "nd-fadein-d2");
    container.appendChild(apropos);
  }
}

export async function render(container) {
  const unlocked = get().unlocked;
  const favs = unlocked ? await favoriteIdSet() : null;
  clear(container);
  if (isTheType()) {
    renderTheType(container, favs);
    renderAnnotationsIn(container);
    return;
  }
  const dateLabel = new Intl.DateTimeFormat(getLang() === "zh" ? "zh-CN" : "en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  }).format(new Date());
  container.appendChild(el("div", { class: "today-masthead" },
    el("h2", { class: "today-greeting" }, greeting()),
    el("p", { class: "today-date" }, dateLabel),
  ));
  const brief = localizedInsights(get().insights)?.brief;
  if (brief) {
    container.appendChild(el("div", { class: "ai-brief-block" },
      el("p", { class: "ai-brief-label" }, `✨ ${t("today.aiSummaryLabel")}`),
      el("p", { class: "ai-brief-text" }, brief),
    ));
  }
  const strip = overviewStrip(favs ? favs.size : null);
  if (strip) container.appendChild(strip);
  const cardOpts = { favs };
  const blocks = [threadsBlock() || highlightsBlock(cardOpts), todaysImageBlock(),
                  storiesBlock(cardOpts), papersBlock(cardOpts), followingBlock(cardOpts)]
    .filter(Boolean);
  const apropos = aproposOfNothingBlock();
  if (!blocks.length && !apropos) container.appendChild(emptyCard());
  if (blocks.length) {
    container.appendChild(el("div", { class: "today-grid" }, blocks));
  }
  if (apropos) container.appendChild(apropos);
  renderAnnotationsIn(container);
}
