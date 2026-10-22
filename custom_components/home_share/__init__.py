"""Home Share: live, reversible manual Google Home exposure management."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import logging
from pathlib import Path

import probatio as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from .config_flow import included_file
from .model import difference, patched, revision
from .runtime import LiveConfig
from .storage import atomic_write, history, managed_file, read, restore_data, save

DOMAIN = "home_share"
_LOGGER = logging.getLogger(__name__)


class Manager:
    def __init__(self, hass, path):
        self.hass = hass
        self.path = path
        self.lock = asyncio.Lock()
        self.sync_lock = asyncio.Lock()
        self.last_sync = None

    def live(self):
        # Resolve again on each operation: native Google may have been reloaded.
        return LiveConfig(self.hass)

    async def snapshot(self):
        live = self.live()
        config = live.current()
        disk = await self.hass.async_add_executor_job(read, self.path)
        if disk != config:
            raise ValueError("The entities file changed outside Home Share. Reload Google Assistant before editing.")
        entities = er.async_get(self.hass)
        devices = dr.async_get(self.hass)
        areas = ar.async_get(self.hass)
        states = {state.entity_id: state for state in self.hass.states.async_all()}
        from homeassistant.components.google_assistant.const import DOMAIN_TO_GOOGLE_TYPES
        from homeassistant.components.google_assistant.helpers import async_get_google_entity_if_supported_cached
        ids = set(config) | {key for key, state in states.items()
            if key.split(".")[0] in DOMAIN_TO_GOOGLE_TYPES
            and async_get_google_entity_if_supported_cached(self.hass, live.google, state) is not None}
        items = []
        for entity_id in sorted(ids):
            state = states.get(entity_id)
            entity = entities.async_get(entity_id)
            device = devices.async_get(entity.device_id) if entity and entity.device_id else None
            area_id = (entity.area_id if entity else None) or (device.area_id if device else None)
            area = areas.async_get_area(area_id) if area_id else None
            settings = config.get(entity_id, {})
            available = bool(state and state.state not in ("unavailable", "unknown"))
            disabled = bool(entity and entity.disabled_by)
            name = (state.attributes.get("friendly_name") if state else None) or (
                (entity.name or entity.original_name) if entity else None) or entity_id.split(".")[1].replace("_", " ").title()
            items.append({"entity_id": entity_id, "name": name, "google_name": settings.get("name", ""),
                          "room": settings.get("room", ""), "area": area.name if area else "Unassigned",
                          "aliases": settings.get("aliases", []), "shared": bool(live.google.should_expose(entity_id)),
                          "available": available, "disabled": disabled, "configured": entity_id in config,
                          "domain": entity_id.split(".")[0], "state": state.state if state else None})
        return {"revision": revision(config), "items": items, "config": config,
                "last_sync": self.last_sync, "live": True, "file": self.path.name,
                "stats": {"shared": sum(x["shared"] for x in items), "total": len(items),
                          "unavailable": sum(x["shared"] and not x["available"] for x in items)}}

    async def preview(self, base, changes, backup=None):
        current = (await self.snapshot())["config"]
        if revision(current) != base:
            raise ValueError("Settings changed in another window. Refresh and review your changes again.")
        new = await self.hass.async_add_executor_job(restore_data, self.path, backup) if backup else patched(current, changes)
        return current, new

    async def apply(self, base, changes, sync=True, backup=None):
        async with self.lock:
            old, new = await self.preview(base, changes, backup)
            diff = difference(old, new)
            backup_id = None
            if diff:
                live = self.live()
                old_yaml = deepcopy(live.yaml.get("entity_config", {}))
                raw, backup_id = await self.hass.async_add_executor_job(save, self.path, new, old)
                try:
                    live.replace(new)
                except Exception:
                    await self.hass.async_add_executor_job(atomic_write, self.path, raw)
                    live.google._config["entity_config"] = old
                    live.yaml["entity_config"] = old_yaml
                    live.google.is_supported_cache.clear()
                    raise
                self.hass.bus.async_fire("home_share_updated", {"revision": revision(new)})
        result = {"applied": True, "restart_required": False, "revision": revision(new),
                  "changed": len(diff), "backup": backup_id}
        if sync:
            result["sync"] = await self.sync()
        return result

    async def sync(self):
        async with self.sync_lock:
            try:
                async with asyncio.timeout(45):
                    result = await self.live().sync()
            except Exception:
                # Do not expose upstream response bodies, credentials or agent IDs.
                _LOGGER.warning("Google sync could not complete; saved settings remain live")
                result = {"ok": False, "message": "Settings are live. Google sync could not complete; retry shortly."}
            self.last_sync = {**result, "at": datetime.now(timezone.utc).isoformat()}
            self.hass.bus.async_fire("home_share_updated", {"sync": result["ok"]})
            return self.last_sync


@websocket_api.websocket_command({vol.Required("type"): "home_share/manage",
    vol.Required("action"): vol.In(["list", "preview", "apply", "sync", "history"]),
    vol.Optional("revision"): str, vol.Optional("changes", default={}): dict,
    vol.Optional("backup"): str, vol.Optional("sync", default=True): bool})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_manage(hass, connection, msg):
    manager = hass.data.get(DOMAIN, {}).get("manager")
    if manager is None:
        connection.send_error(msg["id"], "not_ready", "Home Share is not loaded.")
        return
    try:
        action = msg["action"]
        if action == "list":
            result = await manager.snapshot()
        elif action == "history":
            result = await hass.async_add_executor_job(history, manager.path)
        elif action == "sync":
            result = await manager.sync()
        elif action == "preview":
            old, new = await manager.preview(msg.get("revision"), msg["changes"], msg.get("backup"))
            result = {"changes": difference(old, new), "restart_required": False}
        else:
            result = await manager.apply(msg.get("revision"), msg["changes"], msg["sync"], msg.get("backup"))
        connection.send_result(msg["id"], result)
    except (ValueError, OSError) as exc:
        connection.send_error(msg["id"], "invalid_change", str(exc))
    except Exception:
        _LOGGER.exception("Home Share operation failed")
        connection.send_error(msg["id"], "operation_failed", "The operation failed. Check Home Assistant logs.")


async def async_setup_entry(hass, entry):
    try:
        LiveConfig(hass)
        filename = await hass.async_add_executor_job(included_file, hass.config.config_dir)
        if filename != entry.data["filename"]:
            raise ValueError("The Google entities include has changed. Reconfigure Home Share.")
        path = managed_file(hass.config.config_dir, filename)
        manager = Manager(hass, path)
        await manager.snapshot()
    except (ValueError, OSError) as exc:
        raise ConfigEntryNotReady(str(exc)) from exc
    state = hass.data.setdefault(DOMAIN, {})
    if not state.get("registered"):
        await hass.http.async_register_static_paths([StaticPathConfig(
            "/home_share_static", str(Path(__file__).parent / "frontend"), False)])
        websocket_api.async_register_command(hass, websocket_manage)
        state["registered"] = True
    state["manager"] = manager
    await panel_custom.async_register_panel(hass, webcomponent_name="home-share-panel",
        frontend_url_path="home-share", module_url="/home_share_static/home-share.js?v=0.1.0",
        sidebar_title="Home Share", sidebar_icon="mdi:home-export-outline", require_admin=True,
        config={})
    return True


async def async_unload_entry(hass, entry):
    frontend.async_remove_panel(hass, "home-share")
    hass.data.get(DOMAIN, {}).pop("manager", None)
    return True
