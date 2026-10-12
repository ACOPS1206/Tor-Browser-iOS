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
    @objc private func updateTorStatusButton() {
        guard let button = view.viewWithTag(19050) as? UIButton else { return }
        button.setTitle(TBIOTorService.shared.statusText, for: .normal)
        button.setTitleColor(TBIOTorService.shared.ready ? .systemGreen : .systemOrange, for: .normal)
        view.bringSubviewToFront(button)
    }
    @objc private func openTorStatus() {
        let controller = TorStatusViewController()
        controller.navigationItem.leftBarButtonItem = UIBarButtonItem(barButtonSystemItem: .done, target: self, action: #selector(closeTorStatus))
        present(UINavigationController(rootViewController: controller), animated: true)
    }
    @objc private func closeTorStatus() { dismiss(animated: true) }
}
