import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fingerprinting', ROOT / 'scripts/fingerprinting-policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

def replace(path, before, after):
    source = path.read_text()
    if source.count(before) != 1:
        raise RuntimeError('Changed source anchor')
    path.write_text(source.replace(before, after))

def engine_fixture(engine):
    # Anchor fixtures are transformation tests, never runtime evidence.
    files = {
        'toolkit/moz.configure': '"--enable-proxy-bypass-protection"\n"--disable-proxy-direct-failover"',
        'toolkit/components/resistfingerprinting/nsRFPService.h':
            '#elif defined(MOZ_WIDGET_ANDROID)\n#  define SPOOFED_UA_OS',
        'toolkit/components/resistfingerprinting/nsRFPService.cpp':
            '#if defined(ANDROID)\n  if (aAndroidDesktopMode)',
        'dom/base/Navigator.cpp': '#elif defined(XP_IOS)\n  aPlatform.AssignLiteral("iPhone");',
        'dom/workers/WorkerNavigator.cpp':
            '  // navigator.platform is the same for default and spoofed values. The',
        'mobile/shared/modules/geckoview/GeckoViewSettings.sys.mjs': '    const { settings } = this;',
    }
    for path, content in files.items():
        file = engine / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)

class FingerprintingTests(unittest.TestCase):
    def test_changed_or_duplicate_source_is_rejected(self):
        for modified in ['changed', 'duplicated']:
            with tempfile.TemporaryDirectory() as d:
                engine = Path(d)
                engine_fixture(engine)
                p = engine / 'dom/base/Navigator.cpp'
                p.write_text('changed' if modified == 'changed' else p.read_text() * 2)
                with self.assertRaises(RuntimeError):
                    policy.apply(engine, replace)

    def test_second_application_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            engine = Path(d)
            engine_fixture(engine)
            policy.apply(engine, replace)
            with self.assertRaises(RuntimeError):
                policy.apply(engine, replace)

    def test_locale_and_rfp_apply_in_all_routing_modes(self):
        prefs = json.loads((ROOT / 'privacy-prefs.json').read_text())
        self.assertEqual(prefs['privacy.spoof_english'], 2)
        self.assertTrue(prefs['privacy.resistFingerprinting'])
        source = (ROOT / 'overlay/Gecko/TBIOPrivacy.sys.mjs').read_text()
        self.assertNotIn('privacy.resistFingerprinting', source)
        self.assertNotIn('privacy.spoof_english', source)

    def test_tab_status_refreshes_on_selection_and_session_replacement(self):
        status = (ROOT / 'overlay/Reynard/Tor/TorBrowserStatus.swift').read_text()
        self.assertIn('usesTor(isPrivate: session.isPrivateMode)', status)
        self.assertIn('tabManager.selectedTabMode == .private', status)
        self.assertIn('Direct Connection Policy', status)
        self.assertNotIn('Private tabs only · ', status)
        overlay = (ROOT / 'scripts/apply-overlay.py').read_text()
        for signature in ['tabManagerDidChangeTabs', 'didSelectTabAt', 'didReplaceSelectedSession']:
            self.assertIn(signature, overlay)

    @unittest.skipUnless(os.environ.get('GECKO_REVIEW_SOURCE'), 'Supply reviewed patched Gecko 157 source')
    def test_actual_patched_source_and_compiler_identity_macros(self):
        with tempfile.TemporaryDirectory() as d:
            engine = Path(d) / 'engine'
            shutil.copytree(os.environ['GECKO_REVIEW_SOURCE'], engine)
            policy.apply(engine, replace)
            header = (engine / 'toolkit/components/resistfingerprinting/nsRFPService.h').read_text()
            # Exercise the real header's identity preprocessor section for all
            # platform branches. This does not compile Gecko or emulate iPhone.
            section = header[header.index('#define SPOOFED_UA_OS_OTHER'):header.index('#define LEGACY_BUILD_ID')]
            probe = Path(d) / 'identity.cpp'
            probe.write_text(section + '\nSPOOFED_UA_OS\nSPOOFED_APPVERSION\nSPOOFED_OSCPU\nSPOOFED_MAX_TOUCH_POINTS\n')
            outputs = {}
            for macro in ['XP_IOS', 'MOZ_WIDGET_ANDROID', 'XP_WIN', 'XP_MACOSX', 'LINUX']:
                outputs[macro] = subprocess.check_output(
                    ['c++', '-E', '-P', '-D' + macro, str(probe)], text=True)
            self.assertEqual(outputs['XP_IOS'], outputs['MOZ_WIDGET_ANDROID'])
            self.assertIn('Android 10; Mobile', outputs['XP_IOS'])
            self.assertIn('Windows NT 10.0', outputs['XP_WIN'])
            self.assertIn('Macintosh', outputs['XP_MACOSX'])
            self.assertIn('Linux x86_64', outputs['LINUX'])
            with self.assertRaises(RuntimeError):
                policy.apply(engine, replace)
