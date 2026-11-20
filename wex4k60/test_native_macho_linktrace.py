#!/usr/bin/env python3
"""Synthetic Mach-O checks: the HDMI helper trace is bounded and fail-closed."""
import struct
import uuid
from pathlib import Path
import native_macho_audit as base
import native_macho_linktrace as helper

assert len(helper.WINDOWS)==5
assert len({address for _,address,_ in helper.WINDOWS})==5
assert all(0<length<=0x1000 for _,_,length in helper.WINDOWS)

data=bytearray(0x80000)
struct.pack_into("<IiiIIIII",data,0,0xFEEDFACF,0x01000007,3,0xB,2,96,0,0)
struct.pack_into("<II16sQQQQiiII",data,32,0x19,72,b"__TEXT".ljust(16,b"\0"),
                 0,0x80000,0,0x80000,7,5,0,0)
struct.pack_into("<II16s",data,104,0x1B,24,uuid.UUID(base.EXPECTED_UUID).bytes)
out=helper.collect(data,require_baseline=False)
assert not out["exact_baseline_match"]
for w in out["windows"]:
    assert len(bytes.fromhex(w["hex"]))==w["length"]
try:
    helper.collect(data)
except base.MachOError as ex:
    assert "UUID/SHA256" in str(ex)
else:
    raise AssertionError("mismatching Mach-O was not rejected")
data[104+8] ^= 0xff
try:
    helper.collect(data)
except base.MachOError:
    pass
else:
    raise AssertionError("wrong Mach-O UUID was not rejected")

source=Path(helper.__file__).read_text()
for forbidden in ("subprocess", "sudo ", "nvram -", "kextload", "kmutil load",
                  "ioreg -w", "WriteRegister32", "setRefreshRate"):
    assert forbidden not in source,forbidden
print("PASS: five static helper ranges, exact SHA/UUID gate, bounds and no hardware mutation")
