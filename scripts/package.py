"""Build the HACS release archive from an explicit integration-only file list."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
component = ROOT / "custom_components/home_share"
files = sorted(p for p in component.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".json", ".js", ".png", ".svg"})
assert json.loads((component / "manifest.json").read_text())["domain"] == "home_share"
assert files
required_brand = {"icon.png", "icon@2x.png", "dark_icon.png", "dark_icon@2x.png",
                  "logo.png", "logo@2x.png", "dark_logo.png", "dark_logo@2x.png"}
assert required_brand <= {path.name for path in (component / "brand").glob("*.png")}, "Missing required brand assets"
assert component / "frontend/home-share-mark.svg" in files
with ZipFile(ROOT / "home_share.zip", "w", ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, path.relative_to(component).as_posix())
print(f"Packaged {len(files)} integration files; no configuration or credentials included.")
