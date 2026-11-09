# Security boundary

## Allowed in V1

- Read Linux telemetry from procfs and filesystem statistics.
- Write monitoring measurements to the application's own database.
- Read Xray statistics through its loopback API after that collector is implemented and validated.
- Read X-UI inventory data through a separately validated read-only database access mechanism.
- Send reports and alerts to explicitly authorized Telegram accounts after Telegram integration is implemented.

## Explicitly out of scope

- Restarting, stopping, or modifying X-UI, Xray, or other services.
- Creating, editing, deleting, enabling, or disabling X-UI clients or inbounds.
- Editing Xray configuration, routing, firewall, SSH, or system settings.
- Running shell commands supplied by Telegram or any remote user.
- Reading decrypted HTTPS/VPN application payloads.

## Credential handling

- Never commit bot tokens, API tokens, client UUIDs, private keys, or passwords.
- Keep runtime secrets in root-readable or service-user-readable local files with restrictive permissions.
- Mask identifiers in logs and Telegram output.
- Authorize Telegram sender IDs before returning server-specific information.

## Database handling

The X-UI database is not the monitoring database. Do not change its owner or mode. Confirm SQLite journal mode and sidecar-file behavior before implementing access controls. Prefer a verified read-only snapshot or another safe read-only mechanism over broadening permissions on the live panel database.
