import Foundation
import Network

/// Every browser-owned Foundation request uses SOCKS, including redirects and downloads.
/// Tor unavailable -> request fails. There is no direct fallback or bypass domain.
enum TorNetwork {
    static let session = URLSession(configuration: configuration())
    static func configuration() -> URLSessionConfiguration {
        let configuration = URLSessionConfiguration.ephemeral
        let endpoint = NWEndpoint.hostPort(host: .ipv4(IPv4Address("127.0.0.1")!), port: NWEndpoint.Port(rawValue: 19050)!)
        var proxy = ProxyConfiguration(socksv5Proxy: endpoint)
        proxy.allowFailover = false
        proxy.excludedDomains = []
        configuration.proxyConfigurations = [proxy]
        configuration.protocolClasses = [TorLocalAddressBlocker.self]
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.timeoutIntervalForRequest = 90
        configuration.timeoutIntervalForResource = 600
        return configuration
    }
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
