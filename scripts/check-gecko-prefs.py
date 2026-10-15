#!/usr/bin/env python3
"""Reject typos/removed prefs instead of silently creating inert Gecko prefs."""
import ast
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
engine = Path(sys.argv[1])
static = (engine / 'modules/libpref/init/StaticPrefList.yaml').read_text()
dynamic = (engine / 'modules/libpref/init/all.js').read_text()
names = set(re.findall(r'^-\s*name:\s*(\S+)', static, re.M))
names.update(re.findall(r'\bpref\(\s*"([^"]+)"', dynamic))
# Some JS-only prefs are declared/consumed outside the central default lists.
additional = [engine / 'browser/app/profile/firefox.js',
              engine / 'toolkit/components/telemetry/app/TelemetryControllerBase.sys.mjs',
              engine / 'toolkit/components/telemetry/app/TelemetryUtils.sys.mjs',
              engine / 'toolkit/components/telemetry/Telemetry.cpp',
              engine / 'toolkit/components/extensions/AddonManager.sys.mjs']
sources = '\n'.join(p.read_text() for p in additional if p.exists())
prefs = json.loads((root / 'privacy-prefs.json').read_text())
# Security-level preferences are also verified against this exact Gecko build.
level_source = (root / 'overlay/Gecko/TBIOSecurityPolicy.sys.mjs').read_text()
for key in re.findall(r'"((?:mathml|svg)\.[^"]+)"\s*:', level_source):
    prefs[key] = None
prefs['javascript.enabled'] = None
missing = [key for key in prefs if key not in names and f'"{key}"' not in sources]
if missing:
    raise SystemExit('Unverified Gecko policy prefs: ' + ', '.join(missing))
manifest = ast.parse((engine / 'mobile/shared/modules/geckoview/moz.build').read_text())
for statement in manifest.body:
    if isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name) and statement.target.id == 'EXTRA_JS_MODULES':
        names = ast.literal_eval(statement.value)
        if names != sorted(names, key=str.lower):
            raise SystemExit('Gecko EXTRA_JS_MODULES must be alphabetically sorted')
print(f'Validated {len(prefs)} policy preference names against the compiled Gecko source')
