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

def replace_swift_body(path, signature, body):
    """Replace a reviewed Swift method body; reject missing/duplicate signatures."""
    text = path.read_text()
    if text.count(signature) != 1:
        raise RuntimeError(f'{path}: changed Swift method anchor: {signature}')
    start = text.index('{', text.index(signature))
    depth = 1
    end = start + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    path.write_text(text[:start + 1] + '\n' + body + '\n    ' + text[end - 1:])

def apply_memory_storage(app):
    stores = app / 'Client/Stores'
    for name in ['HistoryStore', 'TabManagementStore', 'SitePermissionStore', 'FaviconStore']:
        path = stores / (name + '.swift')
        replace(path, 'sqlite3_open_v2(storage.databaseURL.path,', 'sqlite3_open_v2(":memory:",')
        replace_swift_body(path, 'private func prepareStorageLocked()', '        // Browsing records live only in memory.')
    tabs = stores / 'TabManagementStore.swift'
    replace(tabs, '    private var database: OpaquePointer?', '    private var thumbnails: [UUID: UIImage] = [:]\n    private var database: OpaquePointer?')
    replace_swift_body(tabs, 'func persistThumbnail(_ image: UIImage?, for tabID: UUID)', '        stateQueue.async { self.thumbnails[tabID] = image }')
    replace_swift_body(tabs, 'private func loadThumbnailLocked(for tabID: UUID)', '        return thumbnails[tabID]')
    replace_swift_body(tabs, 'private func pruneThumbCacheLocked(validTabIDs: Set<UUID>)', '        thumbnails = thumbnails.filter { validTabIDs.contains($0.key) }')
    nav = stores / 'NavigationHistoryStore.swift'
    replace_swift_body(nav, 'private func createStorageDirectory()', '        // No on-disk navigation history.')
    replace_swift_body(nav, 'private func loadHistory(for tabID: UUID)', '''        if let history = historyCache[tabID] { return history }
        let history = StoredHistory(currentEntryID: nil, currentURL: nil,
            currentTitle: nil, currentThumbnailData: nil, backHistory: [],
            forwardHistory: [], usesStoredHistory: nil)
        historyCache[tabID] = history
        return history''')
    replace_swift_body(nav, 'private func saveHistory(_ history: StoredHistory, for tabID: UUID)', '        historyCache[tabID] = history')
    replace_swift_body(nav, 'private func persist(_ histories: [(UUID, StoredHistory)])', '        // Persistence intentionally disabled.')
    icons = stores / 'FaviconStore.swift'
    replace(icons, '    private var database: OpaquePointer?', '    private var memoryImages: [String: UIImage] = [:]\n    private var database: OpaquePointer?')
    replace(icons, '''        if !fileManager.fileExists(atPath: imageURL.path) {
            try? remoteImage.data.write(to: imageURL, options: .atomic)
        }''', '        memoryImages[imageKey] = remoteImage.image')
    replace_swift_body(icons, 'private func loadImageLocked(for imageKey: String)', '        return memoryImages[imageKey]')
    replace(icons, '    private func removeImageLocked(_ imageKey: String) {', '    private func removeImageLocked(_ imageKey: String) {\n        memoryImages.removeValue(forKey: imageKey)')
    metadata = stores / 'SiteMetadataStore.swift'
    replace(metadata, '    private var records:', '    private var memoryImages: [String: UIImage] = [:]\n    private var records:')
    replace_swift_body(metadata, 'private func prepareStorageLocked()', '        // Metadata remains in memory.')
    replace_swift_body(metadata, 'private func loadRecordsLocked()', '        records = [:]')
    replace_swift_body(metadata, 'private func saveRecordsLocked()', '        // No URL or OpenGraph metadata on disk.')
    replace(metadata, '''            if !fileManager.fileExists(atPath: imageURL.path) {
                try? remoteImage.data.write(to: imageURL, options: .atomic)
            }''', '            memoryImages[key] = remoteImage.image')
    replace_swift_body(metadata, 'private func loadImageLocked(for imageKey: String)', '        return memoryImages[imageKey]')
    replace_swift_body(metadata, 'private func removeUnreferencedImagesLocked(removedImageKeys: [String])', '''        let retained = Set(records.values.compactMap(\\.ogImageKey))
        for key in removedImageKeys where !retained.contains(key) {
            memoryImages.removeValue(forKey: key)
        }''')

