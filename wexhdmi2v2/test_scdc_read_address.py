#!/usr/bin/env python3
"""Static check for the isolated, unverified SCDC reply-address hypothesis.

This test checks ONLY the generated source and does not contact I2C hardware.
The native Apple EDID reads have been observed to use even 8-bit reply
addresses successfully, so 0xA9 remains an experiment, NOT proven root cause.
"""
from pathlib import Path

helper=Path("Source/WhateverXe/kern_yoga_hdmi2_candidate.hpp").read_text()
source=Path("Source/WhateverXe/kern_xe.cpp").read_text()
assert helper.count("request.sendAddress=0xA8;")==1
assert helper.count("request.replyAddress=0xA9;")==1
assert "request.replyAddress=0xA8;" not in helper
assert "request.replyTransactionType=1;" in helper
assert "request.sendTransactionType=1;" in helper
assert source.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
assert source.index('display13FBTCHooksReady=processDisplay13FramebufferTC(patcher,index,address,size);')<source.index('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')
print("PASS: isolated SCDC 8-bit read address A9; verified no extra hook or change to CALL installation ordering")
print("NOTE: no real hardware result, native I2C semantics and 4K60 remain unproven")
