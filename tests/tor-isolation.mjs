import assert from "node:assert/strict";
import { createTorChannelFilter } from "../overlay/Gecko/TBIOPrivacy.sys.mjs";
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
