import assert from "node:assert/strict";
import { createTorChannelFilter, configureTorStartupPreferences } from "../overlay/Gecko/TBIOPrivacy.sys.mjs";
let counter = 0;
const service = { newProxyInfoWithAuth(...args) { assert.equal(args.length, 10); return args; } };
const filter = createTorChannelFilter(service, () => `token-${++counter}`, 1);
function route(domain, privateBrowsingId = 1, userContextId = 0, previous = null) {
  let calls = 0, result;
  filter.applyFilter({ loadInfo: { originAttributes: {
    firstPartyDomain: domain, privateBrowsingId, userContextId,
  } } }, previous, { onProxyFilterResult(proxy) { calls++; result = proxy; } });
  assert.equal(calls, 1);
  assert.equal(result[0], "socks");
  assert.equal(result[1], "127.0.0.1");
  assert.equal(result[2], 19050);
  assert.equal(result[7], 1); // SOCKS proxy resolves host, never local DNS.
  assert.equal(result[9], null); // No direct fallback chain.
  assert.equal(result[6], result[3]); // Connection pool isolation key.
  return result.slice(3, 5);
}
const a = route("a.example");
assert.deepEqual(route("a.example", 1, 0, { type: "direct" }), a);
assert.notDeepEqual(route("b.example"), a); // Same CDN on different first parties.
assert.notDeepEqual(route("a.example", 0), a);
assert.notDeepEqual(route("a.example", 1, 2), a);
assert.notDeepEqual(route(""), route("")); // Unknown context never shared.
assert.ok(a.every(value => !value.includes("a.example")));
let missing;
filter.applyFilter({}, null, { onProxyFilterResult(proxy) { missing = proxy; } });
assert.equal(missing[0], "socks");
for (let i = 0; i < 4100; i++) route(`site-${i}.example`);
assert.notDeepEqual(route("a.example"), a); // Bounded map only splits circuits.
globalThis.Cr = { NS_ERROR_ABORT: 42 };
let cancelled = false;
const failing = createTorChannelFilter({ newProxyInfoWithAuth() {
  throw new Error("proxy policy failed");
} }, () => "token", 1);
assert.throws(() => failing.applyFilter({ cancel(status) {
  assert.equal(status, 42); cancelled = true;
} }, null, { onProxyFilterResult() { assert.fail("Unexpected fallback"); } }));
assert.ok(cancelled);
console.log("Tor channel isolation: 10 cases passed");

const routingService = {
  newProxyInfoWithAuth(...args) { assert.equal(args.length, 10); return args; },
  newProxyInfo(...args) {
    // Mirror the pinned Gecko IDL rather than accepting any argument count.
    assert.equal(args.length, 8);
    assert.equal(typeof args[3], "string");
    assert.equal(typeof args[4], "string");
    assert.equal(args[7], null);
    return args;
  },
};
function policy(mode, privateId) {
  const route = createTorChannelFilter(routingService, () => "token", 1, mode);
  let result;
  route.applyFilter({ loadInfo: { originAttributes: { privateBrowsingId: privateId,
    firstPartyDomain: "same.example", userContextId: 0 } } }, null,
    { onProxyFilterResult(p) { result = p; } });
  return result[0];
}
assert.equal(policy("always", 0), "socks");
assert.equal(policy("always", 1), "socks");
assert.equal(policy("privateOnly", 0), "direct");
assert.equal(policy("privateOnly", 1), "socks");
assert.equal(policy("privateOnly", undefined), "socks");
assert.equal(policy("never", 0), "direct");
assert.equal(policy("never", 1), "direct");
assert.equal(policy("invalid", 0), "socks");
assert.equal(policy("", 0), "socks");
console.log("Tor routing mode matrix: 9 cases passed");



