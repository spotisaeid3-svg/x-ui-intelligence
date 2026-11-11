#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./uninstall.sh" >&2
  exit 1
fi
# Only X-UI Intelligence units are touched. Config and collected data are preserved.
systemctl disable --now xui-intelligence.service 2>/dev/null || true
systemctl disable --now xui-intelligence-snapshot.timer 2>/dev/null || true
systemctl stop xui-intelligence-snapshot.service 2>/dev/null || true
rm -f /etc/systemd/system/xui-intelligence.service \
  /etc/systemd/system/xui-intelligence-snapshot.service \
  /etc/systemd/system/xui-intelligence-snapshot.timer
systemctl daemon-reload
rm -rf /opt/xui-intelligence
printf 'Removed X-UI Intelligence application and its systemd units.\n'
printf 'Preserved /etc/xui-intelligence and /var/lib/xui-intelligence.\n'
printf 'The service account/group were preserved. Remove them manually only after review.\n'
