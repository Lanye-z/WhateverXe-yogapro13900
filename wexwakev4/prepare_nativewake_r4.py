#!/usr/bin/env python3
"""R4: remove arbitrary 90s/3s delay gates and preserve 32-event mode history.

Apply AFTER R3 on pinned WhateverXe 0.8.3 with the existing Unified overlay.
Only existing native framebuffer callback and existing HDMI LightUpTMDS CALL
site are touched. No new hook, forced HPD, modeset, I2C request, PHY, DBUF,
watermark, SST/DP, sleep override, or timer.
"""
from pathlib import Path
import argparse
import subprocess


def once(s, old, replacement, why):
    count=s.count(old)
    if count!=1:
        raise RuntimeError(f"R4 {why}: expected one anchor, found {count}")
    return s.replace(old,replacement,1)


POWER_EVIDENCE=r'''// R4: replace artificial 90s/3s periods with verified power transitions.
// The original FB1 power hook is the only writer of inNativeFB1Wake.
// No boot-only high-rate SCDC success can satisfy the Doze->Wake criterion.
static inline uint32_t yogaHDMI2WakeTimeGuard(uint32_t pipe) {
    YogaHDMI2Wake::PowerEvidence p {};
    const auto lastPipe=__atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE);
    p.sameFB1=pipe==1U && lastPipe==pipe;
    p.nativeDozeToWakeWindow=
        __atomic_load_n(&yogaHDMI2WakeInNativeFB1Wake,__ATOMIC_ACQUIRE)==1U;
    p.firstHighAt=__atomic_load_n(&yogaHDMI2WakeFirstGoodHighAt,__ATOMIC_ACQUIRE);
    p.nativeDozeAt=__atomic_load_n(&yogaHDMI2WakeNativeFB1DozeAt,__ATOMIC_ACQUIRE);
    p.now=mach_absolute_time();
    return YogaHDMI2Wake::qualifyPowerEvidence(p);
}
'''

DIAG_GLOBALS=r'''// Diagnostic-only historical evidence. Neither of these snapshots is a
// live-link authorization: the live generation and CTA validity remain the
// authority for the original SCDC transaction.
static volatile uint32_t yogaHDMI2R4LastDDCGen {};
static volatile uint32_t yogaHDMI2R4LastDDCFlags {};
static volatile uint32_t yogaHDMI2R4LastDDCMaxKHz {};
static volatile uint32_t yogaHDMI2R4LastSCDCSuccessGen {};
static volatile uint32_t yogaHDMI2R4LastSCDCSuccessStatus {};
'''

CALLSITE_HISTORY=r'''    if(yogaHDMI2WakeDiag) {
        // Bounded 32-slot chronological journal: seq and mach_absolute_time
        // disambiguate wraps. The original First1..8/Last are also retained.
        // No extra native I2C, register read, or display state change.
        uint64_t trace[20] {
            4U,count,yogaCallStartedAt,mach_absolute_time(),pipe,clock,
            status,result,record[6],record[11],shadowBefore,shadowAfter,
            __atomic_load_n(&yogaHDMI2R4LastDDCGen,__ATOMIC_ACQUIRE),
            __atomic_load_n(&yogaHDMI2R4LastDDCFlags,__ATOMIC_ACQUIRE),
            __atomic_load_n(&yogaHDMI2R4LastDDCMaxKHz,__ATOMIC_ACQUIRE),
            __atomic_load_n(&yogaHDMI2R4LastSCDCSuccessGen,__ATOMIC_ACQUIRE),
            __atomic_load_n(&yogaHDMI2R4LastSCDCSuccessStatus,__ATOMIC_ACQUIRE),
            yogaHDMI2WakeRecover?1ULL:0ULL,
            __atomic_load_n(&yogaHDMI2WakeInNativeFB1Wake,__ATOMIC_ACQUIRE),
            __atomic_load_n(&yogaHDMI2WakeLastGoodPipe,__ATOMIC_ACQUIRE)
        };
        char key[52];
        snprintf(key,sizeof(key),"WEXYogaHDMI2CallsiteHist%02u",
            static_cast<unsigned>((count-1U)%32U+1U));
        IORegistryEntry::getRegistryRoot()->setProperty(key,trace,sizeof(trace));
    }
'''

POWER_HISTORY=r'''            IORegistryEntry::getRegistryRoot()->setProperty(
                "WEXYogaHDMI2WakePowerLast",record,sizeof(record));
            char historyKey[52];
            snprintf(historyKey,sizeof(historyKey),"WEXYogaHDMI2WakePowerHist%02u",
                static_cast<unsigned>((record[1]-1ULL)%32ULL+1ULL));
            IORegistryEntry::getRegistryRoot()->setProperty(
                historyKey,record,sizeof(record));'''


