"""Feed list loading, RSS parsing and new-episode tracking."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
import yaml

log = logging.getLogger(__name__)

COVER_SIZE = 600
ITUNES_NS ="http://www.itunes.com/dtds/podcast-1.0.dtd"
PODCAST_NS = "https://podcastindex.org/namespace/1.0"
PODCAST_NS_OLD = "https://podcastindex.org/namespace/1.0/"
ENCLOSURE_TYPES = ("audio/",)


@dataclass
class FeedSpec:
    url: str
    name: str | None = None


@dataclass
class ParsedEpisode:
    guid: str
    title: str
    published: datetime | None
    audio_url: str | None
    transcript_url: str | None
    transcript_type: str | None


def load_feed_specs(path: Path) -> list[FeedSpec]:
    data = yaml.safe_load(Path(path).read_text()) or {}
    specs = []
    for entry in data.get("feeds", []) or []:
        if isinstance(entry, str):
            specs.append(FeedSpec(entry.strip()))
        elif isinstance(entry, dict) and entry.get("url"):
            specs.append(FeedSpec(str(entry["url"]).strip(), entry.get("name")))
    return specs


def _transcript_kind(mime: str, url: str) -> str | None:
    mime = (mime or "").lower()
    path = url.lower().split("?")[0]
    if "vtt" in mime or path.endswith(".vtt"):
        return "vtt"
    if "subrip" in mime or "srt" in mime or path.endswith(".srt"):
        return "srt"
    if "json" in mime or path.endswith(".json"):
        return "json"
    return None


def pick_transcript(candidates: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Choose (url, kind) from [(url, mime)] preferring vtt > srt > json."""
    best: dict[str, str] = {}
    for url, mime in candidates:
        kind = _transcript_kind(mime, url)
        if kind and kind not in best:
            best[kind] = url
    for kind in ("vtt", "srt", "json"):
        if kind in best:
            return best[kind], kind
    return None


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text.strip())
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_feed(xml_bytes: bytes) -> tuple[str, list[ParsedEpisode]]:
    """Parse RSS; returns (channel_title, episodes)."""
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("not an RSS feed: no <channel>")
    channel_title = (channel.findtext("title") or "").strip()
    episodes = []
    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        audio_url = enclosure.get("url") if enclosure is not None else None
        link = (item.findtext("link") or "").strip() or None
        guid = (item.findtext("guid") or "").strip() or audio_url or link
        if not guid:
            continue
        cands = []
        for ns in (PODCAST_NS, PODCAST_NS_OLD):
            for t in item.findall(f"{{{ns}}}transcript"):
                if t.get("url"):
                    cands.append((t.get("url"), t.get("type", "")))
        picked = pick_transcript(cands)
        episodes.append(
            ParsedEpisode(
                guid=guid,
                title=(item.findtext("title") or "").strip(),
                published=_parse_date(item.findtext("pubDate")),
                audio_url=audio_url,
                transcript_url=picked[0] if picked else None,
                transcript_type=picked[1] if picked else None,
            )
        )
    return channel_title, episodes


def parse_channel_image(xml_bytes: bytes) -> str | None:
    """Cover art URL: <itunes:image href> first, then <image><url>."""
    channel = ET.fromstring(xml_bytes).find("channel")
    if channel is None:
        return None
    itunes = channel.find(f"{{{ITUNES_NS}}}image")
    if itunes is not None and itunes.get("href"):
        return itunes.get("href").strip()
    url = (channel.findtext("image/url") or "").strip()
    return url or None


def _thumbnail(data: bytes, dest: Path) -> None:
    """Scale and center-crop cover art to a small square JPEG (originals can be 3000 px / several MB)."""
    src = dest.with_suffix(".src")
    src.write_bytes(data)
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-frames:v", "1",
             "-vf", f"scale={COVER_SIZE}:{COVER_SIZE}:force_original_aspect_ratio=increase,"
                    f"crop={COVER_SIZE}:{COVER_SIZE}",
             "-q:v", "4", str(dest)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg could not convert cover: {proc.stderr.strip()[-200:]}")
    finally:
        src.unlink(missing_ok=True)


