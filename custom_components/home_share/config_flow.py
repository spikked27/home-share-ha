"""Connect an existing, manual Google Assistant setup without credentials."""
from pathlib import Path

import yaml

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .runtime import LiveConfig
from .storage import managed_file, read


def included_file(config_dir):
    text = (Path(config_dir) / "configuration.yaml").read_text(encoding="utf-8")
    # Compose syntax nodes only: preserve HA tags without loading included
    # credentials or constructing arbitrary YAML objects. Comments and quoted
    # filenames are valid YAML and must not disrupt include detection.
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    sections = [value for key, value in root.value if key.value == "google_assistant"] if isinstance(root, yaml.MappingNode) else []
    if len(sections) != 1 or not isinstance(sections[0], yaml.MappingNode):
        raise ValueError("Manual Google Assistant must be configured in configuration.yaml.")
    includes = [value for key, value in sections[0].value if key.value == "entity_config"]
    if len(includes) != 1 or not isinstance(includes[0], yaml.ScalarNode) or includes[0].tag != "!include":
        raise ValueError("Use entity_config: !include google_assistant_entities.yaml in manual Google Assistant.")
    filename = includes[0].value
    managed_file(config_dir, filename)
    return filename


class HomeShareConfigFlow(config_entries.ConfigFlow, domain="home_share"):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HomeShareOptionsFlow()

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


class HomeShareOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Optional("legacy_hacs_branding", default=self.config_entry.options.get("legacy_hacs_branding", False)): bool
        }))
