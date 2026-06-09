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

**面向 OpenAI-compatible API 网关的轻量用量分析、滥用检测与观测工具。**

LLM Meter 可以把 Nginx / Cloudflare / 自建 AI 网关的访问日志转换为有用的报告：请求量、状态码、Top IP、auth prefix、路径、延迟、Token 用量、估算成本、异常信号、Web Dashboard、Prometheus 指标和 Webhook 告警。

适合运行这些服务的人：CLIProxyAPI、OneAPI/NewAPI、LiteLLM、LocalAI、Ollama-compatible 网关，或任何自建 OpenAI-compatible reverse proxy。

## 为什么需要它

自建 LLM API 网关很容易暴露出去，但很难回答这些问题：

- 哪个 IP 请求最多？
- 401 / 429 / 5xx 是否突然升高？
- 哪个 API key 前缀疑似被滥用？
- 流式请求是否变慢？
- 哪个模型或 key prefix 正在烧 token 和成本？
- 公开分享的 endpoint 是否开始吸引 bot 流量？

LLM Meter 从最可靠也最容易拿到的数据开始：访问日志。

## 功能

- 解析 Nginx combined log 和自定义 LLM gateway log。
- 支持 Cloudflare Logpush JSONL。
- 输出文本报告和 JSON 报告。
- 持久化到 SQLite，支持历史趋势。
- `--follow` 模式持续跟踪日志写入。
- 内置 Web Dashboard。
- Prometheus `/metrics` exporter。
- Webhook / cron 告警。
- YAML 配置文件，适合长期部署。
- SQLite 数据保留清理，避免小 VPS 磁盘被历史日志撑爆。
- 从 JSON 网关日志中统计 token 用量和估算成本。
- Docker、Docker Compose、systemd 示例。
- 默认安全思路：只记录短 auth prefix，不记录完整 API key。

## 快速开始

从源码运行：

```bash
git clone https://github.com/tarai-dl/llm-meter.git
cd llm-meter
python3 -m llm_meter analyze examples/cpa.log
```

分析你的网关日志：

```bash
python3 -m llm_meter analyze /var/log/nginx/llm-gateway-access.log
```

持久化到 SQLite：

```bash
python3 -m llm_meter ingest /var/log/nginx/llm-gateway-access.log --db llm-meter.db
python3 -m llm_meter report --db llm-meter.db
```

持续跟踪日志：

```bash
python3 -m llm_meter ingest /var/log/nginx/llm-gateway-access.log --db llm-meter.db --follow
```

启动 Dashboard：

```bash
python3 -m llm_meter serve --db llm-meter.db
# 打开 http://127.0.0.1:8765
```

启动 Prometheus exporter：

```bash
python3 -m llm_meter export-prometheus --db llm-meter.db
curl http://127.0.0.1:9108/metrics
```

发送告警：

```bash
python3 -m llm_meter alert --db llm-meter.db --text
python3 -m llm_meter alert --db llm-meter.db --webhook-url https://example.com/webhook
```

使用配置文件和自定义告警规则：

```yaml
database: /var/lib/llm-meter/llm-meter.db
retention_days: 30

alert:
  webhook_url: https://example.com/webhook
  include_ok: false
  rules:
    max_4xx_rate: 0.30
    max_5xx_rate: 0.05
    max_latency_seconds: 30
    max_requests_per_ip: 1000
    max_total_cost_usd: 10
    max_total_tokens: 1000000
    max_model_cost_usd: 5
```

```bash
python3 -m llm_meter alert --config examples/llm-meter.yml --text
python3 -m llm_meter prune --config examples/llm-meter.yml
```

当前规则覆盖：4xx 比例、5xx 比例、最大延迟、单 IP 请求量、总成本预算、总 token 预算、单模型成本预算。示例见 [examples/llm-meter.yml](examples/llm-meter.yml)。

Token / 成本分析：

如果你的网关能输出带 model / usage / cost 字段的 JSON 日志，LLM Meter 会自动汇总：

```json
{"timestamp":"2026-06-09T02:00:00Z","ip":"203.0.113.10","host":"api.example","method":"POST","path":"/v1/chat/completions","status":200,"model":"gpt-4o-mini","prompt_tokens":1000,"completion_tokens":500,"total_tokens":1500,"cost_usd":0.000675}
```

