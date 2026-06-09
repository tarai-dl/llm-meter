# LLM Meter

[English](README.md) | [简体中文](README_CN.md)

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

LLM Meter turns plain access logs from Nginx / Cloudflare / self-hosted AI gateways into useful usage reports: request volume, status codes, top IPs, auth prefixes, paths, latency, token usage, estimated cost, and possible abuse patterns.

It is designed for people running OpenAI-compatible API endpoints through tools like CLIProxyAPI, OneAPI/NewAPI, LiteLLM, LocalAI, Ollama-compatible gateways, or custom reverse proxies.

> MVP status: CLI log analyzer plus SQLite history, dashboard, Prometheus exporter, webhook alerts, config files, and retention pruning.

## Why

Self-hosted LLM API gateways are easy to expose, but hard to observe:

- Which IP is consuming the most requests?
- Are 401/429/5xx errors spiking?
- Which API key prefix is being abused?
- Are streaming requests getting slow?
- Which model or key prefix is burning tokens and cost?
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
- YAML config for long-running deployments.
- Database retention pruning for small VPS disks.
- Token and estimated cost analytics from JSON gateway logs.
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
python3 -m llm_meter ingest /var/log/nginx/llm-gateway-access.log --db llm-meter.db --follow
python3 -m llm_meter report --db llm-meter.db
python3 -m llm_meter report --db llm-meter.db --json
python3 -m llm_meter serve --db llm-meter.db --host 127.0.0.1 --port 8765
python3 -m llm_meter export-prometheus --db llm-meter.db --host 127.0.0.1 --port 9108
python3 -m llm_meter prune --db llm-meter.db --keep-days 30
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

Generate a local demo pack for screenshots or quick evaluation:

```bash
python3 -m llm_meter demo --output-dir /tmp/llm-meter-demo
# open /tmp/llm-meter-demo/demo-report.html
```

The demo command writes deterministic sample JSONL logs, a SQLite database, and a static HTML dashboard report with traffic, token, cost, model, and alert-signal data.

Diagnose a deployment before wiring it into cron/systemd:

```bash
python3 -m llm_meter doctor \
  --config examples/llm-meter.yml \
  --db /var/lib/llm-meter/llm-meter.db \
  --log /var/log/nginx/llm-gateway-access.log
```

`doctor` checks config parsing, SQLite readability, and whether a sample of your gateway log is parseable.

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

## Web dashboard

After ingesting logs into SQLite, launch a dependency-free local dashboard:

```bash
python3 -m llm_meter serve --db llm-meter.db
```

Open <http://127.0.0.1:8765>. The dashboard also exposes the full JSON report at `/api/report`.

## Prometheus exporter

Expose metrics from a SQLite database:

```bash
python3 -m llm_meter export-prometheus --db llm-meter.db
curl http://127.0.0.1:9108/metrics
```

Example scrape config:

```yaml
scrape_configs:
  - job_name: llm-meter
    static_configs:
      - targets: ['127.0.0.1:9108']
```

High-cardinality metrics like IPs and paths are capped with `--top`.

## Static HTML export

Export a shareable dashboard report as a single HTML file:

```bash
python3 -m llm_meter export-html --db llm-meter.db --output report.html
```

Export a Markdown report for incident notes, GitHub issues, runbooks, or chat handoff:

```bash
python3 -m llm_meter export-markdown --db llm-meter.db --output report.md
```

Export a complete share bundle for debugging or handoff:

```bash
python3 -m llm_meter export-bundle --db llm-meter.db --output llm-meter-report.zip
```

The bundle contains `report.html`, `report.md`, `report.json`, and `manifest.json`.

This is useful for attaching reports to issues, incident notes, or status pages without running the live dashboard.

## Token and cost analytics

If your gateway emits JSON logs with model / usage / cost fields, LLM Meter rolls them up automatically:

```json
{"timestamp":"2026-06-09T02:00:00Z","ip":"203.0.113.10","host":"api.example","method":"POST","path":"/v1/chat/completions","status":200,"model":"gpt-4o-mini","prompt_tokens":1000,"completion_tokens":500,"total_tokens":1500,"cost_usd":0.000675}
```

Reports include:

- total prompt / completion / total tokens
- estimated total cost in USD
- top models by request count
- estimated cost by model

The same fields are exposed in JSON reports, the web dashboard, and static HTML export.

## Alerts and webhooks

Print current abuse/health signals:

```bash
python3 -m llm_meter alert --db llm-meter.db --text
```

Send JSON to a webhook only when signals are present:

```bash
python3 -m llm_meter alert --db llm-meter.db --webhook-url https://example.com/webhook
```

Useful cron pattern:

```bash
*/5 * * * * llm-meter alert --db /var/lib/llm-meter/llm-meter.db --webhook-url https://example.com/webhook
```

Use `--include-ok` for heartbeat-style notifications, and `--exit-code` if your scheduler should treat signals as a non-zero result.

## Config file and alert rules

For long-running deployments, put shared settings and alert thresholds in a small YAML file:

```yaml
database: /var/lib/llm-meter/llm-meter.db
retention_days: 30

alert:
  webhook_url: https://example.com/webhook
  include_ok: false
  top: 10
  rules:
    max_4xx_rate: 0.30
    max_5xx_rate: 0.05
    max_latency_seconds: 30
    max_requests_per_ip: 1000
    max_total_cost_usd: 10
    max_total_tokens: 1000000
    max_model_cost_usd: 5
```

Then run:

```bash
python3 -m llm_meter alert --config examples/llm-meter.yml --text
python3 -m llm_meter prune --config examples/llm-meter.yml
```

Rules are intentionally simple and dependency-free: high 4xx/5xx rates, slow requests, high request volume from a single IP, total cost budget, total token budget, and per-model cost budget. See [examples/llm-meter.yml](examples/llm-meter.yml).

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

Gateway presets:

- [LiteLLM / OneAPI / NewAPI / LocalAI / Ollama / CLIProxyAPI](docs/gateway-presets.md)
- [systemd deployment examples](docs/systemd.md)

## Supported inputs

| Source | Status |
| --- | --- |
| Nginx combined access log | Supported |
| Nginx custom gateway log | Supported |
| Cloudflare real IP fields | Supported when present in Nginx log |
| Cloudflare Logpush JSON | Supported |
| JSON logs with model / token / cost fields | Supported |
| LiteLLM structured logs | Planned |
| OneAPI/NewAPI logs | Planned |

## Roadmap

- [x] SQLite storage for historical trends
- [x] Web dashboard
- [x] Prometheus exporter
- [x] Telegram / Discord / webhook alerts
- [x] Cloudflare Logpush parser
- [x] LiteLLM / OneAPI / NewAPI specific presets
- [x] Docker Compose example
- [x] Static HTML report export
- [x] YAML config file
- [x] Configurable alert rules
- [x] SQLite retention pruning
- [x] Token / cost analytics from JSON logs
- [x] Budget alert rules for cost and token usage
- [x] Demo data + static report generator
- [x] Deployment doctor diagnostics
- [x] Markdown report export
- [x] Shareable report bundle export
- [ ] Homebrew / PyPI package
- [ ] Richer dashboard charts

## Inspirations

LLM Meter is original code, but it learns from mature observability projects including [GoAccess](https://github.com/allinurl/goaccess), [google/mtail](https://github.com/google/mtail), [Vector](https://github.com/vectordotdev/vector), and [OpenLIT](https://github.com/openlit/openlit). See [docs/inspirations.md](docs/inspirations.md).

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