def apply(target, browser_only=False):
    browser = target / 'browser'
    app = browser / 'Reynard'
    prefs = json.loads((ROOT / 'privacy-prefs.json').read_text())
    shutil.copytree(ROOT / 'overlay/Reynard/Tor', app / 'Tor', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'Podfile', browser / 'Podfile')
    replace(app / 'Bridging/Reynard-Bridging-Header.h', '#import "ExtensionBridge.h"', '#import "TorService.h"\n#import "ExtensionBridge.h"')
    replace(app / 'main.swift', 'GeckoRuntime.main(argc:', 'TorPrivacy.prepareBeforeGecko()\nTBIOTorService.shared.start()\n\nGeckoRuntime.main(argc:')
    # The fork requires iOS 17.4; remove upstream's obsolete iOS 13 path.
    main = app / 'main.swift'
    text = main.read_text()
    start = text.index('@available(iOS, introduced: 13.0, obsoleted: 14.0)')
    end = text.index('private func configureSandboxExtension()', start)
    main.write_text(text[:start] + text[end:])
    replace(main, """if #unavailable(iOS 14.0),
   getEntitlementValue("com.apple.private.security.no-sandbox") {
    configureUnsandboxedAppDataDirectories()
}

""", '')
    apply_memory_storage(app)
    # Upstream compatibility overrides run before Navigator's RFP checks.
    # Do not let per-site UA/appVersion/oscpu/buildID overrides defeat RFP.
    replace_swift_body(app / 'Client/SessionManagement/Settings/WebsiteMode/WebsiteModeSettingManager.swift',
        'func setting(for url: String, tabID: UUID?)', '        return .mobile // Uniform engine identity; no per-site spoofing.')
    replace_swift_body(app / 'Client/SessionManagement/Settings/Language/LanguageSettingManager.swift',
        'func setting()', '        return LanguageSetting(codes: ["en-US", "en"])')
    replace(browser / 'Configuration/Reynard.xcconfig', 'APP_DISPLAY_NAME = Reynard', 'APP_DISPLAY_NAME = Onion Reynard')
    replace(browser / 'Configuration/Reynard.xcconfig', 'IPHONEOS_DEPLOYMENT_TARGET = 13.0', 'IPHONEOS_DEPLOYMENT_TARGET = 17.4')
    replace(browser / 'Configuration/Reynard.xcconfig', 'CURRENT_VERSION = 0.17.0', 'CURRENT_VERSION = 0.1.0')
    pbx = browser / 'Reynard.xcodeproj/project.pbxproj'
    text = pbx.read_text().replace('com.minh-ton.Reynard', 'com.acops1206.TorBrowserIOS')
    pbx.write_text(text)
    replace(app / 'Client/Startup/BrowserUpdates.swift', '        fetchUpdates()', '        // Fork updates must never install the upstream non-Tor app. Disabled.')
    replace(app / 'Resources/Info.plist', '<string>reynard</string>', '<string>onionreynard</string>')
    replace(app / 'Resources/Info.plist', '<string>com.minh-ton.Reynard</string>', '<string>com.acops1206.TorBrowserIOS</string>')
    replace(app / 'SceneDelegate.swift', 'scheme == "reynard"', 'scheme == "onionreynard"')
    replace(browser / 'Extensions/OpenIn/OpenInViewController.swift', 'reynard://open', 'onionreynard://open')
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
    keys = ',\n            '.join(json.dumps(key) for key in [*prefs, 'javascript.enabled'])
    replace(runtime, 'message: preferences', 'message: preferences.filter { !Set<String>([\n            ' + keys + '\n        ]).contains($0.key) }')
    # External applications can connect outside Tor. Apply to every delegate,
    # including addon popups, subframes and redirects, before dispatching to UI.
    nav = browser / 'GeckoView/Delegates/NavigationDelegate.swift'
    replace(nav, 'private func loadRequestTarget', '''private func torAllowsNavigation(_ uri: String) -> Bool {
    guard let scheme = URL(string: uri)?.scheme?.lowercased() else { return false }
    return ["http", "https", "about", "blob", "data", "moz-extension"].contains(scheme)
}

private func loadRequestTarget''')
    replace(nav, '            let target = loadRequestTarget(', '            guard torAllowsNavigation(uri) else { return false }\n            let target = loadRequestTarget(')
    replace(nav, '            let isTopLevel =', '            guard torAllowsNavigation(request.uri) else { return true }\n            let isTopLevel =')
    replace(nav, '            return await delegate?.onPreNavigation', '            guard torAllowsNavigation(request.uri) else { return true }\n            return await delegate?.onPreNavigation')
    if not browser_only:
        apply_engine(target)
    build = target / 'tools/release/build-app.sh'
    replace(build, '-project "$PROJECT_PATH"', '-workspace "$ROOT_DIR/browser/Reynard.xcworkspace"')
    replace(build, '-xcconfig "$BUILD_XCCONFIG_PATH"', 'CURRENT_BUILD="$BUILD_SHA"')
    # Do not depend on a compatibility dylib being present with newer SDKs.
    replace(build, '\txcrun bitcode_strip "$SWIFT_CONCURRENCY_PATH" -r -o "$SWIFT_CONCURRENCY_PATH"\n\t/usr/bin/codesign --force --sign - --verbose "$SWIFT_CONCURRENCY_PATH"', '\tif [ -f "$SWIFT_CONCURRENCY_PATH" ]; then\n\t\txcrun bitcode_strip "$SWIFT_CONCURRENCY_PATH" -r -o "$SWIFT_CONCURRENCY_PATH"\n\t\t/usr/bin/codesign --force --sign - --verbose "$SWIFT_CONCURRENCY_PATH"\n\tfi')
    packaging = target / 'tools/release/create-ipa.sh'
    text = packaging.read_text().replace('com.minh-ton.Reynard', 'com.acops1206.TorBrowserIOS').replace('OUTPUT_NAME="Reynard.ipa"', 'OUTPUT_NAME="Tor-Browser-iOS.ipa"')
    packaging.write_text(text)
    print('Tor overlay applied successfully')

