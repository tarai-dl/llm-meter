from __future__ import annotations

import csv
import os
from pathlib import Path
import sqlite3

from .storage import connect

CSV_COLUMNS = [
    "id",
    "ts",
    "ip",
    "host",
    "method",
    "path",
    "status",
    "body_bytes",
    "auth_prefix",
    "request_time",
    "upstream_response_time",
    "model",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
]


def export_csv(db_path: str | Path, output: str | Path, limit: int | None = None) -> dict:
    """Export stored gateway entries to a spreadsheet-friendly CSV file."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(db_path)
    try:
        rows = _fetch_rows(conn, limit=limit)
    finally:
        conn.close()

    tmp = output.with_suffix(output.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in CSV_COLUMNS})
    os.replace(tmp, output)

    return {"output": str(output), "rows": len(rows)}


def _fetch_rows(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    sql = f"SELECT {', '.join(CSV_COLUMNS)} FROM entries ORDER BY id"
    params: tuple[int, ...] = ()
    if limit is not None:
        sql += " DESC LIMIT ?"
        params = (limit,)
    rows = conn.execute(sql, params).fetchall()
    return list(reversed(rows)) if limit is not None else list(rows)
