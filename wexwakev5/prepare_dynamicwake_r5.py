#!/usr/bin/env python3
"""R5: bind the existing native power observer to the actual, proven HDMI-B FB.

Apply AFTER R4. V3 -> Unified RC1 -> V4/R2/R3/R4 unchanged.
No new hooks, HPD injection, modeset, I2C, PLL, PHY, DBUF or watermark edits.
"""
from pathlib import Path
import argparse
import shutil
import subprocess

HERE=Path(__file__).resolve().parent

def once(s,old,new,why):
    n=s.count(old)
    if n!=1:
        raise RuntimeError(f"R5 {why}: expected one anchor, found {n}")
    return s.replace(old,new,1)

def candidate(s):
    s=once(s,
        '#include "kern_yoga_hdmi2_wake_policy.hpp"',
        '#include "kern_yoga_hdmi2_wake_policy.hpp"\n'
        '#include "kern_yoga_hdmi2_dynamic_policy.hpp"',
        "add pure R5 policy")
    s=once(s,
        'static inline uint32_t yogaHDMI2WakeTimeGuard(uint32_t pipe) {',
        'static volatile uintptr_t yogaHDMI2WakeDozeFB {};\n'
        'static volatile uintptr_t yogaHDMI2WakeActiveWakeFB {};\n'
        'static inline uint32_t yogaHDMI2WakeTimeGuard(uint32_t pipe) {',
        "framebuffer identity state")
    s=once(s,
        '    p.sameFB1=pipe==1U && lastPipe==pipe;',
        '''    p.sameFB1=YogaHDMI2R5::nativeWakeMatches(
        pipe,lastPipe,
        __atomic_load_n(&yogaHDMI2WakeDozeFB,__ATOMIC_ACQUIRE),
        __atomic_load_n(&yogaHDMI2WakeActiveWakeFB,__ATOMIC_ACQUIRE),
        __atomic_load_n(&yogaHDMI2WakeInNativeFB1Wake,__ATOMIC_ACQUIRE)==1U);''',
        "replace fixed FB1 power evidence")
    s=once(s,
        'if(!yogaHDMI2WakeRecover || !port || !path || !lock || pipe!=1U)return false;',
        'if(!yogaHDMI2WakeRecover || !port || !path || !lock)return false;',
        "allow dynamic pipe in prior low-mode safeguard")
    s=once(s,
        '    p.knownPipe1=__atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE)==pipe;',
        '    p.knownHDMIPipe=YogaHDMI2R5::sameBoundPipe(pipe,'
        '__atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE));',
        "low-mode binding gate")
    # Stale native power object identity must not survive a different EDID.
    s=once(s,
        '            yogaHDMI2WakeProven.valid=false;\n',
        '''            yogaHDMI2WakeProven.valid=false;
            __atomic_store_n(&yogaHDMI2WakeDozeFB,static_cast<uintptr_t>(0),__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeActiveWakeFB,static_cast<uintptr_t>(0),__ATOMIC_RELEASE);
''',
        "invalidate old physical framebuffer identity")
    s=once(s,
        '                yogaHDMI2WakeProven.valid=true;\n',
        '''                yogaHDMI2WakeProven.valid=true;
                // A new genuine native SCDC/CTA session rebases future Doze
                // observations on the actual HDMI pipe, not the old FB.
                __atomic_store_n(&yogaHDMI2WakeDozeFB,static_cast<uintptr_t>(0),__ATOMIC_RELEASE);
''',
        "rebase Doze identity after a fresh proven high-TMDS session")
    return s

def session_policy(s):
    # One declaration and one use in mayReconcileLow; both must be migrated.
    if s.count('knownPipe1')!=2:
        raise RuntimeError("R5 session policy has unexpected pipe-field layout")
    return s.replace('knownPipe1','knownHDMIPipe')

