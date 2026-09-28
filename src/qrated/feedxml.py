"""RSS 2.0 (iTunes) feed generation and edition retention."""

from __future__ import annotations

import logging
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime

from .config import Config

log = logging.getLogger(__name__)
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ET.register_namespace("itunes", ITUNES)


def _duration(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def prune_editions(conn: sqlite3.Connection, cfg: Config) -> int:
    rows = conn.execute("SELECT id, file_name FROM editions ORDER BY id DESC").fetchall()
    removed = 0
    for row in rows[cfg.keep_editions:]:
        (cfg.editions_dir / row["file_name"]).unlink(missing_ok=True)
        conn.execute("DELETE FROM editions WHERE id=?", (row["id"],))
        removed += 1
    conn.commit()
    return removed


def write_feed(conn: sqlite3.Connection, cfg: Config) -> str:
    """Regenerate public/feed.xml from all kept editions; returns the file path."""
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = cfg.feed_title
    ET.SubElement(ch, "link").text = cfg.public_base_url
    ET.SubElement(ch, "description").text = f"{cfg.feed_title}: a daily selection of the best podcast fragments."
    ET.SubElement(ch, "language").text = "en"
    ET.SubElement(ch, "{%s}author" % ITUNES).text = cfg.feed_title
    ET.SubElement(ch, "{%s}explicit" % ITUNES).text = "false"
    for ed in conn.execute("SELECT * FROM editions ORDER BY id DESC").fetchall():
        item = ET.SubElement(ch, "item")
        ET.SubElement(item, "title").text = ed["title"]
        ET.SubElement(item, "description").text = ed["description"] or ""
        url = f"{cfg.public_base_url}/editions/{ed['file_name']}"
        ET.SubElement(item, "enclosure", {"url": url, "length": str(ed["size_bytes"]), "type": "audio/mpeg"})
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = ed["file_name"]
        created = datetime.fromisoformat(ed["created_at"]).astimezone(timezone.utc)
        ET.SubElement(item, "pubDate").text = format_datetime(created)
        ET.SubElement(item, "{%s}duration" % ITUNES).text = _duration(ed["duration"] or 0)
    cfg.public_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.public_dir / "feed.xml"
    ET.ElementTree(rss).write(path, encoding="utf-8", xml_declaration=True)
    return str(path)
