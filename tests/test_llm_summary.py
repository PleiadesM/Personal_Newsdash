import json
from pathlib import Path

import responses

from newsdash.http import make_session
from newsdash.summarize import summarize

FIX = Path(__file__).parent / "fixtures" / "llm"
CHAT_URL = "https://api.openai.com/v1/chat/completions"


def make_payloads(news=None, papers=None):
    return {
        "news": {"items": news or []},
        "papers": {"items": papers or []},
    }


def news_item(i, score=0.5):
    return {"title": f"Story {i}", "summary": "…", "source": "S", "score": score}


def paper_item(i, score=0.5):
    return {"title": f"Paper {i}", "summary": "…", "source": "S", "score": score}


def test_no_api_key_makes_no_call():
    payloads = make_payloads(news=[news_item(1)])
    assert summarize(payloads, {}, make_session()) is None


@responses.activate
def test_kill_switch_makes_no_call():
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test", "LLM_SUMMARY_ENABLED": "0"}
    assert summarize(payloads, env, make_session()) is None
    assert len(responses.calls) == 0


def test_empty_items_skips_without_call():
    payloads = make_payloads()
    env = {"LLM_API_KEY": "sk-test"}
    assert summarize(payloads, env, make_session()) is None


@responses.activate
def test_happy_path_returns_all_four_keys():
    responses.post(CHAT_URL, body=(FIX / "chat_completion.json").read_text())
    payloads = make_payloads(
        news=[news_item(i) for i in range(30)],
        papers=[paper_item(i) for i in range(15)],
    )
    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = summarize(payloads, env, make_session())
    assert result.keys() == {"brief", "news_summary", "papers_summary", "image_query"}
    assert result["image_query"] == "clockwork automatons"

    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer sk-test"
    body = json.loads(req.body)
    assert body["model"] == "gpt-4o-mini"
    # capped: only the first MAX_NEWS_ITEMS/MAX_PAPER_ITEMS appear in the prompt
    prompt = body["messages"][1]["content"]
    assert "Story 19" in prompt and "Story 20" not in prompt
    assert "Paper 9" in prompt and "Paper 10" not in prompt


@responses.activate
def test_malformed_json_content_returns_none():
    responses.post(CHAT_URL, json={
        "choices": [{"message": {"content": "not json at all"}}],
    })
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test"}
    assert summarize(payloads, env, make_session()) is None


@responses.activate
def test_missing_key_in_json_returns_none():
    responses.post(CHAT_URL, json={
        "choices": [{"message": {"content": json.dumps({"brief": "x"})}}],
    })
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test"}
    assert summarize(payloads, env, make_session()) is None


@responses.activate
def test_http_error_returns_none():
    responses.post(CHAT_URL, status=500)
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test"}
    assert summarize(payloads, env, make_session()) is None
