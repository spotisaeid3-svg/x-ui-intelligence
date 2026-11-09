from types import SimpleNamespace

from xui_intelligence.collectors import system


def test_cpu_usage_uses_counter_delta(monkeypatch) -> None:
    samples = iter([(100, 40), (200, 80)])
    monkeypatch.setattr(system, "_read_cpu_counters", lambda: next(samples))
    monkeypatch.setattr(
        system,
        "_read_meminfo",
        lambda: {"MemTotal": 1000, "MemAvailable": 250},
    )
    monkeypatch.setattr(
        system,
        "_read_network_counters",
        lambda: {"eth0": {"rx_bytes": 10, "tx_bytes": 20}},
    )
    monkeypatch.setattr(
        system.shutil,
        "disk_usage",
        lambda _: SimpleNamespace(total=1000, used=400, free=600),
    )

    collector = system.SystemCollector()
    first = collector.collect()
    second = collector.collect()

    assert first["cpu"]["usage_percent"] is None
    assert second["cpu"]["usage_percent"] == 60.0
    assert second["memory"]["used_percent"] == 75.0
    assert second["disk_root"]["used_percent"] == 40.0
    assert second["network_interfaces"]["eth0"]["rx_bytes"] == 10


def test_cpu_counter_parser_returns_total_and_idle(monkeypatch) -> None:
    monkeypatch.setattr(
        system.Path,
        "read_text",
        lambda self, **kwargs: "cpu  100 20 30 400 50 0 0 0\n",
    )

    total, idle = system._read_cpu_counters()

    assert total == 600
    assert idle == 450
