"""Exercise real ditto packaging on macOS without certificates or account access."""
import importlib.util
import plistlib
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sign", ROOT / "scripts/sign-ipa.py")
sign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sign)

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    archive = root / "Fixture.xcarchive"
    app = archive / "Products/Applications/Reynard.app"
    for relative, bid in [("", "org.fixture.onion"),
                          ("PlugIns/Reynard Helper.appex", "org.fixture.onion.Helper"),
                          ("PlugIns/OpenIn.appex", "org.fixture.onion.OpenIn")]:
        folder = app / relative
        folder.mkdir(parents=True)
        sign.write_plist(folder / "Info.plist", {"CFBundleIdentifier": bid})
    before = (app / "Info.plist").read_bytes()
    output = root / "fixture.ipa"
    sign.package_archive(archive, output)
    sign.validate_zip(output)
    assert (app / "Info.plist").read_bytes() == before
    with zipfile.ZipFile(output) as z:
        assert plistlib.loads(z.read("Payload/Reynard.app/Info.plist"))["CFBundleIdentifier"] == "org.fixture.onion"
        requirements = plistlib.loads(z.read("Payload/Reynard.app/SigningRequirements.plist"))
        assert requirements["."][sign.MEMORY] is True
        assert requirements["PlugIns/Reynard Helper.appex"]["get-task-allow"] is True
    (app / "embedded.mobileprovision").write_bytes(b"fixture")
    try:
        sign.package_archive(archive, root / "forbidden.ipa")
    except sign.SigningError:
        pass
    else:
        raise AssertionError("Signed archive was accepted for unsigned packaging")
print("macOS unsigned packaging smoke checks passed (no signing certificates used)")
