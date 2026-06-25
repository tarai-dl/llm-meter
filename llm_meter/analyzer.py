from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from typing import Iterable

from .parser import LogEntry, parse_line


@dataclass(slots=True)
class Report:
    total: int = 0
    parsed: int = 0
    failed: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    status_classes: Counter[str] = field(default_factory=Counter)
    statuses: Counter[int] = field(default_factory=Counter)
    methods: Counter[str] = field(default_factory=Counter)
    hosts: Counter[str] = field(default_factory=Counter)
    paths: Counter[str] = field(default_factory=Counter)
    ips: Counter[str] = field(default_factory=Counter)
    auth_prefixes: Counter[str] = field(default_factory=Counter)
    models: Counter[str] = field(default_factory=Counter)
    request_times: list[float] = field(default_factory=list)
    upstream_times: list[float] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cost_by_model: Counter[str] = field(default_factory=Counter)

    def to_dict(self, top: int = 10) -> dict:
        return {
            "total_lines": self.total,
            "parsed_lines": self.parsed,
            "failed_lines": self.failed,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "status_classes": dict(self.status_classes),
            "statuses": {str(k): v for k, v in self.statuses.most_common()},
            "methods": dict(self.methods.most_common(top)),
            "hosts": dict(self.hosts.most_common(top)),
            "paths": dict(self.paths.most_common(top)),
            "top_ips": dict(self.ips.most_common(top)),
            "top_auth_prefixes": dict(self.auth_prefixes.most_common(top)),
            "models": dict(self.models.most_common(top)),
            "tokens": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "total": self.total_tokens,
            },
            "cost": {
                "total_usd": round(self.cost_usd, 8),
                "by_model": {model: round(cost, 8) for model, cost in self.cost_by_model.most_common(top)},
            },
            "latency": self.latency_summary(),
            "signals": self.signals(),
        }

    def latency_summary(self) -> dict:
        def summarize(values: list[float]) -> dict:
            if not values:
                return {"count": 0, "avg": None, "max": None}
            return {"count": len(values), "avg": round(mean(values), 4), "max": round(max(values), 4)}

        return {
            "request_time": summarize(self.request_times),
            "upstream_response_time": summarize(self.upstream_times),
        }

    def signals(self) -> list[dict]:
        """Detect abuse and health signals from the aggregated report.

        Thresholds (hardcoded — consider making configurable for production):
        - dominant_ip: 100+ requests from a single IP with >= 25% traffic share
        - auth_or_rate_limited: < 50 is info, >= 50 is warn (401/403/429)
        - server_errors: any 5xx responses are warned
        - slow_request: any request >= 60 seconds
        - high_auth_prefix_diversity: 10+ unique auth prefixes
        """
        signals: list[dict] = []
        if not self.parsed:
            return signals

        for ip, count in self.ips.most_common(5):
            share = count / self.parsed
            if count >= 100 and share >= 0.25:
                signals.append({
                    "level": "warn",
                    "kind": "dominant_ip",
                    "message": f"{ip} accounts for {share:.1%} of parsed traffic",
                    "ip": ip,
                    "count": count,
                    "share": round(share, 4),
                })

        auth_or_rate_limited = sum(v for k, v in self.statuses.items() if k in (401, 403, 429))
        if auth_or_rate_limited:
            signals.append({
                "level": "info" if auth_or_rate_limited < 50 else "warn",
                "kind": "auth_or_rate_limited",
                "message": f"{auth_or_rate_limited} auth/rate-limit responses",
                "count": auth_or_rate_limited,
            })

        server_errors = sum(v for k, v in self.statuses.items() if 500 <= k <= 599)
        if server_errors:
            signals.append({
                "level": "warn",
                "kind": "server_errors",
                "message": f"{server_errors} server error responses",
                "count": server_errors,
            })

        if self.request_times and max(self.request_times) >= 60:
            signals.append({
                "level": "info",
                "kind": "slow_request",
                "message": f"slowest request took {max(self.request_times):.2f}s",
                "seconds": round(max(self.request_times), 4),
            })

        unique_auth = sum(1 for v in self.auth_prefixes.values() if v > 0)
        if unique_auth >= 10:
            signals.append({
                "level": "warn",
                "kind": "high_auth_prefix_diversity",
                "message": f"{unique_auth} unique auth prefixes seen — possible credential abuse",
                "unique_auth_prefixes": unique_auth,
                "total_auth_prefixes": len(self.auth_prefixes),
            })

        return signals