报告会包含：

- prompt / completion / total tokens
- USD 估算总成本
- Top models
- 按 model 汇总的估算成本

这些字段同样会出现在 JSON report、Web Dashboard 和静态 HTML 报告里。

导出静态 HTML 报告：

```bash
python3 -m llm_meter export-html --db llm-meter.db --output report.html
```

导出 Markdown 报告，适合 incident note、GitHub issue、runbook 或聊天交接：

```bash
python3 -m llm_meter export-markdown --db llm-meter.db --output report.md
```

导出完整分享包，适合排查、交接或发 issue：

```bash
python3 -m llm_meter export-bundle --db llm-meter.db --output llm-meter-report.zip
```

bundle 内包含 `report.html`、`report.md`、`report.json` 和 `manifest.json`。

## Docker

```bash
docker build -t llm-meter .
docker run --rm -v /var/log/nginx:/logs:ro llm-meter analyze /logs/llm-gateway-access.log
```

Docker Compose：

```bash
docker compose up -d
```

生成本地 demo 包，方便快速体验或做截图：

```bash
python3 -m llm_meter demo --output-dir /tmp/llm-meter-demo
# 打开 /tmp/llm-meter-demo/demo-report.html
```

`demo` 命令会生成确定性的示例 JSONL 日志、SQLite 数据库和静态 HTML Dashboard 报告，里面包含流量、Token、成本、模型和告警信号数据。

在接入 cron / systemd 前，可以先做部署诊断：

```bash
python3 -m llm_meter doctor \
  --config examples/llm-meter.yml \
  --db /var/lib/llm-meter/llm-meter.db \
  --log /var/log/nginx/llm-gateway-access.log
```

`doctor` 会检查配置文件解析、SQLite 可读性，以及日志样本是否能被解析。

## Nginx 日志格式

推荐使用自定义 log format，这样能统计 host、auth prefix、延迟等字段：

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

完整配置见：

- [docs/nginx.md](docs/nginx.md)
- [docs/gateway-presets.md](docs/gateway-presets.md)
- [docs/systemd.md](docs/systemd.md)

## 支持输入

| 来源 | 状态 |
| --- | --- |
| Nginx combined access log | 支持 |
| Nginx custom gateway log | 支持 |
| Cloudflare real IP 字段 | Nginx 日志里存在时支持 |
| Cloudflare Logpush JSONL | 支持 |
| 带 model / token / cost 字段的 JSON 日志 | 支持 |
| LiteLLM structured logs | 计划中 |
| OneAPI/NewAPI logs | 计划中 |

## 常见部署方式

推荐 VPS 常驻链路：

```text
Nginx access.log
  → llm-meter ingest --follow
  → SQLite
  → llm-meter serve
  → llm-meter export-prometheus
  → llm-meter alert
```

systemd 示例在：

```text
deploy/systemd/
```

## 路线图

- [x] SQLite 历史存储
- [x] Web Dashboard
- [x] Prometheus exporter
- [x] Webhook 告警
- [x] Cloudflare Logpush parser
- [x] LiteLLM / OneAPI / NewAPI 网关预设
- [x] Docker Compose 示例
- [x] 静态 HTML 报告导出
- [x] YAML 配置文件
- [x] 自定义告警规则
- [x] SQLite 数据保留清理
- [x] JSON 日志 Token / 成本分析
- [x] 成本和 Token 预算告警规则
- [x] Demo 数据和静态报告生成器
- [x] 部署 doctor 诊断命令
- [x] Markdown 报告导出
- [x] 可分享 report bundle 导出
- [ ] PyPI / Homebrew 发布
- [ ] 更完整的 Dashboard 图表

## 致谢 / 借鉴

LLM Meter 是原创代码，但产品思路借鉴了成熟观测项目：

- [GoAccess](https://github.com/allinurl/goaccess)
- [google/mtail](https://github.com/google/mtail)
- [Vector](https://github.com/vectordotdev/vector)
- [OpenLIT](https://github.com/openlit/openlit)

详见 [docs/inspirations.md](docs/inspirations.md)。

## 安全建议

- 不要记录完整 Authorization header。
- 只记录短 `auth_prefix`。
- 不要把真实 access log 提交到 GitHub。
- 分享截图前请打码 IP 和 key prefix。

## License

MIT
