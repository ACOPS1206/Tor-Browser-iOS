import Foundation

let phase = CommandLine.arguments.last ?? "routing"
let localHosts = ["local": "127.0.0.1", "short-ip": "127.1", "octal-ip": "0177.0.0.1", "hex-ip": "0x7f.0.0.1"]
let endpoint = localHosts[phase].map { "http://\($0):19051/" } ?? "http://tor-routing-test.invalid/"
let done = DispatchSemaphore(value: 0)
var passed = false
TorNetwork.session.dataTask(with: URL(string: endpoint)!) { data, response, error in
    if phase == "routing" {
        passed = error == nil && String(data: data ?? Data(), encoding: .utf8) == "tor-proxy-sentinel"
    } else {
        passed = error != nil && response == nil
    }
    done.signal()
}.resume()
if done.wait(timeout: .now() + 20) == .timedOut { exit(2) }
if !passed { exit(1) }
print("Native SOCKS check passed: \(phase)")
