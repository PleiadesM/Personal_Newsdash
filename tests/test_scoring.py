from datetime import datetime, timedelta, timezone

from newsdash.config import TagRule
from newsdash.models import Item
from newsdash.scoring import apply_tags, keyword_relevance, recency_score, score_item

NOW = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)


def make_item(title="Title", summary="", hours_ago=1.0, weight=0.8, kind="news"):
    return Item(
        id="x", title=title, url="https://e.com", source="S", source_id="s",
        category="open", section="news", kind=kind,
        published_at=NOW - timedelta(hours=hours_ago),
        summary=summary, weight=weight,
    )


def test_recency_monotonic():
    older = recency_score(NOW - timedelta(hours=24), NOW, 12)
    newer = recency_score(NOW - timedelta(hours=1), NOW, 12)
    assert newer > older > 0


def test_future_dates_score_full():
    assert recency_score(NOW + timedelta(hours=1), NOW, 12) == 1.0


def test_keyword_relevance():
    item = make_item(title="LLM visualization toolkit", summary="a study")
    assert keyword_relevance(item, [], 0.15) == 0.0
    one = keyword_relevance(item, ["visualization"], 0.15)
    two = keyword_relevance(item, ["visualization", "llm"], 0.15)
    assert 0 < one < two <= 1.0


def test_score_item_combination():
    hot = make_item(title="data visualization news", hours_ago=0.5, weight=1.0)
    cold = make_item(title="unrelated", hours_ago=40, weight=0.4)
    score_item(hot, NOW, ["data visualization"], 0.15)
    score_item(cold, NOW, ["data visualization"], 0.15)
    assert hot.score > cold.score
    assert 0 <= cold.score <= 1 and 0 <= hot.score <= 1


def test_apply_tags_max_and_match():
    item = make_item(title="Introducing our new API release",
                     summary="open source developer tools")
    rules = [
        TagRule("model-release", ["introducing", "release"]),
        TagRule("dev-tools", ["api", "sdk"]),
        TagRule("nope", ["quantum bagel"]),
    ]
    apply_tags(item, rules)
    assert item.tags == ["model-release", "dev-tools"]
