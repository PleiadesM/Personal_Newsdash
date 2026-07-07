from datetime import datetime, timedelta, timezone

from newsdash.dedupe import canonical_url, dedupe_items, title_fingerprint
from newsdash.models import Item

NOW = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)


def make_item(source_id, title, url, *, doi=None, arxiv_id=None, weight=0.8,
              minutes_ago=10):
    extra = {}
    if doi:
        extra["doi"] = doi
    if arxiv_id:
        extra["arxiv_id"] = arxiv_id
    return Item(
        id=f"{source_id}-{title[:8]}", title=title, url=url,
        source=source_id, source_id=source_id, category="open",
        section="news", kind="news",
        published_at=NOW - timedelta(minutes=minutes_ago),
        weight=weight, extra=extra,
    )


def test_canonical_url_strips_tracking():
    url = "http://www.Example.com/post/?utm_source=x&fbclid=abc&b=2&a=1"
    assert canonical_url(url) == "https://example.com/post?a=1&b=2"


def test_canonical_url_trailing_slash_and_fragment():
    assert canonical_url("https://example.com/a/#top") == "https://example.com/a"


def test_title_fingerprint_normalizes():
    assert title_fingerprint("Hello,  World!") == title_fingerprint("hello world")
    assert title_fingerprint("ＡＩ新闻") == title_fingerprint("ai新闻")


def test_url_dedupe_merges_and_records_also_in():
    a = make_item("src_a", "Big model announcement today", "https://ex.com/p?utm_source=rss",
                  weight=1.0)
    b = make_item("src_b", "Big model announcement today!!", "https://www.ex.com/p/",
                  weight=0.5)
    winners = dedupe_items([a, b])
    assert len(winners) == 1
    assert winners[0].source_id == "src_a"  # higher weight wins
    assert winners[0].extra["also_in"] == [{"source": "src_b", "url": b.url}]


def test_paper_dedupe_across_three_apis():
    arxiv = make_item("arxiv", "A Grammar of Interactive Graphics Revisited",
                      "https://arxiv.org/abs/2507.01234",
                      arxiv_id="2507.01234", weight=1.0)
    openalex = make_item("openalex", "A grammar of interactive graphics revisited",
                         "https://doi.org/10.1145/999",
                         doi="10.1145/999", arxiv_id="2507.01234", weight=0.9)
    s2 = make_item("s2", "A Grammar of Interactive Graphics Revisited",
                   "https://semanticscholar.org/paper/xyz",
                   doi="10.1145/999", weight=0.8)
    winners = dedupe_items([arxiv, openalex, s2])
    assert len(winners) == 1
    assert winners[0].source_id == "arxiv"
    assert len(winners[0].extra["also_in"]) == 2


def test_short_fingerprints_do_not_collide():
    a = make_item("a", "Hi", "https://one.example/x")
    b = make_item("b", "Hi", "https://two.example/y")
    assert len(dedupe_items([a, b])) == 2
