from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .alerts import build_alert_payload, format_alert_text, send_webhook, should_alert
from .analyzer import analyze_lines, format_text
from .bundle import export_bundle
from .config import load_config
from .dashboard import render_dashboard, serve_dashboard
from .demo import create_demo
from .doctor import format_doctor_text, run_doctor
from .markdown import render_markdown_report
from .prometheus import serve_prometheus
from .storage import hourly_counts, ingest_lines, prune_db, report_from_db
from .tail import follow_file


def iter_input(path: str):
    if path == "-":
        yield from sys.stdin
        return
    with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
        yield from handle


def cmd_analyze(args: argparse.Namespace) -> int:
    report = analyze_lines(iter_input(args.path))
    if args.json:
        print(json.dumps(report.to_dict(top=args.top), indent=2, ensure_ascii=False))
    else:
        print(format_text(report, top=args.top))
    return 0 if report.parsed else 2


def cmd_ingest(args: argparse.Namespace) -> int:
    source = follow_file(args.path, interval=args.interval, from_end=not args.from_start) if args.follow else iter_input(args.path)
    result = ingest_lines(source, args.db, batch_size=args.batch_size)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Inserted {result['inserted']} entries into {args.db} ({result['failed']} failed lines)")
    return 0 if result["inserted"] else 2


def cmd_report(args: argparse.Namespace) -> int:
    report = report_from_db(args.db, limit=args.limit)
    if args.json:
        payload = report.to_dict(top=args.top)
        payload["hourly"] = hourly_counts(args.db)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(format_text(report, top=args.top))
        hourly = hourly_counts(args.db)
        if hourly:
            print("\nHourly trend:")
            for row in hourly[-24:]:
                print(
                    f"  {row['hour']}:00  "
                    f"req={row['requests']} ok={row['ok']} "
                    f"4xx={row['client_errors']} 5xx={row['server_errors']}"
                )
    return 0 if report.parsed else 2


def cmd_serve(args: argparse.Namespace) -> int:
    serve_dashboard(args.db, host=args.host, port=args.port)
    return 0


def cmd_export_prometheus(args: argparse.Namespace) -> int:
    serve_prometheus(args.db, host=args.host, port=args.port, top=args.top)
    return 0


