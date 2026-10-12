"""Exercise the transformation against an actual pinned Reynard checkout when supplied."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('UPSTREAM_SOURCE'), 'Set UPSTREAM_SOURCE to pinned Reynard source')
class OverlayIntegrationTests(unittest.TestCase):
    def test_actual_source_transformation_and_fail_closed_routes(self):
        spec = importlib.util.spec_from_file_location('overlay', ROOT / 'scripts/apply-overlay.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'upstream'
            shutil.copytree(os.environ['UPSTREAM_SOURCE'], target, ignore=shutil.ignore_patterns('.git'))
            # Engine fixture tests insertion and locking; actual Gecko compilation is a separate CI job.
            engine = target / 'engine/firefox'
            defaults = engine / 'mobile/ios/app/mobile.js'
            defaults.parent.mkdir(parents=True, exist_ok=True)
            defaults.write_text('pref("test.fixture", true);\n')
            startup = engine / 'mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs'
            startup.parent.mkdir(parents=True, exist_ok=True)
            startup.write_text('      case "profile-after-change": {\n}\n')
            module.apply(target)
            prefs = json.loads((ROOT / 'privacy-prefs.json').read_text())
            for key, value in prefs.items():
                self.assertIn(f'pref({json.dumps(key)}, {json.dumps(value)});', defaults.read_text())
                self.assertIn(f'Services.prefs.lockPref({json.dumps(key)});', startup.read_text())
            app = target / 'browser/Reynard'
            for path in app.glob('Client/**/*.swift'):
                source = path.read_text()
                self.assertNotIn('URLSession.shared', source, str(path))
                self.assertNotIn('URLSessionConfiguration.default', source, str(path))
                self.assertNotIn('URLSession(configuration: .default)', source, str(path))
            self.assertNotIn('        fetchUpdates()', (app / 'Client/Startup/BrowserUpdates.swift').read_text())
            self.assertIn('isPrivateMode: true', (app / 'Client/SessionManagement/SessionManager.swift').read_text())
            self.assertIn('-workspace', (target / 'tools/release/build-app.sh').read_text())
            # Applying twice must reject changed anchors, not silently produce a broken build.
            with self.assertRaises(RuntimeError):
                module.apply(target)
