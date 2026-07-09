import json
from urllib.parse import parse_qs, urlparse

import responses

from newsdash.apropos import GDELT_DOC_URL, find_apropos_of_nothing
from newsdash.http import make_session

CHAT_URL = "https://api.openai.com/v1/chat/completions"


def make_payloads():
    return {
        "news": {"items": [
            {
                "title": "LLM benchmark reshapes coding assistants",
                "summary": "A model evaluation story.",
                "source": "AI Wire",
                "score": 0.9,
                "lang": "en",
            },
        ]},
        "papers": {"items": [
            {
                "title": "Visualization grammars for model evaluation",
                "summary": "A research paper about interfaces.",
                "source": "arXiv",
                "score": 0.8,
                "lang": "en",
            },
        ]},
    }


def query_completion():
    return {"choices": [{"message": {"content": json.dumps({
        "topic": "competitive pumpkin growing",
        "search_terms": ["pumpkin championship", "giant pumpkin"],
        "why_irrelevant": "Far away from AI and research feeds.",
    })}}]}


def summary_completion(choice=2):
    return {"choices": [{"message": {"content": json.dumps({
        "choice": choice,
        "summaries": {
            "en": {
                "summary": "A giant pumpkin contest crowned an unusually heavy winner.",
                "why_irrelevant": "A seasonal detour from model and research news.",
            },
            "zh": {
                "summary": "一场巨型南瓜比赛选出了特别沉的冠军。",
                "why_irrelevant": "它和模型、研究新闻相距很远。",
            },
        },
    })}}]}


def gdelt_response():
    return {
        "articles": [
            {
                "title": "Pumpkin festival opens downtown",
                "url": "https://example.com/festival",
                "domain": "example.com",
                "seendate": "20260708090000",
            },
            {
                "title": "Giant pumpkin champion breaks local record",
                "url": "https://example.org/pumpkin",
                "domain": "example.org",
                "seendate": "20260708100000",
                "snippet": "The winner weighed more than expected.",
            },
        ],
    }


def test_no_key_skips_without_call():
    assert find_apropos_of_nothing(make_payloads(), {}, make_session()) is None


@responses.activate
def test_kill_switch_skips_without_call():
    env = {"LLM_API_KEY": "sk-test", "APROPOS_OF_NOTHING_ENABLED": "0"}
    assert find_apropos_of_nothing(make_payloads(), env, make_session()) is None
    assert len(responses.calls) == 0


@responses.activate
def test_happy_path_searches_public_news_and_returns_card_payload():
    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, json=gdelt_response())
    responses.post(CHAT_URL, json=summary_completion())

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result["topic"] == "competitive pumpkin growing"
    assert result["source"] == {
        "title": "Giant pumpkin champion breaks local record",
        "url": "https://example.org/pumpkin",
        "name": "example.org",
        "published_at": "2026-07-08T10:00:00Z",
    }
    assert result["summaries"]["en"]["summary"].startswith("A giant pumpkin")
    assert result["summaries"]["zh"]["summary"].startswith("一场巨型南瓜")
    params = parse_qs(urlparse(responses.calls[1].request.url).query)
    assert params["query"] == ['("pumpkin championship" OR "giant pumpkin")']
    assert params["mode"] == ["artlist"]
    assert json.loads(responses.calls[0].request.body)["response_format"] == {
        "type": "json_object",
    }


@responses.activate
def test_gdelt_429_is_best_effort_skip(capsys):
    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, status=429)

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is None
    assert len(responses.calls) == 2
    out = capsys.readouterr().out
    assert "GDELT rate-limited (429)" in out
    assert "[apropos-of-nothing:search] error" not in out
