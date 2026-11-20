#!/usr/bin/env python3
"""Read-only candidate xrefs of +0x12C in verified Display13 Apple Mach-O.

Matches are only byte-pattern candidates, NOT confirmed instructions or
DisplayPath references. Does not alter any system or display state.
"""
import argparse
import hashlib
import json
from pathlib import Path

from native_macho_audit import (
    DEFAULTS, EXPECTED_UUID, MachOError, image_bytes, parse_macho,
)
from native_macho_deep import REFERENCE_SHA256

NEEDLE = bytes.fromhex("2c010000")

def scan_text(data, macho, context=96, max_hits=256):
    hits = []
    count = 0
    sections = []
    for sec in macho["sections"]:
        if sec["name"] != "__text":
            continue
        size = sec["vmsize"]
        off = sec["fileoff"]
        if size <= 0 or off + size > macho["slice_size"]:
            raise MachOError("invalid __text file backing")
        code = data[macho["slice_start"] + off:macho["slice_start"] + off + size]
        if len(code) != size:
            raise MachOError("truncated __text section")
        sections.append({"section": sec["segment"] + ",__text", "size": size})
        start = 0
        while True:
            i = code.find(NEEDLE, start)
            if i < 0:
                break
            count += 1
            if len(hits) < max_hits:
                lo, hi = max(0, i-context), min(size, i+4+context)
                chunk = code[lo:hi]
                base = sec["vmaddr"] - macho["text_base"]
                hits.append({
                    "match_offset": "0x%X" % (base+i),
                    "window_offset": "0x%X" % (base+lo),
                    "displacement_index": i-lo,
                    "window_hex": chunk.hex(),
                    "window_sha256": hashlib.sha256(chunk).hexdigest(),
                    "section": sec["segment"] + ",__text",
                })
            start = i + 1
    if not sections:
        raise MachOError("no __text section: refusing segment-wide scan")
    return {"match_count": count, "truncated": count > max_hits,
            "sections": sections, "hits": hits}

def collect(data, context=96, max_hits=256):
    parsed = parse_macho(data)
    digest = hashlib.sha256(data).hexdigest()
    if parsed["uuid"] != EXPECTED_UUID or digest != REFERENCE_SHA256:
        raise MachOError("Apple framebuffer UUID/SHA mismatch: abort")
    result = {
        "schema": 1, "object": "AppleIntelTGLGraphicsFramebuffer",
        "uuid": parsed["uuid"], "sha256": digest,
        "exact_baseline_match": True,
        "needle_le": NEEDLE.hex(),
        "meaning": "Only displacement candidates, not proven xrefs or live MMIO.",
    }
    result.update(scan_text(data, parsed, context, max_hits))
    # Prior 0x4D34C capture stopped in the middle of an indirect call.
    tail = image_bytes(data, parsed, 0x4D920, 0x100)
    result["disable_tail"] = {
        "image_offset": "0x4D920", "hex": tail.hex(),
        "sha256": hashlib.sha256(tail).hexdigest(),
    }
    return result

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", help="original Apple framebuffer Mach-O")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--context", type=int, default=96)
    ap.add_argument("--max-hits", type=int, default=256)
    args = ap.parse_args()
    if not 32 <= args.context <= 256:
        ap.error("--context must be 32..256")
    if not 1 <= args.max_hits <= 512:
        ap.error("--max-hits must be 1..512")
    paths = [Path(args.path).expanduser()] if args.path else [Path(p) for p in DEFAULTS]
    path = next((x for x in paths if x.is_file()), None)
    if path is None:
        ap.error("native Apple framebuffer not found: give exact path")
    try:
        report = collect(path.read_bytes(), args.context, args.max_hits)
    except MachOError as error:
        ap.error(str(error))
    out = args.out.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print("Verified original Apple Mach-O UUID/SHA: True")
    print("Candidate +0x12C matches:", report["match_count"])
    print("Truncated:", report["truncated"])
    print("Saved:", out)
    print("No display, EFI, NVRAM, MMIO or Kext changes.")

if __name__ == "__main__":
    main()
