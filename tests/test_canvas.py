import json
from pathlib import Path

import pytest
import responses

from newsdash.fetchers import canvas as canvas_fetcher

FIX = Path(__file__).parent / "fixtures" / "canvas"
BASE = "https://canvas.example.edu"


def _fixture(name):
    return json.loads((FIX / name).read_text())


def _source(make_source):
    return make_source(id="canvas", category="private", type="canvas",
                       section="courses",
                       secret_ref=["CANVAS_BASE_URL", "CANVAS_TOKEN"])


def _env():
    return {"CANVAS_BASE_URL": BASE, "CANVAS_TOKEN": "tok-123"}


@responses.activate
def test_canvas_courses_pagination_and_shape(make_ctx, make_source):
    page2 = f"{BASE}/api/v1/courses?page=2&per_page=100"
    responses.get(f"{BASE}/api/v1/courses", json=_fixture("courses_page1.json"),
                  headers={"Link": f'<{page2}>; rel="next"'})
    responses.get(page2, json=_fixture("courses_page2.json"))
    responses.get(f"{BASE}/api/v1/announcements",
                  json=_fixture("announcements_118234.json"))
    responses.get(f"{BASE}/api/v1/courses/118234/assignments",
                  json=_fixture("assignments_118234.json"))
    responses.get(f"{BASE}/api/v1/announcements", json=[])
    responses.get(f"{BASE}/api/v1/courses/220001/assignments", json=[])

    result = canvas_fetcher.fetch(_source(make_source), make_ctx(env=_env()))
    courses = result["courses"]
    assert [c["id"] for c in courses] == [118234, 220001]  # stub 999999 dropped

    engl = courses[0]
    assert engl["code"] == "ENGL 5920C"
    assert engl["url"] == f"{BASE}/courses/118234"
    assert engl["announcements"][0]["snippet"] == \
        "Presentations begin next Tuesday . Sign-up sheet is posted."

    upcoming = engl["upcoming"]
    assert [a["id"] for a in upcoming] == [556, 555]  # sorted by due_at
    assert upcoming[0]["submitted"] is True
    assert upcoming[1]["submitted"] is False
    # 557 (no due date) and 558 (beyond the 30-day horizon) are excluded
    assert all(a["id"] not in (557, 558) for a in upcoming)


@responses.activate  # no endpoints registered: any HTTP call would explode
def test_missing_secrets_makes_no_network_call(make_ctx, make_source):
    with pytest.raises(RuntimeError):
        canvas_fetcher.fetch(_source(make_source), make_ctx(env={}))
    assert len(responses.calls) == 0


@responses.activate
def test_auth_header_sent_per_request(make_ctx, make_source):
    responses.get(f"{BASE}/api/v1/courses", json=[])
    canvas_fetcher.fetch(_source(make_source), make_ctx(env=_env()))
    assert responses.calls[0].request.headers["Authorization"] == "Bearer tok-123"
