from __future__ import annotations

import threading
import time
from http.server import HTTPServer

from llm_meter.dashboard import render_dashboard, _check_auth, serve_dashboard
from llm_meter.storage import ingest_lines


def test_check_auth_validates_bearer_token():
    class FakeHandler:
        def __init__(self, auth_header):
            self.headers = {"Authorization": auth_header} if auth_header else {}

    assert _check_auth(FakeHandler("Bearer secret123"), "secret123") is True
    assert _check_auth(FakeHandler("Bearer wrong"), "secret123") is False
    assert _check_auth(FakeHandler(""), "secret123") is False
    assert _check_auth(FakeHandler("Basic abc"), "secret123") is False


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
    assert "Hourly chart" in html
    assert "<svg" in html
    assert "client_errors" in html


def test_render_dashboard_limit_shows_recent_entries_only(tmp_path):
    db = tmp_path / "meter.db"
    ingest_lines([
        '203.0.113.10 realip=- cf=- host=a.example auth_prefix=a [09/Jun/2026:01:00:01 +0000] "GET /old HTTP/2.0" 200 1 rt=0.1 uct=0.01 urt=0.09 "-" "curl"',
        '198.51.100.23 realip=- cf=- host=a.example auth_prefix=b [09/Jun/2026:02:00:01 +0000] "GET /new HTTP/2.0" 500 1 rt=0.2 uct=0.01 urt=0.2 "-" "curl"',
    ], db)

    html = render_dashboard(db, limit=1)

    assert "Recent 1 entries" in html
    assert "/new" in html
    assert "/old" not in html
    assert "198.51.100.23" in html
    assert "203.0.113.10" not in html


def test_serve_dashboard_responds_to_requests(tmp_path):
    """Server should start and respond to HTTP requests."""
    db = tmp_path / "meter.db"
    ingest_lines([
        '203.0.113.10 realip=- cf=- host=a.example auth_prefix=a [09/Jun/2026:02:00:01 +0000] "GET /v1/models HTTP/2.0" 200 1 rt=0.1 uct=0.01 urt=0.09 "-" "curl"',
    ], db)

    # Use port 0 to get an available port, then start server in a thread
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    thread = threading.Thread(target=serve_dashboard, args=(db, "127.0.0.1", port), daemon=True)
    thread.start()
    time.sleep(0.5)

    import urllib.request
    resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2)
    assert resp.status == 200
    body = resp.read().decode()
    assert body == "ok"
