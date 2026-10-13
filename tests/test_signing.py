import datetime as dt
import hashlib
import importlib.util
import plistlib
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sign_ipa", ROOT / "scripts/sign-ipa.py")
sign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sign)
spec2 = importlib.util.spec_from_file_location("prepare", ROOT / "scripts/prepare-signing-project.py")
prepare = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(prepare)


class SigningPolicyTests(unittest.TestCase):
    def setUp(self):
        self.team = "ABCDE12345"
        self.cert = b"fixture certificate"
        self.identity = {"team": self.team, "sha": hashlib.sha1(self.cert).hexdigest().upper(),
                         "name": "Apple Development: Fixture (ABCDE12345)"}
        self.bid = "org.example.onion"
        self.data = {
            "ExpirationDate": dt.datetime(2099, 1, 1),
            "TeamIdentifier": [self.team], "ApplicationIdentifierPrefix": ["OLDPREFIX1"],
            "DeveloperCertificates": [self.cert], "ProvisionedDevices": ["PHONE-A"],
            "Entitlements": {"application-identifier": "OLDPREFIX1.org.example.*",
                             "com.apple.developer.team-identifier": self.team,
                             "get-task-allow": True, sign.MEMORY: True}}
        self.profile = {"path": Path("fixture.mobileprovision"), "data": self.data}

    def test_profile_certificate_team_device_and_app_prefix(self):
        prefix = sign.validate_profile(self.profile, self.bid, self.identity, "PHONE-A")
        self.assertEqual(prefix, "OLDPREFIX1")  # App ID prefix need not equal Team ID.
        for field, value in [("TeamIdentifier", ["OTHER12345"]),
                             ("DeveloperCertificates", [b"wrong"]),
                             ("ProvisionedDevices", ["PHONE-B"]),
                             ("ExpirationDate", dt.datetime(2000, 1, 1))]:
            with self.subTest(field=field):
                bad = {"path": self.profile["path"], "data": {**self.data, field: value}}
                with self.assertRaises(sign.SigningError):
                    sign.validate_profile(bad, self.bid, self.identity, "PHONE-A")

    def test_bundle_mismatch(self):
        with self.assertRaisesRegex(sign.SigningError, "Bundle Identifier mismatch"):
            sign.validate_profile(self.profile, "com.other.app", self.identity)

    def test_distribution_profile_rejected(self):
        self.data["Entitlements"]["get-task-allow"] = False
        with self.assertRaisesRegex(sign.SigningError, "development profile"):
            sign.validate_profile(self.profile, self.bid, self.identity)

    def test_entitlement_values_not_just_keys(self):
        for value in (False, 1, "true"):
            with self.subTest(value=value), self.assertRaises(sign.SigningError):
                sign.validate_entitlements({sign.MEMORY: value}, self.data)
        with self.assertRaisesRegex(sign.SigningError, "Unsupported entitlement"):
            sign.validate_entitlements({"platform-application": True}, self.data)

    def test_keychain_wildcards_and_nonterminal_wildcards(self):
        self.assertTrue(sign.permitted(["ABCDE.group"], ["ABCDE.*"]))
        self.assertFalse(sign.permitted(["OTHER.group"], ["ABCDE.*"]))
        self.assertFalse(sign.permitted("ABCDE.group", "*.group"))

    def test_required_helper_debug_entitlement_cannot_be_removed(self):
        with self.assertRaisesRegex(sign.SigningError, "Cannot omit"):
            sign.make_entitlements({"get-task-allow": True}, self.profile, self.bid,
                                   self.identity, "OLDPREFIX1", self.bid, ["get-task-allow"])

    def test_no_silent_memory_removal(self):
        self.data["Entitlements"].pop(sign.MEMORY)
        with self.assertRaisesRegex(sign.SigningError, "Unsupported entitlement"):
            sign.make_entitlements({sign.MEMORY: True}, self.profile, self.bid,
                                   self.identity, "OLDPREFIX1", self.bid, [])
        with patch("sys.stderr"):
            ent = sign.make_entitlements({sign.MEMORY: True}, self.profile, self.bid,
                                        self.identity, "OLDPREFIX1", self.bid, [sign.MEMORY])
        self.assertNotIn(sign.MEMORY, ent)

    def test_resigning_uses_new_profile_identity(self):
        ent = sign.make_entitlements({"application-identifier": "OLD.old.bundle",
                                     "com.apple.developer.team-identifier": "OLD",
                                     "keychain-access-groups": ["OLD.old.bundle"]},
                                    {**self.profile, "data": {**self.data, "Entitlements": {
                                        **self.data["Entitlements"], "keychain-access-groups": ["OLDPREFIX1.*"]}}},
                                    self.bid, self.identity, "OLDPREFIX1", "old.bundle", [])
        self.assertEqual(ent["application-identifier"], "OLDPREFIX1." + self.bid)
        self.assertEqual(ent["com.apple.developer.team-identifier"], self.team)
        self.assertEqual(ent["keychain-access-groups"], ["OLDPREFIX1." + self.bid])


