// Yoga A7A0 HDMI 2.0 *pure link policy* for read-only/test builds.
// Does not perform GMBUS/SCDC transactions, MMIO, hooks or mode switches.
// Sources: upstream WEX #82 gkostadinov kern_hdmi_link.hpp; Wtrwx A7A0
// Display13 HDMI SCDC. Only 8bpc RGB/Y444 is within this first-phase scope.
#ifndef YOGA_WEX_HDMI2_8BPC_PLAN_HPP
#define YOGA_WEX_HDMI2_8BPC_PLAN_HPP
#include <stdint.h>

namespace YogaHDMI2 {

enum class Encoding : uint8_t { RGB, YCbCr444, YCbCr422, YCbCr420, Unknown };
enum class Reject : uint8_t {
    None, NotPhysicalHDMI, NoVerifiedEDID, InvalidClock, UnsupportedDepth,
    UnsupportedEncoding, SinkRateLimit, SinkHasNoSCDC, SourceNotVerified
};
struct Request {
    bool physicalHDMI {};
    bool verifiedEDID {};
    Encoding encoding {Encoding::Unknown};
    uint32_t bitsPerPixel {24};
    uint64_t pixelClockHz {};
    uint32_t sinkMaxTMDSKHz {};
    bool sinkSCDCPresent {};
    bool sourceSCDCVerified {};
};
struct Plan {
    bool accepted {};
    bool highTMDS {};
    uint64_t characterRateHz {};
    uint8_t sinkConfig {};
    uint32_t sourceFlags {};
    Reject reject {Reject::None};
};

static constexpr uint64_t HighTMDSHz=340000000ULL;
static constexpr uint64_t MaxTMDSHz=600000000ULL;
static constexpr uint32_t SourceFlags=0x11U; // FUNC_CTL bit4|bit0
static constexpr uint8_t SinkConfig=0x03U;   // SCDC 0x20 bit1|bit0

static inline Plan plan(const Request &q) {
    Plan p {};
    if(!q.physicalHDMI) {p.reject=Reject::NotPhysicalHDMI;return p;}
    if(!q.verifiedEDID) {p.reject=Reject::NoVerifiedEDID;return p;}
    if(!q.pixelClockHz) {p.reject=Reject::InvalidClock;return p;}
    if(q.bitsPerPixel!=24) {p.reject=Reject::UnsupportedDepth;return p;}
    // 4:2:0 requires half-rate treatment; don't accidentally configure it
    // as 594 MHz 4:4:4 just because the pixel clock is 594 MHz.
    if(q.encoding!=Encoding::RGB && q.encoding!=Encoding::YCbCr444) {
        p.reject=Reject::UnsupportedEncoding;return p;
    }
    p.characterRateHz=q.pixelClockHz;
    if(p.characterRateHz>MaxTMDSHz ||
       (q.sinkMaxTMDSKHz && p.characterRateHz>uint64_t(q.sinkMaxTMDSKHz)*1000ULL)) {
        p.reject=Reject::SinkRateLimit;return p;
    }
    p.highTMDS=p.characterRateHz>HighTMDSHz;
    if(p.highTMDS) {
        if(!q.sinkSCDCPresent) {p.reject=Reject::SinkHasNoSCDC;return p;}
        if(!q.sourceSCDCVerified) {p.reject=Reject::SourceNotVerified;return p;}
        if(!q.sinkMaxTMDSKHz) {p.reject=Reject::SinkRateLimit;return p;}
        p.sinkConfig=SinkConfig;
        p.sourceFlags=SourceFlags;
    }
    p.accepted=true;
    return p;
}

// Only use after a matching successful SCDC readback on the *same*
// connection generation. Source flags are not a substitute for sink I2C.
static inline uint32_t mergeFuncCtl(uint32_t native,uint32_t sourceFlags) {
    return (native&~SourceFlags)|(sourceFlags&SourceFlags);
}
}
#endif
