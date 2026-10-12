/* SPDX-License-Identifier: MPL-2.0 */
// Parent-process channel policy. Credentials are random, never domain names,
// and never persisted. FPI supplies the top-level firstPartyDomain for frames.
export function createTorChannelFilter(proxyService, newToken, proxyFlags) {
  const credentials = new Map();
  return {
    applyFilter(channel, _previousProxy, callback) {
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
    Ci.nsIProxyInfo.TRANSPARENT_PROXY_RESOLVES_HOST);
  installedFilter.QueryInterface = ChromeUtils.generateQI(["nsIProtocolProxyChannelFilter"]);
  proxyService.registerChannelFilter(installedFilter, 0xffffffff);
}
