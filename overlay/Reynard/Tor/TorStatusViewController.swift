import UIKit

final class TorStatusViewController: UIViewController {
    private let statusLabel = UILabel()
    private let progress = UIProgressView(progressViewStyle: .default)
    private let pauseButton = UIButton(type: .system)
    private let javaScriptButton = UIButton(type: .system)
    private let modeButton = UIButton(type: .system)
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
        javaScriptButton.titleLabel?.numberOfLines = 0
        javaScriptButton.addTarget(self, action: #selector(toggleJavaScript), for: .touchUpInside)
        modeButton.titleLabel?.numberOfLines = 0
        modeButton.addTarget(self, action: #selector(selectRoutingMode), for: .touchUpInside)
        let routingInfo = UILabel()
        routingInfo.numberOfLines = 0
        routingInfo.font = .preferredFont(forTextStyle: .footnote)
        routingInfo.text = "변경은 앱을 완전히 종료하고 다시 실행하면 적용됩니다. 일반/개인 탭을 혼용할 때 일반 탭은 실제 IP로 접속합니다. 탭 출처를 알 수 없는 검색 제안·아이콘·메타데이터·미리보기 요청은 차단되어 일부 보조 기능이 제한됩니다. Tor 미사용은 사생활 보호 탭에서도 IP를 숨기지 않습니다.\nChanges require restart. Mixed mode blocks auxiliary requests without a reliable tab context; direct tabs expose your IP."
        let stack = UIStackView(arrangedSubviews: [modeButton, routingInfo, statusLabel, progress, pauseButton, circuit, javaScriptButton, info])
        stack.axis = .vertical
        stack.spacing = 24
        stack.translatesAutoresizingMaskIntoConstraints = false
        let scroll = UIScrollView()
        scroll.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(scroll)
        scroll.addSubview(stack)
        NSLayoutConstraint.activate([
            scroll.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor),
            scroll.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor),
            scroll.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            scroll.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
            stack.leadingAnchor.constraint(equalTo: scroll.contentLayoutGuide.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: scroll.contentLayoutGuide.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: scroll.contentLayoutGuide.topAnchor, constant: 24),
            stack.bottomAnchor.constraint(equalTo: scroll.contentLayoutGuide.bottomAnchor, constant: -24),
            stack.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor, constant: -48)
        ])
        NotificationCenter.default.addObserver(self, selector: #selector(refresh), name: Notification.Name("TBIO.TorStatus"), object: nil)
        refresh()
    }
    deinit { NotificationCenter.default.removeObserver(self) }
    @objc private func refresh() {
        let tor = TBIOTorService.shared
        statusLabel.text = tor.statusText
        modeButton.setTitle("다음 실행: " + TorPrivacy.routingMode.title + "\n현재: " + TorPrivacy.activeRoutingMode.title, for: .normal)
        progress.progress = Float(tor.bootstrapProgress) / 100
        pauseButton.setTitle(tor.paused ? "Tor 다시 연결 / Resume" : "Tor 일시 정지 / Pause", for: .normal)
        pauseButton.isEnabled = tor.ready || tor.paused
        javaScriptButton.setTitle(TorPrivacy.disableJavaScript
            ? "다음 실행: JavaScript 차단 / JS blocked on restart"
            : "다음 실행: JavaScript 허용 / JS allowed on restart", for: .normal)
    }
    @objc private func togglePause() {
        let tor = TBIOTorService.shared
        if tor.paused { tor.start() } else { tor.pause() }
    }
    @objc private func newCircuit() { TBIOTorService.shared.requestNewCircuit() }
    @objc private func toggleJavaScript() {
        TorPrivacy.disableJavaScript.toggle()
        refresh()
    }
    @objc private func selectRoutingMode() {
        let menu = UIAlertController(title: "Tor 사용 범위 / Routing", message: "다음 앱 실행에 적용됩니다. / Applied on restart.", preferredStyle: .actionSheet)
        for mode in TorPrivacy.RoutingMode.allCases {
            menu.addAction(UIAlertAction(title: mode.title, style: .default) { [weak self] _ in
                guard let self else { return }
                if mode == .always {
                    TorPrivacy.routingMode = mode
                    self.refresh()
                    return
                }
                let warning = UIAlertController(title: "실제 IP 노출 / Direct connection",
                    message: mode == .never
                        ? "사생활 보호 탭을 포함한 모든 탭이 Tor 없이 접속합니다. 계속할까요?"
                        : "일반 탭은 Tor 없이 접속합니다. 출처 불명 보조 요청은 차단됩니다. 계속할까요?",
                    preferredStyle: .alert)
                warning.addAction(UIAlertAction(title: "취소 / Cancel", style: .cancel))
                warning.addAction(UIAlertAction(title: "적용 / Apply", style: .destructive) { [weak self] _ in
                    TorPrivacy.routingMode = mode
                    self?.refresh()
                })
                self.present(warning, animated: true)
            })
        }
        menu.addAction(UIAlertAction(title: "취소 / Cancel", style: .cancel))
        menu.popoverPresentationController?.sourceView = modeButton
        menu.popoverPresentationController?.sourceRect = modeButton.bounds
        present(menu, animated: true)
    }
}

extension SettingsViewController {
    @objc func showEmbeddedTor() {
        navigationController?.pushViewController(TorStatusViewController(), animated: true)
    }
}

