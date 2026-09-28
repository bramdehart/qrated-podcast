"""SQLite storage (WAL mode)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds (
    url TEXT PRIMARY KEY,
    name TEXT,
    first_seen TEXT,
    last_checked TEXT,
    last_error TEXT,
    image_url TEXT,
    image_file TEXT
);
CREATE TABLE IF NOT EXISTS episodes (
    guid TEXT PRIMARY KEY,
    feed_url TEXT,
    podcast TEXT,
    title TEXT,
    published TEXT,
    audio_url TEXT,
    transcript_url TEXT,
    transcript_type TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    error TEXT,
    discovered_at TEXT
);
CREATE TABLE IF NOT EXISTS editions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    title TEXT,
    file_name TEXT,
    duration REAL,
    size_bytes INTEGER,
    description TEXT
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_guid TEXT,
    title TEXT,
    summary TEXT,
    intro TEXT,
    start_sec REAL,
    end_sec REAL,
    score REAL,
    status TEXT NOT NULL DEFAULT 'candidate',
    edition_id INTEGER,
    position INTEGER
);
CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the database, creating the schema if needed."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(feeds)")}
    for col in ("image_url", "image_file"):  # migrate databases created before cover art
        if col not in cols:
            conn.execute(f"ALTER TABLE feeds ADD COLUMN {col} TEXT")
    conn.commit()
    return conn
