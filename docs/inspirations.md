# Inspirations and acknowledgements

LLM Meter is original code, but it intentionally learns from mature observability projects.

## Projects we learn from

- [GoAccess](https://github.com/allinurl/goaccess) — real-time web log analysis with a low-friction terminal/browser experience. LLM Meter borrows the product idea of making access logs immediately useful, while focusing specifically on OpenAI-compatible API gateways.
- [google/mtail](https://github.com/google/mtail) — extracting metrics from application logs for time-series databases. LLM Meter borrows the operational idea of turning logs into Prometheus-friendly metrics.
- [Vector](https://github.com/vectordotdev/vector) — high-performance observability pipelines. LLM Meter borrows the idea that logs should be easy to ingest, normalize, and forward, while keeping this project intentionally tiny.
- [OpenLIT](https://github.com/openlit/openlit) — LLM observability and OpenTelemetry-native AI engineering. LLM Meter borrows the LLM-observability framing, but targets simple self-hosted gateway logs.

## Non-goals

LLM Meter does not copy code from these projects. The implementation is intentionally small, dependency-free, and focused on the self-hosted OpenAI-compatible gateway use case.

## Design principles borrowed from the ecosystem

- Logs should become metrics and dashboards quickly.
- Real-time/tail workflows matter for operations.
- High-cardinality labels must be bounded.
- Sensitive credentials must never be logged in full.
- The first-run experience should fit in a few shell commands.
