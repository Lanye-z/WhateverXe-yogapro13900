// R5-Clamshell: pure policy; one session cannot cross a lid-layout change.
// 0=open, 1=closed, 2=unknown. Unknown never qualifies for cached recovery.
#ifndef YOGA_HDMI2_CLAMSHELL_GUARD_HPP
#define YOGA_HDMI2_CLAMSHELL_GUARD_HPP
#include <stdint.h>
namespace YogaHDMI2Clamshell {
inline bool sameLidAtWake(uint32_t observedAtDoze,uint32_t observedAtWake) {
    return observedAtDoze <= 1U && observedAtWake <= 1U &&
           observedAtDoze == observedAtWake;
}
inline bool cachedWakePermitted(bool enabled,uint32_t observedAtDoze,
                                uint32_t observedAtWake) {
    return !enabled || sameLidAtWake(observedAtDoze,observedAtWake);
}
}
#endif
