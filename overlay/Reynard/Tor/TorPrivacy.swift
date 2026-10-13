import Foundation
import Darwin

enum TorPrivacy {
    enum RoutingMode: String, CaseIterable {
        case always, privateOnly, never
        var title: String {
            switch self {
            case .always: return "All Tabs"
            case .privateOnly: return "Private Tabs Only"
            case .never: return "Tor Off"
            }
        }
        func usesTor(isPrivate: Bool) -> Bool {
            self == .always || (self == .privateOnly && isPrivate)
        }
    }
    static var routingMode: RoutingMode {
        get { RoutingMode(rawValue: UserDefaults.standard.string(forKey: "TBIO.RoutingMode") ?? "") ?? .always }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: "TBIO.RoutingMode") }
    }
    // Immutable for this process: do not reroute live tabs/downloads after a UI change.
    static let activeRoutingMode = routingMode
    static var disableJavaScript: Bool {
        get { UserDefaults.standard.bool(forKey: "TBIO.DisableJavaScript") }
        set { UserDefaults.standard.set(newValue, forKey: "TBIO.DisableJavaScript") }
    }

    static func prepareBeforeGecko() {
        // Keep the browser interface in English, independent of the device language.
        UserDefaults.standard.set(["en"], forKey: "AppleLanguages")
        // Read once at process startup. The engine locks this choice for the run.
        setenv("TBIO_DISABLE_JAVASCRIPT", disableJavaScript ? "1" : "0", 1)
        setenv("TBIO_ROUTING_MODE", activeRoutingMode.rawValue, 1)
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


