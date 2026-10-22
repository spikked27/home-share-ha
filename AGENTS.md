# Project instructions

Every project deliverable must include original logo and icon assets. Preserve the Home Share artwork in `custom_components/home_share/brand/`, include light/dark and standard/doubled-resolution PNG variants in release archives, and verify actual display in Home Assistant, HACS, and the panel. Do not replace the logo with a generic placeholder.

Keep household configuration and credentials out of this repository. Use synthetic fixtures and run the existing CI checks before publishing releases. Runtime changes require tests against the native Home Assistant YAML loader and GoogleConfig implementation.
