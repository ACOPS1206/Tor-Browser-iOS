import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "overlay/Reynard/Resources/AppIcon.icon"


class IconInstallationTests(unittest.TestCase):
    def test_uploaded_icon_layer_references(self):
        with (ICON / "icon.json").open(encoding="utf-8") as source:
            info = json.load(source)
        self.assertEqual(len(info["groups"]), 1)
        self.assertEqual(len(info["groups"][0]["layers"]), 5)
        for layer in info["groups"][0]["layers"]:
            self.assertTrue((ICON / "Assets" / layer["image-name"]).is_file())

    def test_install_icon_replaces_original(self):
        with tempfile.TemporaryDirectory() as root:
            upstream = Path(root)
            resources = upstream / "browser/Reynard/Resources"
            old = resources / "Assets.xcassets/AppIcon.appiconset"
            old.mkdir(parents=True)
            (old / "Contents.json").write_text("{}")
            project = upstream / "browser/Reynard.xcodeproj/project.pbxproj"
            project.parent.mkdir(parents=True)
            project.write_text("PBXFileSystemSynchronizedRootGroup\n"
                               "ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;\n")
            subprocess.run([sys.executable, str(ROOT / "scripts/install-app-icon.py"),
                            str(upstream)], check=True, capture_output=True)
            self.assertFalse(old.exists())
            self.assertTrue((resources / "AppIcon.icon/icon.json").is_file())
            self.assertTrue((resources / "AppIcon.icon/Assets/원.svg").is_file())


if __name__ == "__main__":
    unittest.main()
