from __future__ import annotations

import json
from pathlib import Path
from urllib import request

from .storage import report_from_db


def build_alert_payload(db_path: str | Path, top: int = 10, rules: dict | None = None) -> dict:
    report = report_from_db(db_path)
    signals = report.signals()
    signals.extend(_rule_signals(report, rules or {}))
    return {
        "tool": "llm-meter",
        "parsed_lines": report.parsed,
        "first_seen": report.first_seen.isoformat() if report.first_seen else None,
        "last_seen": report.last_seen.isoformat() if report.last_seen else None,
        "signals": signals,
        "top_ips": dict(report.ips.most_common(top)),
        "statuses": {str(k): v for k, v in report.statuses.most_common()},
        "latency": report.latency_summary(),
    }


def _rule_signals(report, rules: dict) -> list[dict]:
    signals: list[dict] = []
    if not report.parsed:
        return signals

    max_4xx_rate = rules.get("max_4xx_rate")
    if max_4xx_rate is not None:
        count = sum(v for k, v in report.statuses.items() if 400 <= k <= 499)
        rate = count / report.parsed
        if rate > float(max_4xx_rate):
            signals.append({
                "level": "warn",
                "kind": "high_4xx_rate",
                "message": f"4xx rate {rate:.1%} exceeds threshold {float(max_4xx_rate):.1%}",
                "count": count,
                "rate": round(rate, 4),
                "threshold": float(max_4xx_rate),
            })

    max_5xx_rate = rules.get("max_5xx_rate")
    if max_5xx_rate is not None:
        count = sum(v for k, v in report.statuses.items() if 500 <= k <= 599)
        rate = count / report.parsed
        if rate > float(max_5xx_rate):
            signals.append({
                "level": "warn",
                "kind": "high_5xx_rate",
                "message": f"5xx rate {rate:.1%} exceeds threshold {float(max_5xx_rate):.1%}",
                "count": count,
                "rate": round(rate, 4),
                "threshold": float(max_5xx_rate),
            })

    max_latency_seconds = rules.get("max_latency_seconds")
    max_request_time = max(report.request_times) if report.request_times else None
    if max_latency_seconds is not None and max_request_time is not None and max_request_time > float(max_latency_seconds):
        signals.append({
            "level": "warn",
            "kind": "high_latency",
            "message": f"max request latency {max_request_time:.2f}s exceeds threshold {float(max_latency_seconds):.2f}s",
            "seconds": round(max_request_time, 4),
            "threshold": float(max_latency_seconds),
        })

    max_requests_per_ip = rules.get("max_requests_per_ip")
    if max_requests_per_ip is not None:
        threshold = int(max_requests_per_ip)
        for ip, count in report.ips.most_common(10):
            if count > threshold:
                signals.append({
                    "level": "warn",
                    "kind": "high_ip_volume",
                    "message": f"{ip} made {count} requests, above threshold {threshold}",
                    "ip": ip,
                    "count": count,
                    "threshold": threshold,
                })

    max_total_cost_usd = rules.get("max_total_cost_usd")
    if max_total_cost_usd is not None and report.cost_usd > float(max_total_cost_usd):
        signals.append({
            "level": "warn",
            "kind": "budget_cost_exceeded",
            "message": f"estimated cost ${report.cost_usd:.4f} exceeds budget ${float(max_total_cost_usd):.4f}",
            "cost_usd": round(report.cost_usd, 8),
            "threshold": float(max_total_cost_usd),
        })

    max_total_tokens = rules.get("max_total_tokens")
    if max_total_tokens is not None and report.total_tokens > int(max_total_tokens):
        signals.append({
            "level": "warn",
            "kind": "budget_tokens_exceeded",
            "message": f"total tokens {report.total_tokens} exceeds budget {int(max_total_tokens)}",
            "tokens": report.total_tokens,
            "threshold": int(max_total_tokens),
        })

    max_model_cost_usd = rules.get("max_model_cost_usd")
    if max_model_cost_usd is not None:
        threshold = float(max_model_cost_usd)
        for model, cost in report.cost_by_model.most_common(10):
            if cost > threshold:
                signals.append({
                    "level": "warn",
                    "kind": "model_cost_exceeded",
                    "message": f"model {model} estimated cost ${cost:.4f} exceeds budget ${threshold:.4f}",
                    "model": model,
                    "cost_usd": round(cost, 8),
                    "threshold": threshold,
                })

    return signals


def format_alert_text(payload: dict) -> str:
    signals = payload.get("signals") or []
    title = "LLM Meter alert" if signals else "LLM Meter status"
    lines = [title, f"parsed_lines={payload.get('parsed_lines', 0)}"]
    if payload.get("first_seen") or payload.get("last_seen"):
        lines.append(f"range={payload.get('first_seen') or '-'} -> {payload.get('last_seen') or '-'}")
    if signals:
        lines.append("signals:")
        for signal in signals:
            lines.append(f"- {signal.get('level','').upper()} {signal.get('kind','')}: {signal.get('message','')}")
    else:
        lines.append("signals=none")
    top_ips = payload.get("top_ips") or {}
    if top_ips:
        lines.append("top_ips:")
        for ip, count in list(top_ips.items())[:5]:
            lines.append(f"- {ip}: {count}")
    return "\n".join(lines)


def send_webhook(url: str, payload: dict, timeout: float = 10.0) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "llm-meter"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - user-provided webhook URL is intentional
        body = resp.read(4096).decode("utf-8", errors="replace")
        return resp.status, body


def should_alert(payload: dict, include_ok: bool = False) -> bool:
    return include_ok or bool(payload.get("signals"))
