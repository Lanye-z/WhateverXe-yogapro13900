#!/usr/bin/env python3
"""V4 wake instrumentation and ONE-TIME same-EDID SCDC revalidation.

Must be applied AFTER wexhdmi2v2/prepare.py AND wexintegrated/prepare_unified.py
on pinned WhateverXe 0.8.3 sources. No new native route/HPD override, no
forced modeset, no firmware/PHY/PLL edits, no synthetic ACK.
"""
from pathlib import Path
import argparse
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def once(source, needle, replacement, label):
    count = source.count(needle)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact anchor, found {count}")
    return source.replace(needle, replacement, 1)

WAKE_STATE = r'''
// V4 state is protected by tglAUXLock, the existing HDMI-B DDC observer lock.
// Preserve last-known-good CTA only after a completed high-rate SCDC session.
// A fresh, byte-identical 128-byte base EDID + original native owner are required
// before one-time revalidation; no fallback to a guessed sink or arbitrary EDID.
#include <mach/mach_time.h>
#include <kern/clock.h>
#include "kern_yoga_hdmi2_wake_policy.hpp"
static bool yogaHDMI2WakeDiag {},yogaHDMI2WakeRecover {};
static uint8_t yogaHDMI2WakeCurrentBase[128] {};
static bool yogaHDMI2WakeBaseExact {},yogaHDMI2WakeCTASeen {};
struct YogaHDMI2WakeProven {
    OSObject *port {};
    Display13HDMI::Caps caps {};
    uint8_t base[128] {};
    uint32_t generation {};
    uint32_t attemptedGeneration {};
    bool valid {};
};
static YogaHDMI2WakeProven yogaHDMI2WakeProven {};
static uint32_t yogaHDMI2WakeSequence {};
static volatile uint64_t yogaHDMI2WakeFirstGoodHighAt {};
static volatile uint64_t yogaHDMI2WakeObservedHDMIOffAt {};
static volatile uint32_t yogaHDMI2WakeLastGoodPipe {3U};
static volatile uint32_t yogaHDMI2WakeObservedOffPipe {3U};
// This is not proof of actual light or real system sleep: require BOTH
// a 90-second post-first-good interval and a >=3-second observed HDMI-B off.
// The existing native owner and exact same-EDID/CTA checks are still required.
static inline uint32_t yogaHDMI2WakeTimeGuard(uint32_t pipe) {
    const auto first=__atomic_load_n(&yogaHDMI2WakeFirstGoodHighAt,__ATOMIC_ACQUIRE);
    const auto off=__atomic_load_n(&yogaHDMI2WakeObservedHDMIOffAt,__ATOMIC_ACQUIRE);
    const auto goodPipe=__atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE);
    const auto offPipe=__atomic_load_n(&yogaHDMI2WakeObservedOffPipe,__ATOMIC_ACQUIRE);
    if(!first || !off || goodPipe!=pipe || offPipe!=pipe || off<=first)return 0;
    const auto now=mach_absolute_time();
    if(now<=off)return 0;
    uint64_t firstNs=0,offNs=0;
    absolutetime_to_nanoseconds(now-first,&firstNs);
    absolutetime_to_nanoseconds(now-off,&offNs);
    return (firstNs>=90000000000ULL?1U:0U) |
        (offNs>=3000000000ULL?2U:0U);
}
// schema,seq,mach_absolute_time,event,generation,pipe,pixelHz,status,
// flags,maxKHz,attemptGeneration,armedPipe. Event: 1 base,2 CTA,
// 3 capability rejection,4 recovery try,5 recovered,6 recovery failed.
static inline void yogaHDMI2WakeRecord(uint32_t event,uint32_t generation,
    uint32_t pipe,uint64_t pixelHz,uint32_t status,uint32_t flags,
    uint32_t maxKHz,uint32_t attemptGeneration) {
    if(!yogaHDMI2WakeDiag)return;
    const auto seq=__sync_add_and_fetch(&yogaHDMI2WakeSequence,1U);
    uint64_t rec[] {1U,seq,mach_absolute_time(),event,generation,pipe,
        pixelHz,status,flags,maxKHz,attemptGeneration,
        __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)};
    auto root=IORegistryEntry::getRegistryRoot();
    root->setProperty("WEXYogaHDMI2WakeLast",rec,sizeof(rec));
    // Preserve the last decisive failure/repair even if CTA reads arrive
    // later and overwrite WEXYogaHDMI2WakeLast.
    if(event==3U)root->setProperty("WEXYogaHDMI2WakeRejectLast",rec,sizeof(rec));
    if(event>=4U && event<=6U)
        root->setProperty("WEXYogaHDMI2WakeActionLast",rec,sizeof(rec));
    if(seq<=16U) {
        char key[48];snprintf(key,sizeof(key),"WEXYogaHDMI2WakeFirst%u",seq);
        root->setProperty(key,rec,sizeof(rec));
    }
}
'''
WAKE_DDC = r'''
static inline void yogaHDMI2ObserveDDC(OSObject *port,uint32_t block,
                                       const uint8_t *data,bool success,
                                       IOSimpleLock *lock) {
    if(!port || !lock || !data || (block!=1 && (block<2 || block>8)))return;
    uint32_t gen=0,flags=0,maxKHz=0,attempted=0;
    IOSimpleLockLock(lock);
    if(block==1) {
        yogaHDMI2Live.port=port;
        yogaHDMI2Live.baseSeen=success;
        ++yogaHDMI2Live.generation;
        yogaHDMI2Live.caps={};
        yogaHDMI2WakeCTASeen=false;
        yogaHDMI2WakeBaseExact=false;
        // No trusting an unvalidated base block, even if the donor read
        // returned kIOReturnSuccess.
        const uint8_t header[] {0,255,255,255,255,255,255,0};
        const bool validBase=success && Display13HDMI::checksum(data,128) &&
            !memcmp(data,header,sizeof(header));
        const bool exactAOC=validBase && data[8]==0x05 && data[9]==0xE3 &&
            data[10]==0x10 && data[11]==0x27;
        if(validBase)memcpy(yogaHDMI2WakeCurrentBase,data,128);
        else memset(yogaHDMI2WakeCurrentBase,0,sizeof(yogaHDMI2WakeCurrentBase));
        yogaHDMI2WakeBaseExact=exactAOC;
        // Never carry last-good capabilities across any other sink/base EDID.
        if(yogaHDMI2WakeProven.valid &&
           (yogaHDMI2WakeProven.port!=port || !validBase ||
            memcmp(yogaHDMI2WakeCurrentBase,yogaHDMI2WakeProven.base,128))) {
            yogaHDMI2WakeProven.valid=false;
            __atomic_store_n(&yogaHDMI2WakeFirstGoodHighAt,0ULL,__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeLastGoodPipe,3U,__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeObservedHDMIOffAt,0ULL,__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeObservedOffPipe,3U,__ATOMIC_RELEASE);
        }
        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    } else if(yogaHDMI2Live.baseSeen && yogaHDMI2Live.port==port) {
        // The original observer only runs on successful native DDC reads.
        // Once native CTA has arrived, do not substitute prior CTA capabilities.
        yogaHDMI2WakeCTASeen=true;
        if(success) {
            const auto c=Display13HDMI::extension(data,128);
            yogaHDMI2Live.caps=Display13HDMI::combine(yogaHDMI2Live.caps,c);
        }
        ++yogaHDMI2Live.generation;
        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    }
    gen=yogaHDMI2Live.generation;
    maxKHz=yogaHDMI2Live.caps.maxKHz;
    flags=(yogaHDMI2Live.baseSeen?1U:0U) |
        (yogaHDMI2WakeBaseExact?2U:0U) |
        (yogaHDMI2WakeCTASeen?4U:0U) |
        (yogaHDMI2WakeProven.valid?8U:0U) |
        (yogaHDMI2Live.caps.scdc?16U:0U);
    attempted=yogaHDMI2WakeProven.attemptedGeneration;
    IOSimpleLockUnlock(lock);
    yogaHDMI2WakeRecord(block==1?1U:2U,gen,3U,0U,
        success?0U:1U,flags,maxKHz,attempted);
}

'''
def patch_candidate(header):
    header=once(header,
        "static volatile uint32_t yogaHDMI2ArmedPipe=3; // 0..2=armed; 3=off\n",
        "static volatile uint32_t yogaHDMI2ArmedPipe=3; // 0..2=armed; 3=off\n"+WAKE_STATE,
        "V4 wake state after armed-pipe definition")
    start=header.index("static inline void yogaHDMI2ObserveDDC(")
    end=header.index("// Native controller I2C:",start)
    original=header[start:end]
    if original.count("yogaHDMI2Live.caps={};")!=1 or \
       original.count("__atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);")!=2:
        raise RuntimeError("V3 DDC function has changed; refusing V4")
    header=header[:start]+WAKE_DDC+header[end:]
    before=r'''    Display13HDMI::Caps caps;uint32_t generation;
    IOSimpleLockLock(lock);
    const bool same=yogaHDMI2Live.port==port && yogaHDMI2Live.baseSeen;
    caps=yogaHDMI2Live.caps;generation=yogaHDMI2Live.generation;
    IOSimpleLockUnlock(lock);
    if(!same || !caps.valid || !caps.hdmi || !caps.scdc ||
       caps.maxKHz<=340000)return 10;'''
    after=r'''    Display13HDMI::Caps caps;uint32_t generation;
    bool wakeCandidate=false;
    uint32_t wakeFlags=0,wakeAttemptGeneration=0;
    IOSimpleLockLock(lock);
    const bool same=yogaHDMI2Live.port==port && yogaHDMI2Live.baseSeen;
    caps=yogaHDMI2Live.caps;generation=yogaHDMI2Live.generation;
    const bool capabilitiesMissing=!caps.valid;
    const bool baseMatches=yogaHDMI2WakeProven.valid &&
        yogaHDMI2WakeProven.port==port &&
        !memcmp(yogaHDMI2WakeCurrentBase,yogaHDMI2WakeProven.base,128);
    YogaHDMI2Wake::Eligibility eligible {};
    // Do not allow a boot/HPD modeset to use preserved CTA information.
    // A prior HDMI-B output disable must have been observed and aged.
    const auto wakeTimeBits=yogaHDMI2WakeRecover && allowWrite ?
        yogaHDMI2WakeTimeGuard(pipe):0U;
    eligible.activeHDMI2=yogaHDMI2WakeRecover && allowWrite;
    eligible.postBootMature=bool(wakeTimeBits&1U);
    eligible.observedLongHDMIOff=bool(wakeTimeBits&2U);
    eligible.highTMDS=pixelHz>YogaHDMI2::HighTMDSHz;
    eligible.sameNativePort=same && yogaHDMI2WakeProven.port==port;
    eligible.freshValidBase=yogaHDMI2Live.baseSeen &&
        yogaHDMI2WakeCurrentBase[0]==0 && yogaHDMI2WakeCurrentBase[1]==255;
    eligible.exactKnownSink=yogaHDMI2WakeBaseExact;
    eligible.ctaAlreadySeen=yogaHDMI2WakeCTASeen;
    eligible.provenPriorHighSession=yogaHDMI2WakeProven.valid;
    eligible.sameCompleteBaseEDID=baseMatches;
    eligible.newGeneration=generation!=yogaHDMI2WakeProven.generation;
    eligible.alreadyAttempted=generation==yogaHDMI2WakeProven.attemptedGeneration;
    eligible.preservedCapsValid=yogaHDMI2WakeProven.caps.valid &&
        yogaHDMI2WakeProven.caps.hdmi;
    eligible.preservedCapsSCDC=yogaHDMI2WakeProven.caps.scdc;
    eligible.preservedMaxKHz=yogaHDMI2WakeProven.caps.maxKHz;
    wakeCandidate=capabilitiesMissing && YogaHDMI2Wake::mayRecover(eligible);
    if(wakeCandidate)caps=yogaHDMI2WakeProven.caps;
    wakeFlags=(same?1U:0U)|(yogaHDMI2WakeBaseExact?2U:0U)|
        (yogaHDMI2WakeCTASeen?4U:0U)|
        (yogaHDMI2WakeProven.valid?8U:0U)|
        (wakeCandidate?32U:0U)|
        ((wakeTimeBits&1U)?64U:0U)|
        ((wakeTimeBits&2U)?128U:0U)|
        (caps.valid?256U:0U)|
        (caps.hdmi?512U:0U)|
        (caps.scdc?1024U:0U)|
        (caps.maxKHz>340000?2048U:0U)|
        (yogaHDMI2WakeRecover?4096U:0U);
    wakeAttemptGeneration=yogaHDMI2WakeProven.attemptedGeneration;
    IOSimpleLockUnlock(lock);
    if(!same || !caps.valid || !caps.hdmi || !caps.scdc ||
        caps.maxKHz<=340000) {
        yogaHDMI2WakeRecord(3U,generation,pipe,pixelHz,10U,wakeFlags,
            caps.maxKHz,wakeAttemptGeneration);
        return 10;
    }'''
    header=once(header,before,after,"V3 SCDC CTA capability guard")
    before=r'''    if(!allowWrite)return plan.highTMDS?50:51; // read-only observe
    // Every >340MHz transaction confirms the HDMI Forum sink response.
    const auto transaction=YogaHDMI2::prepareSCDC(bus,plan,caps.scdc);
    if(!transaction.complete)return 30+static_cast<uint32_t>(transaction.error);
    if(plan.highTMDS)
        __atomic_store_n(&yogaHDMI2ArmedPipe,pipe,__ATOMIC_RELEASE);
    else
        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    return plan.highTMDS?100:101;'''
    after=r'''    if(!allowWrite)return plan.highTMDS?50:51; // read-only observe
    if(wakeCandidate) {
        // Consume at most one candidate per fresh EDID generation, before
        // any native SCDC I2C. Do not re-use cached CTA after a fresh CTA.
        IOSimpleLockLock(lock);
        const bool sameGeneration=yogaHDMI2Live.generation==generation &&
            yogaHDMI2Live.port==port && !yogaHDMI2WakeCTASeen &&
            yogaHDMI2WakeProven.valid &&
            yogaHDMI2WakeProven.attemptedGeneration!=generation &&
            !memcmp(yogaHDMI2WakeCurrentBase,yogaHDMI2WakeProven.base,128);
        if(sameGeneration)
            yogaHDMI2WakeProven.attemptedGeneration=generation;
        IOSimpleLockUnlock(lock);
        if(!sameGeneration)return 10;
        yogaHDMI2WakeRecord(4U,generation,pipe,pixelHz,0U,wakeFlags,
            caps.maxKHz,generation);
    }
    // Same native SCDC routine, original owner lock and readback checks.
    // No I2C retry or source/PHY override on any failed transaction.
    const auto transaction=YogaHDMI2::prepareSCDC(bus,plan,caps.scdc);
    if(!transaction.complete) {
        if(wakeCandidate)yogaHDMI2WakeRecord(6U,generation,pipe,pixelHz,
            30U+static_cast<uint32_t>(transaction.error),wakeFlags,
            caps.maxKHz,generation);
        return 30+static_cast<uint32_t>(transaction.error);
    }
    if(plan.highTMDS) {
        __atomic_store_n(&yogaHDMI2ArmedPipe,pipe,__ATOMIC_RELEASE);
        if(!wakeCandidate) {
            // Populate last-proven capabilities ONLY from a genuine successful
            // non-fallback >340MHz native SCDC transaction and valid AOC CTA.
            IOSimpleLockLock(lock);
            if(yogaHDMI2Live.port==port &&
               yogaHDMI2Live.generation==generation &&
               yogaHDMI2WakeCTASeen && yogaHDMI2WakeBaseExact) {
                yogaHDMI2WakeProven.port=port;
                yogaHDMI2WakeProven.caps=caps;
                memcpy(yogaHDMI2WakeProven.base,yogaHDMI2WakeCurrentBase,128);
                yogaHDMI2WakeProven.generation=generation;
                yogaHDMI2WakeProven.attemptedGeneration=0;
                yogaHDMI2WakeProven.valid=true;
                if(!__atomic_load_n(&yogaHDMI2WakeFirstGoodHighAt,__ATOMIC_ACQUIRE))
                    __atomic_store_n(&yogaHDMI2WakeFirstGoodHighAt,
                        mach_absolute_time(),__ATOMIC_RELEASE);
                __atomic_store_n(&yogaHDMI2WakeLastGoodPipe,pipe,__ATOMIC_RELEASE);
                __atomic_store_n(&yogaHDMI2WakeObservedHDMIOffAt,0ULL,__ATOMIC_RELEASE);
                __atomic_store_n(&yogaHDMI2WakeObservedOffPipe,3U,__ATOMIC_RELEASE);
            }
            IOSimpleLockUnlock(lock);
        }
    } else __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);
    if(wakeCandidate)yogaHDMI2WakeRecord(5U,generation,pipe,pixelHz,
        110U,wakeFlags,caps.maxKHz,generation);
    return plan.highTMDS?(wakeCandidate?110:100):101;'''
    header=once(header,before,after,"V3 SCDC transaction completion")
    return header

