#include "hdmi2_8bpc_plan.hpp"
#include <cassert>
using namespace YogaHDMI2;

int main() {
    Request r{};
    r.physicalHDMI=true;r.verifiedEDID=true;
    r.encoding=Encoding::YCbCr444;r.bitsPerPixel=24;
    r.sinkMaxTMDSKHz=600000;r.sinkSCDCPresent=true;
    // Known 4K30 baseline stays untouched.
    r.pixelClockHz=297000000;
    auto p=plan(r);
    assert(p.accepted && !p.highTMDS && p.sourceFlags==0 && p.sinkConfig==0);
    assert(mergeFuncCtl(0x90030200,p.sourceFlags)==0x90030200);

    // 4K60 8bpc needs both source and sink high TMDS setup.
    r.pixelClockHz=594000000;
    p=plan(r);assert(!p.accepted && p.reject==Reject::SourceNotVerified);
    r.sourceSCDCVerified=true;
    p=plan(r);assert(p.accepted && p.highTMDS && p.characterRateHz==594000000);
    assert(p.sourceFlags==0x11 && p.sinkConfig==0x03);
    assert(mergeFuncCtl(0x90030200,p.sourceFlags)==0x90030211);

    r.sinkSCDCPresent=false;
    p=plan(r);assert(!p.accepted && p.reject==Reject::SinkHasNoSCDC);
    r.sinkSCDCPresent=true;
    r.sinkMaxTMDSKHz=340000;
    p=plan(r);assert(!p.accepted && p.reject==Reject::SinkRateLimit);
    r.sinkMaxTMDSKHz=600000;
    r.bitsPerPixel=30; p=plan(r);assert(!p.accepted && p.reject==Reject::UnsupportedDepth);
    r.bitsPerPixel=24;
    r.encoding=Encoding::YCbCr420;p=plan(r);assert(!p.accepted && p.reject==Reject::UnsupportedEncoding);
    r.encoding=Encoding::RGB;
    r.physicalHDMI=false;p=plan(r);assert(!p.accepted && p.reject==Reject::NotPhysicalHDMI);
    r.physicalHDMI=true;r.verifiedEDID=false;
    p=plan(r);assert(!p.accepted && p.reject==Reject::NoVerifiedEDID);
    return 0;
}
