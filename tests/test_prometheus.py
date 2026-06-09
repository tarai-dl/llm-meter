from llm_meter.prometheus import render_prometheus_metrics
from llm_meter.storage import ingest_lines


def test_render_prometheus_metrics_from_sqlite(tmp_path):
    db = tmp_path / "meter.db"
    ingest_lines([
        '203.0.113.10 realip=- cf=- host=a.example auth_prefix=a [09/Jun/2026:02:00:01 +0000] "GET /v1/models HTTP/2.0" 200 1 rt=0.1 uct=0.01 urt=0.09 "-" "curl"',
        '198.51.100.23 realip=- cf=- host=a.example auth_prefix=- [09/Jun/2026:02:00:02 +0000] "POST /v1/chat/completions HTTP/2.0" 429 1 rt=0.2 uct=0.01 urt=0.19 "-" "curl"',
    ], db)

    text = render_prometheus_metrics(db)
    assert '# HELP llm_meter_requests_total Total parsed gateway requests' in text
    assert '# TYPE llm_meter_requests_total counter' in text
    assert 'llm_meter_requests_total 2' in text
    assert 'llm_meter_status_total{status="200"} 1' in text
    assert 'llm_meter_status_total{status="429"} 1' in text
    assert 'llm_meter_status_class_total{status_class="2xx"} 1' in text
    assert 'llm_meter_status_class_total{status_class="4xx"} 1' in text
    assert 'llm_meter_host_requests_total{host="a.example"} 2' in text
    assert 'llm_meter_path_requests_total{path="/v1/models"} 1' in text
    assert 'llm_meter_latency_seconds_max 0.2' in text


def test_prometheus_escapes_labels(tmp_path):
    db = tmp_path / "meter.db"
    ingest_lines([
        '203.0.113.10 realip=- cf=- host=weird.example auth_prefix=a [09/Jun/2026:02:00:01 +0000] "GET /path?x=1 HTTP/2.0" 200 1 rt=0.1 uct=0.01 urt=0.09 "-" "curl"',
    ], db)
    text = render_prometheus_metrics(db)
    assert 'path="/path"' in text
