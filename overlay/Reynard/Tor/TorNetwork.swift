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
        configuration.urlCache = nil
        configuration.httpCookieStorage = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.timeoutIntervalForRequest = 90
        configuration.timeoutIntervalForResource = 600
        return configuration
    }
}
