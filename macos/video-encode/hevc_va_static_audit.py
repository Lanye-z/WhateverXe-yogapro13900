#!/usr/bin/env python3
"""Read-only hint scan of VA binaries; strings are NOT proof of code support.

This deliberately does not initialize AppleGVA or call any video encoder.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re

NEEDLES = (
    b"/HEVC/Decode/", b"/HEVC/Encode/",
    b"GVAHEVCEncodingImpl", b"GVAAVCEncodingImpl",
    b"codecHALEnableHEVCDecoder", b"codecHALEnableHEVCEncoder",
    b"AVCVDENC", b"HEVCVDENC", b"GVAVPHALPPCreateContext",
)


def read_only_scan(path: Path) -> None:
    content = path.read_bytes()
    print(f"FILE={path}")
    print(f"SIZE={len(content)}")
    print(f"SHA256={sha256(content).hexdigest()}")
    for token in NEEDLES:
        print(f"TOKEN={token.decode()} COUNT={content.count(token)}")
    references = re.findall(rb"[ -~]{12,}", content)
    for line in references:
        if b"/HEVC/" in line or (b"/AVC/" in line and b"Encode" in line):
            print(f"SOURCE_REF_HINT={line[:220].decode(errors='replace')}")
    print("INTERPRETATION=diagnostic hints only; absence of strings does NOT prove missing implementations")
    print("NO_EXECUTION=No provider initialization, video session or binary mutation performed")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("binary", nargs="?", type=Path, default=Path(
        "/Library/GPUBundles/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver"))
    a = p.parse_args()
    if not a.binary.is_file():
        p.error(f"file not found: {a.binary}")
    read_only_scan(a.binary)


if __name__ == "__main__":
    main()
