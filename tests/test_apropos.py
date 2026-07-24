import json
from urllib.parse import parse_qs, urlparse

import responses

import newsdash.apropos as apropos_mod
from newsdash.apropos import (
    GDELT_DOC_URL,
    GOOGLE_NEWS_RSS_URL,
    find_apropos_of_nothing,
)
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


def google_news_rss_body():
    # Two items: RFC-822 pubDates, per-item <source url="..."> publisher tags,
    # titles suffixed " - Publisher", and HTML-link descriptions that just
    # repeat the headline (as Google News actually emits).
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        "<title>Google News</title>"
        "<item>"
        "<title>Giant pumpkin weigh-off draws crowds - The Gazette</title>"
        "<link>https://news.google.com/rss/articles/item1</link>"
        "<pubDate>Wed, 08 Jul 2026 09:00:00 GMT</pubDate>"
        '<description>&lt;a href="https://news.google.com/rss/articles/item1"&gt;'
        "Giant pumpkin weigh-off draws crowds&lt;/a&gt;</description>"
        '<source url="https://gazette.example">The Gazette</source>'
        "</item>"
        "<item>"
        "<title>Pumpkin championship crowns record gourd - Rural Weekly</title>"
        "<link>https://news.google.com/rss/articles/item2</link>"
        "<pubDate>Wed, 08 Jul 2026 10:30:00 GMT</pubDate>"
        '<description>&lt;a href="https://news.google.com/rss/articles/item2"&gt;'
        "Pumpkin championship crowns record gourd&lt;/a&gt;</description>"
        '<source url="https://ruralweekly.example">Rural Weekly</source>'
        "</item>"
        "</channel></rss>"
    )


def empty_google_news_rss_body():
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>Google News</title></channel></rss>'
    )


def linkless_google_news_rss_body():
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>Google News</title>'
        "<item>"
        "<title>Headline with no link - The Gazette</title>"
        "<pubDate>Wed, 08 Jul 2026 09:00:00 GMT</pubDate>"
        "</item>"
        "</channel></rss>"
    )


def _patch_no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(apropos_mod, "GDELT_RETRY_SLEEPS", (0, 0))
    monkeypatch.setattr(apropos_mod.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


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
def test_gdelt_429_then_empty_fallback_is_best_effort_skip(capsys, monkeypatch):
    sleeps = _patch_no_sleep(monkeypatch)

    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GOOGLE_NEWS_RSS_URL, body=empty_google_news_rss_body(),
                 content_type="application/rss+xml")
    responses.get(GOOGLE_NEWS_RSS_URL, body=empty_google_news_rss_body(),
                 content_type="application/rss+xml")

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is None
    # 1 query LLM POST + 3 GDELT attempts + 2 Google News attempts (14d, 30d)
    assert len(responses.calls) == 6
    out = capsys.readouterr().out
    assert "GDELT rate-limited (429); giving up on GDELT this build" in out
    assert "will try again next build" not in out
    assert "falling back to Google News RSS" in out
    assert "retrying broadened" in out
    assert "skipped: Google News fallback had 0 results" in out
    assert "[apropos-of-nothing:search] error" not in out
    assert sleeps == [0, 0]


@responses.activate
def test_gdelt_429_falls_back_to_google_news(capsys, monkeypatch):
    _patch_no_sleep(monkeypatch)

    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GOOGLE_NEWS_RSS_URL, body=google_news_rss_body(),
                 content_type="application/rss+xml")
    responses.post(CHAT_URL, json=summary_completion())

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is not None
    # summary_completion picks choice=2 → the second RSS item.
    assert result["source"]["name"] == "Rural Weekly"
    assert result["source"]["title"] == "Pumpkin championship crowns record gourd"
    assert result["source"]["published_at"] == "2026-07-08T10:30:00Z"

    gn_call = next(c for c in responses.calls
                   if c.request.url.startswith(GOOGLE_NEWS_RSS_URL))
    params = parse_qs(urlparse(gn_call.request.url).query)
    assert params["q"] == ['"pumpkin championship" OR "giant pumpkin" when:14d']
    assert params["hl"] == ["en-US"]
    assert params["gl"] == ["US"]
    assert params["ceid"] == ["US:en"]

    out = capsys.readouterr().out
    assert "falling back to Google News RSS" in out


