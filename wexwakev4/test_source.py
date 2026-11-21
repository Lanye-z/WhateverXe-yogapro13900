#!/usr/bin/env python3
"""V4 generated-source static safety guards after V3 + Unified overlay."""
from pathlib import Path
import json

root=Path("Source")
s=(root/"WhateverXe/kern_xe.cpp").read_text()
h=(root/"WhateverXe/kern_yoga_hdmi2_candidate.hpp").read_text()
a=json.loads((root/"tests/fixtures/boot_argument_names.json").read_text())

# Strict fail-closed scope: V3 signature, TC-before-CALL, no global route.
assert s.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
assert s.index('display13FBTCHooksReady=processDisplay13FramebufferTC(') < s.index('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')
assert 'orgDisplay13HDMI2TMDS' not in s
assert 'yogaHDMI2SafeRequested=checkKernelArgument("-wex-yoga-hdmi2-callsite-safe");' in s
assert 'yogaHDMI2WakeDiag=(state==5 && yogaHDMI2CallsiteSafe &&' in s
assert 'yogaHDMI2WakeRecover=(state==5 && yogaHDMI2CallsiteSafe &&' in s
for flag in ["-wex-yoga-hdmi2-wake-diag","-wex-yoga-hdmi2-wake-recover"]:
    assert flag in a
    assert f'checkKernelArgument("{flag}")' in s

# Preserve Unified RC1 default-on patch behavior and original opt-outs.
for flag in ["-wex-yoga-disable-integrated","-wex-yoga-disable-edp120-admit",
             "-wex-yoga-disable-edp120-wm","-wex-yoga-disable-hdmi-deep8",
             "-wex-yoga-disable-hdmi600","-wex-yoga-disable-tc5-sst"]:
    assert flag in a and f'checkKernelArgument("{flag}")' in s

# The only V4 action is original native SCDC prepare after strict same-base gate.
assert "YogaHDMI2Wake::mayRecover(eligible)" in h
assert "capabilitiesMissing && YogaHDMI2Wake::mayRecover(eligible)" in h
assert "yogaHDMI2WakeProven.attemptedGeneration=generation" in h
assert "yogaHDMI2WakeCTASeen && yogaHDMI2WakeBaseExact" in h
assert "memcmp(yogaHDMI2WakeCurrentBase,yogaHDMI2WakeProven.base,128)" in h
assert "const auto transaction=YogaHDMI2::prepareSCDC(bus,plan,caps.scdc);" in h
assert h.count("YogaHDMI2::prepareSCDC(")==1
assert "if(!same || !caps.valid || !caps.hdmi || !caps.scdc ||" in h
assert "caps.maxKHz<=340000)" in h
assert "return plan.highTMDS?(wakeCandidate?110:100):101;" in h
assert 'if((status==100 || status==110) &&' in s
assert '(yogaHDMI2WakeDiag && status==10)' in s
assert 'WEXYogaHDMI2WakeLast' in h
assert 'WEXYogaHDMI2WakeRecoverEnabled' in s
assert 'WEXYogaHDMI2SourceLast' in s
assert "IOLockTryLock(state.lock)" in h
assert "IORecursiveLockHaveLock(recursive)" in h

# No new I2C in EDID observer, and original SCDC still conditioned on
# a successful native transaction; no direct HPD or display modeset operations.
ddc=h.split('static inline void yogaHDMI2ObserveDDC(',1)[1].split('// Native controller I2C:',1)[0]
assert "prepareSCDC(" not in ddc and "request.sendAddress" not in ddc
assert "yogaHDMI2WakeRecord(" in ddc
assert "setProperty" not in ddc  # emitter called only after lock release
assert h.index("IOSimpleLockUnlock(lock);\n    yogaHDMI2WakeRecord") > h.index("static inline void yogaHDMI2ObserveDDC")
assert "patcher.routeBlock" not in h
assert "WEXYogaHDMI2Callsite" in s
print("PASS: V4 exact sink + fresh base + one attempt; native owner/SCDC unchanged")
print("PASS: optional V4 wake controls require V3 safe and fully installed callsite")
print("PASS: Unified RC1 defaults, Metal TC ordering and DDI5 SST retained")
