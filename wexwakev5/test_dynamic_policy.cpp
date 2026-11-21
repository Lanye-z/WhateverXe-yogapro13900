#include "kern_yoga_hdmi2_dynamic_policy.hpp"
#include <cassert>
#include <cstdio>
using namespace YogaHDMI2R5;
int main() {
    assert(sameBoundPipe(1,1));
    assert(sameBoundPipe(2,2));
    assert(!sameBoundPipe(1,2));
    assert(!sameBoundPipe(2,1));
    assert(!sameBoundPipe(3,3));
    assert(!sameBoundPipe(0,3));
    assert(!sameBoundPipe(3,0));
    assert(!sameBoundPipe(0xffffffffu,1));
    assert(samePowerObject(0x1234,0x1234));
    assert(!samePowerObject(0,0));
    assert(!samePowerObject(0,0x1234));
    assert(!samePowerObject(0x1234,0x5678));
    assert(nativeWakeMatches(1,1,0x111,0x111,true));
    assert(nativeWakeMatches(2,2,0x222,0x222,true));
    assert(!nativeWakeMatches(2,1,0x222,0x222,true));
    assert(!nativeWakeMatches(1,2,0x111,0x111,true));
    assert(!nativeWakeMatches(2,2,0x222,0x333,true));
    assert(!nativeWakeMatches(2,2,0x222,0x222,false));
    assert(!nativeWakeMatches(2,2,0,0,true));
    std::puts("PASS R5: FB1/FB2 dynamic binding, no cross-FB wake, no startup/HPD-only wake");
    return 0;
}
