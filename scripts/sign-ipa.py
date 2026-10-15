#!/usr/bin/env python3
"""Offline IPA re-signing using Apple's security, codesign and ditto tools.

No account login, certificate creation, engine compilation or network requests.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ID = "com.acops1206.TorBrowserIOS"
MEMORY = "com.apple.developer.kernel.increased-memory-limit"
MANAGED = {"application-identifier", "com.apple.developer.team-identifier",
           "keychain-access-groups", "get-task-allow"}
MAGIC = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe",
         b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
         b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}


class SigningError(Exception):
    pass


def run(args, check=True):
    p = subprocess.run([str(x) for x in args], capture_output=True)
    if check and p.returncode:
        detail = (p.stderr or p.stdout).decode(errors="replace").strip()
        raise SigningError(f"{args[0]} failed: {detail}\n"
                           "Check Xcode selection, unlocked login Keychain and signing documentation.")
    return p


def read_plist(path):
    with Path(path).open("rb") as f:
        return plistlib.load(f)


def write_plist(path, value):
    Path(path).write_bytes(plistlib.dumps(value, sort_keys=True))


def entitlement_plist(data):
    start = data.find(b"<?xml")
    if start < 0:
        start = data.find(b"<plist")
    end = data.find(b"</plist>", start)
    if start < 0 or end < 0:
        raise SigningError("Invalid entitlement output from codesign.")
    return plistlib.loads(data[start:end + len(b"</plist>")])


def signed_entitlements(path):
    p = run(["codesign", "-d", "--entitlements", ":-", path], check=False)
    if p.returncode:
        details = (p.stderr + p.stdout).decode(errors="replace")
        if "not signed at all" in details:
            return {}
        raise SigningError(f"Cannot inspect code signature: {path}: {details}")
    data = p.stdout + p.stderr
    if b"<plist" not in data:
        return {}
    return entitlement_plist(data)


def validate_zip(path):
    """Reject traversal, special files, symlink escapes and enormous archives."""
    with zipfile.ZipFile(path) as z:
        seen = set()
        total = 0
        links = {PurePosixPath(i.filename).as_posix().casefold() for i in z.infolist()
                 if stat.S_ISLNK(i.external_attr >> 16)}
        for item in z.infolist():
            name = PurePosixPath(item.filename)
            if any(parent.as_posix().casefold() in links for parent in name.parents):
                raise SigningError("IPA entry would be extracted through a symlink.")
            if (name.is_absolute() or ".." in name.parts or "\\" in item.filename
                    or "\x00" in item.filename):
                raise SigningError("Unsafe IPA archive path.")
            normalized = str(name).casefold()
            if normalized in seen:
                raise SigningError("Duplicate/case-colliding IPA archive path.")
            seen.add(normalized)
            total += item.file_size
            mode = item.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK):
                raise SigningError("IPA contains a special device/file.")
            if item.flag_bits & 1 or total > 8 * 1024**3:
                raise SigningError("Encrypted or excessively large IPA.")
            if stat.S_ISLNK(mode):
                if item.file_size > 4096:
                    raise SigningError("Oversized IPA symlink.")
                target = z.read(item).decode("utf-8")
                if target.startswith("/") or "\\" in target:
                    raise SigningError("Unsafe IPA symlink.")
                stack = list(name.parent.parts)
                for part in PurePosixPath(target).parts:
                    if part == "..":
                        if not stack:
                            raise SigningError("IPA symlink escapes extraction directory.")
                        stack.pop()
                    elif part != ".":
                        stack.append(part)


def check_links(root):
    root = root.resolve()
    for path in root.rglob("*"):
        if path.is_symlink():
            try:
                path.resolve(strict=True).relative_to(root)
            except (ValueError, FileNotFoundError, RuntimeError):
                raise SigningError(f"Broken or escaping symlink: {path}")


def info(path):
    return read_plist(path / "Info.plist")


def app_bundles(app):
    extensions = sorted(app.rglob("*.appex"))
    apps = [p for p in app.rglob("*.app") if p != app]
    if apps:
        raise SigningError("Nested apps/watch apps need separate provisioning; unsupported in this project.")
    return [app, *extensions]


def bundle_ids(app, new_id=None, overrides=None):
    bundles = app_bundles(app)
    old_root = info(app)["CFBundleIdentifier"]
    ids = {}
    for bundle in bundles:
        old = info(bundle)["CFBundleIdentifier"]
        new = (overrides or {}).get(old)
        if new is None:
            if bundle != app and not old.startswith(old_root + "."):
                raise SigningError(f"Bundle Identifier mismatch: {old} is not a child of {old_root}.")
            new = (new_id + old[len(old_root):]) if new_id else old
        if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", new):
            raise SigningError(f"Invalid Bundle Identifier: {new}")
        ids[bundle] = new
    if len(set(ids.values())) != len(ids):
        raise SigningError("Duplicate Bundle Identifiers.")
    root_id = ids[app]
    if any(not v.startswith(root_id + ".") for p, v in ids.items() if p != app):
        raise SigningError("Extension Bundle Identifier must begin with the main app ID plus '.'.")
    return ids


def decode_profile(path):
    p = run(["security", "cms", "-D", "-i", path])
    try:
        return {"path": Path(path), "data": plistlib.loads(p.stdout)}
    except plistlib.InvalidFileException:
        raise SigningError(f"Invalid provisioning profile: {path}")


def identities():
    p = run(["security", "find-identity", "-v", "-p", "codesigning"])
    rows = []
    for fingerprint, name in re.findall(r'([0-9A-Fa-f]{40})\s+"([^"]+)"', p.stdout.decode()):
        if not name.startswith(("Apple Development:", "iPhone Developer:")):
            continue
        match = re.search(r"\(([A-Z0-9]{10})\)$", name)
        team = match.group(1) if match else None
        if team is None:
            cert = run(["security", "find-certificate", "-c", name, "-p"])
            subject = subprocess.run(["openssl", "x509", "-noout", "-subject",
                                      "-nameopt", "sep_multiline"], input=cert.stdout,
                                     capture_output=True)
            match = re.search(r"OU\s*=\s*([A-Z0-9]{10})", subject.stdout.decode())
            team = match.group(1) if match else None
        if team:
            rows.append({"sha": fingerprint.upper(), "name": name, "team": team})
    return rows


def choose_identity(rows, team=None, identity=None):
    rows = [r for r in rows if (not team or r["team"] == team)
            and (not identity or identity in (r["sha"], r["name"]))]
    if not rows:
        raise SigningError("No signing certificate: create Apple Development in Xcode → Settings → "
                           "Accounts → Manage Certificates; the private key must be in your Keychain.")
    if len(rows) == 1:
        return rows[0]
    if not sys.stdin.isatty():
        raise SigningError("Multiple signing certificates/teams. Specify --team-id and --identity SHA1.")
    for n, row in enumerate(rows, 1):
        print(f"{n}: {row['name']} / {row['sha']} / Team {row['team']}")
    try:
        n = int(input("Signing identity number: "))
        if not 1 <= n <= len(rows):
            raise ValueError()
        return rows[n - 1]
    except ValueError:
        raise SigningError("Invalid signing identity selection.")


def permitted(wanted, allowed):
    if isinstance(wanted, bool):
        return isinstance(allowed, bool) and wanted == allowed
    if isinstance(wanted, str):
        return isinstance(allowed, str) and (wanted == allowed or
               (allowed.endswith("*") and wanted.startswith(allowed[:-1])))
    if isinstance(wanted, list):
        return isinstance(allowed, list) and all(
            any(permitted(v, a) for a in allowed) for v in wanted)
    if isinstance(wanted, dict):
        return isinstance(allowed, dict) and all(
            k in allowed and permitted(v, allowed[k]) for k, v in wanted.items())
    return type(wanted) is type(allowed) and wanted == allowed


def validate_entitlements(wanted, profile):
    allowed = profile["Entitlements"]
    for key, value in wanted.items():
        if key not in allowed or not permitted(value, allowed[key]):
            raise SigningError(f"Unsupported entitlement: {key}={value!r}. "
                               "Use an Xcode profile that permits it. No entitlement was silently removed.")


def validate_profile(profile, bid, identity, device=None, now=None):
    data = profile["data"]
    now = now or dt.datetime.now(dt.timezone.utc)
    expiry = data.get("ExpirationDate")
    if not isinstance(expiry, dt.datetime) or expiry.replace(tzinfo=dt.timezone.utc) <= now:
        raise SigningError(f"Expired/invalid provisioning profile: {profile['path']}")
    if identity["team"] not in data.get("TeamIdentifier", []):
        raise SigningError("Provisioning profile Team ID mismatch.")
    hashes = {hashlib.sha1(c).hexdigest().upper() for c in data.get("DeveloperCertificates", [])}
    if identity["sha"] not in hashes:
        raise SigningError("Provisioning profile does not include the chosen signing certificate.")
    prefixes = data.get("ApplicationIdentifierPrefix", [])
    allowed = data.get("Entitlements", {}).get("application-identifier", "")
    prefix = next((p for p in prefixes if permitted(p + "." + bid, allowed)), None)
    if not prefix:
        raise SigningError(f"Bundle Identifier mismatch: {bid} / {allowed}")
    devices = data.get("ProvisionedDevices", [])
    if not devices or data.get("Entitlements", {}).get("get-task-allow") is not True:
        raise SigningError("A device development profile with get-task-allow is required.")
    if device and device not in devices:
        raise SigningError("The iPhone UDID is not in this provisioning profile.")
    return prefix


def requested_entitlements(app, bundle):
    # Ad-hoc CI archives may have no entitlement blob; preserve project requirements.
    manifest = app / "SigningRequirements.plist"
    if manifest.exists():
        policies = read_plist(manifest)
        key = "." if bundle == app else bundle.relative_to(app).as_posix()
        if key not in policies:
            raise SigningError(f"Missing signing requirement for {key}.")
        required = policies[key]
    elif bundle == app:
        required = {MEMORY: True}
    elif bundle.name == "Reynard Helper.appex":
        required = {"get-task-allow": True}
    elif bundle.name == "OpenIn.appex":
        required = {}
    else:
        raise SigningError(f"Unknown extension requirements: {bundle.name}")
    actual = signed_entitlements(bundle)
    for key, value in required.items():
        if key in actual and actual[key] != value:
            raise SigningError(f"Existing signature conflicts with required entitlement: {key}")
    return {**actual, **required}


def make_entitlements(requested, profile, bid, identity, prefix, old_bid, omissions):
    ent = dict(requested)
    for key in omissions:
        if key not in ent:
            raise SigningError(f"Cannot omit absent entitlement: {bid}:{key}")
        if key in MANAGED:
            raise SigningError(f"Cannot omit required signing identity/debug entitlement: {key}")
        print(f"WARNING: explicitly omitting {bid}:{key}; memory/JIT/features may fail.", file=sys.stderr)
        del ent[key]
    # Identity entitlements belong to the new profile, never the former signer.
    ent["application-identifier"] = prefix + "." + bid
    ent["com.apple.developer.team-identifier"] = identity["team"]
    ent["get-task-allow"] = True
    groups = ent.get("keychain-access-groups")
    if groups:
        # Only rewrite the former default app group; never guess custom access groups.
        ent["keychain-access-groups"] = [
            prefix + "." + bid if g.endswith("." + old_bid) else g for g in groups]
    validate_entitlements(ent, profile["data"])
    return ent


def profile_paths(extra):
    dirs = [Path.home() / "Library/MobileDevice/Provisioning Profiles",
            Path.home() / "Library/Developer/Xcode/UserData/Provisioning Profiles",
            *map(Path, extra)]
    return sorted({p for d in dirs if d.exists() for p in d.rglob("*.mobileprovision")})


def select_profile(profiles, bid, identity, device, requested, old_bid, omissions):
    candidates, errors = [], []
    for p in profiles:
        try:
            prefix = validate_profile(p, bid, identity, device)
            ent = make_entitlements(requested, p, bid, identity, prefix, old_bid, omissions)
            candidates.append((p, ent))
        except SigningError as e:
            errors.append(f"{p['path'].name}: {e}")
    if not candidates:
        raise SigningError(f"No provisioning profile for {bid}.\n" +
                           "\n".join(errors[:8]) + "\nCreate profiles with the Xcode preparation project "
                           "or specify --profile BUNDLE_ID=PATH. See docs/LOCAL_SIGNING.md.")
    candidates.sort(key=lambda x: (not x[0]["data"]["Entitlements"]["application-identifier"].endswith("*"),
                                  x[0]["data"]["ExpirationDate"]), reverse=True)
    return candidates[0]


def macho(path):
    if not path.is_file():
        return False
    with path.open("rb") as f:
        return f.read(4) in MAGIC


def signing_order(app):
    """Sign leaf Mach-O files, then nested bundles, then provisioning bundles."""
    provisioned = set(app_bundles(app))
    bundles = [p for p in app.rglob("*") if not p.is_symlink() and p.is_dir()
               and p.suffix in (".framework", ".xpc", ".bundle") and (p / "Info.plist").exists()
               and info(p).get("CFBundleExecutable")
               and macho(p / info(p)["CFBundleExecutable"])]
    # Framework bundle signing covers its executable; don't sign that twice.
    covered = set()
    for bundle in [*provisioned, *bundles]:
        executable = info(bundle).get("CFBundleExecutable")
        if executable:
            covered.add((bundle / executable).resolve())
    leaves = [p for p in app.rglob("*") if not p.is_symlink() and macho(p)
              and p.resolve() not in covered]
    return sorted([*leaves, *bundles, *provisioned], key=lambda p: len(p.parts), reverse=True)


def parse_map(items, label):
    result = {}
    for item in items:
        if "=" not in item:
            raise SigningError(f"{label} expects BUNDLE_ID=VALUE.")
        key, value = item.split("=", 1)
        if not key or not value or key in result:
            raise SigningError(f"Invalid/duplicate {label}: {item}")
        result[key] = value
    return result


def dylib_dependencies(path):
    output = run(["otool", "-L", path]).stdout.decode()
    return [line.strip().rsplit(" (", 1)[0] for line in output.splitlines()[1:]
            if " (" in line]


def normalize_xul_for_sideloading(app):
    """On an unsigned staging copy, make XUL discoverable to suffix-based signers.

    Rewrite all Mach-O consumers, including Helper and GeckoView. The engine
    cache and xcarchive stay untouched. Every modified executable needs signing.
    """
    old = app / "Frameworks/XUL"
    new = app / "Frameworks/XUL.dylib"
    if not old.exists():
        return
    if old.is_symlink() or not macho(old) or new.exists():
        raise SigningError("Unexpected XUL layout; cannot prepare sideloadable engine.")
    binaries = [p for p in app.rglob("*") if not p.is_symlink() and macho(p)]
    dependencies = {p: dylib_dependencies(p) for p in binaries}
    old.rename(new)
    run(["install_name_tool", "-id", "@rpath/XUL.dylib", new])
    for original, names in dependencies.items():
        path = new if original == old else original
        for name in names:
            if name.startswith("@") and name.endswith("/XUL"):
                run(["install_name_tool", "-change", name, name + ".dylib", path])
    # A filename-only rename would still crash dyld. Check the written commands.
    for path in binaries:
        path = new if path == old else path
        if any(name.endswith("/XUL") for name in dylib_dependencies(path)):
            raise SigningError(f"Stale XUL load command after packaging: {path.name}")
    if "@rpath/XUL.dylib" not in dylib_dependencies(new):
        raise SigningError("XUL dylib install name was not updated.")
    print("Prepared Frameworks/XUL.dylib and all Mach-O load commands for re-signing")


def package_archive(archive, output):
    apps = list((Path(archive) / "Products/Applications").glob("*.app"))
    if len(apps) != 1:
        raise SigningError("Expected one .app in archive Products/Applications.")
    # This entry point is specifically unsigned packaging; never alter a signed archive.
    if any(apps[0].rglob("embedded.mobileprovision")):
        raise SigningError("Signed archive detected. Use Xcode exportArchive; do not unsigned-package it.")
    bundle_ids(apps[0])
    with tempfile.TemporaryDirectory(prefix="tor-package-") as d:
        payload = Path(d) / "Payload"
        payload.mkdir()
        dest = payload / apps[0].name
        run(["ditto", apps[0], dest])
        normalize_xul_for_sideloading(dest)
        write_plist(dest / "SigningRequirements.plist", {
            ".": {MEMORY: True}, "PlugIns/Reynard Helper.appex": {"get-task-allow": True},
            "PlugIns/OpenIn.appex": {}})
        # Remove ad-hoc resource seals; this output explicitly requires local signing.
        for signature in dest.rglob("_CodeSignature"):
            if signature.is_dir() and not signature.is_symlink():
                shutil.rmtree(signature)
        run(["ditto", "-c", "-k", "--keepParent", "--norsrc", payload, output])
    print(f"Unsigned IPA: {output} (Bundle IDs preserved; no archive files modified)")


def sign(args):
    config = json.loads(Path(args.config).read_text()) if args.config else {}
    identity = choose_identity(identities(), args.team_id or config.get("team_id"),
                               args.identity or config.get("identity"))
    explicit = {**config.get("profiles", {}), **parse_map(args.profile, "--profile")}
    overrides = {**config.get("bundle_ids", {}), **parse_map(args.bundle_map, "--bundle-map")}
    profile_files = set(profile_paths(args.profile_dir)) | {Path(x).expanduser() for x in explicit.values()}
    profiles = []
    for file in profile_files:
        try:
            profiles.append(decode_profile(file))
        except SigningError as e:
            if str(file) in explicit.values():
                raise
            print(f"Skipping unreadable profile {file.name}: {e}", file=sys.stderr)
    validate_zip(args.input)
    output = Path(args.output).expanduser().resolve()
    app_output = Path(args.app_output).expanduser().resolve() if args.app_output else output.with_suffix(".app")
    if output.exists() or app_output.exists():
        raise SigningError("Output already exists. Choose new --output/--app-output paths.")
    output.parent.mkdir(parents=True, exist_ok=True)
    app_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tor-sign-") as d:
        work = Path(d)
        run(["ditto", "-x", "-k", args.input, work])
        check_links(work)
        apps = list((work / "Payload").glob("*.app"))
        if len(apps) != 1:
            raise SigningError("IPA must contain exactly one main app.")
        app = apps[0]
        ids = bundle_ids(app, args.bundle_id or config.get("bundle_id"), overrides)
        plans = {}
        omit_map = {}
        for item in args.omit_entitlement:
            if ":" not in item:
                raise SigningError("--omit-entitlement expects FINAL_BUNDLE_ID:KEY.")
            bid, key = item.split(":", 1)
            omit_map.setdefault(bid, []).append(key)
        if set(omit_map) - set(ids.values()):
            raise SigningError("Entitlement omission references an unknown Bundle ID.")
        for bundle, bid in ids.items():
            old = info(bundle)["CFBundleIdentifier"]
            requested = requested_entitlements(app, bundle)
            manual = explicit.get(bid)
            pool = [p for p in profiles if p["path"].resolve() == Path(manual).expanduser().resolve()] if manual else profiles
            plans[bundle] = select_profile(pool, bid, identity, args.device, requested, old, omit_map.get(bid, []))
        if set(explicit) - set(ids.values()) or set(overrides) - {info(b)["CFBundleIdentifier"] for b in ids}:
            raise SigningError("Profile/bundle mapping references an unknown Bundle Identifier.")
        devices = [set(p["data"]["ProvisionedDevices"]) for p, _ in plans.values()]
        common = set.intersection(*devices)
        if not common:
            raise SigningError("App and extension profiles do not share any provisioned iPhone.")
        order = signing_order(app)
        # Inspect every executable before signing; preserve and validate nested entitlements.
        nested = {}
        for path in order:
            if path in plans:
                continue
            ent = signed_entitlements(path)
            if any(k in MANAGED for k in ent):
                raise SigningError(f"Unexpected identity entitlements on nested executable {path.name}.")
            validate_entitlements(ent, plans[app][0]["data"])
            nested[path] = ent
        print(f"Team: {identity['team']} / certificate: {identity['name']}")
        print(f"Common provisioned devices: {len(common)}" + (f" / requested UDID: {args.device}" if args.device else ""))
        for bundle, bid in ids.items():
            data = info(bundle)
            data["CFBundleIdentifier"] = bid
            write_plist(bundle / "Info.plist", data)
            profile, ent = plans[bundle]
            shutil.copyfile(profile["path"], bundle / "embedded.mobileprovision")
            print(f"{bid}: {profile['data'].get('Name', '')} / expires {profile['data']['ExpirationDate'].isoformat()}")
        # All plist/profile/resource mutations are complete before the first signature.
        for n, path in enumerate(order):
            ent = plans[path][1] if path in plans else nested[path]
            command = ["codesign", "--force", "--sign", identity["sha"], "--timestamp=none",
                       "--generate-entitlement-der"]
            if ent:
                ent_file = work / f"entitlements-{n}.plist"
                write_plist(ent_file, ent)
                command += ["--entitlements", ent_file]
            run([*command, path])
        for path in order:
            run(["codesign", "--verify", "--strict", "--verbose=2", path])
            expected = plans[path][1] if path in plans else nested[path]
            if signed_entitlements(path) != expected:
                raise SigningError(f"Invalid code signature: signed Entitlements differ for {path.name}")
            details = run(["codesign", "-d", "--verbose=4", path]).stderr.decode()
            if f"TeamIdentifier={identity['team']}" not in details:
                raise SigningError(f"Invalid code signature: Team Identifier differs for {path.name}")
        for bundle, bid in ids.items():
            if info(bundle)["CFBundleIdentifier"] != bid:
                raise SigningError("Bundle Identifier changed after signing.")
            embedded = decode_profile(bundle / "embedded.mobileprovision")
            validate_profile(embedded, bid, identity, args.device)
            validate_entitlements(signed_entitlements(bundle), embedded["data"])
        # Publish only after all signatures pass. ditto preserves signed resources.
        staged_ipa = work / "signed.ipa"
        run(["ditto", "-c", "-k", "--keepParent", "--norsrc", work / "Payload", staged_ipa])
        try:
            run(["ditto", app, app_output])
            for path in signing_order(app_output):
                run(["codesign", "--verify", "--strict", path])
            shutil.copyfile(staged_ipa, output)
        except Exception:
            if app_output.exists():
                shutil.rmtree(app_output)
            if output.exists():
                output.unlink()
            raise
    print(f"Verified IPA: {output}\nInstallable app: {app_output}")
    print("Personal Team profiles normally expire after 7 days; renew and re-sign before expiry.")
    print(f'Install: xcrun devicectl device install app --device <UDID> "{app_output}"')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--app-output")
    parser.add_argument("--team-id")
    parser.add_argument("--identity", help="Apple Development name or SHA-1")
    parser.add_argument("--bundle-id", help="new main ID; child extension suffixes preserved")
    parser.add_argument("--bundle-map", action="append", default=[], help="OLD_ID=NEW_ID")
    parser.add_argument("--profile", action="append", default=[], help="FINAL_ID=PATH")
    parser.add_argument("--profile-dir", action="append", default=[])
    parser.add_argument("--device", help="iPhone UDID; verify every profile includes it")
    parser.add_argument("--config", help="local JSON; never commit credentials/profiles")
    parser.add_argument("--omit-entitlement", action="append", default=[], help="FINAL_ID:KEY; explicit feature degradation")
    parser.add_argument("--package-archive", action="store_true")
    parser.add_argument("--archive")
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        raise SigningError("macOS and full Xcode are required. This script does not authenticate with Apple.")
    for tool in ("security", "codesign", "ditto", "xcrun"):
        if not shutil.which(tool):
            raise SigningError(f"Missing official Apple tool: {tool}; install/select full Xcode.")
    if args.package_archive:
        if not args.archive:
            parser.error("--package-archive requires --archive")
        if Path(args.output).exists():
            raise SigningError("Output already exists.")
        package_archive(args.archive, Path(args.output).resolve())
    else:
        if not args.input:
            parser.error("--input is required")
        sign(args)


if __name__ == "__main__":
    try:
        main()
    except (SigningError, OSError, ValueError, KeyError, plistlib.InvalidFileException, zipfile.BadZipFile) as e:
        print(f"Signing stopped: {e}", file=sys.stderr)
        sys.exit(1)
