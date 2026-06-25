# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in llm-meter, please report it
privately rather than opening a public issue.

**Email**: security@supero07dl-gm.github.io (or open a security advisory on GitHub)

Please include:
- A description of the vulnerability
- Steps to reproduce (if applicable)
- The affected version(s)
- Any potential impact

We aim to acknowledge reports within 72 hours and provide a fix or mitigation
plan within 7 days.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x     | Yes (latest patch) |

## Security Considerations

- **Auth tokens**: Use `--auth-token` when exposing the dashboard or Prometheus
  endpoint beyond localhost. Never share tokens publicly.
- **Webhooks**: Webhook payloads may contain request metadata. Ensure your
  webhook endpoint uses HTTPS and validates the payload source.
- **SQLite database**: The database file contains parsed log data. Treat it as
  sensitive and restrict filesystem permissions accordingly.
- **Config files**: YAML configs may contain webhook URLs and other settings.
  Do not commit secrets to version control.
