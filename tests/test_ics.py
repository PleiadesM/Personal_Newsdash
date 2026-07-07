import base64
import json
from pathlib import Path

import pytest
import responses

from newsdash.fetchers import ics as ics_fetcher

FIX = Path(__file__).parent / "fixtures" / "ics"


def _b64(calendars) -> str:
    return base64.b64encode(json.dumps(calendars).encode()).decode()


def _source(make_source):
    return make_source(id="ics_calendars", category="private", type="ics",
                       section="schedule", secret_ref=["ICS_SOURCES_B64"])


@responses.activate
def test_ics_expansion_and_timezones(make_ctx, make_source):
    responses.get("https://cal.example/google.ics",
                  body=(FIX / "google_utc.ics").read_text())
    responses.get("https://cal.example/outlook.ics",
                  body=(FIX / "outlook_rrule.ics").read_text())
    env = {"ICS_SOURCES_B64": _b64([
        {"id": "gcal", "name": "Google", "url": "https://cal.example/google.ics"},
        {"id": "outlook", "name": "Outlook", "url": "https://cal.example/outlook.ics"},
    ])}
    result = ics_fetcher.fetch(_source(make_source), make_ctx(env=env))
    events = result["events"]
    titles = [e.title for e in events]

    adv = next(e for e in events if e.title == "Advisor meeting")
    assert adv.start == "2026-07-07T10:00:00-05:00"  # 15:00Z in America/Chicago (CDT)
    assert adv.location == "Ross 203"
    assert not adv.all_day

    trip = next(e for e in events if e.title == "Conference trip")
    assert trip.all_day
    assert trip.start == "2026-07-10"
    assert trip.end == "2026-07-11"  # exclusive DTEND 07-12 shown as last day

    assert "Far future outside window" not in titles
    assert "Cancelled thing" not in titles

    standups = sorted((e for e in events if e.title == "Lab standup"),
                      key=lambda e: e.start)
    assert [e.start for e in standups] == [
        "2026-07-06T14:00:00-05:00",  # EXDATE removed 07-13
        "2026-07-20T14:00:00-05:00",
    ]
    assert all(e.recurring for e in standups)

    metas = {c["id"]: c for c in result["calendars"]}
    assert metas["gcal"]["ok"] and metas["outlook"]["ok"]


@responses.activate
def test_one_dead_calendar_is_partial(make_ctx, make_source):
    responses.get("https://cal.example/google.ics",
                  body=(FIX / "google_utc.ics").read_text())
    responses.get("https://cal.example/dead.ics", status=404)
    env = {"ICS_SOURCES_B64": _b64([
        {"id": "gcal", "name": "Google", "url": "https://cal.example/google.ics"},
        {"id": "dead", "name": "Dead", "url": "https://cal.example/dead.ics"},
    ])}
    result = ics_fetcher.fetch(_source(make_source), make_ctx(env=env))
    metas = {c["id"]: c for c in result["calendars"]}
    assert metas["gcal"]["ok"]
    assert not metas["dead"]["ok"]
    assert metas["dead"]["error"] == "HTTPError"  # class name only, no URL


@responses.activate
def test_all_calendars_failing_raises(make_ctx, make_source):
    responses.get("https://cal.example/dead.ics", status=500)
    env = {"ICS_SOURCES_B64": _b64([
        {"id": "dead", "name": "Dead", "url": "https://cal.example/dead.ics"},
    ])}
    with pytest.raises(RuntimeError):
        ics_fetcher.fetch(_source(make_source), make_ctx(env=env))
