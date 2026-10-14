import UIKit

extension BrowserViewController {
    func installTorStatusButton() {
        let button = UIButton(type: .system)
        button.tag = 19050
        button.titleLabel?.font = .preferredFont(forTextStyle: .caption1)
        button.backgroundColor = .secondarySystemBackground
        button.layer.cornerRadius = 12
        button.contentEdgeInsets = UIEdgeInsets(top: 6, left: 12, bottom: 6, right: 12)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.addTarget(self, action: #selector(openTorStatus), for: .touchUpInside)
        view.addSubview(button)
        NSLayoutConstraint.activate([
            button.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -12),
            button.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 4),
            button.widthAnchor.constraint(lessThanOrEqualTo: view.widthAnchor, multiplier: 0.7)
        ])
        NotificationCenter.default.addObserver(self, selector: #selector(updateTorStatusButton), name: Notification.Name("TBIO.TorStatus"), object: nil)
        updateTorStatusButton()
    }
    @objc func updateTorStatusButton() {
        let permitted = TBIOTorService.shared.ready && !TBIOTorService.shared.paused
        TorNetwork.applyTorClientState(permitted: permitted)
        TorPrivacy.engineGatePublisher?(permitted)
        guard let button = view.viewWithTag(19050) as? UIButton else { return }
        guard let session = tabManager.selectedTab?.session else {
            button.setTitle("No Tab · Tor Client: " + TBIOTorService.shared.statusText, for: .normal)
            button.setTitleColor(.secondaryLabel, for: .normal)
            return
        }
        let tab = tabManager.selectedTabMode == .private ? "Private Tab" : "Normal Tab"
        let usesTor = TorPrivacy.activeRoutingMode.usesTor(isPrivate: session.isPrivateMode)
        // This is the selected session policy plus client state, not a
        // measurement of the site's IP or a per-channel route assertion.
        let state = usesTor ? "Tor Policy · Client: " + TBIOTorService.shared.statusText : "Direct Connection Policy"
        button.setTitle(tab + " · " + state, for: .normal)
        button.accessibilityHint = "Routing policy and Tor client state. This does not verify the route of a request."
        button.setTitleColor(usesTor ? .systemOrange : .secondaryLabel, for: .normal)
        view.bringSubviewToFront(button)
    }
    @objc private func openTorStatus() {
        let controller = TorStatusViewController()
        controller.navigationItem.leftBarButtonItem = UIBarButtonItem(barButtonSystemItem: .done, target: self, action: #selector(closeTorStatus))
        present(UINavigationController(rootViewController: controller), animated: true)
    }
    @objc private func closeTorStatus() { dismiss(animated: true) }
}



