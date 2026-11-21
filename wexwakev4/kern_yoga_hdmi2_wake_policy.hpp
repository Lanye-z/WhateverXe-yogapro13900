// Pure, device-independent V4 wake-resume eligibility policy.
// This file MUST NOT read I2C, HPD, MMIO or schedule display modesets.
#ifndef YOGA_HDMI2_WAKE_POLICY_HPP
#define YOGA_HDMI2_WAKE_POLICY_HPP
#include <stdint.h>
namespace YogaHDMI2Wake {
struct Eligibility {
    bool activeHDMI2 {};
    bool highTMDS {};
    bool sameNativePort {};
    bool freshValidBase {};
    bool exactKnownSink {};
    bool ctaAlreadySeen {};
    bool provenPriorHighSession {};
    bool sameCompleteBaseEDID {};
    bool newGeneration {};
    bool alreadyAttempted {};
    bool postBootMature {}; // after one stable native high-rate output\n    bool observedLongHDMIOff {}; // HDMI-B transcoder off, not an HPD bounce\n    bool preservedCapsValid {};
    bool preservedCapsSCDC {};
    uint32_t preservedMaxKHz {};
};
inline bool mayRecover(const Eligibility &s) {
    return s.activeHDMI2 && s.highTMDS && s.sameNativePort &&
        s.freshValidBase && s.exactKnownSink && !s.ctaAlreadySeen &&
        s.provenPriorHighSession && s.sameCompleteBaseEDID &&
        s.newGeneration && !s.alreadyAttempted &&\n        s.postBootMature && s.observedLongHDMIOff &&
        s.preservedCapsValid && s.preservedCapsSCDC &&
        s.preservedMaxKHz>340000 && s.preservedMaxKHz<=600000;
}
} // namespace YogaHDMI2Wake
#endif
