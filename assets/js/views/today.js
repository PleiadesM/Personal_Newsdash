// The Today view: a morning brief — numeric overview strip, schedule strip,
// due-soon course work, top stories by score, top papers, followed scholars.
// Locked private blocks render a lock placeholder instead of leaking that
// they're empty.

import { renderAnnotationsIn } from "../annotate.js";
import { favoriteIdSet } from "../annodb.js";
import { filterItemsForContentLang, localizedInsights } from "../content_lang.js";
import { clear, el, safeHref } from "../dom.js";
import { fmtDate, fmtDateTime, fmtRelative, fmtTime, getLang, t } from "../i18n.js";
import { get } from "../store.js";
import { itemCard, itemLinkAttrs, toggleFavorite } from "./feed.js";
import { emptyCard, lockedCard } from "./shared.js";

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

function eventRow(event) {
  return el("div", { class: "event-row" },
    el("span", { class: "event-time" },
      event.all_day ? t("today.allDay") : fmtTime(event.start)),
    el("span", { class: "event-title" }, event.title),
    event.location ? el("span", { class: "event-loc" }, event.location) : null,
  );
}

function scheduleBlock() {
  const section = get().sections.schedule;
  if (!section || section.status === "not_configured") return null;
  if (section.status === "locked") return block(t("today.schedule"), "schedule", lockedCard());
  const events = section.payload?.events || [];
  const todayKey = localDay(new Date().toISOString());
  const tomorrowKey = localDay(new Date(Date.now() + 86400_000).toISOString());
  const groups = [[t("today.today"), todayKey], [t("today.tomorrow"), tomorrowKey]]
    .map(([label, key]) => [label, events.filter((e) => localDay(e.start) === key)]);
  return block(t("today.schedule"), "schedule",
    groups.map(([label, dayEvents]) =>
      el("div", { class: "day-group" },
        el("h3", { class: "day-label" }, label),
        dayEvents.length
          ? dayEvents.map(eventRow)
          : el("p", { class: "muted" }, t("today.noEvents")),
      )),
  );
}

function dueSoonBlock() {
  const section = get().sections.courses;
  if (!section || section.status === "not_configured") return null;
  if (section.status === "locked") return block(t("today.dueSoon"), "courses", lockedCard());
  const horizon = Date.now() + 7 * 86400_000;
  const due = (section.payload?.courses || [])
    .flatMap((c) => (c.upcoming || []).map((a) => ({ ...a, course: c.code || c.name })))
    .filter((a) => a.due_at && new Date(a.due_at).getTime() <= horizon && !a.submitted)
    .sort((a, b) => a.due_at.localeCompare(b.due_at));
  return block(t("today.dueSoon"), "courses",
    due.length
      ? due.slice(0, 6).map((a) => el("div", { class: "due-row" },
          el("span", { class: "due-course" }, a.course),
          el("a", { class: "due-title", href: safeHref(a.url), target: "_blank", rel: "noopener" }, a.title),
          el("span", { class: "due-when", title: fmtDateTime(a.due_at) },
            fmtRelative(a.due_at)),
        ))
      : el("p", { class: "muted" }, t("today.noDue")),
  );
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

function followingBlock(cardOpts) {
  const section = get().sections.following;
  if (!section || section.status !== "ok") return null;
  const top = filterItemsForContentLang(section.payload?.items || [])
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 5);
  if (!top.length) return null;
  return block(t("nav.following"), "following",
    top.map((item) => itemCard(item, "following", cardOpts)));
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
      ? el("a", { class: "stat-tile", href: "#/favorites" },
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

  const feedSection = theTypeFeedSection(favs);
  if (feedSection) {
    feedSection.classList.add("nd-fadein", "nd-fadein-d1");
    container.appendChild(feedSection);
  }

  const cardOpts = { favs };
  const restBlocks = [scheduleBlock(), dueSoonBlock(), papersBlock(cardOpts), followingBlock(cardOpts)]
    .filter(Boolean);
  if (restBlocks.length) {
    container.appendChild(el("div", { class: "today-grid nd-fadein nd-fadein-d2" }, restBlocks));
  } else if (!grid && !feedSection) {
    container.appendChild(emptyCard());
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
  const blocks = [scheduleBlock(), dueSoonBlock(), todaysImageBlock(),
                  storiesBlock(cardOpts), papersBlock(cardOpts), followingBlock(cardOpts)]
    .filter(Boolean);
  if (!blocks.length) container.appendChild(emptyCard());
  const grid = el("div", { class: "today-grid" }, blocks);
  container.appendChild(grid);
  renderAnnotationsIn(container);
}