class ArchiveTests(unittest.TestCase):
    def test_traversal_case_collision_and_symlink_escape_rejected(self):
        cases = [("../outside", None), ("/absolute", None),
                 ("Payload/link", "../../outside")]
        with tempfile.TemporaryDirectory() as d:
            for filename, target in cases:
                path = Path(d) / "bad.zip"
                with zipfile.ZipFile(path, "w") as z:
                    if target:
                        item = zipfile.ZipInfo(filename)
                        item.external_attr = (stat.S_IFLNK | 0o777) << 16
                        z.writestr(item, target)
                    else:
                        z.writestr(filename, "")
                with self.assertRaises(sign.SigningError):
                    sign.validate_zip(path)
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("Payload/App.app/Info.plist", "")
                z.writestr("Payload/App.app/info.plist", "")
            with self.assertRaises(sign.SigningError):
                sign.validate_zip(path)

    def test_framework_relative_symlinks_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "okay.zip"
            with zipfile.ZipFile(path, "w") as z:
                item = zipfile.ZipInfo("Payload/App.app/Frameworks/F.framework/Versions/Current")
                item.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(item, "A")
            sign.validate_zip(path)

    def test_archive_cannot_write_through_existing_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.zip"
            with zipfile.ZipFile(path, "w") as z:
                item = zipfile.ZipInfo("Payload/link")
                item.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(item, "App.app")
                z.writestr("Payload/link/Info.plist", "overwrite")
            with self.assertRaisesRegex(sign.SigningError, "through a symlink"):
                sign.validate_zip(path)

    def fixture(self, root):
        app = root / "Reynard.app"
        for relative, bid in [("", "com.acops1206.TorBrowserIOS"),
                              ("PlugIns/Reynard Helper.appex", "com.acops1206.TorBrowserIOS.Helper"),
                              ("PlugIns/OpenIn.appex", "com.acops1206.TorBrowserIOS.OpenIn"),
                              ("Frameworks/GeckoView.framework", "org.example.gecko")]:
            folder = app / relative
            folder.mkdir(parents=True, exist_ok=True)
            sign.write_plist(folder / "Info.plist", {"CFBundleIdentifier": bid,
                                                    "CFBundleExecutable": "Executable"})
            (folder / "Executable").write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
        (app / "Frameworks/XUL").write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
        return app

    def test_sign_nested_executables_and_bundles_before_main(self):
        with tempfile.TemporaryDirectory() as d:
            app = self.fixture(Path(d))
            order = sign.signing_order(app)
            self.assertEqual(order[-1], app)
            self.assertIn(app / "Frameworks/XUL", order)
            self.assertIn(app / "Frameworks/GeckoView.framework", order)
            self.assertNotIn(app / "Frameworks/GeckoView.framework/Executable", order)
            resource = app / "Resources.bundle"
            resource.mkdir()
            sign.write_plist(resource / "Info.plist", {"CFBundleIdentifier": "org.fixture.resources"})
            self.assertNotIn(resource, sign.signing_order(app))
            for bundle in sign.app_bundles(app)[1:]:
                self.assertLess(order.index(bundle), order.index(app))

    def test_bundle_remap_retains_extension_relationship_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            app = self.fixture(Path(d))
            ids = sign.bundle_ids(app, "org.personal.onion")
            self.assertEqual(set(ids.values()), {"org.personal.onion", "org.personal.onion.Helper",
                                               "org.personal.onion.OpenIn"})
            self.assertEqual(sign.info(app)["CFBundleIdentifier"], "com.acops1206.TorBrowserIOS")
            helper = app / "PlugIns/Reynard Helper.appex"
            p = sign.info(helper)
            p["CFBundleIdentifier"] = "unrelated.extension"
            sign.write_plist(helper / "Info.plist", p)
            with self.assertRaises(sign.SigningError):
                sign.bundle_ids(app)

    def test_adhoc_or_unsigned_ipa_still_requires_memory_and_debug(self):
        with tempfile.TemporaryDirectory() as d, patch.object(sign, "signed_entitlements", return_value={}):
            app = self.fixture(Path(d))
            self.assertEqual(sign.requested_entitlements(app, app), {sign.MEMORY: True})
            self.assertEqual(sign.requested_entitlements(app, app / "PlugIns/Reynard Helper.appex"),
                             {"get-task-allow": True})

    def test_unknown_extension_not_silently_signed(self):
        with tempfile.TemporaryDirectory() as d, patch.object(sign, "signed_entitlements", return_value={}):
            app = self.fixture(Path(d))
            with self.assertRaises(sign.SigningError):
                sign.requested_entitlements(app, app / "Unknown.appex")

    def test_xcode_preparation_has_three_targets_and_no_engine(self):
        with tempfile.TemporaryDirectory() as d, patch("builtins.print"):
            root = Path(d) / "Preparation"
            prepare.generate(root, "org.personal.onion", "ABCDE12345")
            project = (root / "SigningPreparation.xcodeproj/project.pbxproj").read_text()
            self.assertEqual(project.count("isa = PBXNativeTarget;"), 3)
            self.assertNotIn("Gecko", project)
            self.assertEqual(plistlib.loads((root / "SigningApp/Required.entitlements").read_bytes()),
                             {sign.MEMORY: True})
            self.assertTrue((root / "SigningPreparation.xcodeproj/xcshareddata/xcschemes/SigningApp.xcscheme").exists())
            with self.assertRaises(FileExistsError):
                prepare.generate(root, "org.personal.onion", "ABCDE12345")


if __name__ == "__main__":
    unittest.main()
