import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {execFileSync} from 'node:child_process';
import { noScriptSettings, securityPreferences, securityLevel, verifyNoScriptExport } from '../overlay/Gecko/TBIOSecurityPolicy.sys.mjs';
import { createTorChannelFilter } from '../overlay/Gecko/TBIOPrivacy.sys.mjs';
const root = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const dir = fs.mkdtempSync(path.join(os.tmpdir(),'noscript-policy-'));
try {
  execFileSync('python3',[path.join(root,'scripts/bundle-noscript.py'),path.join(root,'vendor/noscript/noscript.xpi'),dir]);
  // Execute actual policy classes from the verified official XPI, without a
  // browser API mock pretending to have blocked script execution.
  const context = vm.createContext({ URL, console, debug(){}, error(){}, log(){} });
  for (const file of ['lib/punycode.js','common/tld.js','common/Sites.js','common/Permissions.js','common/Policy.js']) {
    vm.runInContext(fs.readFileSync(path.join(dir,'nscl',file),'utf8'),context);
  }
  for (const level of ['standard','safer','safest']) {
    context.settings = noScriptSettings(level);
    vm.runInContext("Sites.onionSecure = true",context);
    const actual = vm.runInContext('new Policy(settings.policy)',context);
    for (const scheme of ['https','http']) {
      const url = `${scheme}://example.com/`;
      assert.equal(actual.can(url,'script'), level==='standard'||(level==='safer'&&scheme==='https'));
      for (const cap of ['media','webgl']) assert.equal(actual.can(url,cap),level==='standard');
      assert.equal(actual.can(url,'font'),level!=='safest');
    }
    assert.equal(actual.can('http://example.onion/','script'),level!=='safest');
    assert.equal(verifyNoScriptExport(JSON.stringify({policy:actual.dry(),local:{isTorBrowser:true}}),context.settings,true),true);
    // Explicit site exception works even in Safest, as in Tor/NoScript.
    context.policy=actual;
    vm.runInContext('policy.set("https://allowed.example", policy.TRUSTED)',context);
    assert.equal(actual.can('https://allowed.example','script'),true);
    assert.equal(securityPreferences(level)['mathml.disabled'],level!=='standard');
    assert.equal(securityPreferences(level)['svg.disabled'],level==='safest');
  }
} finally { fs.rmSync(dir,{recursive:true,force:true}); }
assert.equal(securityLevel('corrupted'),'safest');
assert.throws(()=>verifyNoScriptExport('{"policy":{"enforced":false}}',noScriptSettings('safest'),false));
// NoScript gate must precede *all* route choices, including explicit Direct.
globalThis.Cr={NS_ERROR_NOT_AVAILABLE:99};
for(const mode of ['always','privateOnly','never']) for(const privateId of [0,1]) {
  let cancelled=false;
  const filter=createTorChannelFilter({},()=>'',1,mode,()=>true,()=>false);
  assert.throws(()=>filter.applyFilter({loadInfo:{originAttributes:{privateBrowsingId:privateId}},cancel(c){assert.equal(c,99);cancelled=true;}},null,{onProxyFilterResult(){assert.fail();}}));
  assert.ok(cancelled);
}
console.log('Security levels: official NoScript policy classes and startup route gate passed; not a Gecko runtime test');