def patch_header(s):
    start="static inline uint32_t yogaHDMI2WakeTimeGuard(uint32_t pipe) {"
    assert s.count(start)==1, "R2 wake time helper anchor changed"
    i=s.index(start)
    j=s.find("\n}\n",i)
    if j<=i:raise RuntimeError("R4 could not find wake helper end")
    old=s[i:j+3]
    assert "90000000000ULL" in old and "3000000000ULL" in old, "expected R2 time gate"
    s=s[:i]+POWER_EVIDENCE+s[j+3:]
    s=once(s,"eligible.postBootMature=bool(wakeTimeBits&1U);",
        "eligible.priorNativeHighConfirmed=bool(wakeTimeBits&1U);",
        "pure eligibility field")
    # Preserve active CTA generation updates; they continue invalidating
    # yogaHDMI2ArmedPipe for safety. Keep a *separate* LAST SCDC success fact.
    s=once(s,"// schema,seq,mach_absolute_time,event,generation,pipe,pixelHz,status,",
        DIAG_GLOBALS+"\n// schema,seq,mach_absolute_time,event,generation,pipe,pixelHz,status,",
        "diagnostic history fields")
    anchor="""    IOSimpleLockUnlock(lock);
    yogaHDMI2WakeRecord(block==1?1U:2U,gen,3U,0U,"""
    repl="""    IOSimpleLockUnlock(lock);
    __atomic_store_n(&yogaHDMI2R4LastDDCGen,gen,__ATOMIC_RELEASE);
    __atomic_store_n(&yogaHDMI2R4LastDDCFlags,flags,__ATOMIC_RELEASE);
    __atomic_store_n(&yogaHDMI2R4LastDDCMaxKHz,maxKHz,__ATOMIC_RELEASE);
    yogaHDMI2WakeRecord(block==1?1U:2U,gen,3U,0U,"""
    s=once(s,anchor,repl,"DDC generation publishing after original lock")
    s=once(s,
        "    if(plan.highTMDS) {\n        __atomic_store_n(&yogaHDMI2ArmedPipe,pipe,__ATOMIC_RELEASE);",
        """    if(plan.highTMDS) {
        // Last *completed* sink readback, not necessarily a currently live
        // session. EDID/CTA may invalidate armedPipe without erasing history.
        __atomic_store_n(&yogaHDMI2R4LastSCDCSuccessGen,generation,__ATOMIC_RELEASE);
        __atomic_store_n(&yogaHDMI2R4LastSCDCSuccessStatus,
                         wakeCandidate?110U:100U,__ATOMIC_RELEASE);
        __atomic_store_n(&yogaHDMI2ArmedPipe,pipe,__ATOMIC_RELEASE);""",
        "high SCDC historical evidence only after completed transaction")
    s=once(s,
        "    } else {\n        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);",
        """    } else {
        __atomic_store_n(&yogaHDMI2R4LastSCDCSuccessGen,generation,__ATOMIC_RELEASE);
        __atomic_store_n(&yogaHDMI2R4LastSCDCSuccessStatus,101U,__ATOMIC_RELEASE);
        __atomic_store_n(&yogaHDMI2ArmedPipe,3U,__ATOMIC_RELEASE);""",
        "low SCDC completed readback history")
    # The 110 and 100 return paths remain unchanged. An EDID update still
    # revokes armedPipe and the current-generation check is never weakened.
    assert s.count("YogaHDMI2::prepareSCDC(")==1
    assert s.count("yogaHDMI2WakeTimeGuard(pipe)")==1
    assert "90000000000ULL" not in s and "3000000000ULL" not in s
    return s


def patch_cpp(s):
    s=once(s,
        "    uint64_t record[12] {2,count};",
        "    uint64_t record[12] {2,count};\n"
        "    const uint64_t yogaCallStartedAt=yogaHDMI2WakeDiag ? "
        "mach_absolute_time():0ULL;",
        "CALL-site start timestamp")
    anchor="""    if(count<=16 || status==100 || status==101 || status==110 ||
       (yogaHDMI2WakeDiag && status==10)) {"""
    s=once(s,anchor,CALLSITE_HISTORY+anchor,"last 32 CALL-site events")
    assert s.count("patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));")==1
    assert s.count("yogaHDMI2Callsite(void *controller")==1
    return s


def patch_native_power(s):
    anchor='''            IORegistryEntry::getRegistryRoot()->setProperty(
                "WEXYogaHDMI2WakePowerLast",record,sizeof(record));'''
    s=once(s,anchor,POWER_HISTORY,"last 32 native FB1 Doze/Wake callbacks")
    assert s.count("uint32_t XE::wrapDisplay13SetPowerState(")==1
    assert s.count("FunctionCast(wrapDisplay13SetPowerState,callbackXE->orgDSIAttributes[2])(fb,state);")==1
    return s


def main(root):
    h=root/"WhateverXe/kern_yoga_hdmi2_candidate.hpp"
    cpp=root/"WhateverXe/kern_xe.cpp"
    native=root/"WhateverXe/kern_display13_framebuffer_power.inc"
    hh=patch_header(h.read_text())
    cc=patch_cpp(cpp.read_text())
    nn=patch_native_power(native.read_text())
    h.write_text(hh)
    cpp.write_text(cc)
    native.write_text(nn)
    subprocess.run(["git","-C",str(root),"diff","--check"],check=True)
    print("PASS R4: no wall-clock 90s/Doze 3s requirement; require validated native FB1 power cycle")
    print("PASS R4: old armedPipe safety invalidation preserved; SCDC success history is separate and read-only")
    print("PASS R4: 32 bounded CALL-site + 32 native FB1 power records; no HPD/DP/SST/modeset hooks added")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    args=p.parse_args()
    main(args.source.resolve())
