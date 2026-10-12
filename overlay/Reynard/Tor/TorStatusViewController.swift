import UIKit

final class TorStatusViewController: UIViewController {
    private let statusLabel = UILabel()
    private let progress = UIProgressView(progressViewStyle: .default)
    private let pauseButton = UIButton(type: .system)
    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Tor"
        view.backgroundColor = .systemBackground
        statusLabel.font = .preferredFont(forTextStyle: .title2)
        statusLabel.numberOfLines = 0
        let info = UILabel()
        info.numberOfLines = 0
        info.font = .preferredFont(forTextStyle: .body)
        info.text = "Gecko + Embedded Tor\n\n실험용 비공식 브라우저입니다. Tor Browser의 전체 보호 패치는 아직 이식되지 않았습니다.\n\nExperimental, unofficial browser. Full Tor Browser patches are not ported.\n\n새 회로 요청은 쿠키·탭·기존 연결을 지우지 않습니다. / New circuit does not clear browser identity."
        pauseButton.addTarget(self, action: #selector(togglePause), for: .touchUpInside)
        let circuit = UIButton(type: .system)
        circuit.setTitle("새 회로 요청 / Request new circuit", for: .normal)
        circuit.addTarget(self, action: #selector(newCircuit), for: .touchUpInside)
        let stack = UIStackView(arrangedSubviews: [statusLabel, progress, pauseButton, circuit, info])
        stack.axis = .vertical
        stack.spacing = 24
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 24)
        ])
        NotificationCenter.default.addObserver(self, selector: #selector(refresh), name: Notification.Name("TBIO.TorStatus"), object: nil)
        refresh()
    }
    deinit { NotificationCenter.default.removeObserver(self) }
    @objc private func refresh() {
        let tor = TBIOTorService.shared
        statusLabel.text = tor.statusText
        progress.progress = Float(tor.bootstrapProgress) / 100
        pauseButton.setTitle(tor.paused ? "Tor 다시 연결 / Resume" : "Tor 일시 정지 / Pause", for: .normal)
        pauseButton.isEnabled = tor.ready || tor.paused
    }
    @objc private func togglePause() {
        let tor = TBIOTorService.shared
        if tor.paused { tor.start() } else { tor.pause() }
    }
    @objc private func newCircuit() { TBIOTorService.shared.requestNewCircuit() }
}

extension SettingsViewController {
    @objc func showEmbeddedTor() {
        navigationController?.pushViewController(TorStatusViewController(), animated: true)
    }
}
