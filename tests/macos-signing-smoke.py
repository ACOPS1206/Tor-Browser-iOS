"""Exercise real ditto packaging on macOS without certificates or account access."""
import importlib.util
import plistlib
import subprocess
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

    # Real dylib and consumers: prove both packaging and dyld resolution after
    # suffix normalization. This is a macOS loader test, not an iPhone test.
    native_archive = root / "Native.xcarchive"
    native_app = native_archive / "Products/Applications/Reynard.app"
    frameworks = native_app / "Frameworks"
    frameworks.mkdir(parents=True)
    library = root / "engine.c"
    library.write_text("int engine_answer(void) { return 42; }\n")
    consumer = root / "consumer.c"
    consumer.write_text("extern int engine_answer(void); int main(void) { return engine_answer() == 42 ? 0 : 1; }\n")
    subprocess.run(["xcrun", "clang", "-dynamiclib", str(library), "-o", str(frameworks / "XUL"),
                    "-Wl,-install_name,@rpath/XUL", "-Wl,-headerpad_max_install_names"], check=True)
    for relative, bid in [("", "org.fixture.onion"),
                          ("PlugIns/Reynard Helper.appex", "org.fixture.onion.Helper"),
                          ("Frameworks/GeckoView.framework", "org.fixture.gecko")]:
        folder = native_app / relative
        folder.mkdir(parents=True, exist_ok=True)
        sign.write_plist(folder / "Info.plist", {"CFBundleIdentifier": bid,
                                                "CFBundleExecutable": "Executable"})
        subprocess.run(["xcrun", "clang", str(consumer), str(frameworks / "XUL"),
                        "-o", str(folder / "Executable"), "-Wl,-headerpad_max_install_names",
                        "-Wl,-rpath,@executable_path/Frameworks"], check=True)
    original = {p.relative_to(native_app): p.read_bytes() for p in native_app.rglob("*") if p.is_file()}
    native_output = root / "native.ipa"
    sign.package_archive(native_archive, native_output)
    assert original == {p.relative_to(native_app): p.read_bytes() for p in native_app.rglob("*") if p.is_file()}
    extracted = root / "Extracted"
    sign.run(["ditto", "-x", "-k", native_output, extracted])
    result = extracted / "Payload/Reynard.app"
    assert not (result / "Frameworks/XUL").exists()
    assert (result / "Frameworks/XUL.dylib").is_file()
    for path in [result / "Executable", result / "PlugIns/Reynard Helper.appex/Executable",
                 result / "Frameworks/GeckoView.framework/Executable", result / "Frameworks/XUL.dylib"]:
        names = sign.dylib_dependencies(path)
        assert "@rpath/XUL.dylib" in names, (path, names)
        assert "@rpath/XUL" not in names, (path, names)
        sign.run(["codesign", "--force", "--sign", "-", path])
        sign.run(["codesign", "--verify", "--strict", path])
    subprocess.run([str(result / "Executable")], check=True)
print("macOS unsigned packaging smoke checks passed (no signing certificates used)")
