#ifndef KERN_YOGA_HDMI_COLOR_POLICY_HPP
#define KERN_YOGA_HDMI_COLOR_POLICY_HPP
#include <stdint.h>

// This helper changes *arguments to the native setColorMode call*.
// No display MMIO writes. mode==1 for RGB is an EXPERIMENTAL ABI
// hypothesis from the related TGL/RPL-S report, not yet validated on A7A0.
// A failed preflight MUST leave the original request unchanged.
namespace YogaHDMIColorPolicy {
enum class Variant : uint32_t { Audit=0, Bpc8=1, Rgb8=2 };
enum class Outcome : uint32_t {
    Observe=0, NotQualified=1, Conflict=2, UnknownDepth=3,
    Already8=4, Changed=5
};
struct Decision {
    uint32_t mode,depth;
    Outcome outcome;
};
inline Decision decide(uint32_t mode,uint32_t depth,Variant requested,
                       bool matched,bool flagsConflict) {
    if(!matched)return {mode,depth,Outcome::NotQualified};
    if(flagsConflict)return {mode,depth,Outcome::Conflict};
    if(requested==Variant::Audit)return {mode,depth,Outcome::Observe};
    // Only direct numeric 8/10 bpc or 24/30 bpp are eligible. Any
    // native enum/depth representation we did not establish is a no-op.
    uint32_t newDepth=depth;
    if(depth==10)newDepth=8;
    else if(depth==30)newDepth=24;
    else if(depth!=8 && depth!=24)return {mode,depth,Outcome::UnknownDepth};
    // Requiring a nonzero original mode avoids guessing what mode 0 means.
    // This does not establish that native mode 1 means RGB on A7A0.
    if(requested==Variant::Rgb8 && !mode)return {mode,depth,Outcome::NotQualified};
    const uint32_t newMode=requested==Variant::Rgb8 ? 1U : mode;
    return {newMode,newDepth,
        (newMode!=mode || newDepth!=depth) ? Outcome::Changed : Outcome::Already8};
}
}
#endif
