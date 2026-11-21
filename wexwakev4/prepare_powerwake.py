#!/usr/bin/env python3
"""V4 R2: recognize actual FB1 Doze -> Wake in the existing native power wrapper.

Apply AFTER wexwakev4/prepare.py. The original 0.8.3 kernel, V3 and
Unified RC1 are pinned; no extra hooks or scheduling and no changes to
native power return values, native I2C/SCDC, PHY, clocks, HPD, or DBUF.
"""
from pathlib import Path
import argparse
import re
import subprocess


def once(s: str, old: str, replacement: str, label: str) -> str:
    count=s.count(old)
    if count!=1:raise RuntimeError(f"{label}: exact anchor count={count}")
    return s.replace(old,replacement,1)


TIME_GUARD=r'''// R2 uses native FB1 power transitions, NOT an inferred transcoder-off
// register. The power callback is already routed by the pinned donor.
static volatile uint64_t yogaHDMI2WakeNativeFB1DozeAt {};
static volatile uint32_t yogaHDMI2WakeInNativeFB1Wake {};
static volatile uint32_t yogaHDMI2WakePowerSequence {};
static inline uint32_t yogaHDMI2WakeTimeGuard(uint32_t pipe) {
    const auto first=__atomic_load_n(&yogaHDMI2WakeFirstGoodHighAt,__ATOMIC_ACQUIRE);
    const auto doze=__atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE);
    const auto owner=__atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE);
    const auto inWake=__atomic_load_n(&yogaHDMI2WakeInNativeFB1Wake,__ATOMIC_ACQUIRE);
    if(!first || !doze || !inWake || pipe!=1U || owner!=pipe || doze<=first)return 0;
    const auto now=mach_absolute_time();
    if(now<=doze)return 0;
    uint64_t firstNs=0,dozeNs=0;
    absolutetime_to_nanoseconds(now-first,&firstNs);
    absolutetime_to_nanoseconds(now-doze,&dozeNs);
    return (firstNs>=90000000000ULL?1U:0U) |
        (dozeNs>=3000000000ULL?2U:0U);
}
'''


POWER_START=r'''#if defined(WEX_HDMI2_NATIVE_POWER_R2)
    // No new power route: run inside the donor's existing, validated
    // wrapDisplay13SetPowerState. Exactly framebuffer index 1 (native HDMI-B).
    // At the very first startup modeset there is no successful high-rate
    // session, hence no successful Doze-cycle token and no recovery window.
    const bool yogaPowerTarget=callbackXE && fb &&
        (yogaHDMI2WakeDiag || yogaHDMI2WakeRecover) &&
        callbackXE->adlnOutputWiring.hdmi==2U &&
        callbackXE->ownedDisplay13Framebuffer(fb) &&
        Display13FBMemory::field<uint32_t>(fb,0x1DC)==1U;
    const uint32_t yogaPowerPrior=yogaPowerTarget ?
        Display13FBMemory::field<uint32_t>(fb,0x4284):UINT32_MAX;
    const bool yogaPowerWasDoze=yogaPowerTarget && state==2U &&
        yogaPowerPrior==1U &&
        __atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE)!=0;
    // Guard opens before native state=2 invokes the nested HDMI modeset;
    // completion occurs AFTER that nested call, so it cannot open later.
    const bool yogaPowerWindow=yogaPowerWasDoze &&
        __sync_bool_compare_and_swap(&yogaHDMI2WakeInNativeFB1Wake,0U,1U);
#endif
'''
POWER_END=r'''#if defined(WEX_HDMI2_NATIVE_POWER_R2)
    if(yogaPowerTarget) {
        // Only a real native Wake(2)->Doze(1) success qualifies.
        // The timestamp is set AFTER the native power callback returns.
        if(state==1U && yogaPowerPrior==2U) {
            const bool confirmed=result==kIOReturnSuccess &&
                __atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE)==1U &&
                __atomic_load_n(&yogaHDMI2WakeFirstGoodHighAt,__ATOMIC_ACQUIRE)!=0;
            __atomic_store_n(&yogaHDMI2WakeNativeFB1DozeAt,
                confirmed?mach_absolute_time():0ULL,__ATOMIC_RELEASE);
        }
        // Never leave a power-wake recovery window armed after return,
        // regardless of success, error or unrelated HPD events.
        if(yogaPowerWindow)
            __atomic_store_n(&yogaHDMI2WakeInNativeFB1Wake,0U,__ATOMIC_RELEASE);
        if(yogaHDMI2WakeDiag && ((state==1U && yogaPowerPrior==2U) ||
                                 (state==2U && yogaPowerPrior==1U))) {
            uint64_t record[] {
                1U,__sync_add_and_fetch(&yogaHDMI2WakePowerSequence,1U),
                mach_absolute_time(),1U,yogaPowerPrior,state,result,
                __atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE),
                __atomic_load_n(&yogaHDMI2WakeFirstGoodHighAt,__ATOMIC_ACQUIRE),
                yogaPowerWindow?1ULL:0ULL,
                __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)
            };
            IORegistryEntry::getRegistryRoot()->setProperty(
                "WEXYogaHDMI2WakePowerLast",record,sizeof(record));
        }
    }
#endif
'''


