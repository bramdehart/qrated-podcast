import pytest

from qrated import audio, openrouter
from qrated.config import Config
from qrated.openrouter import OpenRouter, OpenRouterError, parse_json_lenient


def test_lenient_json():
    assert parse_json_lenient('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_lenient('Sure! {"a": 2} done') == {"a": 2}


class FakeResp:
    def __init__(self, code, text="x"):
        self.status_code, self.text, self.content = code, text, b"audio"


def test_retry_and_fail_fast(monkeypatch):
    monkeypatch.setattr(openrouter.time, "sleep", lambda s: None)
    client = OpenRouter(Config(api_key="k"))
    calls = []
    seq = iter([FakeResp(429), FakeResp(503), FakeResp(200)])
    monkeypatch.setattr(client.session, "post", lambda *a, **k: (calls.append(1), next(seq))[1])
    assert client.tts("hi") == b"audio"
    assert len(calls) == 3
    calls.clear()
    monkeypatch.setattr(client.session, "post", lambda *a, **k: (calls.append(1), FakeResp(400))[1])
    with pytest.raises(OpenRouterError):
        client.tts("hi")
    assert len(calls) == 1
    assert client.session.headers["X-Title"] == "qrated"


def test_bed_fallback_and_user_bed(tmp_path):
    cfg = Config(data_dir=tmp_path)

    class Broken:
        def music(self, prompt):
            raise OpenRouterError("down")

    path = audio.generate_bed(cfg, Broken())
    assert path.name == "bed_fallback.mp3" and audio.probe_duration(path) > 10
    assert not (cfg.assets_dir / "bed.mp3").exists()  # Lyria retried next time

    user_bed = cfg.assets_dir / "bed.mp3"
    user_bed.write_bytes(b"mine")
    assert audio.generate_bed(cfg, Broken()) == user_bed  # user-provided bed wins