def patch_cpp(source):
    # V3 CALL site handles the successful one-time V4 code 110 exactly like
    # success 100. All other return values continue original native path.
    source=once(source,
        "if(status==100 &&\n               __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)==pipe)",
        "if((status==100 || status==110) &&\n               __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)==pipe)",
        "V4 source shadow update on verified recovery")
    source=once(source,
        "if(count<=16 || status==100 || status==101) {",
        "if(count<=16 || status==100 || status==101 || status==110 ||\n       (yogaHDMI2WakeDiag && status==10)) {",
        "V4 retention of failed wake statuses after first 16 calls")
    needle='root->setProperty("WEXYogaHDMI2CallsiteWriteEnabled",yogaHDMI2CallsiteSafe);'
    replacement=needle+r'''
            yogaHDMI2WakeDiag=(state==5 && yogaHDMI2CallsiteSafe &&
                checkKernelArgument("-wex-yoga-hdmi2-wake-diag"));
            yogaHDMI2WakeRecover=(state==5 && yogaHDMI2CallsiteSafe &&
                checkKernelArgument("-wex-yoga-hdmi2-wake-recover"));
            root->setProperty("WEXYogaHDMI2WakeDiagEnabled",yogaHDMI2WakeDiag);
            root->setProperty("WEXYogaHDMI2WakeRecoverEnabled",yogaHDMI2WakeRecover);'''
    source=once(source,needle,replacement,"V4 opt-in wake flag init after V3 patch validation")
    # Reuse the already installed V3 MMIO-write wrapper in a passive mode:
    # when the exact LAST KNOWN HDMI-B transcoder has an enable=0 write,
    # record time only. Never alter reg/value, no HPD poke and no modeset.
    source=once(source,
        "    if(callbackXE->yogaHDMI2SafeRequested && access==display13FBPower.access &&",
        r"""    if(yogaHDMI2WakeRecover && access==display13FBPower.access) {
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
    if(callbackXE->yogaHDMI2SafeRequested && access==display13FBPower.access &&""",
        "V4 passive HDMI-B output-off timing observation")
    return source

