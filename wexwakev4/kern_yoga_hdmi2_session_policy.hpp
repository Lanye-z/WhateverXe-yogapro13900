// V4 R3: pure policy for a single post-wake stale high->low transition.
// No I2C, MMIO, IOKit, power callbacks or timers; native SCDC still owns I/O.
#ifndef YOGA_HDMI2_SESSION_POLICY_HPP
#define YOGA_HDMI2_SESSION_POLICY_HPP
#include <stdint.h>
namespace YogaHDMI2Session {
struct LowReconcile {
    bool requested {};
    bool physicalHDMIB {};
    bool knownPipe1 {};
    bool exactAOC {};
    bool provenHighSession {};
    bool sameCompleteBase {};
    bool hadNativeDozeWake {};
    bool priorHighStatus10 {};
    bool freshCTA {};
    bool currentHDMISCDC {};
    bool sourceHasHighFlags {};
    uint32_t failedGeneration {};
    uint32_t currentGeneration {};
    uint32_t maxTMDSKHz {};
};
inline bool mayReconcileLow(const LowReconcile &s) {
    return s.requested && s.physicalHDMIB && s.knownPipe1 &&
           s.exactAOC && s.provenHighSession && s.sameCompleteBase &&
           s.hadNativeDozeWake && s.priorHighStatus10 &&
           s.freshCTA && s.currentHDMISCDC &&
           s.sourceHasHighFlags && s.failedGeneration!=0 &&
           s.currentGeneration>s.failedGeneration &&
           s.maxTMDSKHz>340000 && s.maxTMDSKHz<=600000;
}
} // namespace YogaHDMI2Session
#endif
