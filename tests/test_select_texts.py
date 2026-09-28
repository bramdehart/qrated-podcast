from datetime import date, datetime

from qrated import db
from qrated.cli import next_run
from qrated.config import Config
from qrated.select import select_items
from qrated.texts import lead_for, ordinal, render, spoken_date


def test_select_caps(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    for i, pod in enumerate(["A", "B"]):
        conn.execute("INSERT INTO episodes (guid, podcast, title, status) VALUES (?,?,?, 'analyzed')", (f"g{i}", pod, "t"))
    scores = [("g0", 9), ("g0", 8), ("g0", 7), ("g1", 6), ("g1", 5), ("g1", 8.5)]
    for g, s in scores:
        conn.execute("INSERT INTO items (episode_guid, title, score, status) VALUES (?,?,?, 'candidate')", (g, "x", s))
    cfg = Config(max_items=3, max_items_per_podcast=2, min_score=6)
    got = [(r["podcast"], r["score"]) for r in select_items(conn, cfg)]
    assert got == [("A", 9), ("B", 8.5), ("A", 8)]
    cfg = Config(max_items=10, max_items_per_podcast=2, min_score=6)
    assert len(select_items(conn, cfg)) == 4  # score 5 excluded, A capped at 2, B has 2 above min


def test_dates_and_leads():
    assert spoken_date(date(2026, 9, 29)) == "Tuesday, September 29th"
    assert spoken_date(date(2026, 9, 24), weekday=False) == "September 24th"
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]
    assert [lead_for(i, 4) for i in range(4)] == ["First up", "Next up", "Next up", "And finally"]
    assert [lead_for(i, 2) for i in range(2)] == ["First up", "Next up"]
    assert render("{a} {b}", a="x") == "x {b}"


def test_next_run():
    now = datetime(2026, 9, 28, 7, 0)
    assert next_run(["06:00", "18:30"], now) == datetime(2026, 9, 28, 18, 30)
    assert next_run(["06:00"], now) == datetime(2026, 9, 29, 6, 0)


def test_config_defaults_and_env():
    cfg = Config.from_env({"MAX_ITEMS": "3", "SCHEDULE_TIMES": "06:00, 18:00", "INTRO_TEXT": "Hi {name}"})
    assert cfg.max_items == 3 and cfg.schedule_times == ["06:00", "18:00"]
    assert cfg.intro_text == "Hi {name}" and cfg.llm_model == "google/gemini-3.5-flash-lite"
