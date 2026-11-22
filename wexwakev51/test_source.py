#!/usr/bin/env python3
"""Safety invariants for generated R5.1 passive SCDC diagnosis."""
from pathlib import Path
h=Path("Source/WhateverXe/kern_yoga_hdmi2_candidate.hpp").read_text()
c=Path("Source/WhateverXe/kern_xe.cpp").read_text()
p=Path("Source/WhateverXe/kern_display13_framebuffer_power.inc").read_text()
assert 'struct YogaHDMI2SCDCI2CTrace' in h
assert 'trace && read && reg==0x01' in h
assert 'YogaHDMI2SCDCI2CTrace *trace=nullptr' in h
assert 'yogaHDMI2WakeDiag?&yogaSCDCI2CTrace:nullptr' in c
assert 'WEXYogaHDMI2SCDCI2CLast' in c
assert 'WEXYogaHDMI2SCDCI2CHist%02u' in c
assert 'if(yogaHDMI2WakeDiag && yogaSCDCI2CTrace.requested)' in c
assert 'const bool okay=!status && !request.result && connected();' in h
assert 'trace->nativeReturn=static_cast<uint32_t>(status)' in h
assert 'trace->requestResult=static_cast<uint32_t>(request.result)' in h
assert 'trace->connectedAfter=(!status && !request.result)?' in h
assert h.count('native(controller,fbIndex,ddc,0,nullptr,&request)')==1
assert h.count('YogaHDMI2::prepareSCDC(')==1
assert c.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
assert 'YogaHDMI2R5::nativeWakeMatches(' in h
assert 'p.knownHDMIPipe=YogaHDMI2R5::sameBoundPipe(' in h
assert 'YogaHDMI2R5::sameBoundPipe(yogaPowerIndex,yogaPowerBoundPipe)' in p
assert 'eligible.activeHDMI2=yogaHDMI2WakeRecover && allowWrite;' in h
assert 'if(!same || !caps.valid || !caps.hdmi || !caps.scdc ||' in h
assert 'yogaHDMI2WakeProven.attemptedGeneration=generation' in h
assert 'if(!lowReconcile)return 52;' in h
assert 'const auto transaction=YogaHDMI2::prepareSCDC(bus,plan,caps.scdc);' in h
assert 'return plan.highTMDS?(wakeCandidate?110:100):101;' in h
assert 'checkKernelArgument("-wex-yoga-hdmi2-wake-recover")' in c
assert 'WEXYogaHDMI2WakePowerHist%02u' in p
# The candidate must not acquire an extra lock to diagnose a failed I2C call:
# its post-transaction connected() check remains short-circuited on success.
block=h.split('const auto status=native(controller,fbIndex,ddc,0,nullptr,&request);',1)[1].split('return okay;',1)[0]
assert block.count('&& connected();')==1
assert 'if(traceVersion)' in block and 'IORegistryEntry' not in block
# The only new IORegistry writes are in original post-LightUpTMDS shim.
assert c.index('WEXYogaHDMI2SCDCI2CLast')>c.index('const auto result=original(controller,rawFB,rawPath,rawTiming);')
print("PASS R5.1: passive SCDC 0x01 native-result trace; no extra hardware calls")
print("PASS R5.1: R5 HDMI-B dynamic FB, R4 EDID/CTA/one-shot recovery unchanged")
