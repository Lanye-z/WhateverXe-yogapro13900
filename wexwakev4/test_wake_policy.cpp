#include "kern_yoga_hdmi2_wake_policy.hpp"
#include <cassert>
#include <cstdio>
using YogaHDMI2Wake::Eligibility;
using YogaHDMI2Wake::mayRecover;
using YogaHDMI2Wake::PowerEvidence;
using YogaHDMI2Wake::qualifyPowerEvidence;
int main() {
    Eligibility q {};
    assert(!mayRecover(q));
    q={true,true,true,true,true,false,true,true,true,false,true,true,true,true,600000};
    assert(mayRecover(q));
    {
        Eligibility t=q; t.activeHDMI2=false; assert(!mayRecover(t));
        t=q; t.highTMDS=false; assert(!mayRecover(t));
        t=q; t.sameNativePort=false; assert(!mayRecover(t));
        t=q; t.freshValidBase=false; assert(!mayRecover(t));
        t=q; t.exactKnownSink=false; assert(!mayRecover(t));
        t=q; t.ctaAlreadySeen=true; assert(!mayRecover(t));
        t=q; t.provenPriorHighSession=false; assert(!mayRecover(t));
        t=q; t.sameCompleteBaseEDID=false; assert(!mayRecover(t));
        t=q; t.newGeneration=false; assert(!mayRecover(t));
        t=q; t.alreadyAttempted=true; assert(!mayRecover(t));
        t=q; t.priorNativeHighConfirmed=false; assert(!mayRecover(t));
        t=q; t.nativeDozeWakeVerified=false; assert(!mayRecover(t));
        t=q; t.preservedCapsValid=false; assert(!mayRecover(t));
        t=q; t.preservedCapsSCDC=false; assert(!mayRecover(t));
        t=q; t.preservedMaxKHz=340000; assert(!mayRecover(t));
        t=q; t.preservedMaxKHz=600001; assert(!mayRecover(t));
    }
    // The native 1.37-second Doze observed in real R3 logs now qualifies.
    // Neither initial startup nor an unrelated HPD re-enumeration qualifies.
    PowerEvidence p {true,true,1000000000ULL,1200000000ULL,1200000010ULL};
    assert(qualifyPowerEvidence(p)==3U);
    p.nativeDozeToWakeWindow=false;assert(qualifyPowerEvidence(p)==1U);
    p.nativeDozeToWakeWindow=true;p.nativeDozeAt=0;assert(qualifyPowerEvidence(p)==1U);
    p.nativeDozeAt=900000000ULL;assert(qualifyPowerEvidence(p)==1U);
    p.nativeDozeAt=1200000000ULL;p.now=1200000000ULL;assert(qualifyPowerEvidence(p)==1U);
    p.now=1200000010ULL;p.sameFB1=false;assert(qualifyPowerEvidence(p)==0U);
    p.sameFB1=true;p.firstHighAt=0;assert(qualifyPowerEvidence(p)==0U);
    // Even with a valid native power cycle, no recovery on an unknown sink.
    Eligibility unsafe=q;unsafe.sameCompleteBaseEDID=false;assert(!mayRecover(unsafe));
    unsafe=q;unsafe.alreadyAttempted=true;assert(!mayRecover(unsafe));
    std::puts("PASS: R4 immediate native FB1 Doze->Wake without 90s/3s timers; boot/HPD still fail-closed");
    return 0;
}
