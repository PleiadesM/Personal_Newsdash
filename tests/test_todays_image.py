import json
from pathlib import Path

import responses

from newsdash.http import make_session
from newsdash.todays_image import caption_todays_image, find_todays_image

FIX = Path(__file__).parent / "fixtures" / "smithsonian"
SEARCH_URL = "https://api.si.edu/openaccess/api/v1.0/search"
CHAT_URL = "https://api.openai.com/v1/chat/completions"


def test_no_api_key_makes_no_call():
    assert find_todays_image("automatons", {}, make_session()) is None


def test_no_image_query_makes_no_call():
    env = {"SMITHSONIAN_API_KEY": "dg-test"}
    assert find_todays_image("", env, make_session()) is None


@responses.activate
def test_kill_switch_makes_no_call():
    env = {"SMITHSONIAN_API_KEY": "dg-test", "TODAYS_IMAGE_ENABLED": "0"}
    assert find_todays_image("automatons", env, make_session()) is None
    assert len(responses.calls) == 0


@responses.activate
def test_happy_path_extracts_first_cc0_row():
    responses.get(SEARCH_URL, body=(FIX / "search_response.json").read_text())
    env = {"SMITHSONIAN_API_KEY": "dg-test"}
    image = find_todays_image("automatons", env, make_session())
    assert image["title"] == "Automaton Clock"
    assert image["source_name"] == "Cooper Hewitt, Smithsonian Design Museum"
    assert image["source_url"] == "https://www.si.edu/object/chndm_1931-45-37"
    assert image["image_url"] == "https://ids.si.edu/ids/deliveryService?id=chndm_1931"
    assert "api_key=dg-test" in responses.calls[0].request.url
    req_url = responses.calls[0].request.url
    assert "q=automatons" in req_url
    # Most Smithsonian records have no digitized media at all — the search
    # must itself be narrowed to media-bearing records, not rely on media
    # happening to appear in the first page of a bare keyword search. There
    # is no confirmed-documented CC0 search filter field (unlike
    # online_media_type), so a wider `rows` compensates instead —
    # `_first_cc0_image` remains the sole authority on the CC0 check.
    assert "online_media_type%3AImages" in req_url
    assert "rows=100" in req_url


@responses.activate
def test_multiword_query_ors_the_individual_terms():
    # A literal multi-word phrase (even a concrete one) rarely matches
    # museum catalog metadata verbatim — OR the terms so a hit on any one
    # of them is enough, instead of requiring the full phrase to co-occur.
    responses.get(SEARCH_URL, body=(FIX / "search_response.json").read_text())
    env = {"SMITHSONIAN_API_KEY": "dg-test"}
    find_todays_image("clockwork automatons", env, make_session())
    req_url = responses.calls[0].request.url
    assert "q=%28clockwork+OR+automatons%29+AND+online_media_type%3AImages" in req_url


@responses.activate
def test_no_cc0_media_anywhere_returns_none(capsys):
    only_restricted = json.loads((FIX / "search_response.json").read_text())
    only_restricted["response"]["rows"] = [only_restricted["response"]["rows"][0]]
    responses.get(SEARCH_URL, json=only_restricted)
    env = {"SMITHSONIAN_API_KEY": "dg-test"}
    assert find_todays_image("automatons", env, make_session()) is None
    # Must be distinguishable in the log from a real misconfiguration —
    # this is "ran fine, no CC0 media for this phrase," not an error.
    assert "no CC0 image for query 'automatons'" in capsys.readouterr().out


@responses.activate
def test_http_error_returns_none():
    responses.get(SEARCH_URL, status=500)
    env = {"SMITHSONIAN_API_KEY": "dg-test"}
    assert find_todays_image("automatons", env, make_session()) is None


IMAGE = {
    "image_url": "https://ids.si.edu/x",
    "thumbnail_url": "https://ids.si.edu/x_thumb",
    "title": "Automaton Clock",
    "source_name": "Cooper Hewitt",
    "source_url": "https://www.si.edu/object/x",
}


def test_caption_no_api_key_makes_no_call():
    assert caption_todays_image(IMAGE, "Some story", {}, make_session()) is None


@responses.activate
def test_caption_happy_path():
    responses.post(CHAT_URL, json={
        "choices": [{"message": {
            "content": "Both remind us that clever machines have always captured our imagination.",
        }}],
    })
    env = {"LLM_API_KEY": "sk-test"}
    caption = caption_todays_image(IMAGE, "AI agents ship today", env, make_session())
    assert caption == "Both remind us that clever machines have always captured our imagination."


@responses.activate
def test_caption_http_error_returns_none():
    responses.post(CHAT_URL, status=500)
    env = {"LLM_API_KEY": "sk-test"}
    assert caption_todays_image(IMAGE, "Some story", env, make_session()) is None


@responses.activate
def test_caption_empty_string_base_url_falls_back_to_default():
    # Same GitHub-Actions-empty-string-Variable regression as
    # test_llm_summary.py — `or default`, not `.get(key, default)`.
    responses.post(CHAT_URL, json={"choices": [{"message": {"content": "A caption."}}]})
    env = {"LLM_API_KEY": "sk-test", "LLM_BASE_URL": "", "LLM_MODEL": ""}
    caption = caption_todays_image(IMAGE, "Some story", env, make_session())
    assert caption == "A caption."
    assert responses.calls[0].request.url == CHAT_URL
