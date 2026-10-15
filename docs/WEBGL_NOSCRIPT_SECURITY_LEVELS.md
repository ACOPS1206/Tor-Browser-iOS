# WebGL, bundled NoScript, security levels

## Implementation

- `scripts/security-policy.py` modifies the pinned Gecko 157.0.1 engine. RFP
  suppresses extension enumeration and acquisition through their shared native
  caller gate. System callers are exempt; web pages and OffscreenCanvas/worker
  contexts use the same gate. WebGL 1 and 2 remain enabled in Standard.
- Hardware vendor/debug/renderer-query preferences are locked off. Gecko's
  existing RFP numeric-capability limits remain enabled. Shader-precision
  reporting is clamped to conservative spec floors without increasing a
  driver's capabilities; unsupported precision remains unsupported. Report hashes
  are not randomized. GPU timing/rendering differences can still fingerprint.
- Existing Gecko `readPixels`, PBO and `getBufferSubData` extraction handling is
  preserved. Gecko 157 invokes CanvasUtils extraction policy and RFP element
  randomization/placeholder generation. This is reviewed source behavior, not
  proof that every API/driver is protected on an iPhone. No new readback-noise
  layer or content-script GPU spoofing was added.
- The unmodified official NoScript **13.6.36.1984** XPI is checked against its
  release SHA-256 and extracted offline before framework signing. Its license
  and notices remain in the app. No runtime download is required. The release,
  source and digest are recorded in `vendor/noscript/PROVENANCE.md`.
- `TBIONoScript.sys.mjs` installs the built-in extension, enables it, grants
  private-browsing permission and reloads an existing instance if that grant
  changed. It sends the Tor SecurityLevel-style `updateSettings` message through
  a privileged, fixed-NoScript-ID bridge and reads back `exportSettings`.
  Initial startup/changed presets must confirm the actual NoScript policy before
  web channels are allowed. Missing/failed/timed-out initialization leaves
  normal **and private** web channels blocked, including explicitly Direct tabs.
- NoScript stays visible in the existing extensions action menu, which uses the
  original popup and selected-tab action handling. Engine commands reject its
  removal, disablement, user-triggered update or revocation of PB permission.
- Same-level restarts retain site permissions. Changing the level (or bundled
  package version) resets exceptions. NoScript popup exceptions customize the
  preset. This UI reports the selected preset, not a guarantee that there are
  no site exceptions. Explicitly disabling all NoScript enforcement makes the
  next startup fail closed; change the preset to restore it.

## Effective levels

| Policy | Standard | Safer | Safest |
|---|---|---|---|
| Default scripts | Allowed | HTTPS; HTTP blocked | Blocked |
| HTTP onion scripts | Allowed | Allowed as secure onion context | Blocked |
| Media/WebGL | Allowed | NoScript per-site permission | NoScript per-site permission |
| Web fonts | Allowed | Allowed, existing Graphite/SVG-font restrictions retained | NoScript permission |
| MathML | Enabled | Disabled by native namespace preference | Disabled |
| Inline SVG/SVG documents | Enabled | Enabled | Disabled by native namespace preference |
| JIT/Wasm | Existing fork restrictions retained | Disabled | Disabled |

The existing **Block JavaScript** switch is a separate hard global restriction
at every level, and cannot be undone by a NoScript site exception. All settings
apply after fully closing and reopening the app. Three Tor routing modes and
fail-closed Tor routing are preserved after the security initialization gate.
Standard remains stricter than official Tor defaults because this fork already
locks JIT, Wasm and SVG/Graphite font features off; this change does not weaken
those policies. Supported `mathml.disabled`/`svg.disabled` defaults and namespace
consumers were checked in Gecko 157. The removed `javascript.options.asmjs`
preference is deliberately not used.

## Sources reviewed

- Tor security level descriptions (desktop and Android):
  https://support.torproject.org/tor-browser/features/security-levels/
- Tor SecurityLevel capability/pref implementation:
  https://archives.seul.org/tor/cvs/Jul-2022/msg00157.html
- Subsequent settings confirmation/restart protocol:
  https://archives.seul.org/or/commits/Jun-2025/msg00017.html
- Official current NoScript package/source: https://noscript.net/getit/ and
  https://github.com/hackademix/noscript/releases/tag/13.6.36
- Gecko pinned `FIREFOX_157_0_1_RELEASE`:
  `dom/canvas/{ClientWebGLContext.cpp,WebGLContext.cpp,WebGLContextValidate.cpp}`,
  `dom/base/nsNameSpaceManager.cpp`, `modules/libpref/init/{all.js,StaticPrefList.yaml}`,
  `toolkit/components/extensions/ExtensionParent.sys.mjs`,
  `mobile/shared/modules/geckoview/GeckoViewWebExtension.sys.mjs`.

Tor GitLab raw file access was unavailable. Published official commit diffs
were compared with the exact current NoScript package and pinned Mozilla
sources; this is an adaptation, not a claim of complete Tor Browser parity.
In particular current NoScript normalizes UNTRUSTED capabilities to immutable
restrictions. Tests execute the release's real policy classes rather than
assuming the historic Tor capability lists survive unchanged.

## Verification and remaining checks

Local validation includes 45 Python tests (with actual pinned Reynard and
reviewed Gecko source supplied), the original routing/identity/gate Node tests,
NoScript release extraction/tamper checks, actual NoScript policy class execution
for HTTP/HTTPS and per-site exceptions, five startup lifecycle models, changed
source-anchor rejection, and compilation/execution of the exact precision clamp
block in a small C++ harness. This is not a full Gecko build or runtime test.

Actions runs the source/unit suite, macOS native/Swift checks, the patched-engine
build, app archive and unsigned IPA packaging. Its engine cache key includes the
new transformation script and all Gecko overlay modules. Build and artifact
success must be checked separately; the presence of tests or preferences is
not runtime verification.

**Not verified locally:** full Gecko compilation, actual addon install/messaging,
NoScript popup behavior, private-page enforcement, GPU runtime behavior and
three-mode IP/DNS routing on iPhone. Use `tests/runtime/security-level.html` on
controlled HTTP/HTTPS origins and `tests/runtime/index.html` for GPU probes.
Do not serve the diagnostic origin through a browser that you assume is Tor:
verify server-side ingress IP and the selected routing policy independently.

Device checklist:

1. Offline clean first launch: extension and popup appear without download;
   verify it is active in both normal/private tabs once connected.
2. Each preset on HTTP/HTTPS, with redirect, iframe, worker and .onion cases;
   run script/media/WebGL probes before and after explicit site exceptions.
3. Block JavaScript must win over every exception. Same-level restart retains
   site rules; a changed preset resets them. Verify MathML and SVG rendering.
4. WebGL 1/2 `getParameter`, `getExtension` and enumeration, numeric limits,
   shader precision, image extraction, PBO/getBufferSubData and worker contexts.
   Compare multiple devices/sites/sessions; stable report hash is expected.
5. Force extension installation/policy failure: no remote page may load, even
   with Tor Off. Separately stop Tor and repeat all three routing modes.
6. NoScript permission placeholders are permission-controlled behavior; actual
   autoplay/click-to-play, media downloads and WebGL permission UI need device
   verification. Advanced sites needing WebGL extensions may fail even Standard.

Remaining risks include driver/rendering/timing entropy, unsupported arithmetic
revealing implementation differences, NoScript/Gecko API integration regressions,
preset customization, and the fact that this is an unofficial iOS port outside
Tor Browser's usual fingerprinting population.
