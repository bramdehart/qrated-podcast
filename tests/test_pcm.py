import subprocess

from qrated import audio


def test_pcm_to_wav_duration(tmp_path):
    pcm = tmp_path / "x.pcm"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=2:r=24000",
                    "-ac", "1", "-f", "s16le", str(pcm)], check=True)
    out = audio.pcm_to_wav(pcm.read_bytes(), tmp_path / "x.wav", 24000)
    assert abs(audio.probe_duration(out) - 2.0) < 0.05
    assert not (tmp_path / "x.pcm.tmp").exists()