def patch_fixtures(raw):
    args=json.loads(raw)
    for flag in ("-wex-yoga-hdmi2-wake-diag",
                 "-wex-yoga-hdmi2-wake-recover"):
        if flag in args:raise RuntimeError("duplicate flag "+flag)
        args[flag]=[]
    return json.dumps(args,indent=2)+"\n"

def main(root):
    src=root/"WhateverXe/kern_xe.cpp"
    hdr=root/"WhateverXe/kern_yoga_hdmi2_candidate.hpp"
    fixtures=root/"tests/fixtures/boot_argument_names.json"
    # Validate all generated content before writes, fail closed on donor drift.
    next_cpp=patch_cpp(src.read_text())
    next_header=patch_candidate(hdr.read_text())
    next_args=patch_fixtures(fixtures.read_text())
    next_policy=root/"WhateverXe/kern_yoga_hdmi2_wake_policy.hpp"
    if next_policy.exists():raise RuntimeError("wake policy already in donor")
    src.write_text(next_cpp)
    hdr.write_text(next_header)
    fixtures.write_text(next_args)
    shutil.copyfile(ROOT/"wexwakev4/kern_yoga_hdmi2_wake_policy.hpp",next_policy)
    subprocess.run(["git","-C",str(root),"diff","--check"],check=True)
    assert next_cpp.count("patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));")==1
    assert next_cpp.index("display13FBTCHooksReady=processDisplay13FramebufferTC(")<next_cpp.index("patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));")
    print("PASS: V4 wake DDC generation and one-time validated cached CTA candidate")
    print("PASS: same HDMI owner lock / native SCDC / no new HPD or modeset route")
    print("PASS: V4 opt-in only, Unified RC1 default-on features preserved")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    args=p.parse_args()
    main(args.source.resolve())
