#!/usr/bin/env python3
"""Offline deterministic tests of the read-only native Mach-O verifier."""
import importlib.util
from pathlib import Path
import struct
import uuid

module_path=Path(__file__).with_name("native_macho_audit.py")
spec=importlib.util.spec_from_file_location("native_macho_audit",module_path)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def fake_macho():
    data=bytearray(0x70000)
    uuid_bytes=uuid.UUID(m.EXPECTED_UUID).bytes
    # MH_MAGIC_64, x86_64 kernel kext (filetype 0xB).
    # LC_SEGMENT_64 (__TEXT) + LC_UUID with no section records.
    struct.pack_into("<IiiIIIII",data,0,0xFEEDFACF,0x01000007,3,0xB,
                     2,72+24,0,0)
    struct.pack_into("<II16sQQQQiiII",data,32,0x19,72,
                     b"__TEXT".ljust(16,b"\0"),0,0x70000,
                     0,0x70000,7,5,0,0)
    struct.pack_into("<II16s",data,104,0x1B,24,uuid_bytes)
    for _name,at,prefix in m.TARGETS:
        data[at:at+8]=bytes.fromhex(prefix)
    ret=m.CALLSITE_RETURN
    disp=0x50B22-ret
    data[ret-5:ret]=b"\xe8"+struct.pack("<i",disp)
    return data

data=fake_macho()
out=m.audit_bytes(data)
assert out["uuid_matches_loaded_baseline"]
assert len(out["targets"])==5
assert all(t["first8_match"] and t["file_backed"] for t in out["targets"])
assert out["reference_callsite"]["direct_relative_call"]
assert out["reference_callsite"]["direct_call_targets_LightUpTMDS"]
assert out["reference_callsite"]["direct_call_target"]=="0x50B22"

data[0x50B22] = 0x90
bad=m.audit_bytes(data)
assert not next(t for t in bad["targets"] if t["name"]=="LightUpTMDS")["first8_match"]
assert bad["reference_callsite"]["direct_call_targets_LightUpTMDS"]

# No data beyond __TEXT may be read.
try:
    m.image_bytes(data,m.parse_macho(data),0x6FFF8,16)
except m.MachOError:
    pass
else:
    raise AssertionError("out-of-range read accepted")

# Thin-MachO rejection and x86_64 selection from a fat container.
fat=bytearray(0x80000)
fat[:8]=struct.pack(">II",0xCAFEBABE,1)
struct.pack_into(">IIIII",fat,8,0x01000007,3,0x1000,len(data),0)
fat[0x1000:0x1000+len(data)]=data
slice_start,slice_size=m.choose_arch(fat)
assert slice_start==0x1000 and slice_size==len(data)
assert m.parse_macho(fat)["slice_start"]==0x1000

for incorrect in (b"not a macho", b"", b"\xcf\xfa\xed\xfe"):
    try:
        m.audit_bytes(incorrect)
    except m.MachOError:
        pass
    else:
        raise AssertionError("invalid/truncated file accepted")

source=module_path.read_text()
assert "subprocess" not in source
for forbidden in ("sudo ", "nvram -", "kextload", "kmutil load",
                  "ioreg -w", "setRefreshRate", "WriteRegister32"):
    assert forbidden not in source

print("PASS: Mach-O thin/fat parser, UUID, function entries, call target, fail-closed bounds")
print("PASS: read-only code, no driver load, no EFI/NVRAM/display writes")
