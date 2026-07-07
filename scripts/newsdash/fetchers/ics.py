"""ICS calendar fetcher (private). Calendar URLs are capability URLs —
possession grants read access — so they arrive only through the
ICS_SOURCES_B64 secret (base64 of a JSON array validated against
config/schema/ics-sources.schema.json) and are decoded in-process, never
written to disk. Error detail for calendars is reduced to exception class
names: requests exceptions can echo the URL.

Recurrence expansion is delegated to ``recurring_ical_events`` (RRULE,
RDATE, EXDATE, VTIMEZONE); never hand-roll it."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import icalendar
import jsonschema
import recurring_ical_events

from ..http import get
from ..models import Event


def _load_calendar_list(source, ctx) -> list[dict]:
    secret_name = source.secret_ref[0] if source.secret_ref else "ICS_SOURCES_B64"
    raw = ctx.env.get(secret_name, "")
    decoded = base64.b64decode(raw)
    calendars = json.loads(decoded)
    if ctx.repo_root is not None:
        schema_path = ctx.repo_root / "config" / "schema" / "ics-sources.schema.json"
        with open(schema_path, encoding="utf-8") as fh:
            jsonschema.validate(calendars, json.load(fh))
    return calendars


def _event_id(uid: str, start_repr: str) -> str:
    return hashlib.sha1(f"{uid}|{start_repr}".encode("utf-8")).hexdigest()[:16]


def _to_event(component, cal_cfg: dict, tz: ZoneInfo) -> Event | None:
    summary = str(component.get("SUMMARY", "")).strip() or "(untitled)"
    status = str(component.get("STATUS", "CONFIRMED")).lower()
    if status == "cancelled":
        return None

    dtstart = component.get("DTSTART")
    if dtstart is None:
        return None
    start_val = dtstart.dt
    dtend = component.get("DTEND")
    end_val = dtend.dt if dtend is not None else None

    all_day = isinstance(start_val, date) and not isinstance(start_val, datetime)
    if all_day:
        start_repr = start_val.isoformat()
        # DTEND on all-day events is exclusive; show the human last day
        if isinstance(end_val, date) and not isinstance(end_val, datetime):
            human_end = end_val - timedelta(days=1)
            end_repr = human_end.isoformat() if human_end > start_val else None
        else:
            end_repr = None
    else:
        start_repr = start_val.astimezone(tz).isoformat()
        end_repr = end_val.astimezone(tz).isoformat() if isinstance(end_val, datetime) else None

    uid = str(component.get("UID", summary))
    location = str(component.get("LOCATION", "")).strip() or None
    url = str(component.get("URL", "")).strip() or None
    recurring = component.get("RRULE") is not None or component.get("RECURRENCE-ID") is not None

    return Event(
        id=_event_id(uid, start_repr),
        calendar_id=cal_cfg["id"],
        calendar=cal_cfg["name"],
        title=summary,
        start=start_repr,
        end=end_repr,
        all_day=all_day,
        location=location,
        url=url,
        status=status,
        recurring=recurring,
    )


def fetch(source, ctx) -> dict:
    calendars = _load_calendar_list(source, ctx)
    tz = ZoneInfo(ctx.site.timezone)
    today = ctx.now.astimezone(tz).date()
    win = ctx.site.windows
    window_start = datetime.combine(
        today - timedelta(days=win.schedule_past_days), time.min, tzinfo=tz)
    window_end = datetime.combine(
        today + timedelta(days=win.schedule_horizon_days + 1), time.min, tzinfo=tz)

    events: list[Event] = []
    calendars_meta: list[dict] = []
    for cal_cfg in calendars:
        try:
            url = cal_cfg["url"].replace("webcal://", "https://", 1)
            resp = get(ctx.session, url)
            calendar = icalendar.Calendar.from_ical(resp.content)
            occurrences = recurring_ical_events.of(calendar).between(
                window_start, window_end)
            count = 0
            for component in occurrences:
                event = _to_event(component, cal_cfg, tz)
                if event is not None:
                    events.append(event)
                    count += 1
            calendars_meta.append({"id": cal_cfg["id"], "name": cal_cfg["name"],
                                   "ok": True, "count": count})
        except Exception as exc:  # noqa: BLE001 — class name only; URLs leak in messages
            calendars_meta.append({"id": cal_cfg.get("id", "?"),
                                   "name": cal_cfg.get("name", "?"),
                                   "ok": False, "count": 0,
                                   "error": type(exc).__name__})

    if calendars_meta and all(not c["ok"] for c in calendars_meta):
        raise RuntimeError("all calendars failed")
    return {"events": events, "calendars": calendars_meta}
