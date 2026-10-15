# Bundled NoScript

Unmodified official Tor-update-channel release: **13.6.36.1984**.

- Publisher: Giorgio Maone / hackademix.
- Release: https://github.com/hackademix/noscript/releases/tag/13.6.36
- Download: https://github.com/hackademix/noscript/releases/download/13.6.36/noscript-13.6.36.1984.xpi
- SHA-256: `e6ab6f57074aaf502e4615f904d91d0c2b411e748284838f224171256f5afd60`
- Digest was compared with the release asset metadata, asset ID 603015060.
- Official site links this release: https://noscript.net/getit/
- Corresponding source: https://github.com/hackademix/noscript/tree/13.6.36 (including the pinned nscl submodule).
- Minimum Gecko: 115; this application pins 157.0.1. API behavior still requires runtime testing.

The original XPI includes COPYRIGHT, LICENSE, and Mozilla signature material.
`bundle-noscript.py` verifies the digest and manifest identity, then extracts the
original files without alteration. The license and notices are included in the
app alongside the extension. The digest check is integrity verification, not an
independent cryptographic verification of Mozilla's signature chain.

No startup download or automatic background update is used. Updating the
bundled release requires a reviewed package/hash/version update and app build.
