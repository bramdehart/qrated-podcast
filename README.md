# Q-rated

A self-hosted, AI-curated **daily podcast**. Q-rated follows ~50 podcasts you choose, finds the most
interesting self-contained fragments in their transcripts, and stitches them into one personal episode:
a spoken intro over a chill music bed, a short ding and an announcement before every fragment, and a
closing line. The result is served as a normal podcast RSS feed.

It is built for a small VPS (2 GB RAM, no GPU): there are no local ML models. All AI work (analysis,
text-to-speech, music) goes through [OpenRouter](https://openrouter.ai) with a single API key.

## How it works

1. **Fetch**: polls the RSS feeds in `feeds.yaml` and registers new episodes in SQLite.
2. **Transcripts**: downloads the `<podcast:transcript>` (Podcasting 2.0) file, preferring WebVTT over SRT
   over JSON. Episodes without one get status `no_transcript` and are skipped.
3. **Analyze**: a cheap LLM splits each transcript into topics with an English title, summary, spoken intro,
   score (0-10) and kind. Only `topic` segments are kept, snapped to cue boundaries and limited to
   `MIN_ITEM_SECONDS`..`MAX_ITEM_SECONDS`.
4. **Select**: the top `MAX_ITEMS` candidates with `score >= MIN_SCORE` (max `MAX_ITEMS_PER_PODCAST` per show).
   Chosen items become `used`, all other candidates `rejected`, so every edition contains only fresh content.
   If nothing qualifies, no edition is built.
5. **Audio**: only the needed MP3s are downloaded, fragments are cut with ffmpeg, faded and loudness-normalized
   (-16 LUFS); sources and intermediates are deleted afterwards.
6. **Announcements**: English TTS over the music bed, with ducking.
7. **Homepage**: `index.html` at the site root shows the channel, the editions as expandable cards (newest open),
   and an inventory of all podcasts in `feeds.yaml`. Each edition has a chapter-aware player: the timeline is split
   into stories with show covers above it; hovering the timeline or a cover previews that story's art and info, and
   clicking a cover or a story jumps to it (keys: space play/pause, j/l -/+15 s, p/n previous/next story; lock-screen
   controls show the current story). Story offsets are recorded at build time; run `qrated rebuild` to add them to
   the newest edition if it was built before this feature. Cover art
   is downloaded once and stored as a 300 px thumbnail in `public/covers/` (no hotlinking). It is regenerated after every fetch and build.
8. **Feed**: `feed.xml` (RSS 2.0 with iTunes tags) lists the newest `KEEP_EDITIONS` editions; older ones are deleted.

## Install

```bash
cp .env.example .env        # fill in OPENROUTER_API_KEY, LISTENER_NAME, PUBLIC_BASE_URL, ...
$EDITOR feeds.yaml          # list your podcasts
docker compose up -d
```

The compose file only runs the `app` container, which listens on no port. Serve `./data/public` with your own web
server: for an existing Caddy, add the site block from [Caddyfile.example](Caddyfile.example) to your main Caddyfile
(with your domain and the absolute path to `data/public`) and reload Caddy. Then add `<PUBLIC_BASE_URL>/feed.xml`
to your podcast app. **The feed is public and has no authentication.**

Run manually at any time (a file lock prevents overlap with the scheduled run):

```bash
docker compose exec app qrated run
```

### `feeds.yaml`

```yaml
feeds:
  - name: AI Report        # optional; falls back to the channel title
    url: https://rss.beehiiv.com/podcasts/019d2587-e790-7b44-bb7a-6eebcaae225c.xml
  - https://example.com/plain-url-also-works.xml
```

## Configuration

Everything is set in `.env` (see [.env.example](.env.example)):

| Group | Variables |
| --- | --- |
| API | `OPENROUTER_API_KEY` |
| Analysis | `LLM_MODEL`, `MAX_ITEMS`, `MAX_ITEMS_PER_PODCAST`, `MIN_SCORE`, `MIN_ITEM_SECONDS`, `MAX_ITEM_SECONDS`, `FIRST_RUN_LOOKBACK_DAYS` |
| Voice | `TTS_MODEL`, `TTS_VOICE`, `TTS_STYLE`, `TTS_SAMPLE_RATE` |
| Music | `MUSIC_MODEL`, `MUSIC_PROMPT`, `BED_VOLUME`, `FADE_SECONDS` |
| Texts | `LISTENER_NAME`, `INTRO_TEXT`, `ANNOUNCE_TEXT`, `OUTRO_TEXT` |
| Schedule | `SCHEDULE_TIMES` (comma-separated `HH:MM`, local time), `TZ` |
| Feed | `PUBLIC_BASE_URL`, `FEED_TITLE`, `FEED_DESCRIPTION`, `KEEP_EDITIONS` |
| Cover | `COVER_MODEL`, `COVER_PROMPT` |

Text placeholders: `INTRO_TEXT` supports `{name}`, `{date}`, `{items}`, `{shows}`; `ANNOUNCE_TEXT` supports
`{lead}`, `{podcast}`, `{episode_date}`, `{intro}`, `{title}`, `{name}`; `OUTRO_TEXT` supports `{name}`.
`{lead}` is "First up" for the first item, "And finally" for the last (when there are more than 2), else "Next up".

## Commands

Run inside the container (`docker compose exec app qrated <command>`):

| Command | What it does |
| --- | --- |
| `run` | Full pipeline: fetch, analyze, build |
| `fetch` | Poll feeds and index new episodes only |
| `analyze` | Analyze new transcripts only |
| `build` | Build an edition from what is already analyzed |
| `rebuild` | Rebuild the newest edition from the same stories, keeping its date (TTS cost only, no re-analysis). Use it after changing the voice, music or texts |
| `status` | Feeds with last check/error, episode counts per status, recent editions |
| `make-bed` | (Re)generate the music bed |
| `make-cover` | (Re)generate the podcast cover art and refresh the feed and homepage |
| `serve` | Container entrypoint: runs the full pipeline daily at `SCHEDULE_TIMES` |

## How new-episode tracking works

The episode **GUID** is the unique key (falling back to the enclosure URL, then the link). There is no "last
indexed at" timestamp, because podcasts backdate, change publication dates or publish late: on every run any GUID
that is not in the database is new. Episodes older than `FIRST_RUN_LOOKBACK_DAYS` (default 7) at the moment of
discovery are stored with status `skipped` and never analyzed. That handles both the first run and podcasts added to
`feeds.yaml` later. `last_checked` and `last_error` are stored per feed, and one broken feed never stops the others.

Episode statuses: `new`, `skipped`, `no_transcript`, `analyzed`, `failed`, `used`.

## Cover art

On the first build, if there is no cover yet, one is generated with `COVER_MODEL` from `COVER_PROMPT` (placeholders
`{title}` and `{name}`) and saved as `data/assets/cover.png`. It is published as a 1400x1400 JPEG at
`<PUBLIC_BASE_URL>/cover.jpg` (the size Apple Podcasts requires), used in the feed (`itunes:image`) and on the
homepage. Run `qrated make-cover` to generate a new one after changing the prompt. If generation fails, a gradient
placeholder is used and generation is retried on the next build. Your own `data/assets/cover.jpg` (or `.png`) always
wins. Podcast apps cache artwork, so a new cover can take a while to show up there.

## Music bed and ding

- **Bed**: on first build, if `/data/assets/bed.mp3` does not exist it is generated once with Google Lyria 3 Clip
  via OpenRouter and reused forever. If generation fails, a synthesized pad is saved as `bed_fallback.mp3` (Lyria is
  retried on the next build). Delete `data/assets/bed.mp3` or run `qrated make-bed` to regenerate it.
- **Ding**: a soft two-tone chime generated with ffmpeg.
- **Replace either**: drop your own `bed.mp3` and/or `ding.mp3` into `./data/assets/`. Files you provide always win.

## Data layout

```
data/qrated.db, data/qrated.lock
data/assets/bed.mp3, ding.mp3
data/work/                      temporary, cleaned after each build
data/public/feed.xml, index.html, cover.jpg
data/public/covers/           show cover art
data/public/editions/qrated_YYYY-MM-DD_HHMM.mp3
```

## Costs (approximate)

- LLM analysis (Gemini Flash-Lite, $0.30/$2.50 per M tokens): tens of cents per week.
- TTS (Flash-Lite TTS, ~$0.009 per generated minute, doubling on 1 January 2027): a few cents per week.
- Lyria music bed: one-time ~$0.04.
- Cover art: one-time, a few cents per generated image.

## Development

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

Tests need ffmpeg but no network: the end-to-end test runs against a local mock OpenRouter server and a local mock
RSS feed.

## Out of scope for v1

Whisper/transcription fallback for podcasts without transcripts, an `interests.txt` to personalize scores, listener
feedback and TTS caching.
