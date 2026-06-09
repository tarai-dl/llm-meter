from llm_meter.demo import create_demo
from llm_meter.storage import report_from_db


def test_create_demo_writes_jsonl_db_and_html(tmp_path):
    output_dir = tmp_path / "demo"

    result = create_demo(output_dir, rows=24)

    assert result["log_path"].endswith("demo-gateway.jsonl")
    assert result["db_path"].endswith("demo.db")
    assert result["html_path"].endswith("demo-report.html")
    assert result["bundle_path"].endswith("demo-report.zip")
    assert result["rows"] == 24

    log_path = output_dir / "demo-gateway.jsonl"
    db_path = output_dir / "demo.db"
    html_path = output_dir / "demo-report.html"
    bundle_path = output_dir / "demo-report.zip"
    assert log_path.exists()
    assert db_path.exists()
    assert html_path.exists()
    assert bundle_path.exists()

    report = report_from_db(db_path)
    payload = report.to_dict()
    assert payload["parsed_lines"] == 24
    assert payload["tokens"]["total"] > 0
    assert payload["cost"]["total_usd"] > 0
    assert payload["models"]
    html = html_path.read_text(encoding="utf-8")
    assert "Estimated cost" in html
    assert "Cost by model" in html

    import zipfile

    with zipfile.ZipFile(bundle_path) as archive:
        assert sorted(archive.namelist()) == ["manifest.json", "report.html", "report.json", "report.md"]


def test_create_demo_is_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    create_demo(first, rows=5)
    create_demo(second, rows=5)

    assert (first / "demo-gateway.jsonl").read_text(encoding="utf-8") == (second / "demo-gateway.jsonl").read_text(encoding="utf-8")
