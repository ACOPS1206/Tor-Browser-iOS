import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compact', ROOT / 'scripts/compact-gecko-resources.py')
compact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compact)

class AndroidImprovementTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler unavailable')
    def test_poll_timeout_reordering_pause_and_real_circuit_requirement(self):
        with tempfile.TemporaryDirectory() as d:
            binary = Path(d) / 'poll-check'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I' + str(ROOT / 'overlay/Reynard/Tor'), str(ROOT / 'tests/status-poll.c'),
                '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_resource_compaction_preserves_names_data_order_and_modes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'omni.ja'
            with zipfile.ZipFile(p, 'w') as z:
                z.comment = b'archive-comment'
                info = zipfile.ZipInfo('modules/Policy.sys.mjs')
                info.external_attr = 0o100644 << 16
                z.writestr(info, b'const privacy = true;\n' * 5000)
                z.writestr('locale/ko.txt', '한국어 Ω'.encode())
            with zipfile.ZipFile(p) as z:
                expected = compact.contents(z)
                mode = z.getinfo('modules/Policy.sys.mjs').external_attr
            before, after = compact.compact(p)
            self.assertLess(after, before)
            with zipfile.ZipFile(p) as z:
                self.assertEqual(compact.contents(z), expected)
                self.assertEqual(z.comment, b'archive-comment')
                self.assertEqual(z.getinfo('modules/Policy.sys.mjs').external_attr, mode)
                self.assertEqual(z.getinfo('modules/Policy.sys.mjs').compress_type, zipfile.ZIP_DEFLATED)

    def test_compaction_keeps_original_if_no_size_win(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'omni.ja'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('empty', b'')
            original = p.read_bytes()
            before, after = compact.compact(p)
            self.assertEqual(before, after)
            self.assertEqual(original, p.read_bytes())

    def test_symlink_and_corrupt_archive_are_not_modified(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'bad.ja'
            target.write_bytes(b'not a zip')
            alias = Path(d) / 'omni.ja'
            alias.symlink_to(target)
            with self.assertRaises(ValueError):
                compact.compact(alias)
            with self.assertRaises(zipfile.BadZipFile):
                compact.compact(target)
            self.assertEqual(target.read_bytes(), b'not a zip')
            self.assertFalse(list(Path(d).glob('.omni-*')))

    def test_compaction_reads_zip_with_a_loader_prefix(self):
        # A prefixed ZIP exercises offsets; it is not a complete optimized
        # Gecko omnijar fixture and does not replace a Gecko startup test.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'omni.ja'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('module.js', b'export const x = true;\n' * 1000)
            p.write_bytes(b'prefixed zip\0' + p.read_bytes())
            before, after = compact.compact(p)
            self.assertLess(after, before)
            with zipfile.ZipFile(p) as z:
                self.assertEqual(z.read('module.js'), b'export const x = true;\n' * 1000)

    @unittest.skipUnless(shutil.which('node'), 'Node runtime unavailable')
    def test_blocked_native_and_gecko_gates_do_not_reroute_direct_tabs(self):
        subprocess.run(['node', str(ROOT / 'tests/tor-gate.mjs')], check=True)
        native = (ROOT / 'overlay/Reynard/Tor/TorNetwork.swift').read_text()
        self.assertLess(native.index('if !mode.usesTor'), native.index('[TorUnavailableBlocker.self'))

    def test_resource_transform_runs_before_framework_signing(self):
        source = (ROOT / 'scripts/apply-overlay.py').read_text()
        self.assertIn('Scripts/CompactGeckoResources.py', source)
        self.assertIn('--enable-proxy-bypass-protection', source)
        self.assertIn('--disable-proxy-direct-failover', source)
