from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from .bundle import export_bundle
from .dashboard import render_dashboard
from .storage import ingest_lines

MODELS = [
    ("gpt-4o-mini", 0.00000045),
    ("claude-3-5-sonnet", 0.000006),
    ("qwen2.5-coder", 0.00000025),
    ("llama-3.1-70b", 0.0000008),
]
IPS = ["203.0.113.10", "198.51.100.23", "192.0.2.44", "203.0.113.77"]
PATHS = ["/v1/chat/completions", "/v1/responses", "/v1/models"]
AUTH_PREFIXES = ["sk-live-", "sk-test-", "ak-prod-", "-"]
STATUSES = [200, 200, 200, 200, 401, 429, 500]


def create_demo(output_dir: str | Path, rows: int = 96) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "demo-gateway.jsonl"
    db_path = output / "demo.db"
    html_path = output / "demo-report.html"
    bundle_path = output / "demo-report.zip"

    lines = list(_demo_lines(rows))
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if db_path.exists():
        db_path.unlink()
    ingest_lines(lines, db_path)
    html_path.write_text(render_dashboard(db_path), encoding="utf-8")
    export_bundle(db_path, bundle_path)

    return {
        "rows": rows,
        "log_path": str(log_path),
        "db_path": str(db_path),
        "html_path": str(html_path),
        "bundle_path": str(bundle_path),
    }


def _demo_lines(rows: int):
    start = datetime(2026, 6, 9, 0, 0, tzinfo=timezone.utc)
    for index in range(rows):
        model, price_per_token = MODELS[index % len(MODELS)]
        prompt_tokens = 180 + (index * 37) % 1800
        completion_tokens = 40 + (index * 19) % 900
        total_tokens = prompt_tokens + completion_tokens
        status = STATUSES[index % len(STATUSES)]
        yield json.dumps(
            {
                "timestamp": (start + timedelta(minutes=5 * index)).isoformat().replace("+00:00", "Z"),
                "ip": IPS[index % len(IPS)],
                "host": "api.example",
                "method": "POST" if index % 5 else "GET",
                "path": PATHS[index % len(PATHS)],
                "status": status,
                "auth_prefix": AUTH_PREFIXES[index % len(AUTH_PREFIXES)],
                "request_time_ms": 120 + (index * 113) % 12000,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(total_tokens * price_per_token, 8),
            },
            sort_keys=True,
        )
