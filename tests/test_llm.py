import json

import responses

from newsdash.http import make_session
from newsdash.llm import post_chat, resolve_extra_body

CHAT_URL = "https://api.openai.com/v1/chat/completions"


def completion(content="ok"):
    return {"choices": [{"message": {"content": content}}]}


# --- resolve_extra_body ---------------------------------------------------

def test_resolve_extra_body_valid_object():
    env = {"LLM_EXTRA_BODY": '{"thinking": {"type": "disabled"}}'}
    assert resolve_extra_body(env) == {"thinking": {"type": "disabled"}}


def test_resolve_extra_body_missing_env():
    assert resolve_extra_body({}) == {}


def test_resolve_extra_body_empty_string():
    assert resolve_extra_body({"LLM_EXTRA_BODY": ""}) == {}


def test_resolve_extra_body_whitespace_only():
    assert resolve_extra_body({"LLM_EXTRA_BODY": "   "}) == {}


def test_resolve_extra_body_invalid_json():
    assert resolve_extra_body({"LLM_EXTRA_BODY": "{not json"}) == {}


def test_resolve_extra_body_json_array_is_ignored():
    assert resolve_extra_body({"LLM_EXTRA_BODY": "[1]"}) == {}


def test_resolve_extra_body_json_string_is_ignored():
    assert resolve_extra_body({"LLM_EXTRA_BODY": '"x"'}) == {}


# --- post_chat body merge --------------------------------------------------

@responses.activate
def test_post_chat_merges_extra_body_keys():
    responses.post(CHAT_URL, json=completion())
    post_chat(
        "https://api.openai.com/v1", "sk-test", "gpt-4o-mini",
        [{"role": "user", "content": "hi"}], make_session(),
        extra_body={"thinking": {"type": "disabled"}},
    )
    body = json.loads(responses.calls[0].request.body)
    assert body["thinking"] == {"type": "disabled"}
    assert body["model"] == "gpt-4o-mini"


@responses.activate
def test_post_chat_core_keys_win_over_extra_body():
    responses.post(CHAT_URL, json=completion())
    post_chat(
        "https://api.openai.com/v1", "sk-test", "gpt-4o-mini",
        [{"role": "user", "content": "hi"}], make_session(),
        json_mode=True, max_tokens=999,
        extra_body={
            "model": "should-not-win",
            "max_tokens": 1,
            "response_format": {"type": "text"},
        },
    )
    body = json.loads(responses.calls[0].request.body)
    assert body["model"] == "gpt-4o-mini"
    assert body["max_tokens"] == 999
    assert body["response_format"] == {"type": "json_object"}


@responses.activate
def test_post_chat_extra_body_none_behaves_as_before():
    responses.post(CHAT_URL, json=completion())
    post_chat(
        "https://api.openai.com/v1", "sk-test", "gpt-4o-mini",
        [{"role": "user", "content": "hi"}], make_session(),
        extra_body=None,
    )
    body = json.loads(responses.calls[0].request.body)
    assert body == {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 2000,
    }
