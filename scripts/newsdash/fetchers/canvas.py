"""Canvas LMS REST fetcher (private). Reads CANVAS_BASE_URL + CANVAS_TOKEN
from the environment (GitHub Secrets). The Authorization header is set per
request — never on the shared session, which other fetchers reuse for
arbitrary hosts.

Endpoints: active courses -> recent announcements -> upcoming assignments
(with the caller's own submission state). Pagination follows the
``Link: rel="next"`` headers with a hard page cap."""

from __future__ import annotations

from datetime import timedelta

from ..http import DEFAULT_TIMEOUT
from ..models import clip, strip_html

MAX_PAGES = 10
PER_PAGE = 100
ANNOUNCEMENT_LOOKBACK_DAYS = 14


def _get_paginated(session, url, *, params, headers) -> list:
    results: list = []
    for _ in range(MAX_PAGES):
        resp = session.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        page = resp.json()
        if not isinstance(page, list):
            raise ValueError("unexpected Canvas response shape")
        results.extend(page)
        next_link = resp.links.get("next", {}).get("url")
        if not next_link:
            break
        url, params = next_link, None  # the next URL carries its own params
    return results


def fetch(source, ctx) -> dict:
    base = ctx.env.get("CANVAS_BASE_URL", "").strip().rstrip("/")
    token = ctx.env.get("CANVAS_TOKEN", "").strip()
    if not base or not token:
        raise RuntimeError("canvas secrets missing")
    headers = {"Authorization": f"Bearer {token}"}
    session = ctx.session

    courses_raw = _get_paginated(
        session, f"{base}/api/v1/courses",
        params={"enrollment_state": "active", "per_page": PER_PAGE},
        headers=headers,
    )

    announce_since = (ctx.now - timedelta(days=ANNOUNCEMENT_LOOKBACK_DAYS)).date().isoformat()
    horizon = ctx.now + timedelta(days=ctx.site.windows.courses_horizon_days)

    courses: list[dict] = []
    for course in courses_raw:
        cid = course.get("id")
        name = (course.get("name") or "").strip()
        if not cid or not name:
            continue  # date-restricted enrollments come back as stubs

        announcements = []
        for ann in _get_paginated(
            session, f"{base}/api/v1/announcements",
            params={"context_codes[]": f"course_{cid}",
                    "start_date": announce_since, "per_page": 50},
            headers=headers,
        ):
            announcements.append({
                "id": ann.get("id"),
                "title": strip_html(ann.get("title", "")),
                "url": ann.get("html_url"),
                "posted_at": ann.get("posted_at"),
                "snippet": clip(strip_html(ann.get("message", "")), 240),
            })

        upcoming = []
        for assignment in _get_paginated(
            session, f"{base}/api/v1/courses/{cid}/assignments",
            params={"bucket": "upcoming", "order_by": "due_at",
                    "per_page": PER_PAGE, "include[]": "submission"},
            headers=headers,
        ):
            due_at = assignment.get("due_at")
            if not due_at or due_at > horizon.strftime("%Y-%m-%dT%H:%M:%SZ"):
                continue
            submission = assignment.get("submission") or {}
            upcoming.append({
                "id": assignment.get("id"),
                "type": "assignment",
                "title": strip_html(assignment.get("name", "")),
                "due_at": due_at,
                "points_possible": assignment.get("points_possible"),
                "url": assignment.get("html_url"),
                "submitted": bool(submission.get("submitted_at")),
            })
        upcoming.sort(key=lambda a: a["due_at"])

        courses.append({
            "id": cid,
            "code": (course.get("course_code") or "").strip(),
            "name": name,
            "url": f"{base}/courses/{cid}",
            "announcements": announcements,
            "upcoming": upcoming,
        })
    return {"courses": courses}
