/* SPDX-License-Identifier: MPL-2.0 */
// Tor's SecurityLevel capability model, adapted to pinned Gecko 157 and
// NoScript 13.6.36.1984. No page-injected fingerprint spoofing.
export const NOSCRIPT_ID = "{73a6fe31-595d-460b-a920-fcc0f8843232}";
export function securityLevel(value) {
  return ["standard", "safer", "safest"].includes(value) ? value : "safest";
}
const ALL = ["fetch", "font", "frame", "media", "object", "other", "script",
  "webgl", "noscript", "lazy_load", "unchecked_css", "wasm"];
const MIN = ["frame", "other", "noscript"];
export function noScriptSettings(level) {
  level = securityLevel(level);
  const caps = level === "standard" ? ALL : level === "safer"
    ? ["fetch", "font", "frame", "object", "other", "script", "noscript", "lazy_load", "unchecked_css"] : MIN;
  const untrusted = level === "standard" ? ALL : level === "safer"
    ? ["frame", "font", "object", "other", "noscript"] : MIN;
  return {
    __meta: { name: "updateSettings", recipientInfo: null },
    isTorBrowser: true, tabId: -1,
    settingsHost: { knownCapabilities: ALL },
    local: { showCtxMenuItem: true },
    // Tor's defaults allow explicit per-site exceptions. Changing the level
    // deliberately resets exceptions; ordinary restarts retain saved choices.
    sync: { overrideTorBrowserPolicy: false },
    policy: {
      DEFAULT: { capabilities: [...caps], temp: false },
      TRUSTED: { capabilities: [...ALL], temp: false },
      UNTRUSTED: { capabilities: untrusted.filter(cap => !["script", "object", "wasm", "webgl", "fetch", "other", "ping"].includes(cap)), temp: false },
      sites: { trusted: [], untrusted: level === "safer" ? ["http:"] : [], custom: {}, temp: [] },
      enforced: true, autoAllowTop: false,
    },
  };
}
export function securityPreferences(level) {
  level = securityLevel(level);
  return {
    // Keep the fork's existing no-JIT/no-Wasm policy even at Standard.
    "mathml.disabled": level !== "standard",
    "svg.disabled": level === "safest",
  };
}
export function verifyNoScriptExport(value, expected, requirePreset) {
  const data = JSON.parse(value);
  if (!data.local?.isTorBrowser || !data.policy?.enforced || data.policy.autoAllowTop) {
    throw new Error("NoScript enforcement was not confirmed");
  }
  if (requirePreset) {
    for (const preset of ["DEFAULT", "TRUSTED", "UNTRUSTED"]) {
      const actual = [...data.policy[preset].capabilities].sort();
      const wanted = [...expected.policy[preset].capabilities].sort();
      if (JSON.stringify(actual) !== JSON.stringify(wanted)) throw new Error("NoScript preset mismatch");
    }
    if (JSON.stringify(data.policy.sites.untrusted) !== JSON.stringify(expected.policy.sites.untrusted)) {
      throw new Error("NoScript HTTP policy mismatch");
    }
  }
  return true;
}
