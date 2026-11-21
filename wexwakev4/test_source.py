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
assert "yogaHDMI2WakeTimeGuard(pipe)" in h
assert "YogaHDMI2Wake::qualifyPowerEvidence(p)" in h
assert "90000000000ULL" not in h and "3000000000ULL" not in h
assert "eligible.priorNativeHighConfirmed=bool(wakeTimeBits&1U);" in h
assert "eligible.nativeDozeWakeVerified=bool(wakeTimeBits&2U);" in h
assert "yogaHDMI2WakeLastGoodPipe" in h
assert "yogaHDMI2WakeFirstGoodHighAt" in h
assert "WEXYogaHDMI2WakeRejectLast" in h
assert "WEXYogaHDMI2WakeActionLast" in h
# R2 completely removes the R1 speculative output-off MMIO observer.
assert "reg==0x60400U+0x1000U*knownPipe" not in s
assert "yogaHDMI2WakeObservedHDMIOffAt" not in s
assert "yogaHDMI2WakeObservedOffPipe" not in s
assert "yogaHDMI2WakeNativeFB1DozeAt" in h
assert "yogaHDMI2WakeInNativeFB1Wake" in h
assert "WEX_HDMI2_NATIVE_POWER_R2" in h
native_power=(root/"WhateverXe/kern_display13_framebuffer_power.inc").read_text()
assert "WEXYogaHDMI2WakePowerLast" in native_power
assert native_power.count("uint32_t XE::wrapDisplay13SetPowerState(")==1
assert native_power.count("FunctionCast(wrapDisplay13SetPowerState,callbackXE->orgDSIAttributes[2])(fb,state);")==1
assert "yogaPowerPrior==1U" in native_power
assert "yogaPowerPrior==2U" in native_power
assert "state==2U" in native_power and "state==1U" in native_power
assert "yogaPowerWindow" in native_power
assert "#if defined(WEX_HDMI2_NATIVE_POWER_R2)" in native_power
assert "yogaHDMI2WakeNativeFB1DozeAt" in native_power
assert "yogaHDMI2WakeInNativeFB1Wake" in native_power
# R3 must remain read-only on A group and refuse all low-mode I2C
# until an actual prior 4K60 status10 + native Wake + fresh CTA + exact sink.
assert "YogaHDMI2Session::mayReconcileLow(p)" in h
assert "yogaHDMI2MayReconcileLow(port,path,pipe,lock)" in h
assert "yogaHDMI2WakeMissingCTAAtGen" in h
assert "yogaHDMI2WakeCompletedNativeFB1WakeAt" in h
assert "if(!lowReconcile)return 52;" in h
assert "if(pixelHz>YogaHDMI2::HighTMDSHz && same && baseMatches &&" in h
assert "yogaHDMI2WakeRecord(7U,generation,pipe,pixelHz," in h
assert "if(event>=4U && event<=7U)" in h
assert "p.requested=yogaHDMI2WakeRecover;" in h
assert "if(!yogaHDMI2WakeRecover || !port || !path || !lock || pipe!=1U)" in h
assert "if(state==2U && yogaPowerPrior==1U)" in native_power
assert (root/"WhateverXe/kern_yoga_hdmi2_session_policy.hpp").exists()


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
print("PASS: V4 R2 real FB1 Doze->Wake required + exact sink + native SCDC transaction")
print("PASS: optional V4 wake controls require V3 safe and fully installed callsite")
print("PASS: Unified RC1 defaults, Metal TC ordering and DDI5 SST retained")

print("PASS R3: original native HDMI callsite, readback and A-group behavior preserved; no DDI5/SST changes")

# R4: B-group may recover on first *short* genuine Doze->Wake; still must
# have one real prior 4K60 SCDC success, exact AOC EDID and native locks.
# A-group is diagnostic-only (recoverRequested remains false).
assert "YogaHDMI2Wake::qualifyPowerEvidence(p)" in h
assert "p.nativeDozeToWakeWindow=" in h
assert "p.nativeDozeAt=" in h
assert "eligible.activeHDMI2=yogaHDMI2WakeRecover && allowWrite;" in h
assert "yogaHDMI2WakeProven.valid" in h
assert "yogaHDMI2WakeCTASeen" in h
assert "yogaHDMI2WakeR4" not in h
assert h.count("YogaHDMI2::prepareSCDC(")==1
# Historical confirmation is not an authorization: source and sink generation
# checks and previous armedPipe invalidation must remain in native candidate.
assert "__atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);" in h
assert "yogaHDMI2R4LastSCDCSuccessGen" in h
assert "yogaHDMI2R4LastSCDCSuccessStatus" in h
assert "yogaHDMI2R4LastDDCGen" in h
assert "yogaHDMI2R4LastDDCFlags" in h
assert "yogaHDMI2R4LastDDCMaxKHz" in h
# Last-32 CALL-site history with monotonic timestamps and bounded key count.
assert 'WEXYogaHDMI2CallsiteHist%02u' in s
assert '"WEXYogaHDMI2WakePowerHist%02u"' in native_power
assert "(count-1U)%32U+1U" in s
assert "(record[1]-1ULL)%32ULL+1ULL" in native_power
assert "yogaCallStartedAt" in s
assert "if(yogaHDMI2WakeDiag)" in s
assert "IORegistryEntry::getRegistryRoot()->setProperty(key,trace,sizeof(trace))" in s
# Do not modify other framebuffer modes or install any new call sites.
assert s.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
assert native_power.count('FunctionCast(wrapDisplay13SetPowerState,callbackXE->orgDSIAttributes[2])(fb,state);')==1
print("PASS R4: native-power evidence gating without 90s/3s, bounded 32+32 trace, no new hooks")
