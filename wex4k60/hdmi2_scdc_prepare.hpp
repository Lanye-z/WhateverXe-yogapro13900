// Yoga A7A0 HDMI2 SCDC transaction policy, PURE TEMPLATE (no I2C driver).
// Adapted conceptually from Wtrwx's A7A0 Display13 HDMI SCDC implementation:
// https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh
// Nothing in this header acquires DDC locks or touches macOS MMIO/I2C itself.
// The caller MUST own the proper physical HDMI DDC gate and ensure the
// selected connection generation remains stable throughout the operation.
#ifndef YOGA_WEX_HDMI2_SCDC_PREPARE_HPP
#define YOGA_WEX_HDMI2_SCDC_PREPARE_HPP
#include "hdmi2_8bpc_plan.hpp"

namespace YogaHDMI2 {

enum class SCDCError : uint8_t {
    None, PlanNotAccepted, WrongSourceFlags, Disconnected,
    SinkVersionReadFailed, SinkVersionUnsupported, SourceVersionWriteFailed,
    ConfigReadFailed, ConfigWriteFailed, ConfigReadbackFailed
};

struct SCDCTransaction {
    bool complete {};
    bool changed {};
    bool attemptedConfigWrite {};
    bool attemptedRestore {};
    bool restored {};
    bool sinkPresent {};
    uint8_t sinkVersion {};
    uint8_t before {};
    uint8_t wanted {};
    uint8_t readback {};
    uint32_t sourceFlags {}; // non-zero ONLY if complete=true
    uint64_t connectionGeneration {};
    SCDCError error {SCDCError::None};
};

// Required IO (mocked in CI): connected(), generation(), read(reg, out),
// write(reg, val). It must be scoped to the same physical HDMI/DDC connection,
// and methods must NOT silently redirect to a new sink on hotplug.
template<class IO>
SCDCTransaction prepareSCDC(IO &io,const Plan &plan,bool sinkSCDCPresent) {
    SCDCTransaction s {};
    if(!plan.accepted) {s.error=SCDCError::PlanNotAccepted;return s;}
    if(plan.highTMDS && (plan.sourceFlags!=SourceFlags ||
                         plan.sinkConfig!=SinkConfig || !sinkSCDCPresent)) {
        s.error=SCDCError::WrongSourceFlags;return s;
    }
    if(!plan.highTMDS && (plan.sourceFlags || plan.sinkConfig)) {
        s.error=SCDCError::WrongSourceFlags;return s;
    }
    s.connectionGeneration=io.generation();
    const auto alive=[&](){return io.connected() &&
        io.generation()==s.connectionGeneration;};
    if(!alive()) {s.error=SCDCError::Disconnected;return s;}

    // DVI/legacy HDMI without SCDC: only the <=340MHz plan can proceed.
    if(!sinkSCDCPresent) {
        if(plan.highTMDS) {s.error=SCDCError::WrongSourceFlags;return s;}
        s.complete=true;return s;
    }
    s.sinkPresent=true;
    if(!io.read(0x01,s.sinkVersion)) {
        s.error=SCDCError::SinkVersionReadFailed;return s;
    }
    if(!alive()) {s.error=SCDCError::Disconnected;return s;}
    if(!s.sinkVersion) {s.error=SCDCError::SinkVersionUnsupported;return s;}
    if(!io.write(0x02,0x01)) {
        s.error=SCDCError::SourceVersionWriteFailed;return s;
    }
    if(!alive()) {s.error=SCDCError::Disconnected;return s;}
    if(!io.read(0x20,s.before)) {
        s.error=SCDCError::ConfigReadFailed;return s;
    }
    if(!alive()) {s.error=SCDCError::Disconnected;return s;}
    s.wanted=uint8_t((s.before&uint8_t(~0x03U))|plan.sinkConfig);

    // Caller must not set source bits if the sink write/readback fails.
    const auto restore=[&](){
        if(!alive())return;
        s.attemptedRestore=true;
        uint8_t confirmed=0;
        s.restored=io.write(0x20,s.before) && alive() &&
            io.read(0x20,confirmed) && alive() && confirmed==s.before;
    };
    if(s.wanted!=s.before) {
        s.changed=true;
        // A failed I2C write may have changed the sink: attempt restoration.
        s.attemptedConfigWrite=true;
        if(!io.write(0x20,s.wanted)) {
            s.error=SCDCError::ConfigWriteFailed;
            restore();
            return s;
        }
        if(!alive()) {s.error=SCDCError::Disconnected;return s;}
    }
    if(!io.read(0x20,s.readback) || !alive() || s.readback!=s.wanted) {
        s.error=SCDCError::ConfigReadbackFailed;
        if(s.attemptedConfigWrite)restore();
        return s;
    }
    s.complete=true;
    s.sourceFlags=plan.sourceFlags;
    return s;
}

// On a single still-owned connection, explicitly restore a prior successful
// high-rate transaction when aborting that modeset. A changed generation must
// NOT receive rollback writes. No source-register action is performed here.
template<class IO>
bool restoreSCDC(IO &io,const SCDCTransaction &s) {
    if(!s.complete || !s.sinkPresent || !s.changed)return true;
    if(!io.connected() || io.generation()!=s.connectionGeneration)return false;
    uint8_t actual=0;
    return io.write(0x20,s.before) && io.connected() &&
        io.generation()==s.connectionGeneration && io.read(0x20,actual) &&
        io.connected() && io.generation()==s.connectionGeneration &&
        actual==s.before;
}

}
#endif
