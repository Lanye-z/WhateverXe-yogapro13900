// R5: pure dynamic HDMI framebuffer binding policy; no hardware access.
#ifndef YOGA_HDMI2_DYNAMIC_POLICY_HPP
#define YOGA_HDMI2_DYNAMIC_POLICY_HPP
#include <stdint.h>
namespace YogaHDMI2R5 {
inline bool sameBoundPipe(uint32_t current,uint32_t proven) {
    return current<3U && proven<3U && current==proven;
}
inline bool samePowerObject(uintptr_t observedDoze,uintptr_t waking) {
    return observedDoze!=0 && waking!=0 && observedDoze==waking;
}
inline bool nativeWakeMatches(uint32_t callPipe,uint32_t provenPipe,
                              uintptr_t dozeFB,uintptr_t wakeFB,bool inWake) {
    return inWake && sameBoundPipe(callPipe,provenPipe) &&
           samePowerObject(dozeFB,wakeFB);
}
} // namespace YogaHDMI2R5
#endif
