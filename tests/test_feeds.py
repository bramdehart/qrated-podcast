from datetime import datetime, timedelta, timezone

from qrated import db
from qrated.feeds import load_feed_specs, parse_feed, pick_transcript, register_episodes

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
<channel><title>Show</title>
<item><title>E1</title><guid>g1</guid><pubDate>Mon, 21 Sep 2026 06:00:00 +0000</pubDate>
<enclosure url="http://x/1.mp3" type="audio/mpeg"/>
<podcast:transcript url="http://x/1.json" type="application/json"/>
<podcast:transcript url="http://x/1.srt" type="application/x-subrip"/>
<podcast:transcript url="http://x/1.vtt" type="text/vtt"/>
</item>
<item><title>E2</title><enclosure url="http://x/2.mp3" type="audio/mpeg"/></item>
<item><title>E3</title><guid>g3</guid><enclosure url="http://x/3.mp3"/>
<podcast:transcript url="http://x/3.html" type="text/html"/></item>
</channel></rss>"""


def test_parse_feed_prefers_vtt_and_guid_fallback():
    title, eps = parse_feed(RSS)
    assert title == "Show"
    assert eps[0].transcript_type == "vtt" and eps[0].transcript_url == "http://x/1.vtt"
    assert eps[1].guid == "http://x/2.mp3"  # falls back to enclosure URL
    assert eps[2].transcript_url is None  # html transcripts are unsupported


def test_pick_transcript_order():
    assert pick_transcript([("a.json", "application/json"), ("a.srt", "")]) == ("a.srt", "srt")
    assert pick_transcript([("a.txt", "text/plain")]) is None


def test_lookback_and_dedup(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    _, eps = parse_feed(RSS)
    now = datetime(2026, 9, 28, tzinfo=timezone.utc)
    assert register_episodes(conn, "u", "Show", eps, 7, now) == 3
    st = {r["guid"]: r["status"] for r in conn.execute("SELECT guid, status FROM episodes")}
    assert st["g1"] == "new"
    assert st["http://x/2.mp3"] == "no_transcript"
    # Older than lookback -> skipped
    conn2 = db.connect(tmp_path / "t2.db")
    register_episodes(conn2, "u", "Show", eps, 7, now + timedelta(days=30))
    assert conn2.execute("SELECT status FROM episodes WHERE guid='g1'").fetchone()[0] == "skipped"
    # Second registration adds nothing
    assert register_episodes(conn, "u", "Show", eps, 7, now) == 0


def test_load_feed_specs(tmp_path):
    p = tmp_path / "feeds.yaml"
    p.write_text("feeds:\n  - name: A\n    url: http://a\n  - http://b\n")
    specs = load_feed_specs(p)
    assert [(s.url, s.name) for s in specs] == [("http://a", "A"), ("http://b", None)]
