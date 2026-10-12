#!/usr/bin/env python3
"""Apply the reviewed Tor overlay to the pinned upstream; fail on changed anchors."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace(path, before, after, count=1):
    text = path.read_text()
    actual = text.count(before)
    if actual != count:
        raise RuntimeError(f'{path}: expected {count} anchors, found {actual}: {before!r}')
    path.write_text(text.replace(before, after))

def apply(target):
    browser = target / 'browser'
    app = browser / 'Reynard'
    prefs = json.loads((ROOT / 'privacy-prefs.json').read_text())
    shutil.copytree(ROOT / 'overlay/Reynard/Tor', app / 'Tor', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'Podfile', browser / 'Podfile')
    replace(app / 'Bridging/Reynard-Bridging-Header.h', '#import "ExtensionBridge.h"', '#import "TorService.h"\n#import "ExtensionBridge.h"')
    replace(app / 'main.swift', 'GeckoRuntime.main(argc:', 'TBIOTorService.shared.start()\n\nGeckoRuntime.main(argc:')
    replace(browser / 'Configuration/Reynard.xcconfig', 'APP_DISPLAY_NAME = Reynard', 'APP_DISPLAY_NAME = Onion Reynard')
    replace(browser / 'Configuration/Reynard.xcconfig', 'IPHONEOS_DEPLOYMENT_TARGET = 13.0', 'IPHONEOS_DEPLOYMENT_TARGET = 17.4')
    replace(browser / 'Configuration/Reynard.xcconfig', 'CURRENT_VERSION = 0.17.0', 'CURRENT_VERSION = 0.1.0')
    pbx = browser / 'Reynard.xcodeproj/project.pbxproj'
    text = pbx.read_text().replace('com.minh-ton.Reynard', 'com.acops1206.TorBrowserIOS')
    pbx.write_text(text)
    replace(app / 'Client/Startup/BrowserUpdates.swift', '        fetchUpdates()', '        // Fork updates must never install the upstream non-Tor app. Disabled.')
    replace(app / 'Client/SessionManagement/SessionManager.swift', 'isPrivateMode: isPrivate,', 'isPrivateMode: true, // Always use private Gecko storage.')
    settings = app / 'Client/Interface/Library/Settings/SettingsViewController.swift'
    replace(settings, '        observeJITMode()', '        navigationItem.rightBarButtonItem = UIBarButtonItem(title: "Tor", style: .plain, target: self, action: #selector(showEmbeddedTor))\n        observeJITMode()')
    # A permanent visible status button, including while connecting or paused.
    vc = app / 'Client/Interface/BrowserViewController.swift'
    replace(vc, '        configureBrowserInterface()', '        configureBrowserInterface()\n        installTorStatusButton()')
    # Route native downloads, icons and previews through SOCKS. JIT's local developer
    # connection and its explicitly invoked DDI setup remain outside browser traffic.
    for relative in ['Client/Stores/FaviconStore.swift', 'Client/Stores/SiteMetadataStore.swift', 'Client/Stores/DownloadStore.swift']:
        replace(app / relative, 'URLSessionConfiguration.default', 'TorNetwork.configuration()')
    for relative in ['Client/Interface/ContextMenu/ImagePreview/ImagePreviewLoader.swift', 'Client/SessionManagement/Media/SystemMediaSession.swift']:
        replace(app / relative, 'URLSession.shared', 'TorNetwork.session')
    replace(app / 'Client/Search/SearchCompletion.swift', 'urlSession: URLSession = .shared', 'urlSession: URLSession = TorNetwork.session')
    replace(app / 'Client/Interface/Library/Settings/Sections/Updates/UpdatesSettingsSection.swift', 'URLSession(configuration: .default)', 'URLSession(configuration: TorNetwork.configuration())')
    # Persisted bridge/engine settings cannot change immutable Tor networking defaults.
    runtime = browser / 'GeckoView/Runtime/GeckoRuntime.swift'
    keys = ',\n            '.join(json.dumps(key) for key in prefs)
    replace(runtime, 'message: preferences', 'message: preferences.filter { !Set<String>([\n            ' + keys + '\n        ]).contains($0.key) }')
    # Bake proxy prefs into Gecko before startup networking, not after first tab creation.
    engine = target / 'engine/firefox'
    if (engine / 'mobile/ios/app/mobile.js').exists():
        defaults = engine / 'mobile/ios/app/mobile.js'
        with defaults.open('a') as stream:
            stream.write('\n// Embedded Tor immutable defaults.\n')
            for key, value in prefs.items():
                stream.write(f'pref({json.dumps(key)}, {json.dumps(value)});\n')
        startup = engine / 'mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs'
        locks = '\n'.join('        Services.prefs.lockPref(' + json.dumps(key) + ');' for key in prefs)
        replace(startup, '      case "profile-after-change": {', '      case "profile-after-change": {\n' + locks)
    else:
        raise RuntimeError('Gecko source must be initialized and patched before overlay')
    build = target / 'tools/release/build-app.sh'
    replace(build, '-project "$PROJECT_PATH"', '-workspace "$ROOT_DIR/browser/Reynard.xcworkspace"')
    replace(build, '-xcconfig "$BUILD_XCCONFIG_PATH"', 'CURRENT_BUILD="$BUILD_SHA"')
    # Do not depend on a compatibility dylib being present with newer SDKs.
    replace(build, '\txcrun bitcode_strip "$SWIFT_CONCURRENCY_PATH" -r -o "$SWIFT_CONCURRENCY_PATH"\n\t/usr/bin/codesign --force --sign - --verbose "$SWIFT_CONCURRENCY_PATH"', '\tif [ -f "$SWIFT_CONCURRENCY_PATH" ]; then\n\t\txcrun bitcode_strip "$SWIFT_CONCURRENCY_PATH" -r -o "$SWIFT_CONCURRENCY_PATH"\n\t\t/usr/bin/codesign --force --sign - --verbose "$SWIFT_CONCURRENCY_PATH"\n\tfi')
    packaging = target / 'tools/release/create-ipa.sh'
    text = packaging.read_text().replace('com.minh-ton.Reynard', 'com.acops1206.TorBrowserIOS').replace('OUTPUT_NAME="Reynard.ipa"', 'OUTPUT_NAME="Tor-Browser-iOS.ipa"')
    packaging.write_text(text)
    print('Tor overlay applied successfully')

if __name__ == '__main__':
    apply(Path(sys.argv[1]).resolve())
