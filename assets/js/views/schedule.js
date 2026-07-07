// Agenda view: events grouped by local day.

import { clear, el } from "../dom.js";
import { fmtDate, fmtTime, t } from "../i18n.js";
import { get } from "../store.js";
import { emptyCard, errorCard, lockedCard, notConfiguredCard } from "./shared.js";

function localDay(iso) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso;
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function render(container) {
  clear(container);
  const section = get().sections.schedule;
  if (!section) return container.appendChild(emptyCard());
  if (section.status === "not_configured") return container.appendChild(notConfiguredCard());
  if (section.status === "locked") return container.appendChild(lockedCard());
  if (section.status === "error" || !section.payload) return container.appendChild(errorCard());

  const events = section.payload.events || [];
  if (!events.length) return container.appendChild(
    el("p", { class: "muted" }, t("schedule.empty")));

  const calendars = section.payload.meta?.calendars || [];
  if (calendars.length > 1) {
    container.appendChild(el("p", { class: "calendar-legend muted" },
      `${t("schedule.calendars")}: ${calendars.map((c) => c.name).join(" · ")}`));
  }

  const groups = new Map();
  for (const event of events) {
    const day = localDay(event.start);
    if (!groups.has(day)) groups.set(day, []);
    groups.get(day).push(event);
  }

  for (const [day, dayEvents] of [...groups.entries()].sort()) {
    container.appendChild(el("section", { class: "agenda-day" },
      el("h3", { class: "agenda-date" }, fmtDate(day, { year: "numeric" })),
      dayEvents.map((event) => el("div", { class: "event-row" },
        el("span", { class: "event-time" },
          event.all_day
            ? t("today.allDay")
            : `${fmtTime(event.start)}${event.end ? `–${fmtTime(event.end)}` : ""}`),
        el("span", { class: "event-title" }, event.title),
        event.location ? el("span", { class: "event-loc" }, event.location) : null,
        el("span", { class: "event-cal" }, event.calendar),
      )),
    ));
  }
}
