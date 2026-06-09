from __future__ import annotations

from collections import Counter
from pathlib import Path
import sqlite3
from typing import Iterable

from .analyzer import Report, add_entry
from .parser import LogEntry, parse_line

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    ip TEXT NOT NULL,
    host TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status INTEGER NOT NULL,
    body_bytes INTEGER NOT NULL,
    auth_prefix TEXT NOT NULL,
    request_time REAL,
    upstream_response_time REAL,
    raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_ts ON entries(ts);
CREATE INDEX IF NOT EXISTS idx_entries_ip ON entries(ip);
CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status);
CREATE INDEX IF NOT EXISTS idx_entries_host ON entries(host);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def ingest_lines(lines: Iterable[str], db_path: str | Path, batch_size: int = 1000) -> dict:
    conn = connect(db_path)
    parsed = 0
    failed = 0
    inserted = 0
    rows: list[tuple] = []

    def flush() -> None:
        nonlocal inserted, rows
        if not rows:
            return
        with conn:
            conn.executemany(
                """
                INSERT INTO entries (
                    ts, ip, host, method, path, status, body_bytes, auth_prefix,
                    request_time, upstream_response_time, raw
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        inserted += len(rows)
        rows = []

    try:
        for line in lines:
            entry = parse_line(line)
            if not entry:
                failed += 1
                continue
            parsed += 1
            rows.append(_entry_to_row(entry))
            if len(rows) >= batch_size:
                flush()
    finally:
        flush()
        conn.close()

    return {"parsed": parsed, "failed": failed, "inserted": inserted}


def _entry_to_row(entry: LogEntry) -> tuple:
    return (
        entry.time.isoformat() if entry.time else None,
        entry.ip,
        entry.host,
        entry.method,
        entry.path,
        entry.status,
        entry.body_bytes,
        entry.auth_prefix,
        entry.request_time,
        entry.upstream_response_time,
        entry.raw,
    )


def report_from_db(db_path: str | Path, limit: int | None = None) -> Report:
    conn = connect(db_path)
    sql = "SELECT * FROM entries ORDER BY id"
    params: tuple = ()
    if limit is not None:
        sql += " DESC LIMIT ?"
        params = (limit,)
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    report = Report(total=len(rows))
    # If newest rows were fetched DESC, make time range and output deterministic.
    for row in reversed(rows) if limit is not None else rows:
        entry = LogEntry(
            ip=row["ip"],
            time=_parse_iso(row["ts"]),
            method=row["method"],
            path=row["path"],
            protocol="-",
            status=row["status"],
            body_bytes=row["body_bytes"],
            host=row["host"],
            auth_prefix=row["auth_prefix"],
            request_time=row["request_time"],
            upstream_response_time=row["upstream_response_time"],
            raw=row["raw"],
        )
        add_entry(report, entry)
    return report


def _parse_iso(value: str | None):
    if not value:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def hourly_counts(db_path: str | Path) -> list[dict]:
    conn = connect(db_path)
    rows = conn.execute(
        """
        SELECT substr(ts, 1, 13) AS hour, COUNT(*) AS requests,
               SUM(CASE WHEN status BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS ok,
               SUM(CASE WHEN status BETWEEN 400 AND 499 THEN 1 ELSE 0 END) AS client_errors,
               SUM(CASE WHEN status BETWEEN 500 AND 599 THEN 1 ELSE 0 END) AS server_errors
        FROM entries
        WHERE ts IS NOT NULL
        GROUP BY hour
        ORDER BY hour
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
