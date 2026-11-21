#!/usr/bin/env python3
"""Native Display13 SCDC request/address gate; rejected A9 experiment.

Only validates code generation; it does not contact a real monitor.
Upstream native implementation deliberately uses A8/A8 in IOI2CRequest.
"""
from pathlib import Path
helper=Path("Source/WhateverXe/kern_yoga_hdmi2_candidate.hpp").read_text()
source=Path("Source/WhateverXe/kern_xe.cpp").read_text()
assert helper.count("request.sendAddress=0xA8;")==1
assert helper.count("request.replyAddress=0xA8;")==1
assert "request.replyAddress=0xA9;" not in helper
assert "request.replyTransactionType=1;" in helper
assert "request.sendTransactionType=1;" in helper
assert source.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
assert source.index('display13FBTCHooksReady=processDisplay13FramebufferTC(patcher,index,address,size);')<source.index('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')
print("PASS: native SCDC request 0xA8/0xA8 preserved; A9 hypothesis rejected")
print("NOTE: SCDC SinkVersionReadFailed(34) still unresolved; GMBUS NAK/status analysis required")
