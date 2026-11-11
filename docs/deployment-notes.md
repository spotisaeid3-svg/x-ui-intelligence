# Deployment notes

## Supported deployment

- Ubuntu 22.04+ / compatible systemd Linux.
- Python 3.11+, venv and pip.
- Dedicated unprivileged `xui-intelligence` service account.
- Host monitoring runs without X-UI/Xray integration. Optional integrations are explicitly enabled in TOML.

## Installation behavior

`sudo ./install.sh` installs the package to `/opt/xui-intelligence`, writes configuration only when absent, preserves existing configuration, and enables only `xui-intelligence.service`. It does not call `systemctl` for X-UI or Xray and does not modify their configuration or state.

`sudo ./install.sh --with-xui-snapshot` is an explicit opt-in. It performs one fixed-path read-only SQLite backup and installs a restricted oneshot service plus timer only after that first backup succeeds. The monitor remains configured with X-UI collection disabled until the operator explicitly enables `[xui_database].enabled`.

## Target VPS notes from prior validation

The project context records Ubuntu 24.04.5, SQLite 3.45.1, live X-UI journal mode `wal`, and `0600` WAL/SHM sidecars. A read-only SQLite Online Backup API test and `quick_check` succeeded at that time. These observations do not constitute a fresh test of the current install script, systemd sandbox, live database permissions, or timer on the target VPS.

## Post-install verification

1. Confirm config validity with `xui-intelligence --check-config`.
2. Confirm only `xui-intelligence.service` is enabled by the default installer.
3. Confirm the app runs as `xui-intelligence`, not root.
4. Confirm the monitoring SQLite database is created under `/var/lib/xui-intelligence`.
5. Enable Xray only after confirming the binary and loopback StatsService endpoint.
6. Enable the X-UI snapshot timer only after a successful manual backup on the target system.
7. Enable Telegram only after setting a bot token and explicit sender allowlist.

Do not infer production validation from CI. Run the install and verification steps on the actual target VPS before relying on the service operationally.
