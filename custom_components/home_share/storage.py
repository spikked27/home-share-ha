"""Restricted, atomic entity YAML writes and immutable recovery snapshots."""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import tempfile

import yaml

from .model import validate


def managed_file(config_dir, filename):
    root = Path(config_dir).resolve()
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.ya?ml", filename):
        raise ValueError("Use an entities YAML filename in the configuration directory.")
    path = root / filename
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError("The managed entities file cannot be a symbolic link.")
    return path


def read(path):
    if path.is_symlink() or path.stat().st_size > 2_000_000:
        raise ValueError("The entities file is a symbolic link or exceeds 2 MB.")
    return validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def atomic_write(path, raw):
    if path.is_symlink():
        raise ValueError("Refusing to replace a symbolic link.")
    fd, name = tempfile.mkstemp(prefix=".home_share_", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save(path, config, expected):
    """Check external changes, back up the exact old bytes, then replace atomically."""
    if read(path) != expected:
        raise ValueError("The entities file changed elsewhere. Refresh before applying.")
    raw = path.read_bytes()
    directory = path.parent / "backups" / "home_share"
    # Do not follow a backup path redirected outside the HA config directory.
    for parent in (directory.parent, directory):
        if parent.is_symlink():
            raise ValueError("Backup directories cannot be symbolic links.")
        parent.mkdir(exist_ok=True)
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = directory / (identifier + ".yaml")
    with backup.open("xb") as stream:
        stream.write(raw)
    backup.chmod(0o600)
    atomic_write(path, yaml.safe_dump(config, sort_keys=False, allow_unicode=True).encode())
    return raw, identifier


def history(path):
    directory = path.parent / "backups" / "home_share"
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError("Invalid backup directory.")
    if not directory.exists():
        return []
    return [{"id": p.stem, "entities": len(read(p))} for p in sorted(directory.glob("*.yaml"), reverse=True)[:30]
            if re.fullmatch(r"\d{8}T\d{12}Z", p.stem)]


def restore_data(path, identifier):
    if not re.fullmatch(r"\d{8}T\d{12}Z", identifier):
        raise ValueError("Invalid backup identifier.")
    directory = path.parent / "backups" / "home_share"
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError("Invalid backup directory.")
    return read(directory / (identifier + ".yaml"))
