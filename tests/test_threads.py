import json

import responses

from newsdash.http import make_session
from newsdash.threads import THREADS_MAX_TOKENS, generate_threads

CHAT_URL = "https://api.openai.com/v1/chat/completions"


# ---- fixtures / builders ------------------------------------------------

def item(i, *, source_id="s1", source="Source One", section="news",
         kind="news", score=None, title=None, url=None, summary="a summary",
         full_text_file=None):
    d = {
        "id": f"item{i}",
        "title": title if title is not None else f"Title {i}",
        "url": url or f"https://ex.test/{i}",
        "source": source,
        "source_id": source_id,
        "section": section,
        "kind": kind,
        "score": (1.0 - i * 0.001) if score is None else score,
        "summary": summary,
    }
    if full_text_file:
        d["full_text_file"] = full_text_file
    return d


def payloads(items, *, kind="news", section="news"):
    return {section: {"meta": {"kind": kind, "section": section}, "items": items}}


def angle(n, en="an angle here", zh="角度"):
    return {"item": n, "phrase": {"en": en, "zh": zh}}


def thread(angles, *, keyword=None, gloss=None, why_now=None,
           convergence="convergent", relates_to=None):
    t = {
        "keyword": keyword or {"en": "keyword", "zh": "关键词"},
        "gloss": gloss or {"en": "a gloss", "zh": "一段释义"},
        "why_now": why_now or {"en": "why now", "zh": "此刻"},
        "convergence": convergence,
        "angles": angles,
    }
    if relates_to is not None:
        t["relates_to"] = relates_to
    return t


def completion(threads):
    return {"choices": [{"message":
            {"content": json.dumps({"threads": threads})}}]}


def two_source_payload(**item_kwargs):
    """Three news items across two sources (s1, s2), item1 first by score."""
    return payloads([
        item(1, source_id="s1", source="Alpha", **item_kwargs),
        item(2, source_id="s2", source="Beta"),
        item(3, source_id="s1", source="Alpha"),
    ])


ENV = {"LLM_API_KEY": "sk-test", "LLM_MODEL": "gpt-4o-mini"}


# ---- gates (zero HTTP) --------------------------------------------------

def test_no_api_key_makes_no_call():
    assert generate_threads(
        two_source_payload(), {}, make_session(), scope="public") is None


@responses.activate
def test_kill_switch_makes_no_call():
    env = {**ENV, "LLM_THREADS_ENABLED": "0"}
    assert generate_threads(
        two_source_payload(), env, make_session(), scope="public") is None
    assert len(responses.calls) == 0


@responses.activate
def test_empty_pool_makes_no_call():
    assert generate_threads(
        payloads([]), ENV, make_session(), scope="public") is None
    assert len(responses.calls) == 0


@responses.activate
def test_single_source_pool_makes_no_call():
    single = payloads([
        item(1, source_id="s1"), item(2, source_id="s1"), item(3, source_id="s1"),
    ])
    assert generate_threads(
        single, ENV, make_session(), scope="public") is None
    assert len(responses.calls) == 0


# ---- happy path ---------------------------------------------------------

@responses.activate
def test_happy_path_resolves_angles_and_ids():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(2)]),
        thread([angle(1), angle(2)]),
    ]))
    pay = two_source_payload(full_text_file="articles/news/item1.json")
    result = generate_threads(pay, ENV, make_session(), scope="public")

    assert result["scope"] == "public"
    assert len(result["threads"]) == 2
    assert [t["id"] for t in result["threads"]] == ["t1", "t2"]

    # exactly one POST, JSON mode, the wide token budget
    assert len(responses.calls) == 1
    body = json.loads(responses.calls[0].request.body)
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == THREADS_MAX_TOKENS
    assert body["model"] == "gpt-4o-mini"

    t1 = result["threads"][0]
    assert set(t1["keyword"]) == {"en", "zh"}
    assert set(t1["gloss"]) == {"en", "zh"}
    assert set(t1["why_now"]) == {"en", "zh"}
    # angle ground truth is embedded from the resolved item, not the model
    a0, a1 = t1["angles"]
    assert a0["item_id"] == "item1"
    assert a0["section"] == "news"
    assert a0["source"] == "Alpha"
    assert a0["url"] == "https://ex.test/1"
    assert a0["full_text_file"] == "articles/news/item1.json"
    # item2 has no full-text file -> the key is simply absent
    assert "full_text_file" not in a1
    assert a1["item_id"] == "item2"


@responses.activate
def test_private_scope_assigns_p_ids():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(2)]),
        thread([angle(1), angle(2)]),
    ]))
    pay = payloads([
        item(1, source_id="s1", section="career"),
        item(2, source_id="s2", section="career"),
    ], section="career")
    result = generate_threads(pay, ENV, make_session(), scope="private")
    assert result["scope"] == "private"
    assert [t["id"] for t in result["threads"]] == ["p1", "p2"]


# ---- input caps ---------------------------------------------------------

@responses.activate
def test_input_caps_news_and_papers_separately():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(2)]), thread([angle(1), angle(2)]),
    ]))
    news = [item(i, source_id=f"s{i % 2}", source=f"N{i}", title=f"News {i}")
            for i in range(35)]
    papers = [item(100 + i, source_id="p", source=f"P{i}", kind="paper",
                   title=f"Paper {i}", score=0.5 - i * 0.001)
              for i in range(20)]
    pay = {
        "news": {"meta": {"kind": "news"}, "items": news},
        "papers": {"meta": {"kind": "papers"}, "items": papers},
    }
    generate_threads(pay, ENV, make_session(), scope="public")
    prompt = json.loads(responses.calls[0].request.body)["messages"][1]["content"]
    # 30 news kept, 31st dropped
    assert "News 29" in prompt and "News 30" not in prompt
    # 12 papers kept, 13th dropped
    assert "Paper 11" in prompt and "Paper 12" not in prompt


