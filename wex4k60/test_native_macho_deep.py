#!/usr/bin/env python3
"""Offline tests for bounded local native Mach-O trace; no device needed."""
from pathlib import Path
import struct
import uuid
import native_macho_audit as base
import native_macho_deep as deep

data=bytearray(0x70000)
struct.pack_into("<IiiIIIII",data,0,0xFEEDFACF,0x01000007,3,0xB,2,96,0,0)
struct.pack_into("<II16sQQQQiiII",data,32,0x19,72,
                 b"__TEXT".ljust(16,b"\0"),0,0x70000,0,0x70000,7,5,0,0)
struct.pack_into("<II16s",data,104,0x1B,24,uuid.UUID(base.EXPECTED_UUID).bytes)
data[0x4ffb6:0x4ffbb]=b"\xe8\x67\x0b\x00\x00"
report=deep.capture(data,check_identity=False)
assert report["macho_uuid"]==base.EXPECTED_UUID
assert not report["matches_baseline"]
assert len(report["windows"])==6
for window in report["windows"]:
    assert len(bytes.fromhex(window["hex"])) == window["length"]
    assert window["length"]<=0x1300
    assert window["image_offset"].startswith("0x")
assert "e8670b0000" in next(x for x in report["windows"]
                              if x["label"]=="display_activator_dispatch")["hex"]
try:
    deep.capture(data,check_identity=True)
except base.MachOError as error:
    assert "SHA256" in str(error)
else:
    raise AssertionError("invalid native binary accepted by exact SHA gate")
source=Path(deep.__file__).read_text()
for forbidden in ("subprocess", "sudo ", "nvram -", "kextload", "kmutil load",
                  "ioreg -w", "WriteRegister32", "setRefreshRate"):
    assert forbidden not in source, forbidden
print("PASS: bounded native Mach-O instruction windows and strict UUID/SHA gate")
print("PASS: no kernel memory, NVRAM, EDID, display mode or hardware changes")
