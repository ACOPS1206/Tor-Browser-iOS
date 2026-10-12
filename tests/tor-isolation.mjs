import assert from "node:assert/strict";
import { createTorChannelFilter } from "../overlay/Gecko/TBIOPrivacy.sys.mjs";
let counter = 0;
const service = { newProxyInfoWithAuth(...args) { return args; } };
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
