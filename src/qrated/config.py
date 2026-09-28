"""Configuration loaded from environment variables (.env via docker compose)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_INTRO = (
    "Hi {name}, this is your Q-rated selection of your favourite podcasts for {date}. "
    "Today we've got {items} stories from {shows} shows. Enjoy your day."
)
DEFAULT_ANNOUNCE = "{lead}, from {podcast}, the episode of {episode_date}. {intro}"
DEFAULT_OUTRO = "That's it for today, {name}. See you tomorrow."
DEFAULT_FEED_DESCRIPTION = (
    "A daily AI-curated selection of the most interesting fragments from the podcasts {name} follows, "
    "introduced by a friendly radio host."
)
DEFAULT_COVER_PROMPT = (
    "Square podcast cover art for a daily personal podcast called \"{title}\". A bold, stylized letter Q "
    "formed by flowing sound waves, vibrant violet-to-pink gradient background, modern minimal flat design, "
    "high contrast, clean and legible at small sizes. The only text is the title \"{title}\"."
)
DEFAULT_MUSIC_PROMPT = (
    "instrumental chill lo-fi background, soft Rhodes chords, warm and relaxed, "
    "slow tempo, no vocals, seamless loop"
)


def _env(env: dict, key: str, default: str) -> str:
    value = env.get(key)
    return default if value is None or value == "" else value


@dataclass
class Config:
    api_key: str = ""
    api_base: str = "https://openrouter.ai/api/v1"
    llm_model: str = "google/gemini-3.5-flash-lite"
    max_items: int = 10
    max_items_per_podcast: int = 2
    min_score: float = 6
    min_item_seconds: float = 60
    max_item_seconds: float = 480
    first_run_lookback_days: int = 7
    tts_model: str = "google/gemini-3.8-flash-lite-tts"
    tts_voice: str = "Kore"
    tts_style: str = "warm, relaxed radio host"
    tts_sample_rate: int = 24000
    music_model: str = "google/lyria-3-clip-preview"
    music_prompt: str = DEFAULT_MUSIC_PROMPT
    bed_volume: float = 0.15
    fade_seconds: float = 0.8
    listener_name: str = "Bram"
    intro_text: str = DEFAULT_INTRO
    announce_text: str = DEFAULT_ANNOUNCE
    outro_text: str = DEFAULT_OUTRO
    schedule_times: list[str] = field(default_factory=lambda: ["06:00"])
    tz: str = "Europe/Amsterdam"
    public_base_url: str = "https://podcast.example.com"
    feed_title: str = "Q-rated"
    feed_description: str = DEFAULT_FEED_DESCRIPTION
    cover_model: str = "google/gemini-3.1-flash-image"
    cover_prompt: str = DEFAULT_COVER_PROMPT
    keep_editions: int = 14
    data_dir: Path = Path("/data")
    feeds_file: Path = Path("/config/feeds.yaml")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "qrated.db"

    @property
    def lock_path(self) -> Path:
        return self.data_dir / "qrated.lock"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def work_dir(self) -> Path:
        return self.data_dir / "work"

    @property
    def public_dir(self) -> Path:
        return self.data_dir / "public"

    @property
    def covers_dir(self) -> Path:
        return self.public_dir / "covers"

    @property
    def editions_dir(self) -> Path:
        return self.public_dir / "editions"

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Config":
        e = dict(os.environ if env is None else env)
        d = cls()
        times = [t.strip() for t in _env(e, "SCHEDULE_TIMES", "06:00").split(",") if t.strip()]
        return cls(
            api_key=_env(e, "OPENROUTER_API_KEY", ""),
            api_base=_env(e, "OPENROUTER_BASE_URL", d.api_base).rstrip("/"),
            llm_model=_env(e, "LLM_MODEL", d.llm_model),
            max_items=int(_env(e, "MAX_ITEMS", str(d.max_items))),
            max_items_per_podcast=int(_env(e, "MAX_ITEMS_PER_PODCAST", str(d.max_items_per_podcast))),
            min_score=float(_env(e, "MIN_SCORE", str(d.min_score))),
            min_item_seconds=float(_env(e, "MIN_ITEM_SECONDS", str(d.min_item_seconds))),
            max_item_seconds=float(_env(e, "MAX_ITEM_SECONDS", str(d.max_item_seconds))),
            first_run_lookback_days=int(_env(e, "FIRST_RUN_LOOKBACK_DAYS", str(d.first_run_lookback_days))),
            tts_model=_env(e, "TTS_MODEL", d.tts_model),
            tts_voice=_env(e, "TTS_VOICE", d.tts_voice),
            tts_style=_env(e, "TTS_STYLE", d.tts_style),
            tts_sample_rate=int(_env(e, "TTS_SAMPLE_RATE", str(d.tts_sample_rate))),
            music_model=_env(e, "MUSIC_MODEL", d.music_model),
            music_prompt=_env(e, "MUSIC_PROMPT", d.music_prompt),
            bed_volume=float(_env(e, "BED_VOLUME", str(d.bed_volume))),
            fade_seconds=float(_env(e, "FADE_SECONDS", str(d.fade_seconds))),
            listener_name=_env(e, "LISTENER_NAME", d.listener_name),
            intro_text=_env(e, "INTRO_TEXT", d.intro_text),
            announce_text=_env(e, "ANNOUNCE_TEXT", d.announce_text),
            outro_text=_env(e, "OUTRO_TEXT", d.outro_text),
            schedule_times=times,
            tz=_env(e, "TZ", d.tz),
            public_base_url=_env(e, "PUBLIC_BASE_URL", d.public_base_url).rstrip("/"),
            feed_title=_env(e, "FEED_TITLE", d.feed_title),
            feed_description=_env(e, "FEED_DESCRIPTION", d.feed_description),
            cover_model=_env(e, "COVER_MODEL", d.cover_model),
            cover_prompt=_env(e, "COVER_PROMPT", d.cover_prompt),
            keep_editions=int(_env(e, "KEEP_EDITIONS", str(d.keep_editions))),
            data_dir=Path(_env(e, "DATA_DIR", "/data")),
            feeds_file=Path(_env(e, "FEEDS_FILE", "/config/feeds.yaml")),
        )
