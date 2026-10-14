/* SPDX-License-Identifier: MPL-2.0 */
// Parent-process channel policy. Credentials are random, never domain names,
// and never persisted. FPI supplies the top-level firstPartyDomain for frames.
export function configureTorStartupPreferences(services) {
  const mode = services.env.get("TBIO_ROUTING_MODE");
  const selective = ["privateOnly", "never"].includes(mode);
  const values = {
    "browser.privatebrowsing.autostart": !selective,
    "network.dns.disabled": !selective,
    "javascript.enabled": services.env.get("TBIO_DISABLE_JAVASCRIPT") !== "1",
  };
  const defaults = services.prefs.getDefaultBranch("");
  for (const [name, value] of Object.entries(values)) {
    // mobile.js has already locked these defaults. Gecko silently ignores
    // writes to a locked default branch, even from startup chrome code.
    services.prefs.unlockPref(name);
    try {
      services.prefs.clearUserPref(name);
      defaults.setBoolPref(name, value);
    } finally {
      services.prefs.lockPref(name);
    }
    if (services.prefs.getBoolPref(name) !== value) {
      throw new Error(`Tor startup preference was not applied: ${name}`);
    }
  }
}

export function createTorChannelFilter(proxyService, newToken, proxyFlags, mode = "always") {
  if (!["always", "privateOnly", "never"].includes(mode)) mode = "always";
  const credentials = new Map();
  return {
    applyFilter(channel, _previousProxy, callback) {
      // Direct routing is an explicit user policy, NEVER a Tor error fallback.
      // Unknown context stays on Tor in private-only mode.
      let privateId, forcedPrivate;
      try { privateId = channel.loadInfo.originAttributes.privateBrowsingId; } catch {}
      // Chrome-initiated loads may report privateBrowsingId=0 even when private
      // browsing is forced. Never send those private loads directly.
      try { forcedPrivate = channel.loadInfo.usePrivateBrowsing; } catch {}
      if (mode === "never" || (mode === "privateOnly" && privateId === 0 && forcedPrivate !== true)) {
        // Gecko 157 takes eight arguments; the legacy six-argument call throws
        // and makes Gecko skip this filter, retaining the default SOCKS proxy.
        try {
          callback.onProxyFilterResult(proxyService.newProxyInfo(
            "direct", "", -1, "", "", 0, 0, null
          ));
        } catch (error) {
          channel.cancel(Cr.NS_ERROR_ABORT);
          throw error;
        }
        return;
      }
      let key;
      try {
        const attributes = channel.loadInfo.originAttributes;
        const domain = attributes.firstPartyDomain;
        // A missing top-level key must never merge unrelated unknown channels.
        key = domain ? JSON.stringify([domain, attributes.privateBrowsingId,
          attributes.userContextId]) : newToken();
      } catch {
        key = newToken();
      }
      if (!credentials.has(key)) {
        // Bound memory use; eviction may split a site's circuits, never merge them.
        if (credentials.size >= 4096) credentials.clear();
        credentials.set(key, [newToken(), newToken()]);
      }
      const [username, password] = credentials.get(key);
      let proxy;
      try {
        proxy = proxyService.newProxyInfoWithAuth(
          "socks", "127.0.0.1", 19050, username, password, "", username,
          proxyFlags, 0, null
        );
      } catch (error) {
        // Proxy filters can be skipped after an exception. Cancel the channel
        // first so a failed policy cannot silently continue without isolation.
        channel.cancel(Cr.NS_ERROR_ABORT);
        throw error;
      }
      // Always replace even a null/direct proxy. Never construct a direct fallback.
      callback.onProxyFilterResult(proxy);
    },
  };
}

let installedFilter;
export function installTorChannelIsolation() {
  if (Services.appinfo.processType !== Services.appinfo.PROCESS_TYPE_DEFAULT) return;
  if (installedFilter) return;
  const proxyService = Cc["@mozilla.org/network/protocol-proxy-service;1"]
    .getService(Ci.nsIProtocolProxyService);
  const newToken = () => Services.uuid.generateUUID().toString().slice(1, -1);
  installedFilter = createTorChannelFilter(proxyService, newToken,
    Ci.nsIProxyInfo.TRANSPARENT_PROXY_RESOLVES_HOST,
    Services.env.get("TBIO_ROUTING_MODE"));
  installedFilter.QueryInterface = ChromeUtils.generateQI(["nsIProtocolProxyChannelFilter"]);
  proxyService.registerChannelFilter(installedFilter, 0xffffffff);
}


