# Host telemetry semantics

The first collector is Linux-specific and read-only.

| Measurement | Source | Interpretation |
|---|---|---|
| CPU usage | /proc/stat | Percentage calculated from deltas between consecutive samples. The first sample is intentionally null. |
| Memory | /proc/meminfo | Used memory is calculated as MemTotal minus MemAvailable. |
| Root filesystem | Python disk usage API | Capacity and used percentage for /. |
| Load average | os.getloadavg() | 1, 5, and 15 minute load averages; compare with logical CPU count. |
| Uptime | /proc/uptime | Kernel uptime in seconds. |
| Network | /proc/net/dev | Per-interface byte and packet counters, excluding loopback. Values are cumulative counters, not rates. |

Network throughput must be derived from counter deltas and elapsed wall-clock time by the analytics layer. A counter reset or interface disappearance must be treated as a new baseline rather than a negative traffic rate.

No packet payloads are inspected. This collector does not inspect user traffic content, TLS sessions, or decrypted VPN data.
