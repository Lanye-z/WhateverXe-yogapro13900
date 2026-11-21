#!/usr/bin/env python3
"""R3: separate EDID capability generation from the physical HDMI session.

Applied after the R2 overlay. No new function hook; do not change donor
framebuffer/DP/SST/DBUF/WM, physical HPD, or source code outside the existing
native HDMI2 candidate and its already-routed FB1 power-state observer.
"""
from pathlib import Path
import argparse
import subprocess
import shutil

def once(s, old, new, title):
    n=s.count(old)
    if n!=1:
        raise RuntimeError(f"R3 {title}: expected unique anchor, got {n}")
    return s.replace(old,new,1)


R3_GUARD = r'''
// A failed post-Doze high-rate CALL-site may precede the new CTA.
// This epoch tag is ONLY evidence, never permission for an I2C transaction.
static volatile uint32_t yogaHDMI2WakeMissingCTAAtGen {};
static volatile uint64_t yogaHDMI2WakeCompletedNativeFB1WakeAt {};

// Reconcile an orphaned source high-TMDS session on a subsequent explicit
// low-TMDS modeset. R3 does not generate that modeset: it only answers
// whether the existing native CALL-site may execute normal SCDC readback.
static inline bool yogaHDMI2MayReconcileLow(OSObject *port,OSObject *path,
    uint32_t pipe,IOSimpleLock *lock) {
    if(!yogaHDMI2WakeRecover || !port || !path || !lock || pipe!=1U)return false;
    const uint32_t shadow=Display13FBMemory::field<uint32_t>(path,0x12C);
    const bool shadowHigh=(shadow&YogaHDMI2::SourceFlags)==YogaHDMI2::SourceFlags;
    IOSimpleLockLock(lock);
    const auto generation=yogaHDMI2Live.generation;
    const auto failed=__atomic_load_n(&yogaHDMI2WakeMissingCTAAtGen,__ATOMIC_ACQUIRE);
    const auto slept=__atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE);
    const auto woke=__atomic_load_n(&yogaHDMI2WakeCompletedNativeFB1WakeAt,__ATOMIC_ACQUIRE);
    const auto now=mach_absolute_time();
    uint64_t wakeAgeNs=0;
    if(woke && now>woke)absolutetime_to_nanoseconds(now-woke,&wakeAgeNs);
    // A manually selected 4K30 after failed wake may reconcile for five
    // minutes, never during startup or across an unrelated later session.
    const bool nativeWakeCompleted=slept && woke && woke>slept &&
        now>woke && wakeAgeNs<=300000000000ULL;
    const bool baseMatches=yogaHDMI2WakeProven.valid &&
        yogaHDMI2WakeProven.port==port &&
        !memcmp(yogaHDMI2WakeCurrentBase,yogaHDMI2WakeProven.base,128);
    YogaHDMI2Session::LowReconcile p {};
    p.requested=yogaHDMI2WakeRecover;
    p.physicalHDMIB=yogaHDMI2Live.port==port && yogaHDMI2Live.baseSeen;
    p.knownPipe1=__atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE)==pipe;
    p.exactAOC=yogaHDMI2WakeBaseExact;
    p.provenHighSession=yogaHDMI2WakeProven.valid;
    p.sameCompleteBase=baseMatches;
    p.hadNativeDozeWake=nativeWakeCompleted;
    p.priorHighStatus10=failed!=0;
    p.freshCTA=yogaHDMI2WakeCTASeen;
    p.currentHDMISCDC=yogaHDMI2Live.caps.valid &&
        yogaHDMI2Live.caps.hdmi && yogaHDMI2Live.caps.scdc;
    p.sourceHasHighFlags=shadowHigh;
    p.failedGeneration=failed;
    p.currentGeneration=generation;
    p.maxTMDSKHz=yogaHDMI2Live.caps.maxKHz;
    const bool allowed=YogaHDMI2Session::mayReconcileLow(p);
    IOSimpleLockUnlock(lock);
    return allowed;
}
'''

