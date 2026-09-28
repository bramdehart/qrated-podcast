"""End-to-end run against local mock OpenRouter and RSS servers (no external network)."""

import base64
import json
import subprocess
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from qrated import audio, db
from qrated.cli import cmd_rebuild, cmd_run
from qrated.config import Config


def _sine_mp3(path, seconds, freq=440):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f={freq}:d={seconds}", str(path)],
        check=True,
    )
    return path.read_bytes()


@pytest.fixture()
def servers(tmp_path):
    ep_audio = _sine_mp3(tmp_path / "ep.mp3", 300)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=3:r=24000",
         "-ac", "1", "-f", "s16le", str(tmp_path / "tts.pcm")], check=True)
    tts_audio = (tmp_path / "tts.pcm").read_bytes()
    bed_audio = _sine_mp3(tmp_path / "bed_src.mp3", 30, 200)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=1400x1000",
                    "-frames:v", "1", str(tmp_path / "cover.png")], check=True)
    cover_png = (tmp_path / "cover.png").read_bytes()
    vtt = "WEBVTT\n\n" + "".join(
        f"00:{i * 10 // 60:02d}:{i * 10 % 60:02d}.000 --> 00:{(i * 10 + 10) // 60:02d}:{(i * 10 + 10) % 60:02d}.000\nLine {i}\n\n"
        for i in range(30)
    )
    state = {"tts_calls": 0, "chat_calls": 0, "tts_bodies": [], "image_prompts": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype, code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            base = f"http://127.0.0.1:{self.server.server_port}"
            if self.path == "/feed.xml":
                rss = f"""<?xml version="1.0"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel><title>Mock Show</title>
<itunes:image href="{base}/cover.png"/>
<item><title>Ep One</title><guid>ep-1</guid><pubDate>{format_datetime(datetime.now(timezone.utc))}</pubDate>
<enclosure url="{base}/ep.mp3" type="audio/mpeg" length="1"/>
<podcast:transcript url="{base}/t.vtt" type="text/vtt"/></item></channel></rss>"""
                self._send(rss.encode(), "application/rss+xml")
            elif self.path == "/ep.mp3":
                self._send(ep_audio, "audio/mpeg")
            elif self.path == "/cover.png":
                self._send(cover_png, "image/png")
            elif self.path == "/t.vtt":
                self._send(vtt.encode(), "text/vtt")
            else:
                self._send(b"nope", "text/plain", 404)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/api/v1/audio/speech":
                state["tts_calls"] += 1
                state["tts_bodies"].append(body)
                self._send(tts_audio, "application/octet-stream")
            elif self.path == "/api/v1/chat/completions" and body.get("stream"):
                b64 = base64.b64encode(bed_audio).decode()
                half = len(b64) // 2
                lines = ""
                for part in (b64[:half], b64[half:]):
                    lines += "data: " + json.dumps({"choices": [{"delta": {"audio": {"data": part}}}]}) + "\n\n"
                lines += "data: [DONE]\n\n"
                self._send(lines.encode(), "text/event-stream")
            elif self.path == "/api/v1/chat/completions" and "image" in body.get("modalities", []):
                state["image_prompts"].append(body["messages"][0]["content"])
                url = "data:image/png;base64," + base64.b64encode(cover_png).decode()
                msg = {"role": "assistant", "content": "", "images": [{"type": "image_url", "image_url": {"url": url}}]}
                self._send(json.dumps({"choices": [{"message": msg}]}).encode(), "application/json")
            elif self.path == "/api/v1/chat/completions":
                state["chat_calls"] += 1
                segs = {"segments": [
                    {"title": "Intro", "summary": "s", "intro": "i", "start": 0, "end": 30, "score": 3, "kind": "intro"},
                    {"title": "Big story", "summary": "A big story.", "intro": "Here is a big story.",
                     "start": 33, "end": 153, "score": 9, "kind": "topic"},
                    {"title": "Ad", "summary": "ad", "intro": "ad", "start": 153, "end": 200, "score": 1, "kind": "ad"},
                ]}
                content = "```json\n" + json.dumps(segs) + "\n```"
                self._send(json.dumps({"choices": [{"message": {"content": content}}]}).encode(), "application/json")
            else:
                self._send(b"nope", "text/plain", 404)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, state
    srv.shutdown()


def test_full_pipeline(tmp_path, servers):
    srv, state = servers
    base = f"http://127.0.0.1:{srv.server_port}"
    data = tmp_path / "data"
    feeds = tmp_path / "feeds.yaml"
    feeds.write_text(f"feeds:\n  - name: Mock Show\n    url: {base}/feed.xml\n")
    cfg = Config(
        api_key="test", api_base=f"{base}/api/v1", data_dir=data, feeds_file=feeds,
        public_base_url="https://podcast.example.com", tz="Europe/Amsterdam",
    )
    conn = db.connect(cfg.db_path)
    cmd_run(cfg, conn)

    # database state
    assert conn.execute("SELECT status FROM episodes").fetchone()[0] == "used"
    item = conn.execute("SELECT * FROM items").fetchone()
    assert item["status"] == "used" and item["start_sec"] == 30 and item["end_sec"] == 150
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1

    # TTS: opening + announcement + closing, style passed as provider option, text verbatim
    assert state["tts_calls"] == 3
    body = state["tts_bodies"][0]
    assert body["response_format"] == "pcm"
    assert body["provider"]["options"]["google-ai-studio"]["speech_metadata"]["style"]
    assert body["input"].startswith("Hi Bram, this is your Q-rated selection")
    assert "First up, from Mock Show" in state["tts_bodies"][1]["input"]

    # bed generated and reused; ding synthesized
    assert (data / "assets" / "bed.mp3").exists() and (data / "assets" / "ding.mp3").exists()

    # final MP3
    mp3s = list((data / "public" / "editions").glob("qrated_*.mp3"))
    assert len(mp3s) == 1
    duration = audio.probe_duration(mp3s[0])
    assert 120 + 9 * 2 < duration < 120 + 60
    ed = conn.execute("SELECT * FROM editions").fetchone()
    assert abs(ed["duration"] - duration) < 0.01

    # cover art generated once from COVER_PROMPT, published as a square 1400 px JPEG
    assert len(state["image_prompts"]) == 1 and '"Q-rated"' in state["image_prompts"][0]
    cover = data / "public" / "cover.jpg"
    assert (data / "assets" / "cover.png").exists() and cover.exists()
    dims = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                           str(cover)], capture_output=True, text=True).stdout.strip()
    assert dims == "1400,1400"

    # work dir cleaned
    assert not any((data / "work").iterdir())

    # feed XML valid
    root = ET.parse(data / "public" / "feed.xml").getroot()
    itunes = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
    assert root.find(f"channel/{itunes}image").get("href").startswith("https://podcast.example.com/cover.jpg?v=")
    assert root.find("channel/image/url").text.startswith("https://podcast.example.com/cover.jpg")
    assert "Bram follows" in root.find("channel/description").text
    enclosure = root.find("channel/item/enclosure")
    assert enclosure.get("url").startswith("https://podcast.example.com/editions/qrated_")
    assert int(enclosure.get("length")) == mp3s[0].stat().st_size
    assert "Big story" in root.find("channel/item/description").text

    # homepage with player, cover thumbnail and inventory
    covers = list((data / "public" / "covers").glob("*"))
    assert len(covers) == 1 and covers[0].name.endswith("_600.jpg")  # square thumbnail, not the original
    import subprocess as sp
    dims = sp.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                   str(covers[0])], capture_output=True, text=True).stdout.strip()
    assert dims == "600,600"
    page = (data / "public" / "index.html").read_text(encoding="utf-8")
    assert f'src="editions/{mp3s[0].name}"' in page
    assert f'src="covers/{covers[0].name}"' in page
    assert "Big story" in page and "Shows in the mix <small>1</small>" in page
    assert 'class="logo"><img src="cover.jpg?v=' in page and "og:image" in page

    # chapter offsets of the story inside the edition (after opening + ding)
    item = conn.execute("SELECT * FROM items").fetchone()
    assert 4 < item["chapter_start"] < item["chapter_end"] <= duration + 0.5
    assert item["chapter_end"] - item["chapter_start"] > 120  # ding + announcement + fragment + silence
    assert 'data-chapter="1"' in page and "[0:" in ed["description"]

    # second run: nothing new -> no second edition, no more chat calls
    cmd_run(cfg, conn)
    assert state["chat_calls"] == 1
    assert len(list((data / "public" / "editions").glob("*.mp3"))) == 1

    # rebuild: same stories and date, new audio (TTS only), still one edition, no re-analysis
    old_ed = conn.execute("SELECT * FROM editions").fetchone()
    cmd_rebuild(cfg, conn)
    assert state["chat_calls"] == 1 and state["tts_calls"] == 6
    assert len(state["image_prompts"]) == 1  # cover reused, not regenerated
    eds = conn.execute("SELECT * FROM editions").fetchall()
    assert len(eds) == 1 and eds[0]["id"] != old_ed["id"] and eds[0]["created_at"] == old_ed["created_at"]
    assert [p.name for p in (data / "public" / "editions").glob("*.mp3")] == [old_ed["file_name"]]
    item = conn.execute("SELECT * FROM items").fetchone()
    assert item["edition_id"] == eds[0]["id"] and item["status"] == "used" and item["chapter_start"] > 0
