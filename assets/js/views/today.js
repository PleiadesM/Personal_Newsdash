// The Today view: a morning brief — numeric overview strip, schedule strip,
// due-soon course work, top stories by score, top papers, followed scholars.
// Locked private blocks render a lock placeholder instead of leaking that
// they're empty.

import { renderAnnotationsIn } from "../annotate.js";
import { favoriteIdSet } from "../annodb.js";
import { clear, el, safeHref } from "../dom.js";
import { fmtDate, fmtDateTime, fmtRelative, fmtTime, getLang, t } from "../i18n.js";
import { get } from "../store.js";
import { itemCard } from "./feed.js";
import { emptyCard, lockedCard } from "./shared.js";

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
  const top = [...(section.payload?.items || [])]
    .sort((a, b) => b.score - a.score).slice(0, 6);
  if (!top.length) return null;
  const summary = get().insights?.news_summary;
  return block(t("today.topStories"), "news",
    summary ? el("p", { class: "ai-summary-line" }, summary) : null,
    el("div", { class: "story-grid" }, top.map((item) => itemCard(item, "news", cardOpts))));
}

function papersBlock(cardOpts) {
  const section = get().sections.papers;
  if (!section || section.status !== "ok") return null;
  // priority order: the best-scored (recency · relevance · citations) first
  const top = [...(section.payload?.items || [])]
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 5);
  if (!top.length) return null;
  const summary = get().insights?.papers_summary;
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
  const top = [...(section.payload?.items || [])]
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
    .flatMap((s) => s.payload.items);
  if (!feedItems.length) return null;

  const todayKey = localDay(new Date().toISOString());
  const newToday = feedItems.filter((i) => localDay(i.published_at) === todayKey).length;
  const zh = feedItems.filter((i) => i.lang === "zh").length;
  const en = feedItems.length - zh;

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
    zh && en ? tile(`${en} EN · ${zh} 中文`, t("overview.languages")) : null,
    unlocked && favCount != null
      ? el("a", { class: "stat-tile", href: "#/favorites" },
          el("span", { class: "stat-num" }, `★ ${favCount}`),
          el("span", { class: "stat-label" }, t("overview.favorites")))
      : null,
  ];
  return el("div", { class: "overview-strip" }, tiles);
}

export async function render(container) {
  const unlocked = get().unlocked;
  const favs = unlocked ? await favoriteIdSet() : null;
  clear(container);
  const dateLabel = new Intl.DateTimeFormat(getLang() === "zh" ? "zh-CN" : "en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  }).format(new Date());
  container.appendChild(el("div", { class: "today-masthead" },
    el("h2", { class: "today-greeting" }, greeting()),
    el("p", { class: "today-date" }, dateLabel),
  ));
  const brief = get().insights?.brief;
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
