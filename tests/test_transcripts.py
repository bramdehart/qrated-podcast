import json

from qrated.transcripts import Cue, compact, parse_transcript, snap_segment

VTT = """WEBVTT

00:00:01.000 --> 00:00:04.500
<v Alice>Hello &amp; welcome</v>

2
00:00:04.500 --> 00:00:09.000
second line
continues here

01:00:00.250 --> 01:00:02.000
late cue
"""

SRT = """1
00:00:01,000 --> 00:00:04,500
Hello there

2
00:00:05,000 --> 00:00:08,000
General Kenobi
"""


def test_parse_vtt():
    cues = parse_transcript(VTT, "vtt")
    assert [c.text for c in cues] == ["Hello & welcome", "second line continues here", "late cue"]
    assert cues[0].start == 1.0 and cues[0].end == 4.5
    assert cues[2].start == 3600.25


def test_parse_srt():
    cues = parse_transcript(SRT, "srt")
    assert len(cues) == 2
    assert cues[1].start == 5.0 and cues[1].text == "General Kenobi"


def test_parse_json():
    data = {"version": "1.0.0", "segments": [
        {"speaker": "A", "startTime": 0, "endTime": 2.5, "body": "Hi"},
        {"startTime": 2.5, "endTime": 4, "body": "there"},
        {"startTime": 5, "body": ""},
    ]}
    cues = parse_transcript(json.dumps(data), "json")
    assert [(c.start, c.end, c.text) for c in cues] == [(0.0, 2.5, "Hi"), (2.5, 4.0, "there")]


def test_compact():
    assert compact([Cue(1.9, 3, "a"), Cue(4, 5, "b")]) == "[1] a\n[4] b"


def _cues():
    return [Cue(i * 10, i * 10 + 10, f"c{i}") for i in range(60)]


def test_snap_to_cue_boundaries():
    s, e = snap_segment(_cues(), 13, 187, 60, 480)
    assert s == 10 and e == 190


def test_snap_trims_overlong():
    s, e = snap_segment(_cues(), 0, 600, 60, 250)
    assert (s, e) == (0, 250)


def test_snap_too_short():
    assert snap_segment(_cues(), 0, 30, 60, 480) is None
