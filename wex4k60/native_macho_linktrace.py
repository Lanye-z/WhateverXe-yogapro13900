#!/usr/bin/env python3
"""Bounded, read-only follow-up of original Display13 HDMI helper CALL targets.

Usage:
  python3 wex4k60/native_macho_linktrace.py --out ~/Desktop/Yoga_Display13_HDMI_HelperTrace.json

Requires the same installed Mach-O whose UUID + SHA-256 were verified by the
2026-11-20 HDMI30 baseline. Reads local file bytes only. Never installs
Kexts, routes functions, switches modes, probes hardware, or edits EFI.

Candidate helpers are actual direct CALL targets in user-uploaded native
instructions; names here denote investigation order, NOT verified semantics.
"""
import argparse
import hashlib
import json
from pathlib import Path

from native_macho_audit import DEFAULTS, EXPECTED_UUID, MachOError, image_bytes, parse_macho
from native_macho_deep import REFERENCE_SHA256

WINDOWS=(
    ("called_from_LightUpTMDS_0x50b98",0x48BB6,0x1000),
    ("called_from_LightUpTMDS_0x50bda",0x52106,0x800),
    ("called_from_LightUpTMDS_0x50b40",0x6CCB4,0x700),
    ("called_from_LightUpTMDS_0x50b87",0x65FD4,0x600),
    ("called_from_dispatch_0x4fec7",0x4D34C,0x600),
)

def collect(data,require_baseline=True):
    parsed=parse_macho(data)
    digest=hashlib.sha256(data).hexdigest()
    valid=parsed["uuid"]==EXPECTED_UUID and digest==REFERENCE_SHA256
    if require_baseline and not valid:
        raise MachOError("native Apple driver UUID/SHA256 mismatch; refusing helper trace")
    result={
       "schema":1,
       "object":"AppleIntelTGLGraphicsFramebuffer",
       "uuid":parsed["uuid"],"sha256":digest,
       "exact_baseline_match":valid,
       "meaning":"Original x86_64 Mach-O code bytes only; target identities are investigational.",
       "windows":[]
    }
    for label,offset,length in WINDOWS:
        raw=image_bytes(data,parsed,offset,length)
        result["windows"].append({
            "label":label,
            "image_offset":"0x%X"%offset,
            "length":length,
            "sha256":hashlib.sha256(raw).hexdigest(),
            "hex":raw.hex()
        })
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("path",nargs="?",help="native AppleIntelTGLGraphicsFramebuffer Mach-O")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    paths=[Path(args.path).expanduser()] if args.path else [Path(i) for i in DEFAULTS]
    path=next((x for x in paths if x.is_file()),None)
    if path is None:
        p.error("original native Apple framebuffer not found; supply the file path")
    try:
        record=collect(path.read_bytes())
    except MachOError as err:
        p.error(str(err))
    destination=args.out.expanduser()
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
    print("Native donor UUID/SHA256 match: True")
    print("Verified, bounded helper windows:",len(record["windows"]))
    print("Saved:",destination)
    print("No graphics driver, display settings, NVRAM or EFI modified.")

if __name__=="__main__":
    main()
