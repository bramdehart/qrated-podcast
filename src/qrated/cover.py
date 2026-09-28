"""Podcast cover art: generated once via OpenRouter, user override wins, published as public/cover.jpg."""

from __future__ import annotations

import logging
from pathlib import Path

from .audio import run_ffmpeg
from .config import Config
from .openrouter import OpenRouter
from .texts import render

log = logging.getLogger(__name__)

# Apple Podcasts requires square artwork between 1400 and 3000 px.
PUBLISHED_SIZE = 1400
USER_COVERS = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp")
GENERATED = "cover.png"
FALLBACK = "cover_fallback.png"


def published_cover(cfg: Config) -> Path:
    return cfg.public_dir / "cover.jpg"


def cover_url(cfg: Config, absolute: bool = False) -> str | None:
    """URL of the published cover with a version suffix so apps refresh it after a change."""
    path = published_cover(cfg)
    if not path.exists():
        return None
    rel = f"cover.jpg?v={int(path.stat().st_mtime)}"
    return f"{cfg.public_base_url}/{rel}" if absolute else rel


def _existing_source(cfg: Config) -> Path | None:
    for name in USER_COVERS:
        path = cfg.assets_dir / name
        if path.exists():
            return path
    return None


def _synth_fallback(dest: Path) -> None:
    """Violet-to-pink gradient square, used when image generation fails."""
    s = PUBLISHED_SIZE
    run_ffmpeg(
        "-f", "lavfi",
        "-i", f"gradients=s={s}x{s}:c0=0x5a47e0:c1=0xe0477a:x0=0:y0=0:x1={s}:y1={s}:nb_colors=2",
        "-frames:v", "1", str(dest),
    )


def _publish(src: Path, cfg: Config, force: bool) -> Path:
    dest = published_cover(cfg)
    if not force and dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return dest
    cfg.public_dir.mkdir(parents=True, exist_ok=True)
    s = PUBLISHED_SIZE
    run_ffmpeg(
        "-i", str(src), "-frames:v", "1",
        "-vf", f"scale={s}:{s}:force_original_aspect_ratio=increase:flags=lanczos,crop={s}:{s}",
        "-q:v", "2", str(dest),
    )
    log.info("Published cover art %s", dest)
    return dest


def ensure_cover(cfg: Config, client: OpenRouter, force: bool = False) -> Path | None:
    """Return the published cover, generating it once with COVER_MODEL if no cover exists yet.

    A user-provided assets/cover.(jpg|png|webp) always wins. `force` regenerates assets/cover.png.
    If generation fails, a gradient is saved as cover_fallback.png so generation is retried next time.
    """
    cfg.assets_dir.mkdir(parents=True, exist_ok=True)
    src = None if force else _existing_source(cfg)
    if src is None:
        raw = cfg.assets_dir / "cover_raw.bin"
        try:
            prompt = render(cfg.cover_prompt, title=cfg.feed_title, name=cfg.listener_name)
            raw.write_bytes(client.image(prompt))
            src = cfg.assets_dir / GENERATED
            run_ffmpeg("-i", str(raw), "-frames:v", "1", str(src))
            log.info("Generated cover art with %s", cfg.cover_model)
            force = True
        except Exception as exc:  # noqa: BLE001 - cover art must never break a build
            log.warning("Cover generation failed (%s); using gradient fallback", exc)
            src = _existing_source(cfg) or cfg.assets_dir / FALLBACK
            if not src.exists():
                try:
                    _synth_fallback(src)
                except Exception as fb_exc:  # noqa: BLE001
                    log.warning("Fallback cover failed: %s", fb_exc)
                    return published_cover(cfg) if published_cover(cfg).exists() else None
        finally:
            raw.unlink(missing_ok=True)
    return _publish(src, cfg, force)
