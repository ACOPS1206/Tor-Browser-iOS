import Foundation
import Network

/// URLProtocol callbacks may run outside MainActor. Read gate state under a lock.
nonisolated final class TorRequestGate: @unchecked Sendable {
    static let shared = TorRequestGate()
    private let lock = NSLock()
    private var permitted = false
    func allowsRequests() -> Bool {
        lock.lock(); defer { lock.unlock() }
        return permitted
    }
    @discardableResult func update(permitted: Bool) -> Bool {
        lock.lock(); defer { lock.unlock() }
        let changed = self.permitted != permitted
        self.permitted = permitted
        return changed
    }
}

/// Every browser-owned Foundation request uses SOCKS, including redirects and downloads.
/// Tor unavailable -> request fails. There is no direct fallback or bypass domain.
enum TorNetwork {
    static func applyTorClientState(permitted: Bool) {
        let changed = TorRequestGate.shared.update(permitted: permitted)
        guard changed && !permitted else { return }
        let mode = TorPrivacy.activeRoutingMode
        guard mode != .never else { return }
        let sessions = mode == .always ? [session, privateSession, normalSession] : [privateSession]
        for session in sessions {
            session.getAllTasks { tasks in
                // A delayed enumeration must not cancel requests after resume.
                guard !TorRequestGate.shared.allowsRequests() else { return }
                for task in tasks { task.cancel() }
            }
        }
    }
    static let session = URLSession(configuration: configuration())
    static let privateSession = URLSession(configuration: configuration(isPrivate: true))
    static let normalSession = URLSession(configuration: configuration(isPrivate: false))
    static func session(isPrivate: Bool) -> URLSession {
        isPrivate ? privateSession : normalSession
    }
    static func configuration(isPrivate: Bool? = nil) -> URLSessionConfiguration {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.timeoutIntervalForRequest = 90
        configuration.timeoutIntervalForResource = 600
        let mode = TorPrivacy.activeRoutingMode
        // Shared stores have no trustworthy originating tab. In mixed mode,
        // suppress their auxiliary HTTP requests instead of guessing a route.
        if mode == .privateOnly && isPrivate == nil {
            configuration.protocolClasses = [TorUnknownContextBlocker.self]
            return configuration
        }
        if !mode.usesTor(isPrivate: isPrivate ?? true) {
            configuration.proxyConfigurations = []
            configuration.connectionProxyDictionary = [:]
            return configuration
        }
        let endpoint = NWEndpoint.hostPort(host: .ipv4(IPv4Address("127.0.0.1")!), port: NWEndpoint.Port(rawValue: 19050)!)
        var proxy = ProxyConfiguration(socksv5Proxy: endpoint)
        proxy.allowFailover = false
        proxy.excludedDomains = []
        configuration.proxyConfigurations = [proxy]
        configuration.protocolClasses = [TorUnavailableBlocker.self, TorLocalAddressBlocker.self]
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.timeoutIntervalForRequest = 90
        configuration.timeoutIntervalForResource = 600
        return configuration
    }
}

nonisolated final class TorUnavailableBlocker: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool {
        ["http", "https"].contains(request.url?.scheme?.lowercased() ?? "") &&
            !TorRequestGate.shared.allowsRequests()
    }
    override class func canInit(with task: URLSessionTask) -> Bool {
        guard let request = task.currentRequest ?? task.originalRequest else { return false }
        return canInit(with: request)
    }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet,
            userInfo: [NSLocalizedDescriptionKey: "Tor is unavailable or paused. Request blocked."]))
    }
    override func stopLoading() {}
}

nonisolated final class TorUnknownContextBlocker: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool {
        ["http", "https"].contains(request.url?.scheme?.lowercased() ?? "")
    }
    override class func canInit(with task: URLSessionTask) -> Bool {
        guard let request = task.currentRequest ?? task.originalRequest else { return false }
        return canInit(with: request)
    }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        client?.urlProtocol(self, didFailWithError: URLError(.unsupportedURL,
            userInfo: [NSLocalizedDescriptionKey: "Auxiliary request blocked: private/normal tab context is unknown."]))
    }
    override func stopLoading() {}
}

/// CFNetwork can bypass even an explicit SOCKS proxy for loopback destinations.
/// Reject local names and IP literals before CFNetwork can open a direct socket.
nonisolated final class TorLocalAddressBlocker: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool {
        guard let url = request.url,
              ["http", "https"].contains(url.scheme?.lowercased() ?? ""),
              let rawHost = url.host else { return false }
        let host = rawHost.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "[]."))
        let numericHost = host.split(separator: ".").allSatisfy { label in
            label.allSatisfy(\.isNumber) || (label.hasPrefix("0x") && label.dropFirst(2).allSatisfy(\.isHexDigit))
        }
        return host == "localhost" || host.hasSuffix(".localhost") || host.hasSuffix(".local")
            || !host.contains(".") || host.contains(":") || numericHost || IPv4Address(host) != nil || IPv6Address(host) != nil
    }
    override class func canInit(with task: URLSessionTask) -> Bool {
        guard let request = task.currentRequest ?? task.originalRequest else { return false }
        return canInit(with: request)
    }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        client?.urlProtocol(self, didFailWithError: URLError(.unsupportedURL,
            userInfo: [NSLocalizedDescriptionKey: "Local addresses and IP literals are blocked in Tor browsing."]))
    }
    override func stopLoading() {}
}


