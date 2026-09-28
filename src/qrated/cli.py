"""Command line interface and scheduler."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import audio, db
from .analyze import analyze_new
from .build import build_edition, rebuild_latest
from .config import Config
from .feeds import fetch_all, load_feed_specs
from .lock import file_lock
from .openrouter import OpenRouter
from .site import write_index

log = logging.getLogger("qrated")


def cmd_fetch(cfg: Config, conn) -> None:
    result = fetch_all(conn, load_feed_specs(cfg.feeds_file), cfg.first_run_lookback_days, cfg.covers_dir)
    write_index(conn, cfg)
    log.info("Fetch done: %s", result)


def cmd_analyze(cfg: Config, conn) -> None:
    log.info("Analyze done: %s", analyze_new(conn, OpenRouter(cfg), cfg))


def cmd_build(cfg: Config, conn) -> None:
    edition = build_edition(conn, OpenRouter(cfg), cfg)
    log.info("Build done: edition=%s", edition)


def cmd_rebuild(cfg: Config, conn) -> None:
    log.info("Rebuild done: edition=%s", rebuild_latest(conn, OpenRouter(cfg), cfg))


def cmd_run(cfg: Config, conn) -> None:
    cmd_fetch(cfg, conn)
    cmd_analyze(cfg, conn)
    cmd_build(cfg, conn)


def cmd_make_bed(cfg: Config, conn) -> None:
    path = audio.generate_bed(cfg, OpenRouter(cfg), force=True)
    log.info("Music bed ready: %s", path)


def cmd_status(cfg: Config, conn) -> None:
    print("Feeds:")
    for f in conn.execute("SELECT * FROM feeds ORDER BY name"):
        err = f" ERROR: {f['last_error']}" if f["last_error"] else ""
        print(f"  {f['name'] or f['url']}  last_checked={f['last_checked']}{err}")
    print("Episodes by status:")
    for r in conn.execute("SELECT status, COUNT(*) AS n FROM episodes GROUP BY status ORDER BY status"):
        print(f"  {r['status']}: {r['n']}")
    print("Recent editions:")
    for e in conn.execute("SELECT * FROM editions ORDER BY id DESC LIMIT 5"):
        print(f"  {e['file_name']}  {e['duration'] or 0:.0f}s  {e['title']}")


def next_run(times: list[str], now: datetime) -> datetime:
    """Next datetime (in now's timezone) matching one of the HH:MM schedule times."""
    candidates = []
    for t in times:
        hh, mm = (int(x) for x in t.split(":"))
        c = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if c <= now:
            c += timedelta(days=1)
        candidates.append(c)
    return min(candidates)


def cmd_serve(cfg: Config, conn) -> None:
    conn.close()
    tz = ZoneInfo(cfg.tz)
    log.info("Scheduler started; times=%s tz=%s", cfg.schedule_times, cfg.tz)
    while True:
        now = datetime.now(tz)
        target = next_run(cfg.schedule_times, now)
        log.info("Next run at %s", target.isoformat())
        while datetime.now(tz) < target:
            time.sleep(min(30, max((target - datetime.now(tz)).total_seconds(), 0.5)))
        try:
            run_locked(cfg, cmd_run)
        except Exception:  # noqa: BLE001 - keep the scheduler alive
            log.exception("Scheduled run failed")


def run_locked(cfg: Config, fn) -> None:
    with file_lock(cfg.lock_path):
        conn = db.connect(cfg.db_path)
        try:
            fn(cfg, conn)
        finally:
            conn.close()


COMMANDS = {
    "run": cmd_run, "fetch": cmd_fetch, "analyze": cmd_analyze, "build": cmd_build,
    "rebuild": cmd_rebuild, "status": cmd_status, "make-bed": cmd_make_bed,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qrated", description="Personal AI-curated daily podcast")
    parser.add_argument("command", choices=[*COMMANDS, "serve"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Config.from_env()
    if args.command == "serve":
        cmd_serve(cfg, db.connect(cfg.db_path))
    elif args.command == "status":
        conn = db.connect(cfg.db_path)
        cmd_status(cfg, conn)
    else:
        run_locked(cfg, COMMANDS[args.command])
    return 0


if __name__ == "__main__":
    sys.exit(main())
