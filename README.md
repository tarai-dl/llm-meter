# LLM Meter

<p align="center">
  <img src="assets/banner.svg" alt="LLM Meter banner" width="100%">
</p>

<p align="center">
  <a href="https://github.com/tarai-dl/llm-meter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/tarai-dl/llm-meter/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/tarai-dl/llm-meter/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue.svg">
  <img alt="Status" src="https://img.shields.io/badge/status-MVP-orange.svg">
</p>

**Lightweight usage analytics and abuse detection for OpenAI-compatible API gateways.**

LLM Meter turns plain access logs from Nginx / Cloudflare / self-hosted AI gateways into useful usage reports: request volume, status codes, top IPs, auth prefixes, paths, latency, and possible abuse patterns.

It is designed for people running OpenAI-compatible API endpoints through tools like CLIProxyAPI, OneAPI/NewAPI, LiteLLM, LocalAI, Ollama-compatible gateways, or custom reverse proxies.

> MVP status: CLI log analyzer. Web dashboard, Prometheus exporter, and alerting are on the roadmap.

## Why

Self-hosted LLM API gateways are easy to expose, but hard to observe:

- Which IP is consuming the most requests?
- Are 401/429/5xx errors spiking?
- Which API key prefix is being abused?
- Are streaming requests getting slow?
- Did a public shared endpoint start attracting bot traffic?

LLM Meter starts with the boring, reliable source of truth: your gateway access logs.

## Features

- Parse Nginx-style logs, including custom fields like `host=`, `auth_prefix=`, `rt=`, `urt=`.
- Summarize total requests, status classes, hosts, paths, methods, top IPs, and auth prefixes.
- Detect common abuse signals:
  - high request count from one IP
  - many 401/429 responses
  - slow upstream responses
- Output human-readable text or JSON.
- Works locally, in Docker, or in CI.
- No database required for the first version.
- Safe-by-default examples: log short auth prefixes, never full API keys.

## Quick start

From source:

```bash
git clone https://github.com/tarai-dl/llm-meter.git
cd llm-meter
python3 -m llm_meter analyze examples/cpa.log
```

Analyze your gateway log:

```bash
python3 -m llm_meter analyze /var/log/nginx/llm-gateway-access.log
```

JSON output:

```bash
python3 -m llm_meter analyze /var/log/nginx/llm-gateway-access.log --json
```

Persist to SQLite and report historical trends:

```bash
python3 -m llm_meter ingest /var/log/nginx/llm-gateway-access.log --db llm-meter.db
python3 -m llm_meter report --db llm-meter.db
python3 -m llm_meter report --db llm-meter.db --json
```

Analyze only recent lines:

```bash
tail -n 5000 /var/log/nginx/llm-gateway-access.log | python3 -m llm_meter analyze -
```

Docker:

```bash
docker build -t llm-meter .
docker run --rm -v /var/log/nginx:/logs:ro llm-meter analyze /logs/llm-gateway-access.log
```

Docker Compose:

```bash
docker compose run --rm llm-meter
```

## Example output

```text
LLM Meter Report
================
Lines: 3
Parsed: 3
Time range: 2026-06-09 02:00:01+00:00 -> 2026-06-09 02:00:03+00:00

Status classes:
  4xx                             2   66.7%
  2xx                             1   33.3%

Top hosts:
  yukig.de5.net                   2   66.7%
  tarai05.ccwu.cc                 1   33.3%

Top paths:
  /v1/chat/completions            2   66.7%
  /v1/models                      1   33.3%

Top IPs:
  203.0.113.10                    2   66.7%
  198.51.100.23                   1   33.3%

Top auth prefixes:
  sk-live-                        2   66.7%
  -                               1   33.3%

Signals:
  INFO  2 auth/rate-limit responses
```

## Nginx setup

LLM Meter works with common Nginx combined logs, but a custom format gives better analytics:

```nginx
map $http_authorization $llm_auth_prefix {
    default "-";
    "~^Bearer\\s+(.{8}).*" $1;
    "~^(.{8}).*" $1;
}

log_format llm_gateway '$remote_addr realip=$realip_remote_addr cf=$http_cf_connecting_ip '
                       'host=$host auth_prefix=$llm_auth_prefix '
                       '[$time_local] "$request" $status $body_bytes_sent '
                       'rt=$request_time uct=$upstream_connect_time urt=$upstream_response_time '
                       '"$http_referer" "$http_user_agent"';
```

Full example: [docs/nginx.md](docs/nginx.md)

## Supported inputs

| Source | Status |
| --- | --- |
| Nginx combined access log | Supported |
| Nginx custom gateway log | Supported |
| Cloudflare real IP fields | Supported when present in Nginx log |
| Cloudflare Logpush JSON | Supported |
| LiteLLM structured logs | Planned |
| OneAPI/NewAPI logs | Planned |

## Roadmap

- [x] SQLite storage for historical trends
- [ ] Web dashboard
- [ ] Prometheus exporter
- [ ] Telegram / Discord / webhook alerts
- [x] Cloudflare Logpush parser
- [ ] LiteLLM / OneAPI / NewAPI specific presets
- [x] Docker Compose example
- [ ] Homebrew / PyPI package

## Project goals

- Minimal setup
- Safe-by-default log handling: do not store full API keys
- Useful for tiny VPS deployments and homelab AI gateways
- OpenAI-compatible, not vendor-specific

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

Good first issues:

- Add sanitized log fixtures for your gateway.
- Improve docs for Cloudflare / Nginx / LiteLLM / OneAPI.
- Add new report formats.
- Build the first dashboard prototype.

## License

MIT
