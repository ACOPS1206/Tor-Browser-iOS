"""Exercise the transformation against an actual pinned Reynard checkout when supplied."""
import importlib.util
import ast
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
            from test_fingerprinting import engine_fixture
            engine_fixture(engine)
            defaults = engine / 'mobile/ios/app/mobile.js'
            defaults.parent.mkdir(parents=True, exist_ok=True)
            defaults.write_text('pref("test.fixture", true);\n')
            startup = engine / 'mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs'
            startup.parent.mkdir(parents=True, exist_ok=True)
            startup.write_text('      case "profile-after-change": {\n}\n')
            modules = engine / 'mobile/shared/modules/geckoview'
            modules.mkdir(parents=True, exist_ok=True)
            (modules / 'moz.build').write_text('EXTRA_JS_MODULES += [\n    "BrowserUsageTelemetry.sys.mjs",\n    "Messaging.sys.mjs",\n]\n')
            module.apply(target)
            ui_spec = importlib.util.spec_from_file_location('privacy_ui', ROOT / 'scripts/configure-privacy-ui.py')
            ui_module = importlib.util.module_from_spec(ui_spec)
            ui_spec.loader.exec_module(ui_module)
            ui_module.apply(target)
            settings = (target / 'browser/Reynard/Client/Interface/Library/Settings/SettingsViewController.swift').read_text()
            self.assertIn('return torPrivacySection.rowCount + privacySection.rowCount', settings)
            self.assertIn('privacySection.cell(at: indexPath.row - torPrivacySection.rowCount)', settings)
            self.assertIn('privacySection.selectRow(at: indexPath.row - torPrivacySection.rowCount', settings)
            self.assertIn('footerTitle: TorPrivacySettingsSection.footer', settings)
            self.assertNotIn('navigationItem.rightBarButtonItem = UIBarButtonItem(title: "Tor"', settings)
            with self.assertRaises(RuntimeError):
                ui_module.apply(target)
            prefs = json.loads((ROOT / 'privacy-prefs.json').read_text())
            for key, value in prefs.items():
                self.assertIn(f'pref({json.dumps(key)}, {json.dumps(value)}, locked);', defaults.read_text())
                self.assertIn(f'Services.prefs.lockPref({json.dumps(key)});', startup.read_text())
            app = target / 'browser/Reynard'
            for path in app.glob('Client/**/*.swift'):
                source = path.read_text()
                self.assertNotIn('URLSession.shared', source, str(path))
                self.assertNotIn('URLSessionConfiguration.default', source, str(path))
                self.assertNotIn('URLSession(configuration: .default)', source, str(path))
            self.assertIn('onionreynard://open', (target / 'browser/Extensions/OpenIn/OpenInViewController.swift').read_text())
            self.assertNotIn('<string>reynard</string>', (app / 'Resources/Info.plist').read_text())
            self.assertNotIn('        fetchUpdates()', (app / 'Client/Startup/BrowserUpdates.swift').read_text())
            self.assertIn('isPrivateMode: TorPrivacy.activeRoutingMode == .always || isPrivate', (app / 'Client/SessionManagement/SessionManager.swift').read_text())
            for name in ['HistoryStore', 'TabManagementStore', 'FaviconStore', 'SitePermissionStore']:
                text = (app / f'Client/Stores/{name}.swift').read_text()
                self.assertIn('sqlite3_open_v2(":memory:",', text)
                self.assertNotIn('sqlite3_open_v2(storage.databaseURL.path,', text)
            for name in ['TabManagementStore', 'NavigationHistoryStore', 'FaviconStore', 'SiteMetadataStore']:
                text = (app / f'Client/Stores/{name}.swift').read_text()
                self.assertNotIn('.write(to:', text)
                self.assertNotIn('Data(contentsOf:', text)
            self.assertIn('installTorChannelIsolation()', startup.read_text())
            self.assertIn('configureTorStartupPreferences(Services)', startup.read_text())
            self.assertTrue((modules / 'TBIOPrivacy.sys.mjs').exists())
            # Python syntax alone accepts unsorted lists, but mozbuild rejects them.
            manifest = ast.parse((modules / 'moz.build').read_text())
            for statement in manifest.body:
                if isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name) and statement.target.id == 'EXTRA_JS_MODULES':
                    names = ast.literal_eval(statement.value)
                    self.assertEqual(names, sorted(names, key=str.lower))
            self.assertIn('-workspace', (target / 'tools/release/build-app.sh').read_text())
            # Applying twice must reject changed anchors, not silently produce a broken build.
            with self.assertRaises(RuntimeError):
                module.apply(target)



