"""Reviewed transformations for patched FIREFOX_157_0_1_RELEASE only.

No content-script spoofing and no hard-coded browser version. Keep mobile
layout/touch handling while using Gecko's existing Android RFP identity.
"""
from pathlib import Path


def apply(engine: Path, replace):
    header = engine / 'toolkit/components/resistfingerprinting/nsRFPService.h'
    replace(header, '#elif defined(MOZ_WIDGET_ANDROID)\n#  define SPOOFED_UA_OS',
            '#elif defined(MOZ_WIDGET_ANDROID) || defined(XP_IOS)\n#  define SPOOFED_UA_OS')
    service = engine / 'toolkit/components/resistfingerprinting/nsRFPService.cpp'
    replace(service, '#if defined(ANDROID)\n  if (aAndroidDesktopMode)',
            '#if defined(ANDROID) || defined(XP_IOS)\n  if (aAndroidDesktopMode)')
    navigator = engine / 'dom/base/Navigator.cpp'
    replace(navigator, '#elif defined(XP_IOS)\n  aPlatform.AssignLiteral("iPhone");',
            '''#elif defined(XP_IOS)
  if (aUsePrefOverriddenValue &&
      ShouldResistFingerprinting(aCallerDoc, RFPTarget::NavigatorPlatform)) {
    aPlatform.AssignLiteral("Linux armv81");
  } else {
    aPlatform.AssignLiteral("iPhone");
  }''')
    # Workers otherwise use cached native "iPhone", including service workers
    # with no window. Apply the same RFP target check on their own principal.
    worker = engine / 'dom/workers/WorkerNavigator.cpp'
    replace(worker, '''  // navigator.platform is the same for default and spoofed values. The''',
            '''#ifdef XP_IOS
  if (aCallerType != CallerType::System &&
      workerPrivate->ShouldResistFingerprinting(RFPTarget::NavigatorPlatform)) {
    aPlatform.AssignLiteral("Linux armv81");
    return;
  }
#endif

  // navigator.platform is the same for default and spoofed values. The''')
    # Swift's default settings are not the only producer (extension popups and
    # restored sessions also reach here). Clear identity overrides in the engine
    # bridge before they bypass Navigator RFP. Preserve unrelated settings.
    settings = engine / 'mobile/shared/modules/geckoview/GeckoViewSettings.sys.mjs'
    replace(settings, '    const { settings } = this;', '''    const settings = ChromeUtils.importESModule(
      "resource://gre/modules/TBIOPrivacy.sys.mjs"
    ).fingerprintingSessionSettings(this.settings);''')
