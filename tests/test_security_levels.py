import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile
ROOT = Path(__file__).resolve().parents[1]
def load(script):
    spec = importlib.util.spec_from_file_location(script, ROOT / 'scripts' / script)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
class SecurityLevelTests(unittest.TestCase):
    def test_offline_release_identity_files_and_tampering(self):
        bundle = load('bundle-noscript.py').bundle
        with tempfile.TemporaryDirectory() as d:
            package = ROOT / 'vendor/noscript/noscript.xpi'
            output = Path(d) / 'extension'
            manifest = bundle(package, output)
            self.assertEqual(manifest['incognito'], 'spanning')
            self.assertTrue((output / 'ui/popup.html').is_file())
            self.assertTrue((output / 'LICENSE').is_file())
            with zipfile.ZipFile(package) as archive:
                for name in archive.namelist():
                    if not name.endswith('/'):
                        self.assertEqual((output / name).read_bytes(), archive.read(name))
            tampered = Path(d) / 'tampered.xpi'
            tampered.write_bytes(package.read_bytes() + b'bad')
            with self.assertRaises(RuntimeError): bundle(tampered, output)
    def test_real_noscript_policy_classes_and_bootstrap_model(self):
        for script in ['security-level.mjs', 'noscript-startup.mjs']:
            subprocess.run(['node', str(ROOT / 'tests' / script)], check=True)
    @unittest.skipUnless(shutil.which('c++'), 'C++ compiler unavailable')
    def test_precision_clamp_compiles_and_never_increases_driver_values(self):
        # Compile the exact block to check types/invariants, not GL/Gecko runtime.
        source = (ROOT / 'scripts/security-policy.py').read_text()
        begin = source.index('      if (webgl->mResistFingerprinting)')
        end = source.index('      out->shaderPrecisions->insert', begin)
        block = source[begin:end]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            names=['LOW_FLOAT','MEDIUM_FLOAT','HIGH_FLOAT','LOW_INT','MEDIUM_INT','HIGH_INT']
            defines='\n'.join(f'constexpr int LOCAL_GL_{name} = {i};' for i,name in enumerate(names))
            (p/'test.cpp').write_text('#include <algorithm>\n#include <cstdint>\n#include <cassert>\n'+defines+'''
struct Format { uint8_t rangeMin, rangeMax, precision; };
struct WebGL { bool mResistFingerprinting; bool IsWebGL2() const { return true; } };
Format normalize(Format spf, int precisionType, WebGL* webgl) {
'''+block+'''return spf; }
int main() { WebGL yes{true}, no{false};
for(int t=0;t<6;t++) for(int n=0;n<256;n++) {
  Format input{uint8_t(n),uint8_t(n),uint8_t(n)};
  auto out=normalize(input,t,&yes);
  assert(out.rangeMin<=n && out.rangeMax<=n && out.precision<=n);
  assert(normalize(input,t,&no).precision==n);
}
}
''')
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)
    def test_engine_patch_and_readback_protection_are_not_replaced(self):
        source=(ROOT/'scripts/security-policy.py').read_text()
        self.assertIn('RFPTarget::WebGLRenderCapability',source)
        self.assertNotIn('void ClientWebGLContext::ReadPixels',source)
        self.assertNotIn('Math.random',source)
        prefs=json.loads((ROOT/'privacy-prefs.json').read_text())
        self.assertFalse(prefs['webgl.enable-debug-renderer-info'])
        self.assertFalse(prefs['webgl.enable-renderer-query'])
        self.assertIn("'scripts/security-policy.py'",(ROOT/'.github/workflows/build-ipa.yml').read_text())
    @unittest.skipUnless(os.environ.get('SECURITY_GECKO_SOURCE'), 'Supply patched Gecko 157 review source')
    def test_patch_against_actual_gecko_source(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'engine'
            shutil.copytree(os.environ['SECURITY_GECKO_SOURCE'],target)
            policy=load('security-policy.py')
            policy.apply(target,load('apply-overlay.py').replace)
            for file in ['toolkit/components/extensions/ExtensionParent.sys.mjs',
                         'mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs']:
                subprocess.run(['node','--check',str(target/file)],check=True)
            with self.assertRaises(RuntimeError): policy.apply(target,load('apply-overlay.py').replace)
