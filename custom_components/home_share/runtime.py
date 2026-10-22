"""A small, guarded adapter for HA's manual GoogleConfig live configuration.

HA currently exposes no public reload API for manual entity_config. Keep the
private interface isolated here, verify it, and fail closed if it changes.
"""
from copy import deepcopy

from homeassistant.components.google_assistant.const import DATA_CONFIG, DOMAIN, SOURCE_CLOUD
from homeassistant.components.google_assistant.http import GoogleConfig


class LiveConfig:
    def __init__(self, hass):
        entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)
                   if entry.source != SOURCE_CLOUD and isinstance(getattr(entry, "runtime_data", None), GoogleConfig)]
        if len(entries) != 1:
            raise ValueError("A running manual Google Assistant integration is required.")
        self.google = entries[0].runtime_data
        self.yaml = hass.data.get(DOMAIN, {}).get(DATA_CONFIG)
        if (not isinstance(getattr(self.google, "_config", None), dict)
                or not isinstance(self.yaml, dict)
                or not isinstance(getattr(self.google, "is_supported_cache", None), dict)
                or not callable(getattr(self.google, "async_sync_entities_all", None))):
            raise ValueError("This Home Assistant version changed the live configuration interface.")
        if self.google._config.get("expose_by_default", True):
            raise ValueError("Set expose_by_default: false in manual Google Assistant before using Home Share.")

    def current(self):
        return deepcopy(self.google.entity_config)

    def replace(self, config):
        self.google._config["entity_config"] = deepcopy(config)
        self.yaml["entity_config"] = deepcopy(config)
        self.google.is_supported_cache.clear()

    async def sync(self):
        users = self.google.async_get_agent_users()
        if not users:
            return {"ok": False, "message": "No linked Google account. Link the existing project in Google Home."}
        code = int(await self.google.async_sync_entities_all())
        return {"ok": 200 <= code < 300, "status": code,
                "message": "Google accepted the sync request." if 200 <= code < 300
                else f"Google sync returned {code}. Settings are live; retry sync."}
