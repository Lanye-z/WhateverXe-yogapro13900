#include "kern_yoga_hdmi2_wake_policy.hpp"
#include <cassert>
#include <cstdio>
using YogaHDMI2Wake::Eligibility;
using YogaHDMI2Wake::mayRecover;
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
        t=q; t.postBootMature=false; assert(!mayRecover(t));
        t=q; t.nativeDozeWakeVerified=false; assert(!mayRecover(t));
        t=q; t.preservedCapsValid=false; assert(!mayRecover(t));
        t=q; t.preservedCapsSCDC=false; assert(!mayRecover(t));
        t=q; t.preservedMaxKHz=340000; assert(!mayRecover(t));
        t=q; t.preservedMaxKHz=600001; assert(!mayRecover(t));
    }
    std::puts("PASS: V4 R2 boot-gated native Doze-to-Wake, same EDID, one-time fail-closed");
    return 0;
}
