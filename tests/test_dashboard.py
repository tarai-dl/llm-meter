from llm_meter.dashboard import render_dashboard
from llm_meter.storage import ingest_lines


def test_render_dashboard_contains_metrics(tmp_path):
    db = tmp_path / "meter.db"
    ingest_lines([
        '203.0.113.10 realip=- cf=- host=a.example auth_prefix=a [09/Jun/2026:02:00:01 +0000] "GET /v1/models HTTP/2.0" 200 1 rt=0.1 uct=0.01 urt=0.09 "-" "curl"',
        '198.51.100.23 realip=- cf=- host=a.example auth_prefix=- [09/Jun/2026:02:00:02 +0000] "GET /v1/models HTTP/2.0" 401 1 rt=0.1 uct=0.01 urt=0.09 "-" "curl"',
    ], db)

    html = render_dashboard(db)
    assert "LLM Meter" in html
    assert "Requests" in html
    assert "203.0.113.10" in html
    assert "/api/report" in html
    assert "Hourly trend" in html
