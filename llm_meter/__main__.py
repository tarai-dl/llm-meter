from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .analyzer import analyze_lines, format_text
from .dashboard import serve_dashboard
from .prometheus import serve_prometheus
from .storage import hourly_counts, ingest_lines, report_from_db
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
