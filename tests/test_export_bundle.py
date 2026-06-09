import json
from zipfile import ZipFile

from llm_meter.bundle import export_bundle
from llm_meter.storage import ingest_lines


def _seed_db(db):
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


def test_export_bundle_writes_zip_with_reports_and_manifest(tmp_path):
    db = tmp_path / "meter.db"
    bundle = tmp_path / "llm-meter-bundle.zip"
    _seed_db(db)

    result = export_bundle(db, bundle)

    assert result["output"] == str(bundle)
    assert result["files"] == ["report.html", "report.md", "report.json", "manifest.json"]
    assert bundle.exists()

    with ZipFile(bundle) as archive:
        assert sorted(archive.namelist()) == ["manifest.json", "report.html", "report.json", "report.md"]
        manifest = json.loads(archive.read("manifest.json"))
        report = json.loads(archive.read("report.json"))
        markdown = archive.read("report.md").decode("utf-8")
        html = archive.read("report.html").decode("utf-8")

    assert manifest["tool"] == "llm-meter"
    assert manifest["parsed_lines"] == 2
    assert manifest["total_tokens"] == 4500
    assert manifest["estimated_cost_usd"] == 0.018675
    assert report["tokens"]["total"] == 4500
    assert "# LLM Meter Report" in markdown
    assert "Estimated cost" in html


def test_export_bundle_cli_writes_zip(tmp_path):
    from llm_meter.__main__ import main

    db = tmp_path / "meter.db"
    bundle = tmp_path / "bundle.zip"
    _seed_db(db)

    exit_code = main(["export-bundle", "--db", str(db), "--output", str(bundle)])

    assert exit_code == 0
    with ZipFile(bundle) as archive:
        assert "manifest.json" in archive.namelist()
        assert "report.md" in archive.namelist()
