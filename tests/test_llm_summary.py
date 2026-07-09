import json

import responses

from newsdash.http import make_session
from newsdash.summarize import summarize

CHAT_URL = "https://api.openai.com/v1/chat/completions"


def make_payloads(news=None, papers=None):
    return {
        "news": {"items": news or []},
        "papers": {"items": papers or []},
    }


def completion(**overrides):
    payload = {
        "brief": "English brief",
        "news_summary": "English news",
        "papers_summary": "English papers",
        "image_query": "clockwork automatons",
    }
    payload.update(overrides)
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


def mock_summary_responses(en=None, zh=None):
    responses.post(CHAT_URL, json=completion(**(en or {})))
    responses.post(CHAT_URL, json=completion(**(zh or {
        "brief": "中文简报",
        "news_summary": "中文新闻",
        "papers_summary": "中文论文",
        "image_query": "compass clock",
    })))


def news_item(i, score=0.5, lang="en"):
    return {
        "title": f"Story {i}", "summary": "...", "source": "S",
        "score": score, "lang": lang,
    }


def paper_item(i, score=0.5, lang="en"):
    return {
        "title": f"Paper {i}", "summary": "...", "source": "S",
        "score": score, "lang": lang,
    }


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
def test_happy_path_returns_bilingual_summaries():
    mock_summary_responses()
    payloads = make_payloads(
        news=[news_item(i) for i in range(30)] + [news_item("中文", lang="zh")],
        papers=[paper_item(i) for i in range(15)] + [paper_item("中文", lang="zh")],
    )
    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = summarize(payloads, env, make_session())
    assert result.keys() == {
        "summaries", "brief", "news_summary", "papers_summary", "image_query",
    }
    assert result["summaries"]["en"] == {
        "brief": "English brief",
        "news_summary": "English news",
        "papers_summary": "English papers",
    }
    assert result["summaries"]["zh"] == {
        "brief": "中文简报",
        "news_summary": "中文新闻",
        "papers_summary": "中文论文",
    }
    # top-level fields remain as an English/default compatibility fallback
    assert result["brief"] == "English brief"
    assert result["image_query"] == "clockwork automatons"

    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer sk-test"
    body = json.loads(req.body)
    assert body["model"] == "gpt-4o-mini"
    assert body["response_format"] == {"type": "json_object"}
    # capped: only the first MAX_NEWS_ITEMS/MAX_PAPER_ITEMS appear in the prompt
    prompt = body["messages"][1]["content"]
    assert "Story 19" in prompt and "Story 20" not in prompt
    assert "Paper 9" in prompt and "Paper 10" not in prompt
    assert "Priority English news" in prompt
    assert "Story 中文" in prompt

    zh_body = json.loads(responses.calls[1].request.body)
    assert "Simplified Chinese edition" in zh_body["messages"][0]["content"]
    assert "Priority Simplified Chinese news" in zh_body["messages"][1]["content"]
    assert "Context from English news" in zh_body["messages"][1]["content"]


@responses.activate
def test_markdown_fenced_json_is_unwrapped():
    # some OpenAI-compatible providers still fence JSON in ```json ... ```
    # even with response_format set — must not break parsing.
    fenced = "```json\n" + json.dumps({
        "brief": "b", "news_summary": "n", "papers_summary": "p",
        "image_query": "q",
    }) + "\n```"
    responses.post(CHAT_URL, json={"choices": [{"message": {"content": fenced}}]})
    responses.post(CHAT_URL, json={"choices": [{"message": {"content": fenced}}]})
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test"}
    result = summarize(payloads, env, make_session())
    assert result["summaries"] == {
        "en": {"brief": "b", "news_summary": "n", "papers_summary": "p"},
        "zh": {"brief": "b", "news_summary": "n", "papers_summary": "p"},
    }
    assert result["image_query"] == "q"


@responses.activate
def test_malformed_json_content_returns_none():
    responses.post(CHAT_URL, json={
        "choices": [{"message": {"content": "not json at all"}}],
    })
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
    responses.post(CHAT_URL, json={
        "choices": [{"message": {"content": json.dumps({"brief": "x"})}}],
    })
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test"}
    assert summarize(payloads, env, make_session()) is None


@responses.activate
def test_empty_completion_content_returns_none(capsys):
    # Reasoning-capable models can burn the whole token budget on hidden
    # chain-of-thought and come back with an empty `content` and
    # finish_reason="length" — must not surface as a confusing
    # JSONDecodeError("Expecting value: line 1 column 1 (char 0)").
    responses.post(CHAT_URL, json={
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
    })
    responses.post(CHAT_URL, json={
        "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
    })
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test"}
    assert summarize(payloads, env, make_session()) is None
    err = capsys.readouterr().out
    assert "finish_reason=length" in err


@responses.activate
def test_http_error_returns_none():
    responses.post(CHAT_URL, status=500)
    responses.post(CHAT_URL, status=500)
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test"}
    assert summarize(payloads, env, make_session()) is None


@responses.activate
def test_empty_string_base_url_falls_back_to_default():
    # GitHub Actions sets an env var to "" (not absent) when a workflow
    # references ${{ vars.X }} for a Variable that was never created —
    # env.get(key, default) would NOT catch this (the key exists), only
    # `or default` does. Regression test for exactly that failure mode
    # (surfaced in production as requests.exceptions.MissingSchema).
    mock_summary_responses()
    payloads = make_payloads(news=[news_item(1)])
    env = {"LLM_API_KEY": "sk-test", "LLM_BASE_URL": "", "LLM_MODEL": ""}
    result = summarize(payloads, env, make_session())
    assert result is not None
    assert responses.calls[0].request.url == CHAT_URL
    assert json.loads(responses.calls[0].request.body)["model"] == "gpt-4o-mini"
