# Build "Q-rated": a personal AI-curated daily podcast

Build a self-hosted Python application, packaged with Docker Compose, that turns ~50 podcasts I follow into one personal daily podcast episode containing only the most interesting fragments. It runs on a small Hetzner VPS (2 GB RAM, no GPU), so no local ML models: all AI work goes through OpenRouter.

**All code, comments, docstrings, log messages and docs must be in English.**

## What it does (daily pipeline)

1. **Fetch**: read the podcast list from `feeds.yaml`, poll every RSS feed, and register new episodes in SQLite.
2. **Transcripts**: for each new episode, download the transcript from the `<podcast:transcript>` tag (Podcasting 2.0 namespace). Support WebVTT, SRT and the Podcasting 2.0 JSON format; prefer VTT. Episodes without a transcript get status `no_transcript` and are skipped (Whisper fallback is a later feature, not v1).
3. **Analyze**: send each transcript (compact, one line per cue: `[start_seconds] text`) to a cheap LLM via OpenRouter. It splits the episode into topics and returns JSON per segment: English `title`, one-sentence `summary`, spoken English `intro` (1–2 short sentences, max ~30 words, read aloud by a radio host before the fragment), `start`/`end` in seconds, `score` 0–10 (interest and self-containedness), and `kind` (`topic`, `ad`, `intro`, `outro`, `chitchat`). Keep only `topic`. Snap start/end to cue boundaries so cuts never land mid-sentence. Enforce min/max fragment length (configurable, default 60–480 s; trim over-long segments at the last cue boundary within the limit). Transcripts are often Dutch; the audio stays original, all generated text is English.
4. **Select**: take the top `MAX_ITEMS` candidates across all newly analyzed episodes with `score >= MIN_SCORE`, max `MAX_ITEMS_PER_PODCAST` per show. After building, mark chosen items `used` and all other candidates `rejected`, so every edition only contains fresh content. If nothing qualifies, build no edition that day.
5. **Audio**: download only the needed episode MP3s, cut fragments with ffmpeg, apply **fade-in and fade-out** (`FADE_SECONDS`) and loudness normalization (`loudnorm`, -16 LUFS), and delete the source MP3s and intermediates afterwards.
6. **Announcements** via TTS in English, each spoken over a **chill background music bed with ducking**: music fades in, voice starts ~1.2 s later, music ducks under the voice (sidechaincompress), plays ~1.5 s after the voice ends, then fades out. Start the bed at a random offset each time so it doesn't sound identical.
7. **Assemble** one MP3 per edition:
   - **Opening** (over the bed): `INTRO_TEXT`, default: *"Hi {name}, this is your Q-rated selection of your favourite podcasts for {date}. Today we've got {items} stories from {shows} shows. Enjoy your day."*
   - **Per item**: a short **ding** → announcement (over the bed): `ANNOUNCE_TEXT`, default *"{lead}, from {podcast}, the episode of {episode_date}. {intro}"* where `{lead}` is "First up" for the first item, "And finally" for the last (if more than 2 items), otherwise "Next up" → the fragment → a short silence.
   - **Closing** (over the bed): `OUTRO_TEXT`, default *"That's it for today, {name}. See you tomorrow."*
   - Dates are spoken in English, e.g. "Tuesday, September 29th" and "September 24th".
   - Normalize every part to one format (e.g. 44.1 kHz stereo s16 WAV), concat, encode final MP3 at 128 kbps with ID3 title.
8. **Feed**: regenerate an RSS 2.0 XML (with iTunes tags, enclosure length, duration) listing all kept editions. Show notes per edition: an HTML list of items with title, podcast, episode title, timestamps and summary. Delete editions older than the newest `KEEP_EDITIONS`.

## Music bed and ding

