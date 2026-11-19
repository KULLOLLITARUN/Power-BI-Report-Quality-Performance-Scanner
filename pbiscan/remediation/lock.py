"""One apply at a time per project.

Two `pbiscan fix` runs on the same project (two terminals, CLI plus Studio, an MCP client)
would interleave writes, backups and rollbacks. `apply` holds a lock file beside the project
folder while it writes; a second apply finds it and is refused instead of racing.

The lock lives next to the project, not inside it, because a rollback swaps the whole project
folder for its backup. A lock older than STALE_AFTER_SECONDS is taken to be left over from a
crashed run and is replaced; an apply takes seconds, so an hour is generous.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

STALE_AFTER_SECONDS = 3600.0


class ProjectLockedError(Exception):
    """Another apply holds this project's lock."""

    def __init__(self, lock_path: Path) -> None:
        super().__init__(
            f"Another `pbiscan fix` is applying changes to this project (lock file {lock_path}). "
            "If none is running, delete that file and try again."
        )
        self.lock_path = lock_path


def lock_path_for(project_path: Path) -> Path:
    return project_path.parent / f"{project_path.name}.pbiscan.lock"


def _try_create(lock: Path) -> bool:
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(f"pid={os.getpid()} started={time.time():.0f}\n")
    return True


@contextmanager
def project_lock(project_path: Path, stale_after: float = STALE_AFTER_SECONDS) -> Iterator[Path]:
    """Hold the project's apply lock for the duration of the block, or raise ProjectLockedError."""
    lock = lock_path_for(project_path)
    if not _try_create(lock):
        try:
            age = time.time() - lock.stat().st_mtime
        except FileNotFoundError:
            age = stale_after + 1  # released between the two calls
        if age <= stale_after:
            raise ProjectLockedError(lock)
        lock.unlink(missing_ok=True)
        if not _try_create(lock):
            raise ProjectLockedError(lock)
    try:
        yield lock
    finally:
        lock.unlink(missing_ok=True)
