# Snapshot analytics

The pure analytics module derives throughput from consecutive cumulative counters and evaluates basic resource thresholds. It performs no file, process, network, or database I/O.

## Derived rates

- Host network: receive/transmit byte deltas per interface, divided by the measured interval.
- Xray: aggregate user/inbound/outbound uplink and downlink byte deltas, divided by the measured interval.
- Packet counters are deliberately excluded from the byte-throughput output.
- Missing counters and the first sample produce no rate.
- A decreasing counter is reported in `counter_resets`; it never produces a negative rate. This can occur after a process restart or interface reset.

The caller must provide the actual elapsed interval between snapshots. Do not assume the configured polling interval equals the observed interval.

## Resource alerts

Default thresholds:

| Resource | Warning | Critical |
|---|---:|---:|
| CPU utilization | 85% | 95% |
| Memory utilization | 90% | 97% |
| Root filesystem utilization | 85% | 95% |

Thresholds are configurable through the `AlertThresholds` value when calling the pure analysis function. These are initial operational defaults, not universal capacity-planning limits.

## Current limitations

- Alert evaluation is stateless; persistence, deduplication, cooldowns, and Telegram delivery are separate future components.
- No automatic baseline learning or statistical anomaly detection is claimed yet.
- Xray rates are aggregate only. No client names, UUIDs, or inbound tags are included.
