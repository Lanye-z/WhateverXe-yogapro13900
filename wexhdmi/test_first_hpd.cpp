#include <cassert>
#include "kern_yoga_hdmi_first_hpd.hpp"
int main() {
    using namespace YogaHDMIFirstHPD;
    assert(shouldPromote(BShort,0,true,false));
    assert(asLong(BShort)==BLong);
    assert(asLong(BShort|(1U<<6))==(BLong|(1U<<6)));
    assert(!shouldPromote(BShort,2,true,false)); // display present at boot
    assert(!shouldPromote(BLong,0,true,false)); // true long already delivered
    assert(!shouldPromote(0,0,true,false)); // no IRQ: no workaround
    assert(!shouldPromote(BShort,0,false,false)); // opt-in only
    assert(!shouldPromote(BShort,0,true,true)); // one-shot, never storms
    assert(!shouldPromote(BShort,UINT32_MAX,true,false)); // unknown boot state
    return 0;
}
