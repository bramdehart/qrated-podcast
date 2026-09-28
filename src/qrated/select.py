"""Candidate selection with per-show caps."""

from __future__ import annotations

import sqlite3

from .config import Config


def select_items(conn: sqlite3.Connection, cfg: Config) -> list[sqlite3.Row]:
    """Top candidates by score, honoring MIN_SCORE, MAX_ITEMS and MAX_ITEMS_PER_PODCAST."""
    rows = conn.execute(
        "SELECT i.*, e.podcast, e.title AS episode_title, e.published, e.audio_url"
        " FROM items i JOIN episodes e ON e.guid = i.episode_guid"
        " WHERE i.status='candidate' AND i.score >= ?"
        " ORDER BY i.score DESC, i.id ASC",
        (cfg.min_score,),
    ).fetchall()
    chosen: list[sqlite3.Row] = []
    per_show: dict[str, int] = {}
    for row in rows:
        if len(chosen) >= cfg.max_items:
            break
        if per_show.get(row["podcast"], 0) >= cfg.max_items_per_podcast:
            continue
        per_show[row["podcast"]] = per_show.get(row["podcast"], 0) + 1
        chosen.append(row)
    return chosen
