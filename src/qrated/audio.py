"""ffmpeg helpers: cutting, normalization, music bed, ding, ducked announcements."""

from __future__ import annotations

import logging
import random
import subprocess
from pathlib import Path

import requests

from .config import Config
from .openrouter import OpenRouter

log = logging.getLogger(__name__)

FORMAT = "aformat=sample_rates=44100:channel_layouts=stereo:sample_fmts=s16"
VOICE_LEAD_IN = 1.2
BED_TAIL = 1.5
BED_FADE_IN = 1.0
BED_FADE_OUT = 1.2


def run_ffmpeg(*args: str) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[-500:]}")


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr.strip()}")
    return float(proc.stdout.strip())


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120, headers={"User-Agent": "qrated/0.1"}) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
    return dest


def cut_fragment(src: Path, start: float, end: float, dest: Path, fade: float) -> Path:
    """Cut [start, end] from src, loudness-normalize, fade in/out, output 44.1k stereo WAV."""
    dur = end - start
    fade = min(fade, dur / 2)
    filt = (
        f"loudnorm=I=-16:TP=-1.5:LRA=11,{FORMAT},"
        f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={dur - fade:.3f}:d={fade:.3f}"
    )
    run_ffmpeg("-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-af", filt, str(dest))
    return dest


def make_silence(dest: Path, seconds: float = 1.0) -> Path:
    run_ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{seconds}", "-af", FORMAT, str(dest))
    return dest


def _synth_ding(dest: Path) -> None:
    expr = (
        "0.35*sin(2*PI*880*t)*exp(-5*t)*lt(t,0.25)"
        "+0.35*sin(2*PI*1318.5*(t-0.18))*exp(-4*(t-0.18))*gte(t,0.18)"
    )
    run_ffmpeg("-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d=1.2:c=stereo", "-b:a", "192k", str(dest))


def ensure_ding(cfg: Config) -> Path:
    """Return the ding file; a user-provided ding.mp3 always wins."""
    path = cfg.assets_dir / "ding.mp3"
    if not path.exists():
        cfg.assets_dir.mkdir(parents=True, exist_ok=True)
        _synth_ding(path)
        log.info("Generated ding at %s", path)
    return path


def _synth_pad(dest: Path) -> None:
    """Soft chord pad (Cmaj7-ish) with slow tremolo, 30 seconds."""
    freqs = [130.81, 164.81, 196.0, 246.94, 329.63]
    inputs: list[str] = []
    for f in freqs:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:sample_rate=44100:duration=30"]
    mix = "".join(f"[{i}]" for i in range(len(freqs)))
    filt = (
        f"{mix}amix=inputs={len(freqs)}:normalize=1,tremolo=f=0.2:d=0.3,lowpass=f=1200,"
        "aformat=channel_layouts=stereo,volume=0.8"
    )
    run_ffmpeg(*inputs, "-filter_complex", filt, "-b:a", "128k", str(dest))


def generate_bed(cfg: Config, client: OpenRouter, force: bool = False) -> Path:
    """Return the path of the music bed, generating it via Lyria on first use.

    bed.mp3 (user-provided or previously generated) is reused forever. If Lyria
    fails, an ffmpeg pad is saved as bed_fallback.mp3 so Lyria is retried next time.
    """
    cfg.assets_dir.mkdir(parents=True, exist_ok=True)
    bed = cfg.assets_dir / "bed.mp3"
    if bed.exists() and not force:
        return bed
    tmp_in = cfg.assets_dir / "bed_raw.bin"
    try:
        tmp_in.write_bytes(client.music(cfg.music_prompt))
        run_ffmpeg("-i", str(tmp_in), "-vn", "-b:a", "192k", str(bed))
        log.info("Generated music bed with %s", cfg.music_model)
        return bed
    except Exception as exc:  # noqa: BLE001 - fall back to synthesized pad
        log.warning("Music bed generation failed (%s); using synthesized fallback", exc)
        bed.unlink(missing_ok=True)
        fallback = cfg.assets_dir / "bed_fallback.mp3"
        if not fallback.exists():
            _synth_pad(fallback)
        return fallback
    finally:
        tmp_in.unlink(missing_ok=True)


def speech_over_bed(voice_mp3: Path, bed: Path, dest: Path, cfg: Config, rng: random.Random | None = None) -> Path:
    """Mix a voice clip over the music bed with sidechain ducking.

    Bed fades in, voice starts VOICE_LEAD_IN s later, bed ducks under the voice,
    continues BED_TAIL s after it ends, then fades out. Bed starts at a random offset.
    """
    rng = rng or random.Random()
    voice_dur = probe_duration(voice_mp3)
    total = VOICE_LEAD_IN + voice_dur + BED_TAIL + BED_FADE_OUT
    bed_len = probe_duration(bed)
    offset = rng.uniform(0, max(bed_len - 1.0, 0))
    delay_ms = int(VOICE_LEAD_IN * 1000)
    filt = (
        f"[0:a]aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=11,"
        f"adelay={delay_ms}|{delay_ms},apad=whole_dur={total:.3f},asplit=2[v][sc];"
        f"[1:a]aformat=channel_layouts=stereo,volume={cfg.bed_volume},atrim=0:{total:.3f},"
        f"afade=t=in:st=0:d={BED_FADE_IN},afade=t=out:st={total - BED_FADE_OUT:.3f}:d={BED_FADE_OUT}[bed];"
        f"[bed][sc]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=500[ducked];"
        f"[v][ducked]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95,{FORMAT}[out]"
    )
    run_ffmpeg(
        "-i", str(voice_mp3),
        "-stream_loop", "-1", "-ss", f"{offset:.3f}", "-i", str(bed),
        "-filter_complex", filt, "-map", "[out]", "-t", f"{total:.3f}", str(dest),
    )
    return dest


def pcm_to_wav(pcm: bytes, dest: Path, sample_rate: int) -> Path:
    """Convert raw PCM (s16le, mono) as returned by the TTS endpoint into a WAV file."""
    raw = dest.with_suffix(".pcm")
    raw.write_bytes(pcm)
    try:
        run_ffmpeg("-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-i", str(raw), str(dest))
    finally:
        raw.unlink(missing_ok=True)
    return dest


def to_wav(src: Path, dest: Path) -> Path:
    run_ffmpeg("-i", str(src), "-af", FORMAT, str(dest))
    return dest


def concat_to_mp3(parts: list[Path], dest: Path, title: str, work: Path) -> Path:
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    run_ffmpeg(
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-metadata", f"title={title}", "-id3v2_version", "3", str(dest),
    )
    return dest
