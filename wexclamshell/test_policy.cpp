#include "kern_yoga_hdmi2_clamshell_guard.hpp"
#include <cassert>
int main() {
    using namespace YogaHDMI2Clamshell;
    // Existing R5 is unchanged unless opt-in.
    assert(cachedWakePermitted(false,0,1));
    assert(cachedWakePermitted(false,2,2));
    // Same-lid native Display Sleep -> Wake remains eligible:
    assert(cachedWakePermitted(true,0,0));
    assert(cachedWakePermitted(true,1,1));
    // Close lid AFTER display sleep or open lid during sleep: no cached 110.
    assert(!cachedWakePermitted(true,0,1));
    assert(!cachedWakePermitted(true,1,0));
    // Fail closed for absent/invalid IOPMrootDomain property.
    for(unsigned i=0;i<3;++i) {
        assert(!sameLidAtWake(2,i));
        assert(!sameLidAtWake(i,2));
    }
    assert(!sameLidAtWake(3,3));
}
