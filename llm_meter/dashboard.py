from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .storage import hourly_counts, report_from_db


CSS = """
:root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
body { margin: 0; background: #07111f; color: #e2e8f0; }
main { max-width: 1180px; margin: 0 auto; padding: 34px 22px 60px; }
a { color: #38bdf8; }
.hero { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
h1 { font-size: 46px; margin: 0; letter-spacing: -0.04em; }
.sub { color: #94a3b8; margin-top: 8px; }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.card { background: linear-gradient(180deg, rgba(15,23,42,.96), rgba(15,23,42,.76)); border: 1px solid #1e293b; border-radius: 18px; padding: 18px; box-shadow: 0 20px 80px rgba(0,0,0,.22); }
.metric { font-size: 32px; font-weight: 800; margin-top: 6px; }
.label { color: #94a3b8; font-size: 13px; text-transform: uppercase; letter-spacing: .08em; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 9px 6px; border-bottom: 1px solid #1e293b; }
th { color: #94a3b8; font-weight: 600; }
.bar { display: inline-block; height: 9px; border-radius: 999px; background: linear-gradient(90deg, #38bdf8, #34d399); min-width: 4px; }
.signal { padding: 10px 12px; border-radius: 12px; margin: 8px 0; background: rgba(56,189,248,.10); border: 1px solid rgba(56,189,248,.24); }
.warn { background: rgba(245,158,11,.12); border-color: rgba(245,158,11,.30); }
.err { background: rgba(239,68,68,.12); border-color: rgba(239,68,68,.30); }
footer { color: #64748b; margin-top: 28px; font-size: 13px; }
@media (max-width: 900px) { .grid, .two { grid-template-columns: 1fr; } .hero { display: block; } }
"""


def serve_dashboard(db_path: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    db_path = Path(db_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib API
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                self._send(200, "ok", "text/plain; charset=utf-8")
                return
            if parsed.path == "/api/report":
                payload = _payload(db_path)
                self._send(200, json.dumps(payload, ensure_ascii=False, indent=2), "application/json; charset=utf-8")
                return
            if parsed.path not in ("/", "/index.html"):
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            self._send(200, render_dashboard(db_path), "text/html; charset=utf-8")

        def log_message(self, fmt, *args):  # noqa: A003 - stdlib API
            return

        def _send(self, status: int, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"LLM Meter dashboard: http://{host}:{port}  db={db_path}")
    server.serve_forever()


def _payload(db_path: Path) -> dict:
    report = report_from_db(db_path)
    payload = report.to_dict(top=10)
    payload["hourly"] = hourly_counts(db_path)
    return payload


def render_dashboard(db_path: str | Path) -> str:
    payload = _payload(Path(db_path))
    total = payload["parsed_lines"]
    status_classes = payload["status_classes"]
    latency = payload["latency"]
    hourly = payload["hourly"][-24:]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LLM Meter Dashboard</title>
  <style>{CSS}</style>
</head>
<body>
<main>
  <section class="hero">
    <div>
      <h1>LLM Meter</h1>
      <div class="sub">OpenAI-compatible API gateway traffic dashboard</div>
    </div>
    <div class="sub">{esc(payload.get('first_seen') or '-')} → {esc(payload.get('last_seen') or '-')}</div>
  </section>

  <section class="grid">
    {metric('Requests', total)}
    {metric('2xx', status_classes.get('2xx', 0))}
    {metric('4xx', status_classes.get('4xx', 0))}
    {metric('Max latency', _fmt_seconds(latency['request_time']['max']))}
  </section>

  <section class="two">
    {table_card('Top IPs', payload['top_ips'], total)}
    {table_card('Top paths', payload['paths'], total)}
  </section>

  <section class="two">
    {table_card('Statuses', payload['statuses'], total)}
    {table_card('Auth prefixes', payload['top_auth_prefixes'], total)}
  </section>

  <section class="card" style="margin-top:14px">
    <div class="label">Hourly trend</div>
    {hourly_table(hourly)}
  </section>

  <section class="card" style="margin-top:14px">
    <div class="label">Signals</div>
    {signals(payload['signals'])}
  </section>

  <footer>Generated locally from SQLite. Full JSON: <a href="/api/report">/api/report</a></footer>
</main>
</body>
</html>"""


def esc(value) -> str:
    return html.escape(str(value))


def metric(label: str, value) -> str:
    return f'<div class="card"><div class="label">{esc(label)}</div><div class="metric">{esc(value)}</div></div>'


def table_card(title: str, data: dict, total: int) -> str:
    rows = []
    for key, value in data.items():
        pct = (value / total * 100) if total else 0
        rows.append(
            f"<tr><td>{esc(key)}</td><td>{value}</td><td><span class='bar' style='width:{max(4, min(220, pct * 2.2))}px'></span> {pct:.1f}%</td></tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='3'>-</td></tr>")
    return f"<div class='card'><div class='label'>{esc(title)}</div><table><tbody>{''.join(rows)}</tbody></table></div>"


def hourly_table(rows: list[dict]) -> str:
    if not rows:
        return "<p class='sub'>No timestamped rows.</p>"
    html_rows = ["<tr><th>Hour</th><th>Requests</th><th>2xx</th><th>4xx</th><th>5xx</th></tr>"]
    for row in rows:
        html_rows.append(
            f"<tr><td>{esc(row['hour'])}:00</td><td>{row['requests']}</td><td>{row['ok']}</td><td>{row['client_errors']}</td><td>{row['server_errors']}</td></tr>"
        )
    return f"<table>{''.join(html_rows)}</table>"


def signals(items: list[dict]) -> str:
    if not items:
        return "<div class='signal'>OK no obvious abuse signals</div>"
    out = []
    for item in items:
        cls = "signal warn" if item.get("level") == "warn" else "signal"
        out.append(f"<div class='{cls}'>{esc(item.get('level', '').upper())} {esc(item.get('message', ''))}</div>")
    return "".join(out)


def _fmt_seconds(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}s"
