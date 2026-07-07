from datetime import datetime, timezone

from conftest import FIXED_NOW
from newsdash.fetchers.rss import parse_feed_bytes

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>AI model released</title><link>https://ex.com/a</link>
<pubDate>Mon, 06 Jul 2026 08:00:00 GMT</pubDate>
<description><![CDATA[<p>Big <b>news</b> summary</p>]]></description></item>
<item><title>Gardening tips</title><link>https://ex.com/b</link>
<pubDate>Mon, 06 Jul 2026 09:00:00 GMT</pubDate></item>
<item><title>Undated entry</title><link>https://ex.com/c</link></item>
</channel></rss>"""


def test_parse_basic(make_source):
    items = parse_feed_bytes(RSS, make_source(), FIXED_NOW)
    assert [i.title for i in items] == ["AI model released", "Gardening tips"]
    first = items[0]
    assert first.published_at == datetime(2026, 7, 6, 8, 0, tzinfo=timezone.utc)
    assert first.summary == "Big news summary"
    assert first.kind == "news"
    assert first.weight == 0.9


def test_keyword_filter(make_source):
    items = parse_feed_bytes(RSS, make_source(keywords=["AI"]), FIXED_NOW)
    assert [i.title for i in items] == ["AI model released"]
