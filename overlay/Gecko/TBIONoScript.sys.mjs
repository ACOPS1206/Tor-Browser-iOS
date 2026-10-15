/* SPDX-License-Identifier: MPL-2.0 */
import { NOSCRIPT_ID, noScriptSettings, securityLevel, verifyNoScriptExport } from "resource://gre/modules/TBIOSecurityPolicy.sys.mjs";
import { setTimeout, clearTimeout } from "resource://gre/modules/Timer.sys.mjs";
let ready = false;
let failed = false;
let initialization;
export function noScriptReady() { return ready; }
const bounded = async (promise, ms) => {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error("NoScript initialization timed out")), ms);
    })]);
  } finally { clearTimeout(timer); }
};
async function initialize() {
  const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  const { ExtensionPermissions } = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
  const { ExtensionParent } = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
  await AddonManager.readyPromise;
  // Grant PB before startup, so the first private page is protected as well.
  const hadPrivate = (await ExtensionPermissions.get(NOSCRIPT_ID)).permissions.includes("internal:privateBrowsingAllowed");
  await ExtensionPermissions.add(NOSCRIPT_ID, { permissions: ["internal:privateBrowsingAllowed"], origins: [] });
  let addon = await AddonManager.getAddonByID(NOSCRIPT_ID);
  const reloadForPrivate = addon?.isActive && !hadPrivate;
  if (!addon || addon.version !== "13.6.36.1984" || !addon.isBuiltin) {
    addon = await AddonManager.installBuiltinAddon("resource://tbio-noscript/");
  }
  if (addon.userDisabled) await addon.enable();
  else if (reloadForPrivate) await addon.reload();
  if (!addon.isActive || !addon.isBuiltin) throw new Error("Bundled NoScript is not active");
  const extension = WebExtensionPolicy.getByID(NOSCRIPT_ID)?.extension;
  if (!extension) throw new Error("NoScript extension policy is missing");
  await extension.startupPromise;
  await extension.wakeupBackground?.();
  const send = msg => ExtensionParent.tbioNoScriptMessage(msg);
  // exportSettings awaits NoScript's Wakening/initialization barrier. Retry
  // only before the receiver is registered; all traffic stays gated meanwhile.
  let existing;
  for (let n = 0; n < 100; n++) {
    try {
      existing = await send({ __meta: { name: "exportSettings" } });
      if (typeof existing === "string") break;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (typeof existing !== "string") throw new Error("NoScript did not respond");
  const level = securityLevel(Services.env.get("TBIO_SECURITY_LEVEL") || "standard");
  const expected = noScriptSettings(level);
  const marker = `13.6.36.1984:${level}`;
  const reset = Services.prefs.getStringPref("tbio.noscript.applied", "") !== marker || !JSON.parse(existing).local?.isTorBrowser;
  // Confirm integration on every launch, preserve site permissions on an
  // ordinary restart. A changed preset replaces both preset and exceptions.
  if (reset) await send(expected);
  verifyNoScriptExport(await send({ __meta: { name: "exportSettings" } }), expected, reset);
  if (failed) throw new Error("NoScript initialization already failed");
  Services.prefs.setStringPref("tbio.noscript.applied", marker);
  ready = true;
  Services.obs.notifyObservers(null, "tbio-noscript-ready");
}
export function initializeNoScript() {
  if (!initialization) {
    initialization = bounded(initialize(), 20000).catch(error => {
      failed = true;
      ready = false;
      console.error("Bundled NoScript failed; web traffic remains blocked", error);
    });
  }
  return initialization;
}