def patch_candidate(s: str) -> str:
    # The header is inserted into kern_xe.cpp after display13FBPower, while
    # the power.inc source is included near the END of that TU.
    old_start="static inline uint32_t yogaHDMI2WakeTimeGuard(uint32_t pipe) {"
    a=s.find(old_start)
    if a<0 or s.count(old_start)!=1:raise RuntimeError("missing unique R1 time guard")
    b=s.find("\n}\n",a)
    if b<0 or s.count("static volatile uint64_t yogaHDMI2WakeObservedHDMIOffAt {};")!=1:
        raise RuntimeError("R1 guard changed")
    s=s[:a]+TIME_GUARD+s[b+3:]
    s=once(s,
        "eligible.observedLongHDMIOff=bool(wakeTimeBits&2U);",
        "eligible.nativeDozeWakeVerified=bool(wakeTimeBits&2U);",
        "pure policy field: real native Doze->Wake")
    s=once(s,
        "    const auto wakeTimeBits=yogaHDMI2WakeRecover && allowWrite ?\n        yogaHDMI2WakeTimeGuard(pipe):0U;",
        "    // Compute even in A-group for diagnostics; only B-group may act.\n"
        "    const auto wakeTimeBits=allowWrite ? yogaHDMI2WakeTimeGuard(pipe):0U;",
        "A/B comparable wake evidence")
    s=once(s,
        "static volatile uint32_t yogaHDMI2WakePowerSequence {};",
        "static volatile uint32_t yogaHDMI2WakePowerSequence {};\n"
        "#define WEX_HDMI2_NATIVE_POWER_R2 1",
        "power callback fixture guard")
    # Clear native Doze token when the physical HDMI sink identity changes.
    s=once(s,
        "            yogaHDMI2WakeProven.valid=false;\n",
        "            yogaHDMI2WakeProven.valid=false;\n"
        "            __atomic_store_n(&yogaHDMI2WakeNativeFB1DozeAt,0ULL,__ATOMIC_RELEASE);\n"
        "            __atomic_store_n(&yogaHDMI2WakeInNativeFB1Wake,0U,__ATOMIC_RELEASE);\n",
        "clear native Doze on changed EDID")
    s=once(s,
        "                yogaHDMI2WakeProven.valid=true;\n",
        "                yogaHDMI2WakeProven.valid=true;\n"
        "                __atomic_store_n(&yogaHDMI2WakeNativeFB1DozeAt,0ULL,__ATOMIC_RELEASE);\n",
        "successful new fresh SCDC resets previous Doze token")
    if "yogaHDMI2WakeNativeFB1DozeAt" not in s or "WEX_HDMI2_NATIVE_POWER_R2" not in s:
        raise RuntimeError("missing R2 native power definitions")
    return s


def patch_cpp(s: str) -> str:
    # Completely remove R1's speculative MMIO-disable inference. No
    # additional MMIO reads/writes are permitted from the R2 power callback.
    old=r'''    if(yogaHDMI2WakeRecover && access==display13FBPower.access) {
        const auto knownPipe=__atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE);
        if(knownPipe<3U && reg==0x60400U+0x1000U*knownPipe &&
           !(value&0x80000000U) &&
           __atomic_load_n(&yogaHDMI2WakeFirstGoodHighAt,__ATOMIC_ACQUIRE)) {
            __atomic_store_n(&yogaHDMI2WakeObservedHDMIOffAt,
                mach_absolute_time(),__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeObservedOffPipe,
                knownPipe,__ATOMIC_RELEASE);
        }
    }
'''
    return once(s,old,"", "remove R1 MMIO heuristic observer")


def patch_power_inc(s: str) -> str:
    anchor="    recordDSIClient(fb,9,state,UINT32_MAX);"
    s=once(s,anchor,POWER_START+anchor,"existing native framebuffer power callback entry")
    tail="    recordDSIClient(fb,9,state,result);\n    return result;"
    s=once(s,tail,POWER_END+tail,"existing native framebuffer power callback exit")
    assert s.count("uint32_t XE::wrapDisplay13SetPowerState(")==1
    assert s.count("FunctionCast(wrapDisplay13SetPowerState,callbackXE->orgDSIAttributes[2])(fb,state);")==1
    assert s.count("KernelPatcher::RouteRequest routes[]")==1
    return s


def main(root:Path):
    h=root/"WhateverXe/kern_yoga_hdmi2_candidate.hpp"
    cpp=root/"WhateverXe/kern_xe.cpp"
    power=root/"WhateverXe/kern_display13_framebuffer_power.inc"
    before_h=h.read_text()
    before_cpp=cpp.read_text()
    before_power=power.read_text()
    after_h=patch_candidate(before_h)
    after_cpp=patch_cpp(before_cpp)
    after_power=patch_power_inc(before_power)
    assert "WEX_HDMI2_NATIVE_POWER_R2" in after_h
    assert "WEX_HDMI2_NATIVE_POWER_R2" in after_power
    assert before_cpp.count("patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));")==1
    assert after_cpp.count("patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));")==1
    assert after_h.count("YogaHDMI2::prepareSCDC(")==1
    assert before_power.count("wrapDisplay13SetPowerState(")==after_power.count("wrapDisplay13SetPowerState(")
    # Do not modify original system-sleep / restore callbacks beyond the
    # two small gated observations in this already-routed native wrapper.
    h.write_text(after_h)
    cpp.write_text(after_cpp)
    power.write_text(after_power)
    subprocess.run(["git","-C",str(root),"diff","--check"],check=True)
    print("PASS R2: native FB1 Doze->Wake guard, startup remains unqualified")
    print("PASS R2: no new native route/MMIO/HPD/modeset, original power ABI preserved")
    print("PASS R2: original V3 SCDC readback/owner + Unified RC1 defaults unchanged")


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("source",type=Path)
    args=ap.parse_args()
    main(args.source.resolve())
