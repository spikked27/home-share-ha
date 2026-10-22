# Changelog

## 0.1.1

- Detect the managed entities include through YAML syntax nodes, including configurations with unindented comments, quoted filenames and Home Assistant tags. Never open referenced credential files during detection.

## 0.1.0

- Initial release with a responsive Home Assistant sidebar panel.
- Preserve existing explicit Google sharing, names, rooms, aliases and unavailable entries.
- Search, area filters, bulk sharing and a device detail editor.
- Review changes and apply to both live Google configuration and durable YAML without a routine HA restart.
- Google sync status, conflict protection, atomic writes and recoverable snapshots.
- HACS installation and tests against Home Assistant 2026.10.2.
