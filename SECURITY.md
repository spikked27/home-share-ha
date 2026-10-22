# Security

Report vulnerabilities using this repository's private vulnerability reporting feature. Do not post access tokens, service-account keys, household configuration, addresses or unredacted logs in public issues.

Home Share uses Home Assistant's authenticated WebSocket connection and additionally requires an administrator for every operation. It has no separate authentication service, telemetry, external frontend assets or account system. Google requests use the credentials already held by the native manual Google Assistant integration. Those credentials are never included in Home Share's API responses or snapshots.

Entity settings and recovery files contain household metadata and are private. They belong in `/config`, not in this repository. The release packager includes integration source files only.

Version 0.1.x is supported. The live configuration adapter depends on a guarded private Home Assistant interface and is tested against 2026.10.2. A successful test on one version does not guarantee compatibility with future versions.
