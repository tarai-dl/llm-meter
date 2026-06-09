import json

from llm_meter.alerts import build_alert_payload
from llm_meter.config import load_config
from llm_meter.storage import ingest_lines


def test_budget_alert_rules_detect_cost_and_token_thresholds(tmp_path):
    db = tmp_path / "meter.db"
    ingest_lines([
        json.dumps({
            "timestamp": "2026-06-09T02:00:00Z",
            "ip": "203.0.113.10",
            "host": "api.example",
            "method": "POST",
            "path": "/v1/chat/completions",
            "status": 200,
            "model": "gpt-4o-mini",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "cost_usd": 0.75,
        }),
        json.dumps({
            "timestamp": "2026-06-09T02:01:00Z",
            "ip": "198.51.100.23",
            "host": "api.example",
            "method": "POST",
            "path": "/v1/chat/completions",
            "status": 200,
            "model": "expensive-model",
            "prompt_tokens": 2000,
            "completion_tokens": 1500,
            "total_tokens": 3500,
            "cost_usd": 1.50,
        }),
    ], db)

    payload = build_alert_payload(db, rules={
        "max_total_cost_usd": 1.0,
        "max_total_tokens": 4000,
        "max_model_cost_usd": 1.0,
    })

    kinds = {signal["kind"] for signal in payload["signals"]}
    assert "budget_cost_exceeded" in kinds
    assert "budget_tokens_exceeded" in kinds
    assert "model_cost_exceeded" in kinds
    model_signal = next(signal for signal in payload["signals"] if signal["kind"] == "model_cost_exceeded")
    assert model_signal["model"] == "expensive-model"


def test_config_loads_budget_alert_rules(tmp_path):
    config_path = tmp_path / "llm-meter.yml"
    config_path.write_text(
        """
alert:
  rules:
    max_total_cost_usd: 5.5
    max_total_tokens: 100000
    max_model_cost_usd: 2.25
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.alert.rules.max_total_cost_usd == 5.5
    assert config.alert.rules.max_total_tokens == 100000
    assert config.alert.rules.max_model_cost_usd == 2.25
    assert config.alert.rules.to_dict()["max_total_cost_usd"] == 5.5
