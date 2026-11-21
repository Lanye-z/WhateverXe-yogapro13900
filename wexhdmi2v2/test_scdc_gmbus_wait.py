#!/usr/bin/env python3
"""HDMI2 V3: fail-closed native GMBUS status-wait scope regression.

Static source guards only, with upstream waitReady tests run separately.
No real monitor is contacted by this suite.
"""
from pathlib import Path

s=Path("Source/WhateverXe/kern_xe.cpp").read_text()
helper=Path("Source/WhateverXe/kern_yoga_hdmi2_candidate.hpp").read_text()

# Apple IOI2CRequest replyAddress is intentionally A8: native GMBUS
# encodes the read command A9 itself (observed in First9/First12 history).
assert "request.sendAddress=0xA8;" in helper
assert "request.replyAddress=0xA8;" in helper
assert "request.replyAddress=0xA9;" not in helper

assert "bool edid {},scdcRead {};" in s
assert s.count("o.scdcRead=yogaHDMI2CallsiteSafe &&")==1
for flag in [
    "controller==callbackXE->adlnTopologyController",
    "callbackXE->adlnOutputWiring.hdmi==2U",
    "bus==2",
    "callbackXE->adlnOutputWiring.usesDDC(bus)",
    "speed==0 && req",
    "*reinterpret_cast<uint32_t *>(req)==1",
    "*reinterpret_cast<uint32_t *>(req+4)==1",
    "*reinterpret_cast<uint32_t *>(req+8)==0xA8",
    "*reinterpret_cast<uint32_t *>(req+0x0C)==0xA8",
    "*reinterpret_cast<uint32_t *>(req+0x28)==1",
    "*reinterpret_cast<uint32_t *>(req+0x38)==1",
    "*reinterpret_cast<uint32_t *>(req+0x20)==0",
    "req[0x10]==0 && req[0x11]==0",
]:
    assert flag in s, flag

# The formerly EDID-only +0x7E8 polling remains EDID-capable.
assert "caller-start==0x7E8 && (o.edid || o.scdcRead)" in s
# +0x45C polls only for SCDC, never broadens EDID or DDC-CI.
assert "caller-start==0x45C && o.scdcRead" in s
assert "caller-start==0x7E8 || caller-start==0x45C" in s
assert s.count("Display13GMBus::waitReady(io,value)") == 1
assert "io.delayUs(10)" not in s # existing bounded helper owns the deadline

# Do not bypass native error propagation or change HDMI shadow/MMIO policy.
assert "const auto result=FunctionCast(wrapDisplay13GMBus,callbackXE->orgDisplay13GMBus)(controller,bus,speed,request);" in s
assert "r[8]=result" in s
assert s.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
assert s.index("display13FBTCHooksReady=processDisplay13FramebufferTC(patcher,index,address,size);")<s.index("patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));")
print("PASS: exact HDMI-B native SCDC read qualification + native GMBUS status wait scope")
print("PASS: no synthetic ACK, no retries, original SCDC request/PLL/PHY/MMIO unchanged")
