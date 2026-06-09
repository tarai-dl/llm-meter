from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from . import __version__
from .dashboard import render_dashboard
from .markdown import render_markdown_report
from .storage import hourly_counts, report_from_db

BUNDLE_FILES = ["report.html", "report.md", "report.json", "manifest.json"]


def export_bundle(db_path: str | Path, output: str | Path, top: int = 10) -> dict:
    db_path = Path(db_path)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    report = report_from_db(db_path)
    payload = report.to_dict(top=top)
    payload["hourly"] = hourly_counts(db_path)
    manifest = _manifest(payload)

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("report.html", render_dashboard(db_path))
        archive.writestr("report.md", render_markdown_report(db_path, top=top))
        archive.writestr("report.json", json.dumps(payload, indent=2, ensure_ascii=False))
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    return {"output": str(output), "files": BUNDLE_FILES}


def _manifest(payload: dict) -> dict:
    return {
        "tool": "llm-meter",
        "version": __version__,
        "parsed_lines": payload.get("parsed_lines", 0),
        "first_seen": payload.get("first_seen"),
        "last_seen": payload.get("last_seen"),
        "total_tokens": payload.get("tokens", {}).get("total", 0),
        "estimated_cost_usd": payload.get("cost", {}).get("total_usd", 0),
        "signals": len(payload.get("signals") or []),
        "files": BUNDLE_FILES[:-1],
    }