@responses.activate
def test_gdelt_zero_results_both_queries_falls_back(monkeypatch):
    _patch_no_sleep(monkeypatch)

    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, json={"articles": []})
    responses.get(GDELT_DOC_URL, json={"articles": []})
    responses.get(GOOGLE_NEWS_RSS_URL, body=google_news_rss_body(),
                 content_type="application/rss+xml")
    responses.post(CHAT_URL, json=summary_completion())

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is not None
    assert result["source"]["name"] == "Rural Weekly"


@responses.activate
def test_google_news_fallback_failure_returns_none(capsys, monkeypatch):
    _patch_no_sleep(monkeypatch)

    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GOOGLE_NEWS_RSS_URL, status=503)

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is None
    out = capsys.readouterr().out
    assert "skipped: Google News fallback error" in out
    assert "[apropos-of-nothing:search] error" not in out


@responses.activate
def test_google_news_fallback_all_invalid_items_returns_none(capsys, monkeypatch):
    _patch_no_sleep(monkeypatch)

    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GOOGLE_NEWS_RSS_URL, body=linkless_google_news_rss_body(),
                 content_type="application/rss+xml")
    responses.get(GOOGLE_NEWS_RSS_URL, body=linkless_google_news_rss_body(),
                 content_type="application/rss+xml")

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is None
    out = capsys.readouterr().out
    assert "skipped: Google News fallback had 0 results" in out


@responses.activate
def test_google_news_broadened_second_attempt_succeeds(capsys, monkeypatch):
    _patch_no_sleep(monkeypatch)

    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, json={"articles": []})
    responses.get(GDELT_DOC_URL, json={"articles": []})
    responses.get(GOOGLE_NEWS_RSS_URL, body=empty_google_news_rss_body(),
                 content_type="application/rss+xml")
    responses.get(GOOGLE_NEWS_RSS_URL, body=google_news_rss_body(),
                 content_type="application/rss+xml")
    responses.post(CHAT_URL, json=summary_completion())

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is not None
    assert result["source"]["name"] == "Rural Weekly"

    gn_calls = [c for c in responses.calls
                if c.request.url.startswith(GOOGLE_NEWS_RSS_URL)]
    assert len(gn_calls) == 2
    second_q = parse_qs(urlparse(gn_calls[1].request.url).query)["q"][0]
    assert '"' not in second_q
    assert "pumpkin championship OR giant pumpkin" in second_q
    assert second_q.endswith("when:30d")

    out = capsys.readouterr().out
    assert "retrying broadened" in out


@responses.activate
def test_gdelt_429_then_200_retries_and_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(apropos_mod, "GDELT_RETRY_SLEEPS", (0, 0))
    monkeypatch.setattr(apropos_mod.time, "sleep", lambda s: sleeps.append(s))

    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, status=429)
    responses.get(GDELT_DOC_URL, json=gdelt_response())
    responses.post(CHAT_URL, json=summary_completion())

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is not None
    assert result["topic"] == "competitive pumpkin growing"
    assert sleeps == [0]


@responses.activate
def test_gdelt_zero_results_retries_broadened_query(monkeypatch):
    sleeps = []
    monkeypatch.setattr(apropos_mod, "GDELT_RETRY_SLEEPS", (0, 0))
    monkeypatch.setattr(apropos_mod.time, "sleep", lambda s: sleeps.append(s))

    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, json={"articles": []})
    responses.get(GDELT_DOC_URL, json=gdelt_response())
    responses.post(CHAT_URL, json=summary_completion())

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is not None
    gdelt_calls = [c for c in responses.calls if c.request.url.startswith(GDELT_DOC_URL)]
    assert len(gdelt_calls) == 2
    second_params = parse_qs(urlparse(gdelt_calls[1].request.url).query)
    assert second_params["timespan"] == ["2weeks"]
    assert '"' not in second_params["query"][0]
    assert sleeps == []


@responses.activate
def test_llm_query_malformed_then_valid_retries_once(monkeypatch):
    sleeps = []
    monkeypatch.setattr(apropos_mod, "GDELT_RETRY_SLEEPS", (0, 0))
    monkeypatch.setattr(apropos_mod.time, "sleep", lambda s: sleeps.append(s))

    responses.post(CHAT_URL, json={"choices": [{"message": {"content": "{not json"}}]})
    responses.post(CHAT_URL, json=query_completion())
    responses.get(GDELT_DOC_URL, json=gdelt_response())
    responses.post(CHAT_URL, json=summary_completion())

    env = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}
    result = find_apropos_of_nothing(make_payloads(), env, make_session())

    assert result is not None
    assert result["topic"] == "competitive pumpkin growing"
    assert sleeps == []
