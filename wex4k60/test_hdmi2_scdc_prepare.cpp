#include "hdmi2_scdc_prepare.hpp"
#include <cassert>
#include <cstdint>
using namespace YogaHDMI2;

struct MockBus {
    bool online=true;
    uint64_t id=42;
    uint8_t regs[256] {};
    int reads=0,writes=0;
    bool failVersionRead=false,failSourceWrite=false,failConfigWrite=false;
    bool corruptConfigReadback=false,disconnectAfterConfig=false;
    uint64_t generation()const{return id;}
    bool connected()const{return online;}
    bool read(uint8_t address,uint8_t &v) {
        ++reads;
        if(!online || (address==1 && failVersionRead))return false;
        v=regs[address];
        if(address==0x20 && corruptConfigReadback && writes>1)
            v=uint8_t(v^1U);
        return true;
    }
    bool write(uint8_t address,uint8_t v) {
        ++writes;
        if(!online || (address==2 && failSourceWrite))return false;
        if(address==0x20 && failConfigWrite && v!=0) {
            regs[address]=v; // simulate write success on wire but error return
            failConfigWrite=false;
            return false;
        }
        regs[address]=v;
        if(address==0x20 && disconnectAfterConfig) {
            online=false;++id;
        }
        return true;
    }
};

int main() {
    Request r {};
    r.physicalHDMI=r.verifiedEDID=r.sinkSCDCPresent=r.sourceSCDCVerified=true;
    r.encoding=Encoding::RGB;r.bitsPerPixel=24;r.pixelClockHz=594000000;
    r.sinkMaxTMDSKHz=600000;
    auto high=plan(r);
    assert(high.accepted && high.highTMDS);
    MockBus io{};io.regs[1]=1;
    auto result=prepareSCDC(io,high,true);
    assert(result.complete && result.changed && result.sinkVersion==1);
    assert(result.before==0 && result.wanted==3 && result.readback==3);
    assert(result.sourceFlags==0x11 && io.regs[0x20]==3);
    assert(restoreSCDC(io,result) && io.regs[0x20]==0);

    // Preserve unrelated sink config bits.
    MockBus other{};other.regs[1]=1;other.regs[0x20]=0x80;
    result=prepareSCDC(other,high,true);
    assert(result.complete && result.wanted==0x83);
    assert(restoreSCDC(other,result) && other.regs[0x20]==0x80);

    // An already-correct sink has no needless 0x20 write.
    MockBus existing{};existing.regs[1]=1;existing.regs[0x20]=3;
    result=prepareSCDC(existing,high,true);
    assert(result.complete && !result.changed && !result.attemptedConfigWrite);

    // Never configure source on SCDC errors.
    MockBus badVer{};badVer.regs[1]=0;
    result=prepareSCDC(badVer,high,true);
    assert(!result.complete && !result.sourceFlags &&
           result.error==SCDCError::SinkVersionUnsupported);
    MockBus badWrite{};badWrite.regs[1]=1;badWrite.failConfigWrite=true;
    result=prepareSCDC(badWrite,high,true);
    assert(!result.complete && !result.sourceFlags && result.attemptedRestore);
    assert(result.restored && badWrite.regs[0x20]==0);

    // No bus transactions are allowed to cross hotplug generations.
    MockBus unplug{};unplug.regs[1]=1;unplug.disconnectAfterConfig=true;
    result=prepareSCDC(unplug,high,true);
    assert(!result.complete && !result.sourceFlags &&
           result.error==SCDCError::Disconnected && !result.attemptedRestore);
    assert(!restoreSCDC(unplug,result));

    // A <=340 MHz, non-SCDC sink never needs SCDC transaction.
    r.pixelClockHz=297000000;r.sinkSCDCPresent=false;
    auto low=plan(r);assert(low.accepted && !low.highTMDS);
    MockBus legacy{};
    result=prepareSCDC(legacy,low,false);
    assert(result.complete && result.sourceFlags==0 && legacy.writes==0);
    return 0;
}
