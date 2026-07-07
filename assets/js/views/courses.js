// Courses view: per-course upcoming work + recent announcements.

import { clear, el, safeHref } from "../dom.js";
import { fmtDateTime, fmtRelative, t } from "../i18n.js";
import { get } from "../store.js";
import { emptyCard, errorCard, lockedCard, notConfiguredCard } from "./shared.js";

export function render(container) {
  clear(container);
  const section = get().sections.courses;
  if (!section) return container.appendChild(emptyCard());
  if (section.status === "not_configured") return container.appendChild(notConfiguredCard());
  if (section.status === "locked") return container.appendChild(lockedCard());
  if (section.status === "error" || !section.payload) return container.appendChild(errorCard());

  const courses = section.payload.courses || [];
  if (!courses.length) return container.appendChild(emptyCard());

  for (const course of courses) {
    container.appendChild(el("section", { class: "course-card" },
      el("header", { class: "course-header" },
        el("h2", {},
          el("a", { href: safeHref(course.url), target: "_blank", rel: "noopener" },
            course.code ? `${course.code} · ${course.name}` : course.name)),
      ),
      el("div", { class: "course-columns" },
        el("div", { class: "course-col" },
          el("h3", {}, t("courses.upcoming")),
          course.upcoming?.length
            ? course.upcoming.map((a) => el("div", { class: `due-row${a.submitted ? " submitted" : ""}` },
                el("a", { class: "due-title", href: safeHref(a.url), target: "_blank", rel: "noopener" }, a.title),
                el("span", { class: "due-when", title: fmtDateTime(a.due_at, { year: "numeric" }) },
                  t("courses.due", { time: fmtRelative(a.due_at) })),
                a.points_possible != null
                  ? el("span", { class: "due-points" }, t("courses.points", { n: a.points_possible }))
                  : null,
                a.submitted ? el("span", { class: "due-submitted" }, `✓ ${t("courses.submitted")}`) : null,
              ))
            : el("p", { class: "muted" }, t("courses.noUpcoming")),
        ),
        el("div", { class: "course-col" },
          el("h3", {}, t("courses.announcements")),
          course.announcements?.length
            ? course.announcements.map((ann) => el("div", { class: "announcement" },
                el("a", { class: "ann-title", href: safeHref(ann.url), target: "_blank", rel: "noopener" }, ann.title),
                ann.posted_at ? el("time", { class: "ann-when", datetime: ann.posted_at },
                  fmtRelative(ann.posted_at)) : null,
                ann.snippet ? el("p", { class: "ann-snippet" }, ann.snippet) : null,
              ))
            : el("p", { class: "muted" }, t("courses.noAnnouncements")),
        ),
      ),
    ));
  }
}
