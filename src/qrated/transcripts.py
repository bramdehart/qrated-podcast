"""Transcript parsing (WebVTT, SRT, Podcasting 2.0 JSON) and cue helpers."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

TIME_RE = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _ts(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def _clean(text: str) -> str:
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_timed_blocks(content: str) -> list[Cue]:
    cues: list[Cue] = []
    content = content.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    for block in re.split(r"\n\s*\n", content):
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            m = TIME_RE.search(line)
            if not m:
                continue
            g = m.groups()
            text = _clean(" ".join(lines[i + 1:]))
            if text:
                cues.append(Cue(_ts(*g[0:4]), _ts(*g[4:8]), text))
            break
    return cues


def parse_vtt(content: str) -> list[Cue]:
    return _parse_timed_blocks(content)


def parse_srt(content: str) -> list[Cue]:
    return _parse_timed_blocks(content)


def parse_json_transcript(content: str) -> list[Cue]:
    data = json.loads(content)
    segments = data.get("segments", []) if isinstance(data, dict) else data
    cues: list[Cue] = []
    for seg in segments:
        try:
            start = float(seg["startTime"])
            end = float(seg.get("endTime", start))
            text = _clean(str(seg.get("body", "")))
        except (KeyError, TypeError, ValueError):
            continue
        if text:
            cues.append(Cue(start, end, text))
    return cues


def parse_transcript(content: str, kind: str) -> list[Cue]:
    """Parse transcript text of the given kind ('vtt', 'srt' or 'json')."""
    if kind == "vtt":
        cues = parse_vtt(content)
    elif kind == "srt":
        cues = parse_srt(content)
    elif kind == "json":
        cues = parse_json_transcript(content)
    else:
        raise ValueError(f"unsupported transcript type: {kind}")
    cues.sort(key=lambda c: c.start)
    return cues


def compact(cues: list[Cue]) -> str:
    """One line per cue: '[start_seconds] text'."""
    return "\n".join(f"[{int(c.start)}] {c.text}" for c in cues)


def snap_segment(
    cues: list[Cue], start: float, end: float, min_len: float, max_len: float
) -> tuple[float, float] | None:
    """Snap a segment to cue boundaries and enforce length limits.

    The start snaps to the start of the cue containing/nearest before it; the end
    snaps to the end of the cue nearest to it. Over-long segments are trimmed at the
    last cue boundary within max_len. Returns None if the result is too short.
    """
    if not cues or end <= start:
        return None
    starts = [c for c in cues if c.start <= start]
    first = starts[-1] if starts else cues[0]
    s = first.start
    inside = [c for c in cues if c.start >= s and c.start < end]
    if not inside:
        return None
    # end: the cue whose end is closest to the requested end
    last = min(inside, key=lambda c: abs(c.end - end))
    e = last.end
    if e - s > max_len:
        fitting = [c for c in inside if c.end - s <= max_len]
        if not fitting:
            return None
        e = fitting[-1].end
    if e - s < min_len:
        return None
    return s, e
