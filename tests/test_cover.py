import subprocess

from qrated import cover
from qrated.config import Config
from qrated.openrouter import OpenRouterError


def _png(path, color="blue", size="800x600"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s={size}",
                    "-frames:v", "1", str(path)], check=True)


def _dims(path):
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                           str(path)], capture_output=True, text=True).stdout.strip()


class Broken:
    calls = 0

    def image(self, prompt):
        Broken.calls += 1
        raise OpenRouterError("down")


def test_fallback_then_user_cover_wins(tmp_path):
    cfg = Config(data_dir=tmp_path)
    assert cover.cover_url(cfg) is None
    path = cover.ensure_cover(cfg, Broken())
    assert (cfg.assets_dir / "cover_fallback.png").exists()
    assert not (cfg.assets_dir / "cover.png").exists()  # generation is retried next time
    assert _dims(path) == "1400,1400" and cover.cover_url(cfg).startswith("cover.jpg?v=")

    _png(cfg.assets_dir / "cover.jpg", "green", "3000x2000")  # user-provided, non-square
    before = Broken.calls
    path = cover.ensure_cover(cfg, Broken())
    assert Broken.calls == before  # no generation when a cover exists
    assert _dims(path) == "1400,1400"


def test_prompt_placeholders(tmp_path):
    seen = []

    class Client:
        def image(self, prompt):
            seen.append(prompt)
            _png(tmp_path / "gen.png")
            return (tmp_path / "gen.png").read_bytes()

    cfg = Config(data_dir=tmp_path / "d", feed_title="My Show", cover_prompt="Cover for {title} by {name}")
    cover.ensure_cover(cfg, Client())
    assert seen == ["Cover for My Show by Bram"]
    cover.ensure_cover(cfg, Client())
    assert len(seen) == 1  # generated once, reused
    cover.ensure_cover(cfg, Client(), force=True)
    assert len(seen) == 2  # make-cover regenerates
