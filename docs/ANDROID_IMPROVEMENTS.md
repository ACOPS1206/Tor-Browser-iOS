# Android Tor reference improvements applied — 2026-10-14

This update includes the fingerprinting review commit `73f5923` plus the changes
below. No Actions workflow is modified and no build is dispatched. The commit
uses `[skip ci]` when main is updated. No new IPA is produced in this task.

## Changes

| Area | Implementation | Validation limits |
|---|---|---|
| iOS mobile RFP | Existing Gecko Android identity constants reused; window/Worker platform and session identity overrides handled; English Intl policy added | Prior local source/preprocessor/model checks; no Gecko/iPhone runtime |
| Connection state | Separate stage/progress/readiness notifications alongside compatible TorStatus notifications. Authentication and GETINFO have 10-second bounds; no overlapping status query. Monotonic deadlines and generations reject late/reordered responses. Malformed replies never reuse previous 100% readiness | Portable C model compiled/executed; Objective-C framework integration not compiled here |
| New Tor requests | Default-closed Gecko channel gate receives native readiness via privileged GeckoView messaging. Paused/unavailable channels are cancelled, never changed to Direct. Native URLProtocol checks a locked shared gate; active native Tor tasks are cancelled when the gate closes | 12 routing cases plus production listener model executed in Node; native/iPhone execution pending |
| Resume | Native authentication reapplies DisableNetwork and waits for its acknowledgement before querying readiness. Control failure keeps new requests blocked. Late callbacks cannot restore stale ready state | Source review and poll model; actual control/socket races pending |
| Direct modes | Gate evaluated after explicit Direct selection. Native direct sessions have no Tor-unavailable protocol. Normal Direct tabs in private-only and both Direct tabs in off retain their policy | Node matrix verified; real HTTP/DNS path pending |
| Engine bypass defence | Pinned Gecko options verified in toolkit/moz.configure; upstream build-gecko.sh transformation adds --enable-proxy-bypass-protection and --disable-proxy-direct-failover | Source options and nsHttpChannel guards reviewed; full configure/build not executed |
| Removed preference | network.proxy.failover_direct removed: disabling that code at compile time also removes its StaticPref declaration. network.proxy.allow_bypass=false retained/locked instead | Avoids manufacturing an inert removed preference. Existing direct-filter selection is a separate code path |
| Remote search suggestions | SearchCompletion returns an empty result without URL construction or a dataTask. Local bookmark/history providers are unchanged | Upstream source transformation checked; UI responsiveness needs device QA |
| Resource size | Copied omni.ja repacked using ZIP/DEFLATE supported by Gecko's existing ZIP reader. Source cache/dist is untouched. Entry order/content/archive comment are checked before replacement, and replacement occurs only on a size win, before GeckoView.framework signing | ZIP fixtures verified. Actual omnijar, signature, startup and IPA-size measurements pending |
| CI compatibility | UI stubs now include the selected tab/session fields required by the new status indicator. Native proxy test adds a closed-gate case | Workflow files unchanged; UIKit/CFNetwork checks not run on this Linux host |

## Why this differs from Android

Android's omni.ja XZ change includes a Java extractor, Gradle packaging and JNI
integration. iOS has none of those entry points. This patch uses Gecko-supported
DEFLATE inside omni.ja and the existing iOS copy/sign pipeline. It does not add
startup extraction, write decompressed browser resources into application data,
remove shared resources, or add an XZ runtime dependency.

Converting an optimized omnijar to an ordinary ZIP can lose preload/locality
optimizations. Size may decrease without improving launch time or RAM. Launch
performance and actual resource compatibility must be checked in Gecko. No
actual IPA reduction percentage or build-time speedup is claimed.

The engine flags remove proxy-error fallback and suspected bypass mechanisms;
they do not disable the explicitly selected Direct proxy type in the tab policy.
This distinction is based on Gecko 157's compile guard and routing code. It still
requires verification with real normal/private tabs after building.

Android's separate process shutdown and Android lifecycle code were not copied
into TORThread: the iOS app embeds a process-local Tor thread. Control files
already live in Application Support rather than purgeable cache, so that design
was retained. Tor guard/consensus state and the three route settings are preserved.

## Executed locally

* Python unittest: **40 tests passed**, with reviewed Gecko source and pinned
  Reynard source-file fixture supplied. The overlay integration fixture contains
  selected real Reynard files and synthetic Gecko insertion anchors, not a full
  engine checkout/build.
* The new portable C poll test covers overlap, timeout, late response, duplicate
  response, pause invalidation and bootstrap-without-circuit rejection.
