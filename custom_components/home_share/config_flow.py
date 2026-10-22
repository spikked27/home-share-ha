"""Connect an existing, manual Google Assistant setup without credentials."""
from pathlib import Path
import re

import probatio as vol
from homeassistant import config_entries

from .runtime import LiveConfig
from .storage import managed_file, read


def included_file(config_dir):
    text = (Path(config_dir) / "configuration.yaml").read_text(encoding="utf-8")
    section = re.search(r"(?m)^google_assistant:\s*\n((?:[ \t]+[^\n]*\n|\s*\n)*)", text + "\n")
    if not section:
        raise ValueError("Manual Google Assistant must be configured in configuration.yaml.")
    match = re.search(r"(?m)^  entity_config:\s*!include\s+([A-Za-z0-9_-]+\.ya?ml)\s*(?:#.*)?$", section[1])
    if not match:
        raise ValueError("Use entity_config: !include google_assistant_entities.yaml in manual Google Assistant.")
    return match[1]


class HomeShareConfigFlow(config_entries.ConfigFlow, domain="home_share"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("home_share")
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            try:
                live = LiveConfig(self.hass)
                filename = await self.hass.async_add_executor_job(included_file, self.hass.config.config_dir)
                path = managed_file(self.hass.config.config_dir, filename)
                data = await self.hass.async_add_executor_job(read, path)
                if data != live.current():
                    raise ValueError("The entities file differs from the running Google configuration. Reload Google first.")
            except (ValueError, OSError) as exc:
                return self.async_show_form(step_id="user", data_schema=vol.Schema({}),
                                            errors={"base": "setup_failed"}, description_placeholders={"error": str(exc)})
            return self.async_create_entry(title="Home Share", data={"filename": filename})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}), errors=errors,
                                    description_placeholders={"error": ""})
