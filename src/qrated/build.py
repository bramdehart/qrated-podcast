"""Edition building: select, cut, announce, assemble, publish."""

from __future__ import annotations

import html
import logging
import random
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import audio
from .config import Config
from .feedxml import prune_editions, write_feed
from .openrouter import OpenRouter
from .select import select_items
from .texts import lead_for, render, spoken_date

log = logging.getLogger(__name__)


def _mmss(sec: float) -> str:
    s = int(sec)
    return f"{s // 60}:{s % 60:02d}"


def show_notes(items: list[dict]) -> str:
    lis = []
    for it in items:
        lis.append(
            "<li><b>{title}</b> &mdash; {podcast}, <i>{episode}</i> ({start}&ndash;{end})<br/>{summary}</li>".format(
                title=html.escape(it["title"]), podcast=html.escape(it["podcast"]),
                episode=html.escape(it["episode_title"] or ""),
                start=_mmss(it["start_sec"]), end=_mmss(it["end_sec"]),
                summary=html.escape(it["summary"]),
            )
        )
    return "<ul>" + "".join(lis) + "</ul>"


def _episode_date(published: str | None, tz: ZoneInfo) -> str:
    if not published:
        return "recently"
    return spoken_date(datetime.fromisoformat(published).astimezone(tz), weekday=False)


def build_edition(conn: sqlite3.Connection, client: OpenRouter, cfg: Config, now: datetime | None = None) -> int | None:
    """Build one edition from analyzed candidates; returns edition id or None."""
    chosen = select_items(conn, cfg)
    if not chosen:
        log.info("No candidates qualify; not building an edition")
        return None

    tz = ZoneInfo(cfg.tz)
    now = (now or datetime.now(tz)).astimezone(tz)
    work = cfg.work_dir / now.strftime("%Y%m%d_%H%M%S")
    work.mkdir(parents=True, exist_ok=True)
    try:
        bed = audio.generate_bed(cfg, client)
        ding = audio.to_wav(audio.ensure_ding(cfg), work / "ding.wav")
        silence = audio.make_silence(work / "silence.wav", 1.0)

        # download each needed episode once
        sources: dict[str, Path | None] = {}
        for row in chosen:
            guid = row["episode_guid"]
            if guid in sources:
                continue
            try:
                sources[guid] = audio.download(row["audio_url"], work / f"src_{len(sources)}.mp3")
            except Exception as exc:  # noqa: BLE001
                log.warning("Download failed for %s: %s", row["audio_url"], exc)
                sources[guid] = None
        usable = [r for r in chosen if sources.get(r["episode_guid"])]
        if not usable:
            log.warning("No audio could be downloaded; not building an edition")
            return None

        shows = len({r["podcast"] for r in usable})
        rng = random.Random()
        parts: list[Path] = []

        def announce(text: str, name: str) -> Path:
            voice = work / f"{name}.mp3"
            voice.write_bytes(client.tts(text))
            return audio.speech_over_bed(voice, bed, work / f"{name}.wav", cfg, rng)

        parts.append(announce(
            render(cfg.intro_text, name=cfg.listener_name, date=spoken_date(now),
                   items=len(usable), shows=shows),
            "opening",
        ))
        built: list[sqlite3.Row] = []
        for idx, row in enumerate(usable):
            try:
                text = render(
                    cfg.announce_text, lead=lead_for(idx, len(usable)), podcast=row["podcast"],
                    episode_date=_episode_date(row["published"], tz), intro=row["intro"],
                    title=row["title"], name=cfg.listener_name,
                )
                ann = announce(text, f"ann_{idx}")
                frag = audio.cut_fragment(
                    sources[row["episode_guid"]], row["start_sec"], row["end_sec"],
                    work / f"frag_{idx}.wav", cfg.fade_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("Skipping item %s: %s", row["id"], exc)
                continue
            parts += [ding, ann, frag, silence]
            built.append(row)
        if not built:
            log.warning("All items failed; not building an edition")
            return None
        parts.append(announce(render(cfg.outro_text, name=cfg.listener_name), "closing"))

        title = f"{cfg.feed_title} - {spoken_date(now)}"
        file_name = f"qrated_{now:%Y-%m-%d_%H%M}.mp3"
        cfg.editions_dir.mkdir(parents=True, exist_ok=True)
        out = audio.concat_to_mp3(parts, cfg.editions_dir / file_name, title, work)
        duration = audio.probe_duration(out)

        notes = show_notes([dict(r) for r in built])
        cur = conn.execute(
            "INSERT INTO editions (created_at, title, file_name, duration, size_bytes, description)"
            " VALUES (?,?,?,?,?,?)",
            (now.isoformat(), title, file_name, duration, out.stat().st_size, notes),
        )
        edition_id = cur.lastrowid
        for pos, row in enumerate(built, start=1):
            conn.execute("UPDATE items SET status='used', edition_id=?, position=? WHERE id=?",
                         (edition_id, pos, row["id"]))
        conn.execute("UPDATE items SET status='rejected' WHERE status='candidate'")
        conn.execute(
            "UPDATE episodes SET status='used' WHERE guid IN"
            " (SELECT DISTINCT episode_guid FROM items WHERE status='used')"
        )
        conn.commit()
        prune_editions(conn, cfg)
        write_feed(conn, cfg)
        log.info("Built edition %s (%d items, %.0fs)", file_name, len(built), duration)
        return edition_id
    finally:
        shutil.rmtree(work, ignore_errors=True)