* Resource tests cover content/order/permissions/comment preservation, no-size-win
  retention, symlink/corrupt archive refusal, temporary-file cleanup and prefixed
  ZIP offsets. The prefixed fixture is not an actual optimized Gecko omnijar.
* Node legacy isolation/routing tests and four session-identity cases passed.
* Node new gate matrix: 12 cases plus cold-start, readiness, pause and malformed
  message cases through the modeled production listener passed.
* Whitespace and JS syntax checks passed. No workflow differences.

Native Foundation proxy tests, Objective-C TorService compilation, Swift/UIKit
type checking, actual Gecko networking/rendering, iPhone routing and code signing
are **not executed here**. Their prepared tests are not reported as passes.

## Important remaining limits

The new gate controls new Gecko channels after its state message is received.
It does not prove termination of an already upgraded Gecko WebSocket or an
already open media stream. Tor DisableNetwork remains responsible for those
connections. Native task cancellation is asynchronous. The UI says "new requests
blocked" on control failure rather than promising all transport has stopped.

State publication to Gecko is installed by the browser host after engine startup;
initial/default state is closed and subsequent publications retry delivery. A
page attempted before Tor becomes ready may require reload. Pausing while a
control command is in flight, multiple windows and foreground/background
transitions require device testing.

Fonts, actual viewport letterboxing, complete AudioContext extraction defence,
official NoScript security-level integration and per-site native SOCKS credential
isolation remain separate work. No extra disabled WebGL/Audio preferences or
unsupported Android APIs were added. Mixed-mode native requests without known
tab context remain blocked.

The workflow's existing engine cache key includes apply-overlay.py, Gecko
overlay and preference changes, so these changes invalidate old binaries. It
does not separately hash fingerprinting-policy.py: future changes to that helper
must also bump/change apply-overlay.py until a workflow revision is authorized.
C++ and compile-flag changes require rebuilding Gecko; this task does not alter
that workflow or implement JS-only engine reuse.

## Device checks before declaring success

1. Verify normal/private IP paths for Always, PrivateOnly and Off, including
   HTTP, WebSocket, media, redirects, downloads and extension background traffic.
2. Pause and break control/SOCKS connections; after ten seconds UI must stop
   presenting stale readiness and new Tor requests must fail without Direct
   fallback. Confirm normal Direct tabs still work in private-only.
3. Resume after a lost control connection, repeatedly pause/resume, background
   the app and reopen it. Confirm late callbacks cannot reopen a closed gate.
4. Use tests/runtime probes to compare HTTP/JS/Worker identity, Canvas/WebGL and
   locale. Real DNS leak checks need network/DNS observation, not just an IP page.
5. Build/archive with resource compaction, verify nested signatures and launch
   Gecko/readerview/addons/locales. Compare real IPA size and cold-start time.

## References actually inspected

Official Android diffs:

* [Stage event migration](https://lists.torproject.org/mailman3/hyperkitty/list/tbb-commits@lists.torproject.org/thread/7CRERJE4REQESY6MUGK35XCLAMCPMPYK/)
* [Native process shutdown](https://lists.torproject.org/mailman3/hyperkitty/list/tbb-commits@lists.torproject.org/thread/QSDVE6NEMX22KQZ2AU6LDGTOJI4PUSW5/)
* [Engine failover build flags](https://lists.torproject.org/mailman3/hyperkitty/list/tor-commits@lists.torproject.org/thread/4B5JWOTPSXRDCBQGO4GIQJQAMFY7JA6E/)
* [XZ resource packaging](https://lists.torproject.org/mailman3/hyperkitty/list/tbb-commits@lists.torproject.org/thread/4KSG6GK62UENGKZ34GCWHRMFNNQ2LI2Y/)
* [Search suggestion removal](https://lists.torproject.org/mailman3/hyperkitty/list/tor-commits@lists.torproject.org/2026/9/?count=50&page=4)

Pinned source:

* [Gecko configure options](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/toolkit/moz.configure)
* [Gecko HTTP fallback guard](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/netwerk/protocol/http/nsHttpChannel.cpp)
* [Gecko ZIP reader](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/modules/libjar/nsZipArchive.cpp)
* [GeckoView messaging](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/mobile/shared/modules/geckoview/Messaging.sys.mjs)
* [Reynard resource copy/sign script](https://github.com/minh-ton/reynard-browser/blob/ddaacd18b8c5661d495acfc0f3e90a86c484e64d/browser/Scripts/AddGecko.sh)

GitLab full latest Tor files were inaccessible. These are inspected diffs and
the pinned Gecko/Reynard files, not a claim of complete latest Android source audit.
