from __future__ import annotations

from pathlib import Path
import time
from typing import Iterator, TextIO


def follow_file(path: str | Path, interval: float = 1.0, from_end: bool = True) -> Iterator[str]:
    """Yield new lines appended to a file, similar to tail -f.

    This is deliberately small and dependency-free. It handles simple log rotation by
    reopening the file when its inode changes or the file shrinks.
    """
    path = Path(path)
    handle: TextIO | None = None
    inode: int | None = None
    position = 0

    try:
        while True:
            try:
                stat = path.stat()
            except FileNotFoundError:
                time.sleep(interval)
                continue

            if handle is None or inode != stat.st_ino or stat.st_size < position:
                if handle is not None:
                    handle.close()
                handle = path.open("r", encoding="utf-8", errors="replace")
                inode = stat.st_ino
                if from_end:
                    handle.seek(0, 2)
                position = handle.tell()

            line = handle.readline()
            if line:
                position = handle.tell()
                yield line
            else:
                time.sleep(interval)
    finally:
        if handle is not None:
            handle.close()
