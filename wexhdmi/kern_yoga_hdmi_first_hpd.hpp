// Yoga 82Y7/A7A0: strictly opt-in, one-shot native HDMI-B short HPD retry.
// No MMIO writes, no callback invocation, no changes to HDMI clocks or EDID.
#ifndef KERN_YOGA_HDMI_FIRST_HPD_HPP
#define KERN_YOGA_HDMI_FIRST_HPD_HPP
#include <stdint.h>
namespace YogaHDMIFirstHPD {
constexpr uint32_t BLong = 1U << 2;
constexpr uint32_t BShort = 1U << 3;
// Only an observed short pulse, not a missing interrupt, can be retried.
// A port whose first probe was connected must behave exactly as upstream.
inline bool shouldPromote(uint32_t nativeEvents,uint32_t firstPortBResult,bool enabled,bool alreadyUsed) {
    return enabled && firstPortBResult==0 && !alreadyUsed &&
        (nativeEvents&BShort) && !(nativeEvents&BLong);
}
inline uint32_t asLong(uint32_t nativeEvents) {
    return (nativeEvents&~BShort)|BLong;
}
}
#endif