// Reproduce the old call: XPCOM rejects it and Gecko keeps the prior SOCKS proxy.
assert.throws(() => routingService.newProxyInfo("direct", "", -1, 0, 0, null));
for (const mode of ["never", "privateOnly"]) {
  let received;
  const previousSocks = { type: "socks", host: "127.0.0.1", port: 19050 };
  createTorChannelFilter(routingService, () => "token", 1, mode).applyFilter(
    { loadInfo: { originAttributes: { privateBrowsingId: 0 } } }, previousSocks,
    { onProxyFilterResult(proxy) { received = proxy; } });
  assert.equal(received[0], "direct"); // Must replace an existing SOCKS proxy.
}
let directCancelled = false;
assert.throws(() => createTorChannelFilter({ newProxyInfo() { throw Error("bad direct proxy"); } },
  () => "token", 1, "never").applyFilter({ cancel(code) {
    assert.equal(code, 42); directCancelled = true;
  } }, null, { onProxyFilterResult() { assert.fail("Unexpected fallback"); } }));
assert.ok(directCancelled);
console.log("Gecko 157 direct-proxy API regression: 4 cases passed");

let privateChromeProxy;
createTorChannelFilter(routingService, () => "token", 1, "privateOnly").applyFilter(
  { loadInfo: { usePrivateBrowsing: true, originAttributes: { privateBrowsingId: 0 } } }, null,
  { onProxyFilterResult(proxy) { privateChromeProxy = proxy; } });
assert.equal(privateChromeProxy[0], "socks");
console.log("Forced-private chrome request remains on Tor: passed");

// Model Gecko Preferences::SetDefault: locked defaults ignore writes silently.
// Include user values left by an earlier launch, not just a clean profile.
function startupServices(mode, blockJS = "0") {
  const defaults = new Map([
    ["browser.privatebrowsing.autostart", true],
    ["network.dns.disabled", true], ["javascript.enabled", true],
  ]);
  const users = new Map(defaults);
  const locked = new Set(defaults.keys());
  const prefs = {
    getDefaultBranch() { return { setBoolPref(name, value) {
      if (!locked.has(name)) defaults.set(name, value);
    } }; },
    unlockPref(name) { locked.delete(name); },
    clearUserPref(name) { users.delete(name); },
    lockPref(name) { locked.add(name); },
    getBoolPref(name) { return !locked.has(name) && users.has(name)
      ? users.get(name) : defaults.get(name); },
  };
  return { prefs, locked, users, env: { get(name) {
    return name === "TBIO_ROUTING_MODE" ? mode : blockJS;
  } } };
}
const legacy = startupServices("privateOnly");
legacy.prefs.getDefaultBranch("").setBoolPref("browser.privatebrowsing.autostart", false);
assert.equal(legacy.prefs.getBoolPref("browser.privatebrowsing.autostart"), true);
assert.equal(policy("privateOnly", 1), "socks"); // Ordinary window forced private by old default.
let startupCases = 0;
for (const mode of ["always", "privateOnly", "never", "invalid", ""]) {
  for (const blockJS of ["0", "1"]) {
    const services = startupServices(mode, blockJS);
    configureTorStartupPreferences(services);
    const selective = ["privateOnly", "never"].includes(mode);
    assert.equal(services.prefs.getBoolPref("browser.privatebrowsing.autostart"), !selective);
    assert.equal(services.prefs.getBoolPref("network.dns.disabled"), !selective);
    assert.equal(services.prefs.getBoolPref("javascript.enabled"), blockJS !== "1");
    assert.equal(services.users.size, 0);
    assert.equal(services.locked.size, 3);
    // WindowWatcher applies the global autostart pref OR the session's private flag.
    for (const privateTab of [false, true]) {
      const enginePrivate = services.prefs.getBoolPref("browser.privatebrowsing.autostart") || privateTab;
      assert.equal(policy(mode, enginePrivate ? 1 : 0),
        mode === "never" || (mode === "privateOnly" && !privateTab) ? "direct" : "socks");
    }
    startupCases++;
  }
}
console.log(`Locked startup preferences and resulting tab routing: ${startupCases} cases passed`);
