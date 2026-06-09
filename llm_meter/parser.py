from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Optional


TIME_FORMAT = "%d/%b/%Y:%H:%M:%S %z"

LOG_RE = re.compile(
    r'^(?P<ip>\S+)\s+'
    r'(?:realip=(?P<realip>\S+)\s+)?'
    r'(?:cf=(?P<cf>\S+)\s+)?'
    r'(?:host=(?P<host>\S+)\s+)?'
    r'(?:auth_prefix=(?P<auth_prefix>\S+)\s+)?'
    r'\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<request>[^"]*)"\s+'
    r'(?P<status>\d{3})\s+'
    r'(?P<body_bytes>\S+)'
    r'(?:\s+rt=(?P<rt>\S+))?'
    r'(?:\s+uct=(?P<uct>\S+))?'
    r'(?:\s+urt=(?P<urt>\S+))?'
)

COMBINED_RE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+'
    r'\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<request>[^"]*)"\s+'
    r'(?P<status>\d{3})\s+'
    r'(?P<body_bytes>\S+)'
)


@dataclass(slots=True)
class LogEntry:
    ip: str
    time: Optional[datetime]
    method: str
    path: str
    protocol: str
    status: int
    body_bytes: int
    host: str = "-"
    auth_prefix: str = "-"
    realip: str = "-"
    cf: str = "-"
    request_time: Optional[float] = None
    upstream_response_time: Optional[float] = None
    raw: str = ""


def _parse_float(value: Optional[str]) -> Optional[float]:
    if not value or value == "-":
        return None
    # Nginx may emit comma-separated upstream timings for retries.
    first = value.split(",", 1)[0]
    try:
        return float(first)
    except ValueError:
        return None


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _parse_time(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, TIME_FORMAT)
    except ValueError:
        return None


def _parse_request(value: str) -> tuple[str, str, str]:
    parts = value.split()
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1], "-"
    if len(parts) == 1 and parts[0]:
        return "-", parts[0], "-"
    return "-", "-", "-"


def parse_line(line: str) -> Optional[LogEntry]:
    line = line.rstrip("\n")
    if not line:
        return None
    if line.lstrip().startswith("{"):
        return _parse_json_line(line)

    match = LOG_RE.match(line) or COMBINED_RE.match(line)
    if not match:
        return None

    data = match.groupdict()
    method, path, protocol = _parse_request(data.get("request") or "")

    return LogEntry(
        ip=data.get("ip") or "-",
        realip=data.get("realip") or "-",
        cf=data.get("cf") or "-",
        host=data.get("host") or "-",
        auth_prefix=data.get("auth_prefix") or "-",
        time=_parse_time(data.get("time") or ""),
        method=method,
        path=path,
        protocol=protocol,
        status=int(data.get("status") or 0),
        body_bytes=_parse_int(data.get("body_bytes") or "0"),
        request_time=_parse_float(data.get("rt")),
        upstream_response_time=_parse_float(data.get("urt")),
        raw=line,
    )


def _parse_json_line(line: str) -> Optional[LogEntry]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    # Cloudflare Logpush commonly uses fields like ClientIP, ClientRequestHost,
    # ClientRequestMethod, ClientRequestURI, EdgeResponseStatus, EdgeStartTimestamp.
    ip = _first(data, "ClientIP", "clientIP", "client_ip", "ip") or "-"
    host = _first(data, "ClientRequestHost", "host", "requestHost") or "-"
    method = _first(data, "ClientRequestMethod", "method") or "-"
    path = _first(data, "ClientRequestURI", "ClientRequestPath", "path", "uri") or "-"
    protocol = _first(data, "ClientRequestProtocol", "protocol") or "-"
    status = int(_first(data, "EdgeResponseStatus", "OriginResponseStatus", "status") or 0)
    body_bytes = _parse_int(str(_first(data, "EdgeResponseBytes", "OriginResponseBytes", "body_bytes") or "0"))
    ts = _parse_json_time(_first(data, "EdgeStartTimestamp", "Datetime", "timestamp", "ts"))
    request_time = _parse_float(str(_first(data, "OriginResponseDurationMs", "RequestTimeMs") or ""))
    if request_time is not None:
        request_time = request_time / 1000

    return LogEntry(
        ip=ip,
        realip="-",
        cf=ip,
        host=host,
        auth_prefix="-",
        time=ts,
        method=method,
        path=path,
        protocol=protocol,
        status=status,
        body_bytes=body_bytes,
        request_time=request_time,
        upstream_response_time=request_time,
        raw=line,
    )


def _first(data: dict, *keys: str):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _parse_json_time(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        # Cloudflare may use nanoseconds in some exports. Be permissive.
        if value > 10_000_000_000_000:
            value = value / 1_000_000_000
        elif value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
