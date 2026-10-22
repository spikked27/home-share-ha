"""Exercise our adapter and transaction against the real HA GoogleConfig class."""
import asyncio
from copy import deepcopy
import pathlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.components.google_assistant.http import GoogleConfig
from homeassistant.helpers import entity_registry as er, device_registry as dr, area_registry as ar

from custom_components.home_share import Manager, websocket_manage
from custom_components.home_share.config_flow import included_file
from custom_components.home_share.model import patched, revision
from custom_components.home_share.runtime import LiveConfig
from custom_components.home_share.storage import read


class LiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.tmp.name)
        self.config = {"light.example": {"expose": True, "name": "Original", "room": "Study"},
                       "switch.missing": {"expose": True, "name": "Retained"}}
        self.google = GoogleConfig(self.hass, {"entity_config": deepcopy(self.config), "expose_by_default": False,
            "exposed_domains": ["light", "switch"], "service_account": {"private_key": "SYNTHETIC_ONLY"}})
        self.google._store = SimpleNamespace(agent_user_ids={"synthetic": {}})
        self.entry = SimpleNamespace(source="import", runtime_data=self.google)
        self.hass.config_entries = MagicMock()
        self.hass.config_entries.async_entries.return_value = [self.entry]
        self.hass.data["google_assistant"] = {"config": deepcopy(self.google._config)}
        await dr.async_load(self.hass)
        await ar.async_load(self.hass)
        await er.async_load(self.hass)
        self.path = pathlib.Path(self.tmp.name) / "entities.yaml"
        import yaml
        self.path.write_text(yaml.safe_dump(self.config))
        self.manager = Manager(self.hass, self.path)

    async def asyncTearDown(self):
        await self.hass.async_stop()
        self.tmp.cleanup()

    async def test_changes_native_exposure_and_names_without_restart(self):
        self.assertTrue(self.google.should_expose("light.example"))
        result = await self.manager.apply(revision(self.config), {"light.example": {"expose": False, "name": "New"}}, sync=False)
        self.assertFalse(result["restart_required"])
        self.assertFalse(self.google.should_expose("light.example"))
        self.assertEqual(self.google.entity_config["light.example"]["name"], "New")
        self.assertEqual(self.google.entity_config, read(self.path))
        self.assertEqual(self.google.entity_config["switch.missing"], self.config["switch.missing"])
        self.assertEqual(self.google._config["service_account"]["private_key"], "SYNTHETIC_ONLY")

    async def test_google_sync_serialization_reads_live_names_rooms_and_aliases(self):
        from homeassistant.components.google_assistant.helpers import GoogleEntity
        from homeassistant.core import State
        state = State("light.example", "on", {"friendly_name": "Example", "supported_color_modes": ["onoff"]})
        entity = GoogleEntity(self.hass, self.google, state)
        self.assertEqual(entity.sync_serialize("synthetic", "synthetic")["name"]["name"], "Original")
        await self.manager.apply(revision(self.config), {"light.example": {
            "name": "Reading lamp", "room": "Library", "aliases": ["Book light"]}}, sync=False)
        payload = entity.sync_serialize("synthetic", "synthetic")
        self.assertEqual(payload["name"]["name"], "Reading lamp")
        self.assertEqual(payload["name"]["nicknames"], ["Reading lamp", "Book light"])
        self.assertEqual(payload["roomHint"], "Library")

    async def test_stale_revision_cannot_write(self):
        with self.assertRaisesRegex(ValueError, "another window"):
            await self.manager.apply("stale", {"light.example": {"expose": False}}, False)
        self.assertEqual(read(self.path), self.config)

    async def test_runtime_failure_rolls_back_yaml(self):
        with patch.object(LiveConfig, "replace", side_effect=RuntimeError("synthetic failure")) as replacement:
            with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                await self.manager.apply(revision(self.config), {"light.example": {"expose": False}}, False)
            replacement.assert_called_once()
        self.assertEqual(read(self.path), self.config)
        self.assertEqual(self.google.entity_config, self.config)

    async def test_reload_uses_new_runtime(self):
        original = self.manager.live().google
        self.entry.runtime_data = GoogleConfig(self.hass, deepcopy(original._config))
        self.assertIsNot(self.manager.live().google, original)

    async def test_snapshot_retains_missing_entities_without_secrets(self):
        result = await self.manager.snapshot()
        item = next(x for x in result["items"] if x["entity_id"] == "switch.missing")
        self.assertTrue(item["shared"])
        self.assertFalse(item["available"])
        self.assertNotIn("SYNTHETIC_ONLY", str(result))

    async def test_native_sync_and_failure(self):
        with patch.object(self.google, "async_sync_entities_all", new=AsyncMock(return_value=200)):
            self.assertTrue((await self.manager.sync())["ok"])
        with patch.object(self.google, "async_sync_entities_all", new=AsyncMock(side_effect=TimeoutError)):
            self.assertFalse((await self.manager.sync())["ok"])

    async def test_non_admin_is_rejected(self):
        from homeassistant.exceptions import Unauthorized
        connection = SimpleNamespace(user=SimpleNamespace(is_admin=False))
        with self.assertRaises(Unauthorized):
            websocket_manage(self.hass, connection, {"id": 1, "type": "home_share/manage", "action": "list"})

    async def test_default_sharing_fails_closed(self):
        self.google._config["expose_by_default"] = True
        with self.assertRaises(ValueError):
            LiveConfig(self.hass)

    async def test_configuration_include_detection(self):
        path = pathlib.Path(self.tmp.name) / "configuration.yaml"
        path.write_text("google_assistant:\n  expose_by_default: false\n  entity_config: !include entities.yaml\nother:\n  test: true\n")
        self.assertEqual(included_file(self.tmp.name), "entities.yaml")


if __name__ == "__main__":
    unittest.main()