def analyze_lines(lines: Iterable[str]) -> Report:
    report = Report()
    for line in lines:
        report.total += 1
        entry = parse_line(line)
        if not entry:
            report.failed += 1
            continue
        add_entry(report, entry)
    return report


def add_entry(report: Report, entry: LogEntry) -> None:
    report.parsed += 1
    if entry.time:
        if report.first_seen is None or entry.time < report.first_seen:
            report.first_seen = entry.time
        if report.last_seen is None or entry.time > report.last_seen:
            report.last_seen = entry.time

    report.status_classes[f"{entry.status // 100}xx"] += 1
    report.statuses[entry.status] += 1
    report.methods[entry.method] += 1
    report.hosts[entry.host] += 1
    report.paths[entry.path.split("?", 1)[0]] += 1
    report.ips[entry.ip] += 1
    report.auth_prefixes[entry.auth_prefix] += 1
    if entry.model and entry.model != "-":
        report.models[entry.model] += 1
    report.prompt_tokens += entry.prompt_tokens
    report.completion_tokens += entry.completion_tokens
    report.total_tokens += entry.total_tokens
    report.cost_usd += entry.cost_usd
    if entry.model and entry.model != "-" and entry.cost_usd:
        report.cost_by_model[entry.model] += entry.cost_usd
    if entry.request_time is not None:
        report.request_times.append(entry.request_time)
    if entry.upstream_response_time is not None:
        report.upstream_times.append(entry.upstream_response_time)


def format_text(report: Report, top: int = 10) -> str:
    lines = ["LLM Meter Report", "================", f"Lines: {report.total}", f"Parsed: {report.parsed}"]
    if report.failed:
        lines.append(f"Failed: {report.failed}")
    if report.first_seen or report.last_seen:
        lines.append(f"Time range: {report.first_seen or '-'} -> {report.last_seen or '-'}")

    def section(title: str, counter: Counter) -> None:
        lines.append("")
        lines.append(f"{title}:")
        if not counter:
            lines.append("  -")
            return
        for key, value in counter.most_common(top):
            share = value / report.parsed if report.parsed else 0
            lines.append(f"  {str(key):24} {value:8}  {share:6.1%}")

    section("Status classes", report.status_classes)
    section("Statuses", report.statuses)
    section("Top hosts", report.hosts)
    section("Top paths", report.paths)
    section("Top IPs", report.ips)
    section("Top auth prefixes", report.auth_prefixes)
    section("Top models", report.models)

    if report.total_tokens or report.cost_usd:
        lines.append("")
        lines.append("Token / cost:")
        lines.append(
            f"  tokens prompt={report.prompt_tokens} completion={report.completion_tokens} total={report.total_tokens}"
        )
        lines.append(f"  estimated_cost_usd={round(report.cost_usd, 8)}")

    latency = report.latency_summary()
    lines.append("")
    lines.append("Latency:")
    for name, stats in latency.items():
        lines.append(f"  {name:24} count={stats['count']} avg={stats['avg']} max={stats['max']}")

    lines.append("")
    lines.append("Signals:")
    signals = report.signals()
    if not signals:
        lines.append("  OK no obvious abuse signals")
    else:
        for signal in signals:
            lines.append(f"  {signal['level'].upper():5} {signal['message']}")

    return "\n".join(lines)
