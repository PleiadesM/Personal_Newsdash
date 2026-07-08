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
    assert "q=automatons" in responses.calls[0].request.url


@responses.activate
def test_no_cc0_media_anywhere_returns_none():
    only_restricted = json.loads((FIX / "search_response.json").read_text())
    only_restricted["response"]["rows"] = [only_restricted["response"]["rows"][0]]
    responses.get(SEARCH_URL, json=only_restricted)
    env = {"SMITHSONIAN_API_KEY": "dg-test"}
    assert find_todays_image("automatons", env, make_session()) is None


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
