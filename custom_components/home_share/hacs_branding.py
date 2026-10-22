"""Opt-in, reversible Home Share icon compatibility for legacy HACS 2.0.5.

Legacy HACS constructs a CDN URL instead of using HA's bundled brand assets.
Only the Home Share domain is redirected. Newer HACS/Marketplace is untouched.
"""
import gzip
import hashlib
import json
from pathlib import Path
import re

from .storage import atomic_write

PATTERN = re.compile(r'(?P<arg>[a-zA-Z_$][\w$]*)=>(?P<url>`https://brands\.home-assistant\.io/[^`]+`)')
MARKER = '.domain==="home_share"?`/home_share_brand/'


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _replacement(match):
    arg, url = match['arg'], match['url']
    if '${'+arg+'.domain}' not in url or '${'+arg+'.type}' not in url:
        raise ValueError("Unexpected HACS brand URL format; no changes made.")
    return f'{arg}=>{arg}.domain==="home_share"?`/home_share_brand/${{{arg}.darkOptimized?"dark_":""}}${{{arg}.type}}.png`:{url}'


def configure(config_dir, enabled):
    root = Path(config_dir).resolve()
    hacs = root / 'custom_components/hacs'
    backup = root / 'backups/home_share/hacs_branding'
    receipt = backup / 'receipt.json'
    for path in (hacs, backup.parent.parent, backup.parent, backup):
        if path.is_symlink():
            raise ValueError("Refusing to follow a symbolic link while configuring HACS branding.")
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    if not enabled:
        restored, skipped = 0, 0
        for relative, info in previous.items():
            if not re.fullmatch(r'hacs_frontend/frontend_latest/[0-9]+\.[a-f0-9]+\.js(?:\.gz)?', relative):
                raise ValueError("Invalid HACS branding recovery entry.")
            path = hacs / relative
            source = backup / relative
            if not path.resolve().is_relative_to(root) or not source.resolve().is_relative_to(root):
                raise ValueError("HACS branding recovery path leaves the configuration directory.")
            if path.is_symlink() or source.is_symlink():
                raise ValueError("Invalid HACS branding recovery path.")
            if not path.exists() or _hash(path.read_bytes()) != info['patched']:
                skipped += 1
                continue
            raw = source.read_bytes()
            if _hash(raw) != info['original']:
                raise ValueError("HACS branding backup integrity check failed.")
            atomic_write(path, raw)
            restored += 1
        return {'status': 'restored' if restored else 'unchanged', 'restored': restored, 'skipped': skipped}
    if not (hacs / 'manifest.json').exists():
        return {'status': 'not_installed'}
    if json.loads((hacs / 'manifest.json').read_text()).get('version') != '2.0.5':
        return {'status': 'unsupported_version'}
    version_file = hacs / 'hacs_frontend/version.py'
    if not version_file.exists() or '20250128065759' not in version_file.read_text():
        return {'status': 'unsupported_frontend'}
    directory = hacs / 'hacs_frontend/frontend_latest'
    if directory.parent.is_symlink() or directory.is_symlink() or not directory.is_dir():
        return {'status': 'unsupported_frontend'}
    planned = []
    for path in directory.glob('*.js'):
        if path.is_symlink():
            raise ValueError("Invalid HACS frontend asset path.")
        raw = path.read_bytes()
        content = raw.decode('utf-8')
        if MARKER in content:
            continue
        updated, count = PATTERN.subn(_replacement, content)
        if not count:
            continue
        if count != 1:
            raise ValueError("Unexpected HACS asset structure; no changes made.")
        planned.append((path, raw, updated.encode()))
        compressed = path.with_suffix(path.suffix + '.gz')
        if compressed.exists():
            if compressed.is_symlink():
                raise ValueError("Invalid compressed HACS asset path.")
            original_gzip = compressed.read_bytes()
            if gzip.decompress(original_gzip) != raw:
                raise ValueError("HACS compressed asset differs from its source; no changes made.")
            planned.append((compressed, original_gzip, gzip.compress(updated.encode(), mtime=0)))
    # Recognized distribution: seven duplicated webpack brand URL modules.
    if planned and sum(path.suffix == '.js' for path, _, _ in planned) != 7:
        raise ValueError("Unrecognized HACS distribution; no changes made.")
    written = []
    try:
        for path, old, new in planned:
            relative = path.relative_to(hacs).as_posix()
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != old:
                raise ValueError("An existing HACS backup differs; refusing to overwrite it.")
            if not target.exists():
                atomic_write(target, old)
            atomic_write(path, new)
            written.append((path, old))
            previous[relative] = {'original': _hash(old), 'patched': _hash(new)}
        if planned:
            atomic_write(receipt, json.dumps(previous, indent=2).encode())
    except Exception:
        for path, old in reversed(written):
            atomic_write(path, old)
        raise
    return {'status': 'patched' if planned else 'unchanged', 'files': len(planned)}