def download_cover(conn: sqlite3.Connection, feed_url: str, image_url: str | None, covers_dir: Path) -> None:
    """Store the cover locally (no hotlinking); failures are logged and ignored."""
    if not image_url:
        return
    name = f"{hashlib.sha1(image_url.encode()).hexdigest()[:12]}_{COVER_SIZE}.jpg"
    row = conn.execute("SELECT image_file FROM feeds WHERE url=?", (feed_url,)).fetchone()
    if row and row["image_file"] == name and (covers_dir / name).exists():
        return
    try:
        resp = requests.get(image_url, timeout=30, headers={"User-Agent": "qrated/0.1"})
        resp.raise_for_status()
        if len(resp.content) > 20_000_000:
            raise ValueError("cover image too large")
        covers_dir.mkdir(parents=True, exist_ok=True)
        _thumbnail(resp.content, covers_dir / name)
        old = row["image_file"] if row else None
        if old and old != name:
            (covers_dir / old).unlink(missing_ok=True)
        conn.execute("UPDATE feeds SET image_url=?, image_file=? WHERE url=?", (image_url, name, feed_url))
    except Exception as exc:  # noqa: BLE001 - cover art is optional
        log.warning("Cover download failed for %s: %s", feed_url, exc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def register_episodes(
    conn: sqlite3.Connection,
    feed_url: str,
    podcast: str,
    episodes: list[ParsedEpisode],
    lookback_days: int,
    now: datetime | None = None,
) -> int:
    """Insert unseen GUIDs. Old episodes get status 'skipped'; returns count of new ones."""
    now = now or _now()
    cutoff = now - timedelta(days=lookback_days)
    added = 0
    for ep in episodes:
        if conn.execute("SELECT 1 FROM episodes WHERE guid=?", (ep.guid,)).fetchone():
            continue
        old = ep.published is not None and ep.published < cutoff
        if old:
            status = "skipped"
        elif not ep.transcript_url or not ep.audio_url:
            status = "no_transcript" if not ep.transcript_url else "failed"
        else:
            status = "new"
        conn.execute(
            "INSERT INTO episodes (guid, feed_url, podcast, title, published, audio_url,"
            " transcript_url, transcript_type, status, error, discovered_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                ep.guid, feed_url, podcast, ep.title,
                ep.published.isoformat() if ep.published else None,
                ep.audio_url, ep.transcript_url, ep.transcript_type, status,
                "no audio enclosure" if status == "failed" else None,
                now.isoformat(),
            ),
        )
        added += 1
    conn.commit()
    return added


def fetch_all(
    conn: sqlite3.Connection, specs: list[FeedSpec], lookback_days: int, covers_dir: Path | None = None
) -> dict:
    """Poll every feed; one broken feed never stops the others."""
    summary = {"feeds": 0, "errors": 0, "new_episodes": 0}
    for spec in specs:
        now = _now().isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO feeds (url, name, first_seen) VALUES (?,?,?)",
            (spec.url, spec.name, now),
        )
        summary["feeds"] += 1
        try:
            resp = requests.get(spec.url, timeout=30, headers={"User-Agent": "qrated/0.1"})
            resp.raise_for_status()
            title, episodes = parse_feed(resp.content)
            name = spec.name or title or spec.url
            n = register_episodes(conn, spec.url, name, episodes, lookback_days)
            summary["new_episodes"] += n
            if covers_dir is not None:
                download_cover(conn, spec.url, parse_channel_image(resp.content), covers_dir)
            conn.execute(
                "UPDATE feeds SET name=?, last_checked=?, last_error=NULL WHERE url=?",
                (name, now, spec.url),
            )
            log.info("Feed %s: %d episodes, %d new", name, len(episodes), n)
        except Exception as exc:  # noqa: BLE001 - isolate feed failures
            summary["errors"] += 1
            log.warning("Feed %s failed: %s", spec.url, exc)
            conn.execute(
                "UPDATE feeds SET last_checked=?, last_error=? WHERE url=?",
                (now, str(exc)[:500], spec.url),
            )
        conn.commit()
    return summary