def patch_header(s):
    s=once(s,'#include "kern_yoga_hdmi2_wake_policy.hpp"',
        '#include "kern_yoga_hdmi2_wake_policy.hpp"\n#include "kern_yoga_hdmi2_session_policy.hpp"',
        "pure session policy header")
    # Insert after both original V4 WAKE_STATE and R2 power time helper.
    anchor="// schema,seq,mach_absolute_time,event,generation,pipe,pixelHz,status,"
    s=once(s,anchor,R3_GUARD+"\n"+anchor,"session state helper")
    old="""        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    } else if(yogaHDMI2Live.baseSeen && yogaHDMI2Live.port==port) {"""
    new="""        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    } else if(yogaHDMI2Live.baseSeen && yogaHDMI2Live.port==port) {"""
    # Reset a stale failed-epoch token ONLY for sink identity loss, not each
    # new matching EDID base/extension, otherwise the 30Hz fallback is blind.
    s=once(s,
        "            yogaHDMI2WakeProven.valid=false;\n",
        "            yogaHDMI2WakeProven.valid=false;\n"
        "            __atomic_store_n(&yogaHDMI2WakeMissingCTAAtGen,0U,__ATOMIC_RELEASE);\n"
        "            __atomic_store_n(&yogaHDMI2WakeCompletedNativeFB1WakeAt,0ULL,__ATOMIC_RELEASE);\n",
        "clear new state on changed AOC EDID")
    # At a low speed native caller, the formerly-armed token may be gone
    # solely due to an EDID re-read; only allow a narrow, proven exception.
    old_low="""    if(allowWrite && pixelHz<=YogaHDMI2::HighTMDSHz &&
       __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)>=3U)return 52;"""
    new_low="""    bool lowReconcile=false;
    if(allowWrite && pixelHz<=YogaHDMI2::HighTMDSHz &&
       __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)>=3U) {
        lowReconcile=yogaHDMI2MayReconcileLow(port,path,pipe,lock);
        if(!lowReconcile)return 52;
    }"""
    s=once(s,old_low,new_low,"fail-closed low mode exception")
    # These bits explain the full-capability gate even in the diagnostic-only
    # A group. Only the existing SCDC transaction writes to the sink.
    old_flag="""        (yogaHDMI2WakeRecover?4096U:0U);"""
    new_flag="""        (yogaHDMI2WakeRecover?4096U:0U)|
        (baseMatches?8192U:0U)|
        (eligible.newGeneration?16384U:0U)|
        (eligible.alreadyAttempted?32768U:0U);"""
    s=once(s,old_flag,new_flag,"preserve R3 gate reason bits")
    # Record a high-mode return-10 only if we were actually inside an
    # already-confirmed native FB1 Doze->Wake cycle, with same sink/EDID.
    old_fail="""        yogaHDMI2WakeRecord(3U,generation,pipe,pixelHz,10U,wakeFlags,
            caps.maxKHz,wakeAttemptGeneration);
        return 10;"""
    new_fail="""        if(pixelHz>YogaHDMI2::HighTMDSHz && same && baseMatches &&
           yogaHDMI2WakeBaseExact && yogaHDMI2WakeProven.valid &&
           !yogaHDMI2WakeCTASeen && (wakeTimeBits&3U)==3U) {
            IOSimpleLockLock(lock);
            if(yogaHDMI2Live.generation==generation &&
               !yogaHDMI2WakeCTASeen &&
               yogaHDMI2WakeProven.valid)
                __atomic_store_n(&yogaHDMI2WakeMissingCTAAtGen,
                                 generation,__ATOMIC_RELEASE);
            IOSimpleLockUnlock(lock);
        }
        yogaHDMI2WakeRecord(3U,generation,pipe,pixelHz,10U,wakeFlags,
            caps.maxKHz,wakeAttemptGeneration);
        return 10;"""
    s=once(s,old_fail,new_fail,"record genuine post-Doze capability miss")
    # Do not allow the low transition after a successful high recovery. It
    # no longer represents stale high state and must not be blindly cleared.
    s=once(s,"                yogaHDMI2WakeProven.valid=true;\n",
        "                yogaHDMI2WakeProven.valid=true;\n"
        "                __atomic_store_n(&yogaHDMI2WakeMissingCTAAtGen,0U,__ATOMIC_RELEASE);\n",
        "reset failed wake on real successful high")
    old_success="""    } else __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    if(wakeCandidate)yogaHDMI2WakeRecord(5U,generation,pipe,pixelHz,
        110U,wakeFlags,caps.maxKHz,generation);
    return plan.highTMDS?(wakeCandidate?110:100):101;"""
    new_success="""    } else {
        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
        if(lowReconcile) {
            __atomic_store_n(&yogaHDMI2WakeMissingCTAAtGen,0U,__ATOMIC_RELEASE);
            yogaHDMI2WakeRecord(7U,generation,pipe,pixelHz,
                101U,wakeFlags,caps.maxKHz,0U);
        }
    }
    if(wakeCandidate) {
        __atomic_store_n(&yogaHDMI2WakeMissingCTAAtGen,0U,__ATOMIC_RELEASE);
        yogaHDMI2WakeRecord(5U,generation,pipe,pixelHz,
            110U,wakeFlags,caps.maxKHz,generation);
    }
    return plan.highTMDS?(wakeCandidate?110:100):101;"""
    s=once(s,old_success,new_success,"record SCDC readback and low cleanup success")
    s=once(s,"if(event>=4U && event<=6U)",
        "if(event>=4U && event<=7U)",
        "retain one-time low cleanup event")
    # No new touch of path/PHY/PLL: same original SCDC routine only.
    assert s.count("YogaHDMI2::prepareSCDC(")==1
    assert s.count("yogaHDMI2MayReconcileLow(")==2
    return s