- **Bed**: on first build, if `/data/assets/bed.mp3` does not exist, generate it **once** with **Google Lyria 3 Clip via OpenRouter** (`google/lyria-3-clip-preview`, ~$0.04 per 30-second clip) using `MUSIC_PROMPT` (default: *"instrumental chill lo-fi background, soft Rhodes chords, warm and relaxed, slow tempo, no vocals, seamless loop"*; "no vocals" matters because Lyria sings by default). Save and reuse it forever. Deleting `bed.mp3` or running `qrated make-bed` regenerates it. If generation fails, fall back to an ffmpeg-synthesized soft chord pad saved as `bed_fallback.mp3` (different name, so Lyria is retried next time). A user-provided `bed.mp3` always wins.
- **Ding**: generate a soft two-tone chime with ffmpeg (`aevalsrc`, decaying sines, e.g. 880 Hz then 1318.5 Hz). A user-provided `/data/assets/ding.mp3` overrides it.

## OpenRouter API details (verified, one key for everything)

- **LLM**: `POST https://openrouter.ai/api/v1/chat/completions`, `response_format: {"type": "json_object"}`, low temperature. Default model `google/gemini-3.5-flash-lite` ($0.30/$2.50 per M tokens, 1M context). Parse JSON leniently (strip code fences).
- **TTS**: `POST https://openrouter.ai/api/v1/audio/speech` (OpenAI-compatible), body `{model, input, voice, response_format: "mp3"}`. Returns raw audio bytes, not JSON. Default model `google/gemini-3.8-flash-lite-tts`, voices like Kore, Puck, Charon, Aoede (30 prebuilt). Gemini TTS reads `input` verbatim, so pass the delivery style as a provider option, not in the text:
  ```json
  "provider": {"options": {"google-ai-studio": {"speech_metadata": {"style": "warm, relaxed radio host"}}}}
  ```
- **Music (Lyria)**: no dedicated endpoint. Use `/chat/completions` with `modalities: ["text", "audio"]` and `stream: true`; collect base64 audio from each SSE chunk's `choices[0].delta.audio.data` until `[DONE]`, join and decode. Lyria returns MP3 and ignores a requested format; re-encode with ffmpeg anyway.
- Retry with backoff on 408/429/5xx; fail fast on other 4xx. Set an `X-Title: qrated` header.

## Tracking new episodes

Use the episode **GUID** as the unique key (fall back to enclosure URL, then link). Don't rely on a "last indexed at" timestamp: podcasts backdate, change pubDates or publish late. Each run, any GUID not in the database is new. Episodes older than `FIRST_RUN_LOOKBACK_DAYS` (default 7) at discovery are stored with status `skipped` and never analyzed; this handles both the very first run and podcasts added to `feeds.yaml` later. Store `last_checked` and `last_error` per feed. One broken feed must never stop the others.

## Database (SQLite, one file in the data volume)

- `feeds`: url (PK), name, first_seen, last_checked, last_error
- `episodes`: guid (PK), feed_url, podcast, title, published, audio_url, transcript_url, transcript_type, status (`new|skipped|no_transcript|analyzed|failed|used`), error, discovered_at
- `items`: id, episode_guid, title, summary, intro, start_sec, end_sec, score, status (`candidate|used|rejected`), edition_id, position
- `editions`: id, created_at, title, file_name, duration, size_bytes, description

Use WAL mode. Record analysis failures on the episode and continue.

## CLI (and scheduler)

Package as `qrated`, runnable inside the container:

- `qrated run`: full pipeline (fetch → analyze → build)
- `qrated fetch`: only poll feeds and index new episodes
- `qrated analyze`: only analyze new transcripts
- `qrated build`: only build an edition from what's already analyzed
- `qrated status`: feeds with last check/error, episode counts per status, recent editions
- `qrated make-bed`: (re)generate the music bed
- `qrated serve`: container entrypoint; long-running scheduler that runs the full pipeline daily at `SCHEDULE_TIMES` (comma-separated `HH:MM`, local time from `TZ`). Don't depend on `croniter` (no longer on PyPI); a simple loop is fine.

Manual runs and scheduled runs must never overlap: use a file lock (`fcntl`) in the data dir. Running `run` twice a day is fine; the second edition only contains what's new since.

Use Python 3.12, `requests`, `pyyaml` and the standard library (`xml.etree`, `sqlite3`); call ffmpeg/ffprobe via subprocess. Parse RSS with ElementTree so the Podcasting 2.0 namespace is handled reliably. Log to stdout.

