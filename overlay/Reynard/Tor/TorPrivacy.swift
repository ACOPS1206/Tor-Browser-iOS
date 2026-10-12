import Foundation
import Darwin

enum TorPrivacy {
    static var disableJavaScript: Bool {
        get { UserDefaults.standard.bool(forKey: "TBIO.DisableJavaScript") }
        set { UserDefaults.standard.set(newValue, forKey: "TBIO.DisableJavaScript") }
    }

    static func prepareBeforeGecko() {
        // Read once at process startup. The engine locks this choice for the run.
        setenv("TBIO_DISABLE_JAVASCRIPT", disableJavaScript ? "1" : "0", 1)
        // Remove legacy automatic browsing records, preserving bookmarks,
        // explicit downloads, preferences, JIT pairing and Tor guard state.
        guard let base = FileManager.default.urls(for: .applicationSupportDirectory,
            in: .userDomainMask).first else { return }
        for name in ["History", "TabManagement", "TabSessions", "Favicons",
                     "SiteMetadata", "SitePermissions"] {
            try? FileManager.default.removeItem(at: base
                .appendingPathComponent("AppData", isDirectory: true)
                .appendingPathComponent(name, isDirectory: true))
        }
    }
}
