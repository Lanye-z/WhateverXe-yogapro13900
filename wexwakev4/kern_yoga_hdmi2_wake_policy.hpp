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
    bool priorNativeHighConfirmed {}; // this boot: real successful high-rate SCDC
    bool nativeDozeWakeVerified {}; // real FB1 power callback: Wake->Doze->Wake
    bool preservedCapsValid {};
    bool preservedCapsSCDC {};
    uint32_t preservedMaxKHz {};
};

// The power callback is a validated native FB1 callback, not an HPD bounce.
// Bits: 1=successful native high-rate session already observed in this boot;
//       2=confirmed FB1 Wake->Doze and currently inside Doze->Wake.
// Deliberately NO arbitrary elapsed 90-second or 3-second threshold.
// A successful boot modeset alone must never make bit 2 true.
struct PowerEvidence {
    bool sameFB1 {};
    bool nativeDozeToWakeWindow {};
    uint64_t firstHighAt {};
    uint64_t nativeDozeAt {};
    uint64_t now {};
};
inline uint32_t qualifyPowerEvidence(const PowerEvidence &p) {
    const bool highKnown=p.sameFB1 && p.firstHighAt!=0;
    const bool nativeCycle=highKnown && p.nativeDozeToWakeWindow &&
        p.nativeDozeAt>p.firstHighAt && p.now>p.nativeDozeAt;
    return (highKnown?1U:0U) | (nativeCycle?2U:0U);
}

inline bool mayRecover(const Eligibility &s) {
    return s.activeHDMI2 && s.highTMDS && s.sameNativePort &&
        s.freshValidBase && s.exactKnownSink && !s.ctaAlreadySeen &&
        s.provenPriorHighSession && s.sameCompleteBaseEDID &&
        s.newGeneration && !s.alreadyAttempted &&
        s.priorNativeHighConfirmed && s.nativeDozeWakeVerified &&
        s.preservedCapsValid && s.preservedCapsSCDC &&
        s.preservedMaxKHz>340000 && s.preservedMaxKHz<=600000;
}
} // namespace YogaHDMI2Wake
#endif
