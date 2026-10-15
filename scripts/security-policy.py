"""Pinned Gecko 157 transformations; reject moved or duplicate anchors."""
from pathlib import Path


def apply(engine: Path, replace):
    client = engine / 'dom/canvas/ClientWebGLContext.cpp'
    replace(client, '''  if (StaticPrefs::webgl_enable_privileged_extensions()) {
    return false;
  }''', '''  // Match Tor's extension-surface minimization. Both enumeration and
  // getExtension() use this gate, including OffscreenCanvas in workers.
  if (ShouldResistFingerprinting(RFPTarget::WebGLRenderCapability)) {
    return true;
  }
  if (StaticPrefs::webgl_enable_privileged_extensions()) {
    return false;
  }''')
    host = engine / 'dom/canvas/WebGLContext.cpp'
    replace(host, '''      out->shaderPrecisions->insert({{shaderType, precisionType}, spf});''', '''      // Report spec-floor precision rather than the driver's extra precision.
      // Clamp downward only; never advertise unsupported arithmetic.
      if (webgl->mResistFingerprinting) {
        const bool isFloat = precisionType == LOCAL_GL_LOW_FLOAT ||
            precisionType == LOCAL_GL_MEDIUM_FLOAT ||
            precisionType == LOCAL_GL_HIGH_FLOAT;
        const uint8_t bits = precisionType == LOCAL_GL_LOW_FLOAT ? 8 :
            precisionType == LOCAL_GL_MEDIUM_FLOAT ? 10 : 23;
        const uint8_t exponent = precisionType == LOCAL_GL_LOW_FLOAT ? 8 :
            precisionType == LOCAL_GL_MEDIUM_FLOAT ? 14 : 127;
        const uint8_t integerBits = precisionType == LOCAL_GL_LOW_INT ? 8 :
            precisionType == LOCAL_GL_MEDIUM_INT ? 10 :
            webgl->IsWebGL2() ? 31 : 16;
        spf.rangeMin = std::min(spf.rangeMin, uint8_t(isFloat ? exponent : integerBits));
        spf.rangeMax = std::min(spf.rangeMax, uint8_t(isFloat ? exponent : integerBits - 1));
        spf.precision = std::min(spf.precision, uint8_t(isFloat ? bits : 0));
      }
      out->shaderPrecisions->insert({{shaderType, precisionType}, spf});''')
    parent = engine / 'toolkit/components/extensions/ExtensionParent.sys.mjs'
    replace(parent, 'export var ExtensionParent = {', '''// Privileged Tor SecurityLevel-style internal messaging. No web-exposed API,
// no arbitrary target extension and no synthetic sender from page content.
async function tbioNoScriptMessage(message) {
  const extensionId = "{73a6fe31-595d-460b-a920-fcc0f8843232}";
  const { promises } = ProxyMessenger.conduit.castRuntimeMessage("messenger", {
    extensionId,
    holder: new StructuredCloneHolder("tbioNoScriptMessage", null, message),
    query: true, firstResponse: true,
    sender: { id: extensionId, extensionId },
  });
  const result = await raceResponses(promises);
  return result?.value?.deserialize({});
}

export var ExtensionParent = {
  tbioNoScriptMessage,''')
    # Enforce lifecycle invariants in the engine, including UI and restored
    # callers. Built-in NoScript remains enabled and allowed in private tabs.
    gv = engine / 'mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs'
    replace(gv, '  /* eslint-disable complexity */\n  async onEvent(aEvent, aData, aCallback) {\n    debug`onEvent ${aEvent} ${aData}`;\n\n    switch (aEvent) {', '''  /* eslint-disable complexity */
  async onEvent(aEvent, aData, aCallback) {
    debug`onEvent ${aEvent} ${aData}`;

    if (aData?.webExtensionId === "{73a6fe31-595d-460b-a920-fcc0f8843232}" ||
        aData?.extensionId === "{73a6fe31-595d-460b-a920-fcc0f8843232}") {
      if (["GeckoView:WebExtension:Disable", "GeckoView:WebExtension:Uninstall",
           "GeckoView:WebExtension:Update"].includes(aEvent) ||
          (aEvent === "GeckoView:WebExtension:SetPBAllowed" && !aData.allowed)) {
        aCallback.onError("Bundled NoScript is required for browser protection");
        return;
      }
    }
    switch (aEvent) {''')