def cmd_alert(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db = args.db or config.database
    if not db:
        raise SystemExit("alert requires --db or database in --config")
    webhook_url = args.webhook_url or config.alert.webhook_url
    include_ok = args.include_ok or config.alert.include_ok
    top = args.top if args.top is not None else config.alert.top
    timeout = args.timeout if args.timeout is not None else config.alert.timeout
    payload = build_alert_payload(db, top=top, rules=config.alert.rules.to_dict())
    if args.text:
        body = format_alert_text(payload)
        print(body)
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    if not should_alert(payload, include_ok=include_ok):
        return 0
    if webhook_url and not args.dry_run:
        status, response_body = send_webhook(webhook_url, payload, timeout=timeout)
        print(f"webhook_status={status}")
        if response_body:
            print(response_body[:500])
    return 1 if payload.get("signals") and args.exit_code else 0


def cmd_export_html(args: argparse.Namespace) -> int:
    html = render_dashboard(args.db)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


def cmd_export_markdown(args: argparse.Namespace) -> int:
    markdown = render_markdown_report(args.db, top=args.top)
    Path(args.output).write_text(markdown, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


def cmd_export_bundle(args: argparse.Namespace) -> int:
    result = export_bundle(args.db, args.output, top=args.top)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"wrote {result['output']}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    db = args.db or config.database
    keep_days = args.keep_days or config.retention_days
    if not db:
        raise SystemExit("prune requires --db or database in --config")
    if not keep_days:
        raise SystemExit("prune requires --keep-days or retention_days in --config")
    result = prune_db(db, keep_days=keep_days)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"deleted {result['deleted']} entries older than {result['cutoff']} ({result['remaining']} remaining)")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    result = create_demo(args.output_dir, rows=args.rows)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("LLM Meter demo generated")
        print(f"  log:  {result['log_path']}")
        print(f"  db:   {result['db_path']}")
        print(f"  html: {result['html_path']}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    result = run_doctor(db_path=args.db, config_path=args.config, log_path=args.log)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_doctor_text(result))
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-meter",
        description="Analyze OpenAI-compatible API gateway access logs.",
    )
    parser.add_argument("--version", action="version", version=f"llm-meter {__version__}")

    sub = parser.add_subparsers(dest="command")

    analyze = sub.add_parser("analyze", help="analyze an access log file or stdin")
    analyze.add_argument("path", help="log path, or '-' for stdin")
    analyze.add_argument("--json", action="store_true", help="emit JSON")
    analyze.add_argument("--top", type=int, default=10, help="top N rows per section")
    analyze.set_defaults(func=cmd_analyze)

    ingest = sub.add_parser("ingest", help="parse a log file into a SQLite database")
    ingest.add_argument("path", help="log path, or '-' for stdin")
    ingest.add_argument("--db", required=True, help="SQLite database path")
    ingest.add_argument("--json", action="store_true", help="emit JSON")
    ingest.add_argument("--follow", "-f", action="store_true", help="keep ingesting appended lines, like tail -f")
    ingest.add_argument("--from-start", action="store_true", help="with --follow, ingest existing lines before following")
    ingest.add_argument("--interval", type=float, default=1.0, help="poll interval for --follow")
    ingest.add_argument("--batch-size", type=int, default=1000, help="SQLite insert batch size")
    ingest.set_defaults(func=cmd_ingest)

    report = sub.add_parser("report", help="report from a SQLite database")
    report.add_argument("--db", required=True, help="SQLite database path")
    report.add_argument("--json", action="store_true", help="emit JSON")
    report.add_argument("--top", type=int, default=10, help="top N rows per section")
    report.add_argument("--limit", type=int, help="only report over the newest N ingested entries")
    report.set_defaults(func=cmd_report)

    serve = sub.add_parser("serve", help="serve a local web dashboard from a SQLite database")
    serve.add_argument("--db", required=True, help="SQLite database path")
    serve.add_argument("--host", default="127.0.0.1", help="listen host")
    serve.add_argument("--port", type=int, default=8765, help="listen port")
    serve.set_defaults(func=cmd_serve)

    exporter = sub.add_parser("export-prometheus", help="serve Prometheus metrics from a SQLite database")
    exporter.add_argument("--db", required=True, help="SQLite database path")
    exporter.add_argument("--host", default="127.0.0.1", help="listen host")
    exporter.add_argument("--port", type=int, default=9108, help="listen port")
    exporter.add_argument("--top", type=int, default=50, help="top N label values for high-cardinality metrics")
    exporter.set_defaults(func=cmd_export_prometheus)

    alert = sub.add_parser("alert", help="emit or send webhook alerts based on current signals")
    alert.add_argument("--db", help="SQLite database path")
    alert.add_argument("--config", help="llm-meter YAML config path")
    alert.add_argument("--webhook-url", help="POST JSON payload to this webhook URL")
    alert.add_argument("--dry-run", action="store_true", help="do not send webhook, only print payload")
    alert.add_argument("--include-ok", action="store_true", help="send/print even when there are no signals")
    alert.add_argument("--exit-code", action="store_true", help="exit with 1 when signals are present")
    alert.add_argument("--text", action="store_true", help="print human-readable text instead of JSON")
    alert.add_argument("--top", type=int, help="top N IPs in payload")
    alert.add_argument("--timeout", type=float, help="webhook timeout seconds")
    alert.set_defaults(func=cmd_alert)

    html = sub.add_parser("export-html", help="export a static HTML dashboard report")
    html.add_argument("--db", required=True, help="SQLite database path")
    html.add_argument("--output", required=True, help="output HTML file")
    html.set_defaults(func=cmd_export_html)

    markdown = sub.add_parser("export-markdown", help="export a Markdown incident/share report")
    markdown.add_argument("--db", required=True, help="SQLite database path")
    markdown.add_argument("--output", required=True, help="output Markdown file")
    markdown.add_argument("--top", type=int, default=10, help="top N rows per section")
    markdown.set_defaults(func=cmd_export_markdown)

    bundle = sub.add_parser("export-bundle", help="export HTML, Markdown, JSON, and manifest as a zip bundle")
    bundle.add_argument("--db", required=True, help="SQLite database path")
    bundle.add_argument("--output", required=True, help="output zip file")
    bundle.add_argument("--top", type=int, default=10, help="top N rows per section")
    bundle.add_argument("--json", action="store_true", help="emit JSON")
    bundle.set_defaults(func=cmd_export_bundle)

    prune = sub.add_parser("prune", help="delete old SQLite entries by retention window")
    prune.add_argument("--db", help="SQLite database path")
    prune.add_argument("--config", help="llm-meter YAML config path")
    prune.add_argument("--keep-days", type=int, help="keep entries newer than this many days")
    prune.add_argument("--json", action="store_true", help="emit JSON")
    prune.set_defaults(func=cmd_prune)

    demo = sub.add_parser("demo", help="generate deterministic demo logs, SQLite data, and HTML report")
    demo.add_argument("--output-dir", required=True, help="directory for demo artifacts")
    demo.add_argument("--rows", type=int, default=96, help="number of demo log rows")
    demo.add_argument("--json", action="store_true", help="emit JSON")
    demo.set_defaults(func=cmd_demo)

    doctor = sub.add_parser("doctor", help="diagnose config, database, and log parseability")
    doctor.add_argument("--db", help="SQLite database path")
    doctor.add_argument("--config", help="llm-meter YAML config path")
    doctor.add_argument("--log", help="gateway log path to sample")
    doctor.add_argument("--json", action="store_true", help="emit JSON")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
