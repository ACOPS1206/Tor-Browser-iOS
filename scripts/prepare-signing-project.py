#!/usr/bin/env python3
"""Generate a tiny Xcode project to provision the three IDs; no browser compilation."""
import argparse
import plistlib
import re
from pathlib import Path


def generate(output, bundle_id, team_id):
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", bundle_id):
        raise ValueError("Invalid Bundle Identifier")
    if not re.fullmatch(r"[A-Z0-9]{10}", team_id):
        raise ValueError("Team ID must be ten uppercase letters/digits")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    objects = {}
    counter = 0

    def obj(value):
        nonlocal counter
        counter += 1
        key = f"{counter:024X}"
        objects[key] = value
        return key

    def q(value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def configs(settings):
        refs = []
        for name in ("Debug", "Release"):
            refs.append(obj("{isa = XCBuildConfiguration; name = " + name +
                            "; buildSettings = {" + settings + "};}"))
        return obj("{isa = XCConfigurationList; buildConfigurations = (" +
                   ",".join(refs) + "); defaultConfigurationIsVisible = 0; defaultConfigurationName = Debug;}")

    products, files, targets = [], [], []
    extension_products = []
    dependencies = []
    for name, suffix in (("Helper", ".Helper"), ("OpenIn", ".OpenIn"), ("SigningApp", "")):
        extension = bool(suffix)
        folder = output / name
        folder.mkdir()
        source = ("#import <UIKit/UIKit.h>\n@interface SigningExtension: UIViewController @end\n"
                  "@implementation SigningExtension @end\n" if extension else
                  "#import <UIKit/UIKit.h>\nint main(int argc, char **argv) { @autoreleasepool { "
                  "return UIApplicationMain(argc, argv, nil, nil); } }\n")
        (folder / "main.m").write_text(source)
        plist = {"CFBundleIdentifier": "$(PRODUCT_BUNDLE_IDENTIFIER)",
                 "CFBundleExecutable": "$(EXECUTABLE_NAME)", "CFBundleName": "$(PRODUCT_NAME)",
                 "CFBundlePackageType": "XPC!" if extension else "APPL",
                 "CFBundleVersion": "1", "CFBundleShortVersionString": "1.0"}
        if extension:
            plist["NSExtension"] = {
                "NSExtensionPointIdentifier": "com.apple.ar.viewer" if name == "Helper" else "com.apple.share-services",
                "NSExtensionPrincipalClass": "SigningExtension",
                "NSExtensionAttributes": {"NSExtensionActivationRule": "FALSEPREDICATE"}}
        else:
            plist["UILaunchScreen"] = {}
        (folder / "Info.plist").write_bytes(plistlib.dumps(plist))
        ent = {"get-task-allow": True} if name == "Helper" else (
              {"com.apple.developer.kernel.increased-memory-limit": True} if not extension else {})
        (folder / "Required.entitlements").write_bytes(plistlib.dumps(ent))
        source_ref = obj("{isa = PBXFileReference; lastKnownFileType = sourcecode.c.objc; path = " +
                         q(name + "/main.m") + "; sourceTree = SOURCE_ROOT;}")
        files.append(source_ref)
        source_build = obj("{isa = PBXBuildFile; fileRef = " + source_ref + ";}")
        source_phase = obj("{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (" +
                           source_build + "); runOnlyForDeploymentPostprocessing = 0;}")
        framework_phase = obj("{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; "
                              "files = (); runOnlyForDeploymentPostprocessing = 0;}")
        product = obj("{isa = PBXFileReference; explicitFileType = " +
                      ("wrapper.app-extension" if extension else "wrapper.application") +
                      "; path = " + q(name + (".appex" if extension else ".app")) +
                      "; sourceTree = BUILT_PRODUCTS_DIR;}")
        products.append(product)
        build_settings = {
            "PRODUCT_NAME": name, "PRODUCT_BUNDLE_IDENTIFIER": bundle_id + suffix,
            "DEVELOPMENT_TEAM": team_id, "CODE_SIGN_STYLE": "Automatic",
            "CODE_SIGN_IDENTITY": "Apple Development", "INFOPLIST_FILE": name + "/Info.plist",
            "CODE_SIGN_ENTITLEMENTS": name + "/Required.entitlements",
            "SDKROOT": "iphoneos", "IPHONEOS_DEPLOYMENT_TARGET": "17.4",
            "TARGETED_DEVICE_FAMILY": "1,2", "CLANG_ENABLE_OBJC_ARC": "YES", "CLANG_ENABLE_MODULES": "YES",
            "SKIP_INSTALL": "YES" if extension else "NO",
            "APPLICATION_EXTENSION_API_ONLY": "YES" if extension else "NO"}
        cfg = configs("".join(k + " = " + q(v) + ";" for k, v in build_settings.items()))
        phases = [source_phase, framework_phase]
        if not extension:
            builds = [obj("{isa = PBXBuildFile; fileRef = " + p +
                          "; settings = {ATTRIBUTES = (RemoveHeadersOnCopy,);};}") for p in extension_products]
            phases.append(obj("{isa = PBXCopyFilesBuildPhase; buildActionMask = 2147483647; "
                              "dstPath = \"\"; dstSubfolderSpec = 13; name = \"Embed App Extensions\"; files = (" +
                              ",".join(builds) + "); runOnlyForDeploymentPostprocessing = 0;}"))
        target = obj("{isa = PBXNativeTarget; name = " + q(name) + "; productName = " + q(name) +
                     "; productReference = " + product + "; productType = " +
                     q("com.apple.product-type.app-extension" if extension else "com.apple.product-type.application") +
                     "; buildConfigurationList = " + cfg + "; buildPhases = (" + ",".join(phases) +
                     "); buildRules = (); dependencies = (" + (",".join(dependencies) if not extension else "") + ");}")
        targets.append(target)
        if extension:
            extension_products.append(product)
            dependencies.append(obj("{isa = PBXTargetDependency; target = " + target + ";}"))
    product_group = obj("{isa = PBXGroup; name = Products; sourceTree = \"<group>\"; children = (" +
                        ",".join(products) + ");}")
    group = obj("{isa = PBXGroup; sourceTree = \"<group>\"; children = (" +
                ",".join([*files, product_group]) + ");}")
    project = obj("{isa = PBXProject; attributes = {LastUpgradeCheck = 1600;}; "
                  "buildConfigurationList = " + configs("") + "; compatibilityVersion = \"Xcode 14.0\"; "
                  "developmentRegion = en; knownRegions = (en, Base); mainGroup = " + group +
                  "; productRefGroup = " + product_group + "; projectDirPath = \"\"; projectRoot = \"\"; targets = (" +
                  ",".join(targets) + ");}")
    path = output / "SigningPreparation.xcodeproj"
    path.mkdir()
    (path / "project.pbxproj").write_text("// !$*UTF8*$!\n{archiveVersion = 1; classes = {}; objectVersion = 56; "
                                       "objects = {\n" + "\n".join(k + " = " + v + ";" for k, v in objects.items()) +
                                       "\n}; rootObject = " + project + ";}\n")
    schemes = path / "xcshareddata/xcschemes"
    schemes.mkdir(parents=True)
    (schemes / "SigningApp.xcscheme").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<Scheme version="1.3">'
        '<BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries>'
        '<BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" '
        'buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" '
        f'BlueprintIdentifier="{targets[-1]}" BuildableName="SigningApp.app" BlueprintName="SigningApp" '
        'ReferencedContainer="container:SigningPreparation.xcodeproj"/></BuildActionEntry>'
        '</BuildActionEntries></BuildAction><LaunchAction buildConfiguration="Debug"/>'
        '<ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/></Scheme>')
    print(f"Open {path} in Xcode, sign in under Settings → Accounts, select your iPhone.")
    print("Build the SigningApp target; this only builds tiny provisioning placeholders.")
    print(f'xcodebuild -project "{path}" -scheme SigningApp -configuration Debug '
          '-destination "id=<IPHONE_UDID>" -allowProvisioningUpdates '
          '-allowProvisioningDeviceRegistration build')
    print("Do not install/Run this placeholder over your browser; use build only.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--bundle-id", required=True)
    p.add_argument("--team-id", required=True)
    args = p.parse_args()
    try:
        generate(args.output, args.bundle_id, args.team_id)
    except (ValueError, OSError) as e:
        p.exit(1, f"Preparation stopped: {e}\n")
