from xui_intelligence.analytics import AlertThresholds, analyze_snapshots


def test_network_and_xray_rates_are_derived_from_counter_deltas() -> None:
    previous = {
        "network_interfaces": {
            "eth0": {"rx_bytes": 1000, "tx_bytes": 500, "rx_packets": 10}
        },
        "xray": {"aggregates": {"user_uplink_bytes": 200, "user_downlink_bytes": 400}},
    }
    current = {
        "network_interfaces": {
            "eth0": {"rx_bytes": 3000, "tx_bytes": 1500, "rx_packets": 30}
        },
        "xray": {"aggregates": {"user_uplink_bytes": 600, "user_downlink_bytes": 1000}},
        "cpu": {"usage_percent": 30},
        "memory": {"used_percent": 50},
        "disk_root": {"used_percent": 60},
    }

    result = analyze_snapshots(previous, current, elapsed_seconds=2)

    assert result["network_bytes_per_second"]["eth0"] == {
        "rx_bytes": 1000.0,
        "tx_bytes": 500.0,
    }
    assert result["xray_bytes_per_second"] == {
        "user_downlink_bytes": 300.0,
        "user_uplink_bytes": 200.0,
    }
    assert result["counter_resets"] == []
    assert result["alerts"] == []


def test_counter_decrease_is_reported_as_reset_not_negative_rate() -> None:
    previous = {
        "network_interfaces": {"eth0": {"rx_bytes": 500}},
        "xray": {"aggregates": {"inbound_uplink_bytes": 900}},
    }
    current = {
        "network_interfaces": {"eth0": {"rx_bytes": 20}},
        "xray": {"aggregates": {"inbound_uplink_bytes": 10}},
    }

    result = analyze_snapshots(previous, current, elapsed_seconds=5)

    assert result["network_bytes_per_second"] == {}
    assert result["xray_bytes_per_second"] == {}
    assert "network:eth0:rx_bytes" in result["counter_resets"]
    assert "xray:inbound_uplink_bytes" in result["counter_resets"]


def test_first_sample_has_no_rates_but_can_raise_resource_alerts() -> None:
    current = {
        "cpu": {"usage_percent": 96},
        "memory": {"used_percent": 92},
        "disk_root": {"used_percent": 80},
    }

    result = analyze_snapshots(None, current)

    assert result["network_bytes_per_second"] == {}
    assert [alert["code"] for alert in result["alerts"]] == [
        "cpu_high",
        "memory_high",
    ]
    assert result["alerts"][0]["severity"] == "critical"
    assert result["alerts"][1]["severity"] == "warning"


def test_invalid_interval_does_not_produce_rates() -> None:
    result = analyze_snapshots(
        {"network_interfaces": {"eth0": {"rx_bytes": 1}}},
        {"network_interfaces": {"eth0": {"rx_bytes": 100}}},
        elapsed_seconds=0,
    )
    assert result["network_bytes_per_second"] == {}


def test_custom_thresholds_are_supported() -> None:
    result = analyze_snapshots(
        None,
        {"cpu": {"usage_percent": 70}},
        thresholds=AlertThresholds(cpu_warning=65, cpu_critical=90),
    )
    assert result["alerts"][0]["severity"] == "warning"
