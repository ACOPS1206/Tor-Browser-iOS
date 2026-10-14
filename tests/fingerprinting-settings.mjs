import assert from 'node:assert/strict';
import { fingerprintingSessionSettings } from '../overlay/Gecko/TBIOPrivacy.sys.mjs';

for (const kind of ['normal', 'private', 'extension-popup', 'restored']) {
  const input = Object.freeze({ kind, userAgentMode: 1, viewportMode: 1,
    isPrivate: kind === 'private', allowJavascript: false,
    userAgentOverride: 'custom', platformOverride: 'iPhone',
    appVersionOverride: 'custom', oscpuOverride: 'custom', buildIDOverride: 'custom' });
  const output = fingerprintingSessionSettings(input);
  assert.equal(output.userAgentMode, 0);
  for (const field of ['userAgent', 'platform', 'appVersion', 'oscpu', 'buildID']) {
    assert.equal(output[`${field}Override`], null);
  }
  assert.equal(output.viewportMode, input.viewportMode);
  assert.equal(output.isPrivate, input.isPrivate);
  assert.equal(output.allowJavascript, input.allowJavascript);
  assert.equal(input.platformOverride, 'iPhone');
}
console.log('Session identity bridge: 4 modeled session types passed (not Gecko runtime)');
