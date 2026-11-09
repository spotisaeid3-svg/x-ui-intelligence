import json
import subprocess
from types import SimpleNamespace

import pytest

from xui_intelligence.collectors.xray import XrayStatsCollector, XrayStatsError


def test_xray_stats_aggregate_without_identifiers(monkeypatch) -> None:
    payload = {
        "stat": [
            {"name": "user>>>alice@example.test>>>traffic>>>uplink", "value": "100"},
            {"name": "user>>>alice@example.test>>>traffic>>>downlink", "value": "200"},
            {"name": "inbound>>>vless-in>>>traffic>>>uplink", "value": "300"},
            {"name": "unrelated>>>counter", "value": "999"},
        ]
    }
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = XrayStatsCollector().collect()

    assert result["aggregates"] == {
        "inbound_uplink_bytes": 300,
        "user_downlink_bytes": 200,
        "user_uplink_bytes": 100,
    }
    assert "alice" not in json.dumps(result)
    assert captured["kwargs"]["shell"] is False
    assert "-reset=false" in captured["command"]


def test_xray_stats_rejects_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="not-json", stderr=""),
    )

    with pytest.raises(XrayStatsError, match="valid JSON"):
        XrayStatsCollector().collect()


def test_xray_binary_must_be_absolute() -> None:
    with pytest.raises(ValueError, match="absolute"):
        XrayStatsCollector(binary="xray")


def test_xray_api_must_be_loopback() -> None:
    with pytest.raises(ValueError, match="loopback"):
        XrayStatsCollector(address="0.0.0.0")
