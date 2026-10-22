# Changelog

## 0.1.3

- Add an original Home Share logo and icon, SVG source artwork, and light/dark PNG exports at standard and doubled resolutions.
- Bundle Home Assistant integration branding in every HACS release and display the same logo in the sidebar panel and repository README.
- Fail packaging if required brand assets are missing.
- Add an optional, backed-up and reversible Home Share logo fix for the known legacy HACS 2.0.5 frontend. Other repository icons remain unchanged.

## 0.1.2

- Normalize Home Assistant's annotated YAML types before persistence, preserving exact entity values while allowing safe serialization.
- Exercise live apply, Google serialization and recovery using the native HA YAML loader in regression tests.

## 0.1.1

- Detect the managed entities include through YAML syntax nodes, including configurations with unindented comments, quoted filenames and Home Assistant tags. Never open referenced credential files during detection.

## 0.1.0

- Initial release with a responsive Home Assistant sidebar panel.
- Preserve existing explicit Google sharing, names, rooms, aliases and unavailable entries.
- Search, area filters, bulk sharing and a device detail editor.
- Review changes and apply to both live Google configuration and durable YAML without a routine HA restart.
- Google sync status, conflict protection, atomic writes and recoverable snapshots.
- HACS installation and tests against Home Assistant 2026.10.2.
