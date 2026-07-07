// The Today view: a morning brief — schedule strip, due-soon course work,
// top stories by score, latest papers. Locked private blocks render a lock
// placeholder instead of leaking that they're empty.

import { renderAnnotationsIn } from "../annotate.js";
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

function storiesBlock() {
  const section = get().sections.news;
  if (!section || section.status !== "ok") return null;
  const top = [...(section.payload?.items || [])]
    .sort((a, b) => b.score - a.score).slice(0, 6);
  if (!top.length) return null;
  return block(t("today.topStories"), "news",
    el("div", { class: "story-grid" }, top.map((item) => itemCard(item, "news"))));
}

function papersBlock() {
  const section = get().sections.papers;
  if (!section || section.status !== "ok") return null;
  const latest = (section.payload?.items || []).slice(0, 5);
  if (!latest.length) return null;
  return block(t("today.latestPapers"), "papers",
    latest.map((item) => itemCard(item, "papers")));
}

export function render(container) {
  clear(container);
  const dateLabel = new Intl.DateTimeFormat(getLang() === "zh" ? "zh-CN" : "en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  }).format(new Date());
  container.appendChild(el("div", { class: "today-masthead" },
    el("h2", { class: "today-greeting" }, greeting()),
    el("p", { class: "today-date" }, dateLabel),
  ));
  const blocks = [scheduleBlock(), dueSoonBlock(), storiesBlock(), papersBlock()]
    .filter(Boolean);
  if (!blocks.length) container.appendChild(emptyCard());
  const grid = el("div", { class: "today-grid" }, blocks);
  container.appendChild(grid);
  renderAnnotationsIn(container);
}
