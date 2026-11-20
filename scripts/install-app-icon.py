#!/usr/bin/env python3
"""Install the Tor Icon Composer app icon into the pinned Reynard build."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "overlay/Reynard/Resources/AppIcon.icon"


def install(upstream: Path) -> None:
    assets = upstream / "browser/Reynard/Resources"
    project = upstream / "browser/Reynard.xcodeproj/project.pbxproj"
    old = assets / "Assets.xcassets/AppIcon.appiconset"
    target = assets / "AppIcon.icon"

    metadata = json.loads((ICON / "icon.json").read_text(encoding="utf-8"))
    images = [layer["image-name"] for group in metadata["groups"]
              for layer in group["layers"]]
    for name in images:
        if not (ICON / "Assets" / name).is_file():
            raise FileNotFoundError(f"Missing Icon Composer layer: {name}")
    pbx = project.read_text(encoding="utf-8")
    if ("ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;" not in pbx
            or "PBXFileSystemSynchronizedRootGroup" not in pbx):
        raise RuntimeError("Pinned upstream Xcode project no longer recognizes the AppIcon source")

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ICON, target)

    # A second AppIcon source with the same name causes a conflicting catalog.
    if old.exists():
        shutil.rmtree(old)
    print(f"Installed Icon Composer AppIcon.icon with {len(images)} layers")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: install-app-icon.py PATH_TO_UPSTREAM")
    install(Path(sys.argv[1]).resolve())
