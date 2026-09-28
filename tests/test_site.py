from datetime import datetime, timezone

from qrated import db
from qrated.config import Config
from qrated.feeds import parse_channel_image
from qrated.site import render_index, write_index

ITUNES_RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel><title>S</title>
<itunes:image href="http://x/cover.jpg"/><image><url>http://x/other.png</url></image></channel></rss>"""
PLAIN_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>S</title>
<image><url>http://x/other.png</url></image></channel></rss>"""


def test_parse_channel_image():
    assert parse_channel_image(ITUNES_RSS) == "http://x/cover.jpg"
    assert parse_channel_image(PLAIN_RSS) == "http://x/other.png"
    assert parse_channel_image(b"<rss><channel><title>S</title></channel></rss>") is None


def _seed(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO feeds (url, name, image_file) VALUES ('u1','Show <One>','abc.jpg')")
    conn.execute("INSERT INTO feeds (url, name) VALUES ('u2','Show Two')")
    conn.execute("INSERT INTO episodes (guid, feed_url, podcast, title, status) VALUES ('g','u1','Show <One>','Ep A','used')")
    conn.execute(
        "INSERT INTO editions (id, created_at, title, file_name, duration, size_bytes, description)"
        " VALUES (1, ?, 'Q-rated - Tuesday', 'qrated_x.mp3', 600, 1, '')",
        (datetime(2026, 9, 29, 6, 0, tzinfo=timezone.utc).isoformat(),),
    )
    conn.execute(
        "INSERT INTO items (episode_guid, title, summary, start_sec, end_sec, score, status, edition_id, position)"
        " VALUES ('g','Big <story>','A summary.',65,185,9,'used',1,1)"
    )
    conn.commit()
    return conn


def test_render_index(tmp_path):
    conn = _seed(tmp_path)
    page = render_index(conn, Config(feed_title="Q-rated", data_dir=tmp_path))
    assert 'src="editions/qrated_x.mp3"' in page  # player
    assert 'src="covers/abc.jpg"' in page  # channel thumb
    assert "Big &lt;story&gt;" in page and "Show &lt;One&gt;" in page  # escaped
    assert "1:05&ndash;3:05" in page
    assert "Podcasts included (2)" in page and "Show Two" in page  # inventory incl. feeds w/o cover
    assert "1 featured" in page


def test_render_index_chapters(tmp_path):
    import json
    import re

    conn = _seed(tmp_path)
    conn.execute("UPDATE items SET chapter_start=12.5, chapter_end=150")
    conn.commit()
    page = render_index(conn, Config(feed_title="Q-rated", data_dir=tmp_path))
    blob = re.search(r'<script type="application/json">(.*?)</script>', page).group(1)
    chapters = json.loads(blob)["chapters"]
    assert [c["kind"] for c in chapters] == ["intro", "item", "outro"]
    assert chapters[1]["start"] == 12.5 and chapters[1]["art"] == "covers/abc.jpg"
    assert chapters[1]["title"] == "Big <story>"  # raw in JSON, escaped when rendered by JS
    assert chapters[2] == {**chapters[2], "start": 150, "end": 600}
    assert 'data-chapter="1"' in page and '<span class="at">0:12</span>' in page
    assert 'class="seg k-item"' in page


def test_json_script_cannot_break_out(tmp_path):
    conn = _seed(tmp_path)
    conn.execute("UPDATE items SET title='</script><b>x', chapter_start=1, chapter_end=2")
    conn.commit()
    page = render_index(conn, Config(data_dir=tmp_path))
    assert "</script><b>x" not in page


def test_render_index_empty_and_write(tmp_path):
    conn = db.connect(tmp_path / "e.db")
    cfg = Config(data_dir=tmp_path / "d")
    path = write_index(conn, cfg)
    text = open(path, encoding="utf-8").read()
    assert "No editions yet" in text and text.startswith("<!doctype html>")


def test_db_migration_adds_cover_columns(tmp_path):
    import sqlite3

    old = sqlite3.connect(tmp_path / "old.db")
    old.execute("CREATE TABLE feeds (url TEXT PRIMARY KEY, name TEXT, first_seen TEXT, last_checked TEXT, last_error TEXT)")
    old.commit()
    old.close()
    conn = db.connect(tmp_path / "old.db")
    assert {"image_url", "image_file"} <= {r["name"] for r in conn.execute("PRAGMA table_info(feeds)")}
