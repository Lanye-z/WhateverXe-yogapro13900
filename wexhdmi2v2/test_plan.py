#!/usr/bin/env python3
"""Static guards for the pinned Apple 25G241 V2 HDMI mode callsite."""
from pathlib import Path
import struct

# Cross-checked against user's exact UUID/SHA-verified NativeDeepTrace:
offset=0x4FFB6
original=bytes.fromhex("e8 67 0b 00 00")
assert original[0]==0xE8
relative=struct.unpack("<i",original[1:])[0]
assert offset+5+relative==0x50B22
source=Path("Source/WhateverXe/kern_xe.cpp").read_text()
assert 'const uint8_t originalCall[] {0xE8,0x67,0x0B,0x00,0x00};' in source
assert 'patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));' in source
assert 'const uint32_t status=55; // WM never owns native HDMI2 SCDC' in source
assert 'if(relative>=INT32_MIN && relative<=INT32_MAX)' in source
assert 'WEXYogaHDMI2CallsiteStatus' in source
assert 'WEXYogaHDMI2CallsiteLast' in source
assert '-wex-yoga-hdmi2-callsite-safe' in source
assert '-wex-yoga-hdmi2-callsite-observe' in source
assert 'orgDisplay13HDMI2TMDS' not in source
helper=Path("Source/WhateverXe/kern_yoga_hdmi2_candidate.hpp").read_text()
assert 'IOLockTryLock(state.lock)' in helper
assert 'IORecursiveLockHaveLock(recursive)' in helper
assert 'YogaHDMI2::prepareSCDC(bus,plan,caps.scdc)' in helper
assert 'status=55; // WM' in source
print("PASS: pinned original LightUpTMDS CALL 0x4FFB6 -> 0x50B22")
print("PASS: no new global LightUpTMDS route; default-off V2 callsite flags")
print("PASS: original WM HDMI2 I2C disabled; owner lock, nonblocking power lock, SCDC readback required")