def native_power(s):
    s=once(s,
        '''    const bool yogaPowerTarget=callbackXE && fb &&''',
        '''    // Read the FB index only after the native owner validates the object.
    // A transient non-owned pointer must never be dereferenced here.
    const uint32_t yogaPowerIndex=(callbackXE && fb &&
        callbackXE->ownedDisplay13Framebuffer(fb)) ?
        Display13FBMemory::field<uint32_t>(fb,0x1DC):3U;
    const uint32_t yogaPowerBoundPipe=
        __atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE);
    const bool yogaPowerTarget=callbackXE && fb &&''',
        "capture actual native framebuffer index")
    s=once(s,
        '''        Display13FBMemory::field<uint32_t>(fb,0x1DC)==1U;''',
        '''        YogaHDMI2R5::sameBoundPipe(yogaPowerIndex,yogaPowerBoundPipe);''',
        "replace fixed FB1 power target")
    s=once(s,
        '''        yogaPowerPrior==1U &&
        __atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE)!=0;''',
        '''        yogaPowerPrior==1U &&
        __atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE)!=0 &&
        YogaHDMI2R5::samePowerObject(
            __atomic_load_n(&yogaHDMI2WakeDozeFB,__ATOMIC_ACQUIRE),
            reinterpret_cast<uintptr_t>(fb));''',
        "require same framebuffer object on Doze and Wake")
    s=once(s,
        '''    const bool yogaPowerWindow=yogaPowerWasDoze &&
        __sync_bool_compare_and_swap(&yogaHDMI2WakeInNativeFB1Wake,0U,1U);''',
        '''    const bool yogaPowerWindow=yogaPowerWasDoze &&
        __sync_bool_compare_and_swap(&yogaHDMI2WakeInNativeFB1Wake,0U,1U);
    if(yogaPowerWindow)
        __atomic_store_n(&yogaHDMI2WakeActiveWakeFB,
                         reinterpret_cast<uintptr_t>(fb),__ATOMIC_RELEASE);''',
        "publish only matched active native Wake object")
    s=once(s,
        '''                __atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE)==1U &&''',
        '''                YogaHDMI2R5::sameBoundPipe(
                    yogaPowerIndex,
                    __atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE)) &&''',
        "native successful Doze matches dynamic bound pipe")
    s=once(s,
        '''            __atomic_store_n(&yogaHDMI2WakeNativeFB1DozeAt,
                confirmed?mach_absolute_time():0ULL,__ATOMIC_RELEASE);''',
        '''            __atomic_store_n(&yogaHDMI2WakeDozeFB,
                confirmed?reinterpret_cast<uintptr_t>(fb):static_cast<uintptr_t>(0),
                __ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeNativeFB1DozeAt,
                confirmed?mach_absolute_time():0ULL,__ATOMIC_RELEASE);''',
        "save native Doze timestamp and framebuffer identity")
    s=once(s,
        '''            const bool completed=result==kIOReturnSuccess &&
                __atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE)!=0;''',
        '''            const bool completed=result==kIOReturnSuccess &&
                __atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE)!=0 &&
                YogaHDMI2R5::samePowerObject(
                    __atomic_load_n(&yogaHDMI2WakeDozeFB,__ATOMIC_ACQUIRE),
                    reinterpret_cast<uintptr_t>(fb));''',
        "record completed wake only for the same original framebuffer")
    s=once(s,
        '''        if(yogaPowerWindow)
            __atomic_store_n(&yogaHDMI2WakeInNativeFB1Wake,0U,__ATOMIC_RELEASE);''',
        '''        if(yogaPowerWindow) {
            __atomic_store_n(&yogaHDMI2WakeActiveWakeFB,
                static_cast<uintptr_t>(0),__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeInNativeFB1Wake,0U,__ATOMIC_RELEASE);
        }''',
        "close matched wake window without leaking stale framebuffer pointer")
    s=once(s,
        '''                mach_absolute_time(),1U,yogaPowerPrior,state,result,''',
        '''                mach_absolute_time(),yogaPowerIndex,yogaPowerPrior,state,result,''',
        "PowerHist now records real FB1 or FB2")
    return s

def main(root):
    h=root/"WhateverXe/kern_yoga_hdmi2_candidate.hpp"
    p=root/"WhateverXe/kern_yoga_hdmi2_session_policy.hpp"
    n=root/"WhateverXe/kern_display13_framebuffer_power.inc"
    out_h=candidate(h.read_text())
    out_p=session_policy(p.read_text())
    out_n=native_power(n.read_text())
    if "pipe==1U" in out_h or "pipe!=1U" in out_h:
        raise RuntimeError("R5 refusal: old fixed HDMI Pipe1 guard persists")
    if "Display13FBMemory::field<uint32_t>(fb,0x1DC)==1U" in out_n:
        raise RuntimeError("R5 refusal: native power still fixed to FB1")
    target=root/"WhateverXe/kern_yoga_hdmi2_dynamic_policy.hpp"
    if target.exists():raise RuntimeError("R5 policy already exists in source")
    source=HERE/"kern_yoga_hdmi2_dynamic_policy.hpp"
    if not source.is_file():raise RuntimeError("R5 pure policy source missing")
    h.write_text(out_h)
    p.write_text(out_p)
    n.write_text(out_n)
    shutil.copyfile(source,target)
    subprocess.run(["git","-C",str(root),"diff","--check"],check=True)
    print("PASS R5: physical HDMI-B native session binds FB1 or FB2 without static pipe")
    print("PASS R5: same framebuffer object required for actual Doze->Wake")
    print("PASS R5: low-rate fallback follows verified pipe; old CTA/EDID and SCDC safeguards retained")
    print("PASS R5: only existing SCDC and native power callbacks; no HPD/modeset/new hooks")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("source",type=Path)
    main(ap.parse_args().source.resolve())
