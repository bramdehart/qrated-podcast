"""Transcript analysis: split episodes into scored, self-contained topics."""

from __future__ import annotations

import logging
import sqlite3

import requests

from .config import Config
from .openrouter import OpenRouter
from .transcripts import Cue, compact, parse_transcript, snap_segment

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You analyze podcast transcripts for a personal daily radio show.
The transcript has one line per cue in the form "[start_seconds] text". The audio may be
in any language (often Dutch), but ALL text you write must be in English.

Split the episode into consecutive topical segments and return JSON:
{"segments": [{"title": str, "summary": str, "intro": str, "start": number, "end": number,
"score": number, "kind": "topic"|"ad"|"intro"|"outro"|"chitchat"}]}

Rules:
- title: short English title. summary: one English sentence.
- intro: spoken English, 1-2 short sentences, max 30 words, read aloud by a radio host
  right before the fragment. Do not mention the podcast name or date.
- start/end: seconds, taken from the cue timestamps; segments must not overlap.
- score 0-10: how interesting the fragment is AND how well it stands on its own without
  the rest of the episode.
- kind: "ad" for sponsor reads, "intro"/"outro" for show openers and closers, "chitchat"
  for small talk, "topic" for real content.
Return only JSON."""


def build_user_prompt(podcast: str, title: str, cues: list[Cue]) -> str:
    return f"Podcast: {podcast}\nEpisode: {title}\n\nTranscript:\n{compact(cues)}"


def segments_to_items(segments: list[dict], cues: list[Cue], cfg: Config) -> list[dict]:
    """Keep 'topic' segments, snap to cue boundaries, enforce length limits."""
    items = []
    for seg in segments:
        if not isinstance(seg, dict) or seg.get("kind") != "topic":
            continue
        try:
            start, end = float(seg["start"]), float(seg["end"])
            score = float(seg.get("score", 0))
        except (KeyError, TypeError, ValueError):
            continue
        snapped = snap_segment(cues, start, end, cfg.min_item_seconds, cfg.max_item_seconds)
        if snapped is None:
            continue
        items.append(
            {
                "title": str(seg.get("title", "")).strip(),
                "summary": str(seg.get("summary", "")).strip(),
                "intro": str(seg.get("intro", "")).strip(),
                "start": snapped[0],
                "end": snapped[1],
                "score": score,
            }
        )
    return items


def analyze_episode(conn: sqlite3.Connection, ep: sqlite3.Row, client: OpenRouter, cfg: Config) -> int:
    resp = requests.get(ep["transcript_url"], timeout=60, headers={"User-Agent": "qrated/0.1"})
    resp.raise_for_status()
    cues = parse_transcript(resp.content.decode("utf-8", errors="replace"), ep["transcript_type"])
    if not cues:
        raise ValueError("transcript contains no cues")
    result = client.chat_json(SYSTEM_PROMPT, build_user_prompt(ep["podcast"], ep["title"], cues))
    items = segments_to_items(result.get("segments", []), cues, cfg)
    for it in items:
        conn.execute(
            "INSERT INTO items (episode_guid, title, summary, intro, start_sec, end_sec, score, status)"
            " VALUES (?,?,?,?,?,?,?, 'candidate')",
            (ep["guid"], it["title"], it["summary"], it["intro"], it["start"], it["end"], it["score"]),
        )
    conn.execute("UPDATE episodes SET status='analyzed', error=NULL WHERE guid=?", (ep["guid"],))
    conn.commit()
    return len(items)


def analyze_new(conn: sqlite3.Connection, client: OpenRouter, cfg: Config) -> dict:
    """Analyze all episodes with status 'new'; failures are recorded and skipped."""
    summary = {"analyzed": 0, "failed": 0, "items": 0}
    for ep in conn.execute("SELECT * FROM episodes WHERE status='new' ORDER BY published").fetchall():
        try:
            n = analyze_episode(conn, ep, client, cfg)
            summary["analyzed"] += 1
            summary["items"] += n
            log.info("Analyzed %s - %s: %d candidate items", ep["podcast"], ep["title"], n)
        except Exception as exc:  # noqa: BLE001 - record and continue
            summary["failed"] += 1
            log.warning("Analysis failed for %s: %s", ep["guid"], exc)
            conn.execute("UPDATE episodes SET status='failed', error=? WHERE guid=?", (str(exc)[:500], ep["guid"]))
            conn.commit()
    return summary
