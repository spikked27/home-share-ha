"""Pure configuration operations. No household data or credentials live here."""
from copy import deepcopy
import hashlib
import json
import re

ENTITY_ID = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
FIELDS = {"expose", "name", "room", "aliases"}


def validate(config):
    """Validate an entity-only mapping without discarding inherited fields."""
    if not isinstance(config, dict) or len(config) > 10000:
        raise ValueError("The entities file must contain an entity mapping (maximum 10,000).")
    for entity_id, item in config.items():
        if not isinstance(entity_id, str) or not ENTITY_ID.fullmatch(entity_id):
            raise ValueError("Invalid entity identifier.")
        if not isinstance(item, dict):
            raise ValueError(f"Invalid configuration for {entity_id}.")
        for key, value in item.items():
            if key == "expose" and type(value) is not bool:
                raise ValueError("Exposure must be true or false.")
            if key in ("name", "room") and (not isinstance(value, str) or len(value) > 255):
                raise ValueError("Names and rooms must be text, up to 255 characters.")
            if key == "aliases" and (not isinstance(value, list) or len(value) > 20
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 255 for v in value)):
                raise ValueError("Use up to 20 nonempty aliases, each up to 255 characters.")
    # Also rejects exotic YAML objects and excessive payloads.
    serialized = json.dumps(config, allow_nan=False)
    if len(serialized.encode()) > 2_000_000:
        raise ValueError("Configuration is too large.")
    # HA's YAML loader returns annotated dict/list/string subclasses. Preserve
    # their values, not source annotations that PyYAML cannot serialize safely.
    return json.loads(serialized)


def revision(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def patched(config, changes):
    """Patch only requested fields; retain missing/disabled entities and extra settings."""
    result = validate(config)
    if not isinstance(changes, dict) or len(changes) > 10000:
        raise ValueError("Select at most 10,000 entities at a time.")
    for entity_id, fields in changes.items():
        if not isinstance(fields, dict) or not fields or set(fields) - FIELDS:
            raise ValueError("Unsupported change.")
        item = result.setdefault(entity_id, {})
        for key, value in fields.items():
            if value is None and key != "expose":
                item.pop(key, None)
            else:
                item[key] = value
    return validate(result)


def difference(before, after):
    return [{"entity_id": key, "before": before.get(key, {}), "after": after.get(key, {})}
            for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)]