def patch_power(s):
    # R2 already observes Doze and Wake transitions. R3 merely remembers
    # successful wake completion for a later user-triggered 30Hz modeset.
    old="""            __atomic_store_n(&yogaHDMI2WakeNativeFB1DozeAt,
                confirmed?mach_absolute_time():0ULL,__ATOMIC_RELEASE);
        }
        // Never leave a power-wake recovery window armed after return,"""
    new="""            __atomic_store_n(&yogaHDMI2WakeNativeFB1DozeAt,
                confirmed?mach_absolute_time():0ULL,__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeCompletedNativeFB1WakeAt,
                0ULL,__ATOMIC_RELEASE);
        }
        if(state==2U && yogaPowerPrior==1U) {
            const bool completed=result==kIOReturnSuccess &&
                __atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE)!=0;
            __atomic_store_n(&yogaHDMI2WakeCompletedNativeFB1WakeAt,
                completed?mach_absolute_time():0ULL,__ATOMIC_RELEASE);
        }
        // Never leave a power-wake recovery window armed after return,"""
    return once(s,old,new,"native wake completion only")

def main(root):
    hp=root/"WhateverXe/kern_yoga_hdmi2_candidate.hpp"
    pp=root/"WhateverXe/kern_display13_framebuffer_power.inc"
    out_h=patch_header(hp.read_text())
    out_p=patch_power(pp.read_text())
    target=root/"WhateverXe/kern_yoga_hdmi2_session_policy.hpp"
    policy=Path(__file__).resolve().parent/"kern_yoga_hdmi2_session_policy.hpp"
    if target.exists():raise RuntimeError("R3 native donor already has session policy")
    if not policy.is_file():raise RuntimeError("missing R3 pure session policy")
    hp.write_text(out_h)
    pp.write_text(out_p)
    shutil.copyfile(policy,target)
    subprocess.run(["git","-C",str(root),"diff","--check"],check=True)
    print("PASS R3: previous native FB1 wake failure is separate from fresh CTA cache")
    print("PASS R3: strict one-time 30Hz SCDC cleanup only after verified matching AOC/CTA and old source flags")
    print("PASS R3: no new hooks, MMIO writes, modeset requests, or USB-C/SST changes")

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("source",type=Path)
    args=a.parse_args()
    main(args.source.resolve())
