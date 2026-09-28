"""Inter-process lock so manual and scheduled runs never overlap."""

from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path


class LockBusy(RuntimeError):
    pass


@contextmanager
def file_lock(path: Path, blocking: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(fh, flags)
        except BlockingIOError as exc:
            raise LockBusy(f"another qrated process holds {path}") from exc
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
