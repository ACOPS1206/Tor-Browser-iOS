#!/usr/bin/env python3
"""Compact copied omni.ja before code signing using Gecko-supported DEFLATE.

Never touch engine cache inputs. Keep the original if it is already smaller.
Do not wrap the resource in XZ: iOS startup has no Android XzExtractor.
"""
import copy
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import zipfile


def contents(archive):
    result = []
    for entry in archive.infolist():
        digest = hashlib.sha256()
        with archive.open(entry) as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        result.append((entry.filename, entry.file_size, digest.digest()))
    return result


def compact(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a regular copied omni.ja file')
    before = path.stat().st_size
    fd, candidate = tempfile.mkstemp(prefix='.omni-', suffix='.ja', dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(path) as source:
            entries = source.infolist()
            if len({entry.filename for entry in entries}) != len(entries):
                raise ValueError('Duplicate resource names in omni.ja')
            expected = contents(source)
            with zipfile.ZipFile(candidate, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
                target.comment = source.comment
                for entry in entries:
                    info = copy.copy(entry)
                    info.compress_type = zipfile.ZIP_STORED if entry.is_dir() else zipfile.ZIP_DEFLATED
                    # ZipInfo carries the per-entry level; set it explicitly.
                    info._compresslevel = 9
                    with source.open(entry) as src, target.open(info, 'w') as dst:
                        while chunk := src.read(1024 * 1024):
                            dst.write(chunk)
            with zipfile.ZipFile(candidate) as verified:
                if contents(verified) != expected or verified.comment != source.comment:
                    raise ValueError('Resource verification failed; original retained')
        after = os.path.getsize(candidate)
        if after < before:
            os.chmod(candidate, stat.S_IMODE(path.stat().st_mode))
            os.replace(candidate, path)
        else:
            after = before
        return before, after
    finally:
        if os.path.exists(candidate):
            os.unlink(candidate)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('omni_jar')
    args = parser.parse_args()
    before, after = compact(args.omni_jar)
    print(f'Gecko resources: {before} -> {after} bytes; saved {before - after} bytes (before signing)')
