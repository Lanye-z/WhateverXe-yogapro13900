#!/usr/bin/env python3
"""R5 source invariants; run after the new overlay, never replacing V4 checks."""
from pathlib import Path
root=Path("Source")
h=(root/"WhateverXe/kern_yoga_hdmi2_candidate.hpp").read_text()
p=(root/"WhateverXe/kern_display13_framebuffer_power.inc").read_text()
s=(root/"WhateverXe/kern_xe.cpp").read_text()
sess=(root/"WhateverXe/kern_yoga_hdmi2_session_policy.hpp").read_text()
pure=(root/"WhateverXe/kern_yoga_hdmi2_dynamic_policy.hpp").read_text()

assert 'kern_yoga_hdmi2_dynamic_policy.hpp' in h
assert 'YogaHDMI2R5::nativeWakeMatches(' in h
assert 'yogaHDMI2WakeDozeFB' in h and 'yogaHDMI2WakeActiveWakeFB' in h
assert 'p.sameFB1=YogaHDMI2R5::nativeWakeMatches(' in h
assert 'p.sameFB1=pipe==1U' not in h
assert 'pipe!=1U' not in h
assert 'p.knownHDMIPipe=YogaHDMI2R5::sameBoundPipe(' in h
assert 'p.knownPipe1=' not in h
assert 'knownHDMIPipe' in sess and 'knownPipe1' not in sess
assert 'Display13FBMemory::field<uint32_t>(fb,0x1DC)==1U' not in p
assert 'YogaHDMI2R5::sameBoundPipe(yogaPowerIndex,yogaPowerBoundPipe)' in p
assert 'reinterpret_cast<uintptr_t>(fb)' in p
assert 'YogaHDMI2R5::samePowerObject(' in p
assert 'mach_absolute_time(),yogaPowerIndex,yogaPowerPrior,state,result,' in p
assert 'mach_absolute_time(),1U,yogaPowerPrior,state,result,' not in p
assert p.count('FunctionCast(wrapDisplay13SetPowerState,callbackXE->orgDSIAttributes[2])(fb,state);')==1
assert p.count('uint32_t XE::wrapDisplay13SetPowerState(')==1
assert p.count('"WEXYogaHDMI2WakePowerHist%02u"')==1

# The validated physical HDMI-B owner and exact sink must still authorize it.
assert 'callbackXE->adlnOutputWiring.hdmi==2U' in p
assert 'callbackXE->ownedDisplay13Framebuffer(fb)' in p
assert 'yogaHDMI2WakeBaseExact' in h
assert 'memcmp(yogaHDMI2WakeCurrentBase,yogaHDMI2WakeProven.base,128)' in h
assert 'eligible.activeHDMI2=yogaHDMI2WakeRecover && allowWrite;' in h
assert 'YogaHDMI2Wake::mayRecover(eligible)' in h
assert 'yogaHDMI2WakeProven.attemptedGeneration=generation' in h
assert 'if(!lowReconcile)return 52;' in h
assert h.count('YogaHDMI2::prepareSCDC(')==1
assert 'return plan.highTMDS?(wakeCandidate?110:100):101;' in h
assert 'WEXYogaHDMI2WakeRejectLast' in h
assert 'WEXYogaHDMI2WakeActionLast' in h

# Never change the validated original SCDC owner lock, Metal callsite route
# order or R4 journal, and never make the recovery a boot-time default.
assert 'IOLockTryLock(state.lock)' in h
assert 'IORecursiveLockHaveLock(recursive)' in h
assert 'yogaHDMI2SafeRequested=checkKernelArgument("-wex-yoga-hdmi2-callsite-safe");' in s
assert 'yogaHDMI2WakeRecover=(state==5 && yogaHDMI2CallsiteSafe &&' in s
assert 'checkKernelArgument("-wex-yoga-hdmi2-wake-recover")' in s
assert s.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
assert s.index('display13FBTCHooksReady=processDisplay13FramebufferTC(') < s.index('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')
assert s.count('WEXYogaHDMI2CallsiteHist%02u')==1
assert '"WEXYogaHDMI2WakePowerHist%02u"' in p
assert 'prepareSCDC(' not in pure
assert 'setProperty(' not in pure
assert 'sendAddress(' not in pure
print("PASS R5 generated-source: physical HDMI-B owner + dynamic FB1/FB2 identity; guarded low reconcile")
print("PASS R5 generated-source: no additional SCDC/MMIO/HPD/modeset and no other FB route")
