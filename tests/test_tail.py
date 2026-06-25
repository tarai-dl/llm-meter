from __future__ import annotations

from pathlib import Path
import threading
import time

from llm_meter.tail import follow_file


def test_follow_file_reads_appended_line(tmp_path):
    log = tmp_path / "access.log"
    log.write_text("old line\n")

    follower = follow_file(log, interval=0.01, from_end=True)

    def append_later():
        time.sleep(0.05)
        with log.open("a") as handle:
            handle.write("new line\n")

    thread = threading.Thread(target=append_later)
    thread.start()
    try:
        assert next(follower) == "new line\n"
    finally:
        follower.close()
        thread.join(timeout=1)


def test_follow_file_can_read_from_start(tmp_path):
    log = tmp_path / "access.log"
    log.write_text("first line\n")
    follower = follow_file(log, interval=0.01, from_end=False)
    try:
        assert next(follower) == "first line\n"
    finally:
        follower.close()


def test_follow_file_truncates_long_lines(tmp_path):
    log = tmp_path / "access.log"
    long_line = "x" * 5000 + "\n"
    log.write_text(long_line)
    follower = follow_file(log, interval=0.01, from_end=False, max_line_length=100)
    try:
        result = next(follower)
        # readline(size) reads at most size bytes; long lines are truncated.
        assert len(result) == 100
        assert result == "x" * 100
    finally:
        follower.close()
