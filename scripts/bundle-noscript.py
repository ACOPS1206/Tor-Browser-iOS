#!/usr/bin/env python3
"""Verify and unpack the unmodified official release, without any network I/O."""
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

DIGEST = 'e6ab6f57074aaf502e4615f904d91d0c2b411e748284838f224171256f5afd60'
ID = '{73a6fe31-595d-460b-a920-fcc0f8843232}'

def bundle(package, destination):
    if hashlib.sha256(package.read_bytes()).hexdigest() != DIGEST:
        raise RuntimeError('Official NoScript archive hash mismatch')
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        if manifest['version'] != '13.6.36.1984' or manifest['browser_specific_settings']['gecko']['id'] != ID:
            raise RuntimeError('Unexpected NoScript release identity')
        for name in archive.namelist():
            p = Path(name)
            if p.is_absolute() or '..' in p.parts:
                raise RuntimeError('Unsafe archive member')
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        archive.extractall(destination)
    return manifest

if __name__ == '__main__':
    bundle(Path(sys.argv[1]), Path(sys.argv[2]))