@responses.activate
def test_private_pool_flat_cap():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(2)]), thread([angle(1), angle(2)]),
    ]))
    items = [item(i, source_id=f"s{i % 2}", title=f"Priv {i}",
                  score=1.0 - i * 0.001) for i in range(40)]
    generate_threads(payloads(items), ENV, make_session(), scope="private")
    prompt = json.loads(responses.calls[0].request.body)["messages"][1]["content"]
    assert "Priv 29" in prompt and "Priv 30" not in prompt


# ---- normalization / anti-hallucination --------------------------------

@responses.activate
def test_single_source_thread_dropped_others_kept():
    # thread B references two items from the SAME source -> < 2 distinct
    # sources -> dropped; the two valid threads survive.
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(2)]),
        thread([angle(1), angle(3)], keyword={"en": "SOLO", "zh": "独"}),
        thread([angle(1), angle(2)]),
    ]))
    result = generate_threads(
        two_source_payload(), ENV, make_session(), scope="public")
    assert len(result["threads"]) == 2
    assert all(t["keyword"]["en"] != "SOLO" for t in result["threads"])


@responses.activate
def test_out_of_range_ref_dropped():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(2), angle(99)]),
        thread([angle(1), angle(2), angle(99)]),
    ]))
    result = generate_threads(
        two_source_payload(), ENV, make_session(), scope="public")
    for t in result["threads"]:
        assert len(t["angles"]) == 2
        assert {a["item_id"] for a in t["angles"]} == {"item1", "item2"}


@responses.activate
def test_duplicate_item_ref_deduped():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(1), angle(2)]),
        thread([angle(1), angle(2)]),
    ]))
    result = generate_threads(
        two_source_payload(), ENV, make_session(), scope="public")
    assert [a["item_id"] for a in result["threads"][0]["angles"]] == ["item1", "item2"]


@responses.activate
def test_cap_at_max_threads():
    responses.post(CHAT_URL, json=completion(
        [thread([angle(1), angle(2)]) for _ in range(5)]))
    result = generate_threads(
        two_source_payload(), ENV, make_session(), scope="public", max_threads=2)
    assert len(result["threads"]) == 2


@responses.activate
def test_phrase_clipped_to_eight_words():
    long_en = "one two three four five six seven eight nine ten eleven"
    responses.post(CHAT_URL, json=completion([
        thread([angle(1, en=long_en), angle(2)]),
        thread([angle(1), angle(2)]),
    ]))
    result = generate_threads(
        two_source_payload(), ENV, make_session(), scope="public")
    phrase = result["threads"][0]["angles"][0]["phrase"]["en"]
    assert phrase == "one two three four five six seven eight…"


@responses.activate
def test_bad_convergence_coerced_to_mixed():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(2)], convergence="wildly-off"),
        thread([angle(1), angle(2)], convergence="divergent"),
    ]))
    result = generate_threads(
        two_source_payload(), ENV, make_session(), scope="public")
    assert result["threads"][0]["convergence"] == "mixed"
    assert result["threads"][1]["convergence"] == "divergent"


@responses.activate
def test_relates_to_resolved_self_and_dangling_dropped():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1), angle(2)], relates_to=[2, 1, 99]),
        thread([angle(1), angle(2)]),
    ]))
    result = generate_threads(
        two_source_payload(), ENV, make_session(), scope="public")
    # position 2 -> t2 kept; self (1) and dangling (99) dropped
    assert result["threads"][0]["relates_to"] == ["t2"]
    assert result["threads"][1]["relates_to"] == []


@responses.activate
def test_html_stripped_from_llm_strings():
    responses.post(CHAT_URL, json=completion([
        thread([angle(1, en="<b>bold</b> plain"), angle(2)],
               gloss={"en": "<i>italic</i> text", "zh": "释义"}),
        thread([angle(1), angle(2)]),
    ]))
    result = generate_threads(
        two_source_payload(), ENV, make_session(), scope="public")
    t0 = result["threads"][0]
    assert t0["gloss"]["en"] == "italic text"
    assert "<" not in t0["angles"][0]["phrase"]["en"]
    assert t0["angles"][0]["phrase"]["en"] == "bold plain"


# ---- failure modes ------------------------------------------------------

@responses.activate
def test_malformed_json_returns_none():
    responses.post(CHAT_URL, json={
        "choices": [{"message": {"content": "not json at all"}}]})
    assert generate_threads(
        two_source_payload(), ENV, make_session(), scope="public") is None


@responses.activate
def test_below_min_threads_returns_none():
    responses.post(CHAT_URL, json=completion([thread([angle(1), angle(2)])]))
    assert generate_threads(
        two_source_payload(), ENV, make_session(), scope="public") is None


@responses.activate
def test_http_error_public_returns_none():
    responses.post(CHAT_URL, status=500)
    assert generate_threads(
        two_source_payload(), ENV, make_session(), scope="public") is None


@responses.activate
def test_private_scope_error_withholds_detail(capsys):
    # A 500 body carrying a private marker title must never reach stdout on
    # the private path — public Actions logs. The public path may echo (masked)
    # detail, but the private path prints only the type name.
    marker = "ZZ_SECRET_PRIVATE_TITLE_ZZ"
    responses.post(CHAT_URL, status=500, body=marker)
    pay = payloads([
        item(1, source_id="s1", section="career", title=marker),
        item(2, source_id="s2", section="career"),
    ], section="career")
    result = generate_threads(pay, ENV, make_session(), scope="private")
    assert result is None
    out = capsys.readouterr().out
    assert marker not in out
    assert "[threads:private] error:" in out
    assert "(detail withheld)" in out
