import assert from 'node:assert/strict';
import fs from 'node:fs';
import { noScriptSettings } from '../overlay/Gecko/TBIOSecurityPolicy.sys.mjs';
const policyURL = new URL('../overlay/Gecko/TBIOSecurityPolicy.sys.mjs',import.meta.url).href;
const code = fs.readFileSync(new URL('../overlay/Gecko/TBIONoScript.sys.mjs',import.meta.url),'utf8')
  .replace('resource://gre/modules/TBIOSecurityPolicy.sys.mjs',policyURL)
  .replace('resource://gre/modules/Timer.sys.mjs','node:timers');
for (const scenario of ['fresh','existing-without-private-permission','restart-with-site-choice','unconfirmed','install-error']) {
  let installed=0,reloaded=0,settingsApplied=0,permissionsAdded=0;
  let marker=scenario==='restart-with-site-choice'?'13.6.36.1984:safer':'';
  const actual = { policy:noScriptSettings('safer').policy,local:{isTorBrowser:true} };
  const addon={version:'13.6.36.1984',isBuiltin:true,isActive:true,userDisabled:false,
    async reload(){ reloaded++; assert.equal(permissionsAdded,1); }};
  globalThis.Services={env:{get(){return 'safer';}},prefs:{getStringPref(){return marker;},setStringPref(k,v){marker=v;}},obs:{notifyObservers(){}}};
  globalThis.WebExtensionPolicy={getByID(){return {extension:{startupPromise:Promise.resolve()}};}};
  globalThis.ChromeUtils={importESModule(uri){
    if(uri.includes('AddonManager'))return {AddonManager:{readyPromise:Promise.resolve(),async getAddonByID(){return scenario==='fresh'?null:addon;},async installBuiltinAddon(location){installed++;assert.equal(location,'resource://tbio-noscript/');assert.equal(permissionsAdded,1);if(scenario==='install-error')throw Error('failure');return addon;}}};
    if(uri.includes('ExtensionPermissions'))return {ExtensionPermissions:{async get(){return {permissions:scenario==='restart-with-site-choice'?['internal:privateBrowsingAllowed']:[]};},async add(){permissionsAdded++;}}};
    if(uri.includes('ExtensionParent'))return {ExtensionParent:{async tbioNoScriptMessage(msg){
      if(msg.__meta.name==='updateSettings'){settingsApplied++;actual.policy=msg.policy;}
      if(scenario==='unconfirmed')return JSON.stringify({policy:{enforced:false}});
      return JSON.stringify(actual);
    }}};
    throw Error(uri);
  }};
  // Force the install-error case down the actual install branch.
  if(scenario==='install-error') addon.version='old';
  const module=await import(`data:text/javascript;base64,${Buffer.from(code+`\n// ${scenario}`).toString('base64')}`);
  assert.equal(module.noScriptReady(),false);
  const savedError=console.error;
  console.error=(label)=>assert.match(label,/NoScript failed/);
  try { await module.initializeNoScript(); } finally { console.error=savedError; }
  const failed=['unconfirmed','install-error'].includes(scenario);
  assert.equal(module.noScriptReady(),!failed,scenario);
  if(scenario==='fresh')assert.equal(installed,1);
  if(scenario==='existing-without-private-permission')assert.equal(reloaded,1);
  if(scenario==='restart-with-site-choice')assert.equal(settingsApplied,0);
  // Initialization is idempotent.
  await module.initializeNoScript();
  assert.ok(settingsApplied<=1);
}
console.log('NoScript startup lifecycle model: 5 cases passed; not actual addon installation');
