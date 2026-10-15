import assert from 'node:assert/strict';
import { createTorChannelFilter, installTorChannelIsolation } from '../overlay/Gecko/TBIOPrivacy.sys.mjs';
globalThis.Cr = { NS_ERROR_OFFLINE: 43, NS_ERROR_ABORT: 42 };
const service = {
  newProxyInfo(...args) { assert.equal(args.length, 8); return {type:args[0]}; },
  newProxyInfoWithAuth(...args) { assert.equal(args.length, 10); return {type:args[0]}; },
  registerChannelFilter(filter) { globalThis.registeredFilter = filter; },
};
function request(filter, privateId) {
  let cancelled, proxy;
  const channel = {loadInfo:{originAttributes:{privateBrowsingId:privateId,firstPartyDomain:'test.invalid'}},
    cancel(reason) { cancelled=reason; }};
  try { filter.applyFilter(channel, null, {onProxyFilterResult(p){proxy=p.type;}}); }
  catch(e) { assert.equal(e.message,'Tor unavailable: request blocked'); }
  return {cancelled,proxy};
}
for (const mode of ['always','privateOnly','never']) {
  for (const permitted of [false,true]) {
    for (const privateId of [0,1]) {
      const route = request(createTorChannelFilter(service,()=> 'token',1,mode,()=>permitted),privateId);
      const direct = mode==='never'||(mode==='privateOnly'&&privateId===0);
      assert.equal(route.cancelled, !direct&&!permitted ? 43 : undefined);
      assert.equal(route.proxy, direct ? 'direct' : permitted ? 'socks' : undefined);
    }
  }
}
// Exercise the production install path and its GeckoView event listener.
let listener;
globalThis.Services = {appinfo:{processType:0,PROCESS_TYPE_DEFAULT:0},
  env:{get(){return 'privateOnly';}},uuid:{generateUUID(){return '{token}';}}};
globalThis.Cc = {'@mozilla.org/network/protocol-proxy-service;1':{getService(){return service;}}};
globalThis.Ci = {nsIProtocolProxyService:{},nsIProxyInfo:{TRANSPARENT_PROXY_RESOLVES_HOST:1}};
globalThis.ChromeUtils = {generateQI(){return ()=>{};},importESModule(){return {
  noScriptReady: () => true,
  EventDispatcher:{instance:{registerListener(l,events){assert.deepEqual(events,['TBIO:TorState']);listener=l;}}}};}};
installTorChannelIsolation();
assert.equal(request(registeredFilter,1).cancelled,43); // cold start fails closed
listener.onEvent('TBIO:TorState',{permitted:true});
assert.equal(request(registeredFilter,1).proxy,'socks');
listener.onEvent('TBIO:TorState',{permitted:false});
assert.equal(request(registeredFilter,1).cancelled,43);
assert.equal(request(registeredFilter,0).proxy,'direct');
listener.onEvent('TBIO:TorState',{permitted:'true'});
assert.equal(request(registeredFilter,1).cancelled,43); // malformed state cannot open gate
listener.onEvent('TBIO:TorState',{permitted:true});
listener.onEvent('TBIO:TorState',null);
assert.equal(request(registeredFilter,1).cancelled,43);
console.log('Tor gate: 12 routing cases + production listener model passed; no real Gecko networking');
