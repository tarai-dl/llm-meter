from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .storage import report_from_db


def render_prometheus_metrics(db_path: str | Path, top: int = 50) -> str:
    report = report_from_db(db_path)
    lines: list[str] = []

    def help_type(name: str, help_text: str, metric_type: str) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")

    help_type("llm_meter_requests_total", "Total parsed gateway requests", "counter")
    lines.append(f"llm_meter_requests_total {report.parsed}")

    help_type("llm_meter_status_total", "Gateway requests by HTTP status", "counter")
    for status, count in sorted(report.statuses.items()):
        lines.append(f'llm_meter_status_total{{status="{_label(status)}"}} {count}')

    help_type("llm_meter_status_class_total", "Gateway requests by HTTP status class", "counter")
    for klass, count in sorted(report.status_classes.items()):
        lines.append(f'llm_meter_status_class_total{{status_class="{_label(klass)}"}} {count}')

    help_type("llm_meter_host_requests_total", "Gateway requests by host", "counter")
    for host, count in report.hosts.most_common(top):
        lines.append(f'llm_meter_host_requests_total{{host="{_label(host)}"}} {count}')

    help_type("llm_meter_path_requests_total", "Gateway requests by normalized path", "counter")
    for path, count in report.paths.most_common(top):
        lines.append(f'llm_meter_path_requests_total{{path="{_label(path)}"}} {count}')

    help_type("llm_meter_ip_requests_total", "Gateway requests by client IP", "counter")
    for ip, count in report.ips.most_common(top):
        lines.append(f'llm_meter_ip_requests_total{{ip="{_label(ip)}"}} {count}')

    latency = report.latency_summary()["request_time"]
    help_type("llm_meter_latency_seconds_avg", "Average request latency in seconds", "gauge")
    lines.append(f"llm_meter_latency_seconds_avg {_number(latency['avg'])}")
    help_type("llm_meter_latency_seconds_max", "Maximum request latency in seconds", "gauge")
    lines.append(f"llm_meter_latency_seconds_max {_number(latency['max'])}")

    help_type("llm_meter_signals_total", "Current abuse or health signals", "gauge")
    for signal in report.signals():
        lines.append(
            f'llm_meter_signals_total{{level="{_label(signal.get("level", ""))}",kind="{_label(signal.get("kind", ""))}"}} 1'
        )

    return "\n".join(lines) + "\n"


def serve_prometheus(db_path: str | Path, host: str = "127.0.0.1", port: int = 9108, top: int = 50) -> None:
    db_path = Path(db_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/healthz":
                self._send(200, "ok\n", "text/plain; charset=utf-8")
                return
            if self.path not in ("/metrics", "/"):
                self._send(404, "not found\n", "text/plain; charset=utf-8")
                return
            self._send(200, render_prometheus_metrics(db_path, top=top), "text/plain; version=0.0.4; charset=utf-8")

        def log_message(self, fmt, *args):  # noqa: A003
            return

        def _send(self, status: int, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"LLM Meter Prometheus exporter: http://{host}:{port}/metrics  db={db_path}")
    server.serve_forever()


def _label(value) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number(value) -> str:
    if value is None:
        return "0"
    return str(value)
