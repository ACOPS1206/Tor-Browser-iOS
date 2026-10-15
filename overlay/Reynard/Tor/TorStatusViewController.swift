import UIKit

/// Shared rows used directly in Settings' Privacy section and on the status page.
final class TorPrivacySettingsSection {
    let rowCount = 5
    var didChange: (() -> Void)?

    func cell(at row: Int, from controller: UIViewController) -> UITableViewCell {
        let cell = UITableViewCell(style: .default, reuseIdentifier: nil)
        switch row {
        case 0, 1, 2:
            let toggle = UISwitch()
            toggle.tag = row
            let titles = ["Use Tor", "Private Tabs Only", "Block JavaScript"]
            cell.textLabel?.text = titles[row]
            cell.textLabel?.numberOfLines = 0
            toggle.accessibilityLabel = titles[row]
            let mode = TorPrivacy.routingMode
            toggle.isOn = row == 0 ? mode != .never : row == 1 ? mode == .privateOnly : TorPrivacy.disableJavaScript
            toggle.isEnabled = row != 1 || mode != .never
            toggle.addTarget(self, action: #selector(changed(_:)), for: .valueChanged)
            cell.accessoryView = toggle
            cell.selectionStyle = .none
        case 3:
            cell.textLabel?.text = "Security Level: \(TorPrivacy.securityLevel.title)"
            cell.accessoryType = .disclosureIndicator
        default:
            cell.textLabel?.text = "Tor Connection & Relays"
            cell.accessoryType = .disclosureIndicator
        }
        // Keep presentation ownership weak; Settings and the status page retain this section.
        presentingController = controller
        return cell
    }

    private weak var presentingController: UIViewController?

    func selectRow(at row: Int, from controller: UIViewController) {
        if row == 3 {
            let alert = UIAlertController(title: "Security Level",
                message: "Standard: compatible defaults. Safer: HTTPS-only scripts; media and WebGL need permission. Safest: scripts blocked by default; fonts, MathML and SVG restricted. Block JavaScript overrides all site exceptions. Changes reset NoScript exceptions and apply after fully closing and reopening the app.", preferredStyle: .alert)
            for level in TorPrivacy.SecurityLevel.allCases {
                alert.addAction(UIAlertAction(title: level.title, style: .default) { [weak self] _ in
                    TorPrivacy.securityLevel = level
                    self?.didChange?()
                })
            }
            alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
            controller.present(alert, animated: true)
            return
        }
        guard row == 4 else { return }
        controller.navigationController?.pushViewController(TorStatusViewController(), animated: true)
    }

    @objc private func changed(_ toggle: UISwitch) {
        if toggle.tag == 2 {
            TorPrivacy.disableJavaScript = toggle.isOn
            didChange?()
            return
        }
        let current = TorPrivacy.routingMode
        let proposed: TorPrivacy.RoutingMode = toggle.tag == 0
            ? (toggle.isOn ? .always : .never)
            : (toggle.isOn ? .privateOnly : .always)
        // Restore the saved value while the user decides. Cancel/dismiss never saves a change.
        toggle.setOn(toggle.tag == 0 ? current != .never : current == .privateOnly, animated: true)
        guard proposed != current else { return }
        if proposed == .always {
            TorPrivacy.routingMode = proposed
            didChange?()
            return
        }
        let alert = UIAlertController(title: "Direct Connection",
            message: proposed == .never
                ? "All tabs, including private tabs, will connect without Tor and may expose your real IP address. This applies after restarting the app."
                : "Regular tabs will connect without Tor and may expose your real IP address. Only private tabs will use Tor. This applies after restarting the app.",
            preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        alert.addAction(UIAlertAction(title: "Apply", style: .destructive) { [weak self] _ in
            TorPrivacy.routingMode = proposed
            self?.didChange?()
        })
        presentingController?.present(alert, animated: true)
    }

    static let footer = "Use Tor for all tabs, or enable Private Tabs Only to use Tor only in private tabs. Turn Use Tor off for direct connections in all tabs. Security level and JavaScript changes require fully closing and reopening the app. In private-only mode, auxiliary requests with no reliable tab context are blocked."
}

final class TorStatusViewController: UITableViewController {
    private let privacy = TorPrivacySettingsSection()
    private var relayTimer: Timer?

    init() { super.init(style: .insetGrouped) }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Tor Connection & Relays"
        privacy.didChange = { [weak self] in self?.tableView.reloadData() }
        NotificationCenter.default.addObserver(self, selector: #selector(refresh),
            name: Notification.Name("TBIO.TorStatus"), object: nil)
    }
    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        TBIOTorService.shared.refreshRelayInfo()
        relayTimer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { _ in
            // All Tor UI and service access is on the main actor.
            DispatchQueue.main.async { TBIOTorService.shared.refreshRelayInfo() }
        }
    }
    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        relayTimer?.invalidate()
        relayTimer = nil
    }
    deinit { NotificationCenter.default.removeObserver(self) }
    @objc private func refresh() { tableView.reloadData() }
    override func numberOfSections(in tableView: UITableView) -> Int { 4 }
    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        [privacy.rowCount - 1, 3, 2, 1][section]
    }
    override func tableView(_ tableView: UITableView, titleForHeaderInSection section: Int) -> String? {
        ["Privacy", "Connection", "Built Circuits", "About"][section]
    }
    override func tableView(_ tableView: UITableView, titleForFooterInSection section: Int) -> String? {
        switch section {
        case 0: return TorPrivacySettingsSection.footer
        case 1: return "Requesting a new circuit does not clear cookies, tabs or existing connections. Tor may rate-limit requests."
        case 2: return "Tor can use several circuits at once. These are built general-purpose circuits, including unused ones; they are not attributed to the current tab. Onion-service circuits do not have an exit relay and are excluded. Relay details come from the local Tor controller, without an external lookup service."
        default: return nil
        }
    }
    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let tor = TBIOTorService.shared
        if indexPath.section == 0 { return privacy.cell(at: indexPath.row, from: self) }
        let cell = UITableViewCell(style: .subtitle, reuseIdentifier: nil)
        cell.textLabel?.numberOfLines = 0
        cell.detailTextLabel?.numberOfLines = 0
        cell.selectionStyle = .none
        switch (indexPath.section, indexPath.row) {
        case (1, 0):
            cell.textLabel?.text = tor.statusText
            cell.detailTextLabel?.text = "Current routing: \(TorPrivacy.activeRoutingMode.title)\nNext launch: \(TorPrivacy.routingMode.title)\nBootstrap: \(tor.bootstrapProgress)%"
        case (1, 1):
            cell.textLabel?.text = tor.paused ? "Resume Tor" : "Pause Tor"
            cell.textLabel?.textColor = tor.ready || tor.paused ? .systemBlue : .secondaryLabel
            cell.selectionStyle = tor.ready || tor.paused ? .default : .none
        case (1, 2):
            cell.textLabel?.text = "Request New Circuit"
            cell.textLabel?.textColor = tor.ready ? .systemBlue : .secondaryLabel
            cell.selectionStyle = tor.ready ? .default : .none
        case (2, 0):
            cell.textLabel?.text = tor.relayInfoText
            cell.textLabel?.font = .monospacedSystemFont(ofSize: 13, weight: .regular)
        case (2, 1):
            cell.textLabel?.text = "Refresh Relays"
            cell.textLabel?.textColor = tor.ready ? .systemBlue : .secondaryLabel
            cell.selectionStyle = tor.ready ? .default : .none
        default:
            cell.textLabel?.text = "Gecko + Embedded Tor"
            cell.detailTextLabel?.text = "Experimental, unofficial browser. Full Tor Browser protections have not been ported."
        }
        return cell
    }
    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)
        let tor = TBIOTorService.shared
        switch (indexPath.section, indexPath.row) {
        case (1, 1):
            if tor.paused { tor.start() } else if tor.ready { tor.pause() }
        case (1, 2): if tor.ready { tor.requestNewCircuit() }
        case (2, 1): if tor.ready { tor.refreshRelayInfo() }
        default: break
        }
    }
}

extension SettingsViewController {
    @objc func showEmbeddedTor() {
        navigationController?.pushViewController(TorStatusViewController(), animated: true)
    }
}
