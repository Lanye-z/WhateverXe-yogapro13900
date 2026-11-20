#!/usr/bin/env python3
"""Read-only bounded native Display13 disassembly evidence collector.

This exports *selected code bytes* from the running-system-matching original
AppleIntelTGLGraphicsFramebuffer Mach-O.  It NEVER modifies EFI, Kexts,
registers, boot-args or display mode; it does not install software.

Usage (inside the existing research checkout):
  python3 wex4k60/native_macho_deep.py --out ~/Desktop/Yoga_Display13_NativeDeepTrace.json
  python3 wex4k60/native_macho_deep.py /exact/path/to/AppleIntelTGLGraphicsFramebuffer --out ...

Must NOT be given WhateverXe.kext.  The exact loaded UUID AND prior 4K30
native Mach-O SHA256 are required; a mismatch is a hard failure.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from native_macho_audit import DEFAULTS, EXPECTED_UUID, MachOError, image_bytes, parse_macho

REFERENCE_SHA256="115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e"

# Chosen to include the HDMI dispatcher and candidate high-TMDS dataflow.
# All values are *relative to __TEXT VM base*, not raw file offsets.
WINDOWS=(
    ("display_activator_dispatch",0x4FE80,0x220),
    ("LightUpTMDS",0x50B22,0x1300),
    ("setColorMode",0x491F2,0x500),
    ("hwDoI2CRequest",0x53A20,0x180),
    ("hwDoGMBusRequest",0x53A7C,0x380),
    ("getOnlineInfo",0x2E232,0x400),
)

def capture(data, check_identity=True):
    parsed=parse_macho(data)
    checksum=hashlib.sha256(data).hexdigest()
    if check_identity:
        if parsed["uuid"]!=EXPECTED_UUID:
            raise MachOError("UUID differs from verified HDMI30 baseline; refusing ungrounded trace")
        if checksum!=REFERENCE_SHA256:
            raise MachOError("SHA256 differs from locally audited Apple driver; refusing ungrounded trace")
    result={
       "schema":1,
       "object":"AppleIntelTGLGraphicsFramebuffer",
       "macho_uuid":parsed["uuid"],
       "expected_uuid":EXPECTED_UUID,
       "sha256":checksum,
       "matches_baseline":parsed["uuid"]==EXPECTED_UUID and checksum==REFERENCE_SHA256,
       "text_vmaddr": "0x%X"%parsed["text_base"],
       "windows":[],
       "notes":"Hex bytes from bounded static code windows only. Do not infer live SCDC or MMIO status; no hardware reads."
    }
    for label,offset,n in WINDOWS:
        data_bytes=image_bytes(data,parsed,offset,n)
        result["windows"].append({
           "label":label,
           "image_offset":"0x%X"%offset,
           "length":n,
           "sha256":hashlib.sha256(data_bytes).hexdigest(),
           "hex":data_bytes.hex()
        })
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path",nargs="?",help="path to native AppleIntelTGLGraphicsFramebuffer Mach-O")
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    paths=[Path(args.path).expanduser()] if args.path else [Path(p) for p in DEFAULTS]
    path=next((p for p in paths if p.is_file()),None)
    if path is None:
        parser.error("Apple native framebuffer executable not found; pass the explicit file path")
    try:
        report=capture(path.read_bytes())
    except MachOError as error:
        parser.error(str(error))
    dest=args.out.expanduser()
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("UUID/SHA256 exact baseline match:",report["matches_baseline"])
    print("Bounded static code windows:",len(report["windows"]))
    print("Saved read-only report:",dest)
    print("No display modes, NVRAM, EFI or kernel code were changed.")

if __name__=="__main__":
    main()
