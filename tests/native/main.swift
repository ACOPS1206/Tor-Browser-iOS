import Foundation

let phase = CommandLine.arguments.last ?? "routing"
let endpoint = phase == "routing" ? "http://tor-routing-test.invalid/" : "http://127.0.0.1:19051/"
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
