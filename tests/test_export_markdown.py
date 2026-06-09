import json

from llm_meter.markdown import render_markdown_report
from llm_meter.storage import ingest_lines


def test_render_markdown_report_contains_operational_sections(tmp_path):
    db = tmp_path / "meter.db"
    ingest_lines([
        json.dumps({
            "timestamp": "2026-06-09T02:00:00Z",
            "ip": "203.0.113.10",
            "host": "api.example",
            "method": "POST",
            "path": "/v1/chat/completions",
            "status": 200,
            "model": "gpt-4o-mini",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "cost_usd": 0.000675,
        }),
        json.dumps({
            "timestamp": "2026-06-09T03:00:00Z",
            "ip": "198.51.100.23",
            "host": "api.example",
            "method": "POST",
            "path": "/v1/responses",
            "status": 429,
            "model": "claude-3-5-sonnet",
            "prompt_tokens": 2000,
            "completion_tokens": 1000,
            "total_tokens": 3000,
            "cost_usd": 0.018,
        }),
    ], db)

    markdown = render_markdown_report(db)

    assert markdown.startswith("# LLM Meter Report")
    assert "## Summary" in markdown
    assert "## Token and cost" in markdown
    assert "## Top models" in markdown
    assert "## Signals" in markdown
    assert "gpt-4o-mini" in markdown
    assert "claude-3-5-sonnet" in markdown
    assert "0.018675" in markdown
    assert "| 429 | 1 |" in markdown


def test_export_markdown_cli_writes_file(tmp_path):
    from llm_meter.__main__ import main

    db = tmp_path / "meter.db"
    output = tmp_path / "report.md"
    ingest_lines([
        '203.0.113.10 realip=- cf=- host=a.example auth_prefix=a [09/Jun/2026:02:00:01 +0000] "GET /v1/models HTTP/2.0" 200 1 rt=0.1 uct=0.01 urt=0.09 "-" "curl"',
    ], db)

    exit_code = main(["export-markdown", "--db", str(db), "--output", str(output)])

    assert exit_code == 0
    content = output.read_text(encoding="utf-8")
    assert "# LLM Meter Report" in content
    assert "## Summary" in content
