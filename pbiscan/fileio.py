"""File writing helpers shared by suppressions and remediation."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional


def atomic_write_text(path: Path, text: str, newline: Optional[str] = None) -> None:
    """Write via a temp file in the same directory, then rename over the target,
    so a crash mid-write leaves either the old file or the new one, never half of each.

    `newline` is passed to open(): None translates "\\n" to the platform line
    ending, "\\n" or "\\r\\n" writes exactly that.
    """
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