## Configuration (`.env`)

```env
# API
OPENROUTER_API_KEY=sk-or-...

# Analysis
LLM_MODEL=google/gemini-3.5-flash-lite
MAX_ITEMS=10
MAX_ITEMS_PER_PODCAST=2
MIN_SCORE=6
MIN_ITEM_SECONDS=60
MAX_ITEM_SECONDS=480
FIRST_RUN_LOOKBACK_DAYS=7

# Voice
TTS_MODEL=google/gemini-3.8-flash-lite-tts
TTS_VOICE=Kore
TTS_STYLE=warm, relaxed radio host

# Music
MUSIC_MODEL=google/lyria-3-clip-preview
MUSIC_PROMPT=instrumental chill lo-fi background, soft Rhodes chords, warm and relaxed, slow tempo, no vocals, seamless loop
BED_VOLUME=0.15
FADE_SECONDS=0.8

# Texts
LISTENER_NAME=Bram
INTRO_TEXT=Hi {name}, this is your Q-rated selection of your favourite podcasts for {date}. Today we've got {items} stories from {shows} shows. Enjoy your day.
ANNOUNCE_TEXT={lead}, from {podcast}, the episode of {episode_date}. {intro}
OUTRO_TEXT=That's it for today, {name}. See you tomorrow.

# Schedule
SCHEDULE_TIMES=06:00
TZ=Europe/Amsterdam

# Feed
PUBLIC_BASE_URL=https://podcast.example.com
FEED_TITLE=Q-rated
KEEP_EDITIONS=14
```

Ship this as `.env.example`. All text templates, the listener name, voice, models and music prompt must be configurable here.

## `feeds.yaml`

```yaml
feeds:
  - name: AI Report
    url: https://rss.beehiiv.com/podcasts/019d2587-e790-7b44-bb7a-6eebcaae225c.xml
```

`name` is optional (fall back to the channel title). Also accept plain URL strings. This AI Report feed is a good real test case: it has VTT transcripts for almost every episode.

## Docker

- `Dockerfile`: Python 3.12 slim + ffmpeg + tzdata, install the package, entrypoint `qrated serve`.
- `docker-compose.yml`:
  - `app`: the pipeline/scheduler, `env_file: .env`, volume `./data:/data`, `./feeds.yaml:/config/feeds.yaml:ro`, `restart: unless-stopped`.
  - `caddy`: serves `/data/public` (feed.xml + editions/*.mp3) read-only with automatic HTTPS for the domain in `PUBLIC_BASE_URL`. **No authentication**; the feed is public.
- Install: fill in `.env` and `feeds.yaml`, `docker compose up -d`, add `<PUBLIC_BASE_URL>/feed.xml` to a podcast app.
- Manual run: `docker compose exec app qrated run`.

## Data layout

```
/data/qrated.db
/data/qrated.lock
/data/assets/bed.mp3, ding.mp3 (optional overrides)
/data/work/        # temporary, cleaned after each build
/data/public/feed.xml
/data/public/editions/qrated_YYYY-MM-DD_HHMM.mp3
```

## Quality bar

- Write a README (English) covering install, configuration, commands, how new-episode tracking works, costs, and how to replace the bed/ding.
- Add tests with **no network access**: VTT/SRT/JSON parsing, cue snapping, feed parsing incl. transcript tag selection, lookback/skipping logic, selection caps, and an end-to-end run against a local mock OpenRouter server (JSON for chat, generated MP3 for TTS, streamed base64 SSE for music) and a local mock RSS feed with a synthetic MP3 + VTT. Verify the final MP3 exists, has the expected duration and the feed XML is valid.
- Run the tests and fix failures before finishing.

## Expected costs (for the README)

LLM analysis: tens of cents per week. TTS (Flash-Lite TTS, ~$0.009 per generated minute, doubling on 1 January 2027): a few cents per week. Lyria bed: one-time $0.04.

## Out of scope for v1 (keep the design open for these)

Whisper/transcription API fallback for podcasts without transcripts, an `interests.txt` to personalize scores, listener feedback, TTS caching.