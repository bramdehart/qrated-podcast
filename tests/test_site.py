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


def _data(page):
    import json
    import re

    return json.loads(re.search(r'<script type="application/json" id="qrated-data">(.*?)</script>', page).group(1))


def test_render_index_sheet_and_fallback(tmp_path):
    conn = _seed(tmp_path)
    page = render_index(conn, Config(feed_title="Q-rated", data_dir=tmp_path))
    assert 'href="editions/qrated_x.mp3" download' in page  # episode download in the info sheet
    assert 'src="editions/qrated_x.mp3"' in page  # <noscript> fallback player
    assert 'src="covers/abc.jpg"' in page  # show thumbnails
    assert "Big &lt;story&gt;" in page and "Show &lt;One&gt;" in page  # escaped in HTML
    assert "Shows in the mix <small>2</small>" in page and "Show Two" in page
    assert 'data-goto="1"' in page and 'class="feed"' in page


def test_slides_from_chapters(tmp_path):
    conn = _seed(tmp_path)
    conn.execute("UPDATE items SET chapter_start=12.5, chapter_end=150")
    conn.commit()
    data = _data(render_index(conn, Config(feed_title="Q-rated", data_dir=tmp_path)))
    assert data["slides"] == [{
        "ed": 1, "n": 0, "start": 12.5, "end": 150, "title": "Big <story>", "podcast": "Show <One>",
        "summary": "A summary.", "episode": "Ep A", "art": "covers/abc.jpg",
    }]
    assert data["editions"][0]["file"] == "editions/qrated_x.mp3" and data["editions"][0]["count"] == 1


def test_edition_without_chapters_is_one_full_slide(tmp_path):
    conn = _seed(tmp_path)
    data = _data(render_index(conn, Config(data_dir=tmp_path)))
    (slide,) = data["slides"]
    assert slide["start"] == 0 and slide["end"] == 600 and slide["episode"] == "Full episode"
    assert "Big <story>" in slide["summary"]


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
    assert "No episodes yet" in text and text.startswith("<!doctype html>")


def test_db_migration_adds_cover_columns(tmp_path):
    import sqlite3

    old = sqlite3.connect(tmp_path / "old.db")
    old.execute("CREATE TABLE feeds (url TEXT PRIMARY KEY, name TEXT, first_seen TEXT, last_checked TEXT, last_error TEXT)")
    old.commit()
    old.close()
    conn = db.connect(tmp_path / "old.db")
    assert {"image_url", "image_file"} <= {r["name"] for r in conn.execute("PRAGMA table_info(feeds)")}