def apply_engine(target):
    prefs = json.loads((ROOT / 'privacy-prefs.json').read_text())
    # Bake proxy prefs into Gecko before startup networking, not after first tab creation.
    engine = target / 'engine/firefox'
    if (engine / 'mobile/ios/app/mobile.js').exists():
        defaults = engine / 'mobile/ios/app/mobile.js'
        with defaults.open('a') as stream:
            stream.write('\n// Embedded Tor immutable defaults.\n')
            for key, value in prefs.items():
                stream.write(f'pref({json.dumps(key)}, {json.dumps(value)}, locked);\n')
        modules = engine / 'mobile/shared/modules/geckoview'
        shutil.copy2(ROOT / 'overlay/Gecko/TBIOPrivacy.sys.mjs', modules / 'TBIOPrivacy.sys.mjs')
        # mozbuild enforces alphabetical ordering, not just Python syntax.
        replace(modules / 'moz.build', '    "Messaging.sys.mjs",',
            '    "Messaging.sys.mjs",\n    "TBIOPrivacy.sys.mjs",')
        startup = engine / 'mobile/shared/components/geckoview/GeckoViewStartup.sys.mjs'
        locks = '\n'.join('        Services.prefs.lockPref(' + json.dumps(key) + ');' for key in prefs)
        policy = '''
        const defaults = Services.prefs.getDefaultBranch("");
        defaults.setBoolPref("javascript.enabled", Services.env.get("TBIO_DISABLE_JAVASCRIPT") !== "1");
        Services.prefs.lockPref("javascript.enabled");
        ChromeUtils.importESModule("resource://gre/modules/TBIOPrivacy.sys.mjs").installTorChannelIsolation();'''
        replace(startup, '      case "profile-after-change": {', '      case "profile-after-change": {\n' + locks + policy)
    else:
        raise RuntimeError('Gecko source must be initialized and patched before overlay')

if __name__ == '__main__':
    target = Path(sys.argv[1]).resolve()
    phase = sys.argv[2] if len(sys.argv) > 2 else 'all'
    if phase == 'engine':
        apply_engine(target)
        print('Tor engine policy applied successfully')
    elif phase in ('all', 'browser'):
        apply(target, browser_only=phase == 'browser')
    else:
        raise SystemExit('Phase must be all, browser, or engine')
