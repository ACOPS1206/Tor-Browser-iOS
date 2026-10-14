// The real browser types are compiled by the full build. These stubs allow the
// Tor UI files to be type-checked against UIKit before spending hours on Gecko.
import UIKit
enum TabMode { case regular, `private` }
final class StubSession { var isPrivateMode = false }
final class StubTab { let session = StubSession() }
final class StubTabManager {
    var selectedTab: StubTab?
    var selectedTabMode: TabMode = .regular
}
final class BrowserViewController: UIViewController {
    let tabManager = StubTabManager()
}
final class SettingsViewController: UIViewController {}

