#include "kern_yoga_hdmi_edid_ab.hpp"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <stdint.h>

using namespace YogaHDMIEDIDAB;
static void sample(uint8_t *d) {
    memset(d,0,128);
    // Synthetic CTA sample with the same standard VSDB/Forum/Y420
    // capabilities but no serial, monitor name, or live EDID DTD bytes.
    const uint8_t blocks[]={
        0x02,0x03,0x40,0xF1,
        0x4c,0x90,0x04,0x03,0x1f,0x13,0x01,0x12,0x5d,0x5e,0x5f,0x60,0x61,
        0x23,0x09,0x07,0x07,
        0x83,0x01,0x00,0x00,
        0x6d,0x03,0x0c,0x00,0x20,0x00,0x38,0x3c,0x20,0x00,0x60,0x01,0x02,0x03,
        0x67,0xd8,0x5d,0xc4,0x01,0x78,0x80,0x03,
        0x68,0x1a,0x00,0x00,0x01,0x01,0x17,0x4b,0xe6,
        0xe3,0x05,0xe3,0x01,
        0xe3,0x0f,0x00,0x0c
    };
    static_assert(sizeof(blocks)==64,"CTA DB count");
    memcpy(d,blocks,sizeof(blocks));
    for(unsigned i=64;i<127;++i)d[i]=uint8_t((i*7U+11U)&0xFFU);
    d[127]=checksum(d);
    assert(checksumValid(d));
}
static void checkOnly(const uint8_t *a,const uint8_t *b,
                      const unsigned *allowed,unsigned count) {
    for(unsigned i=0;i<128;++i) {
        bool permit=false;for(unsigned j=0;j<count;++j)permit|=i==allowed[j];
        if(!permit)assert(a[i]==b[i]);
    }
}
int main(){
    uint8_t original[128] {},data[128] {};
    sample(original);
    memcpy(data,original,128);
    const unsigned aAllowed[]={31,46,127};
    auto r=apply(data,Variant::DeepColor8);
    assert(r.result==Result::Applied && r.featureAfter==0xF1);
    assert(r.classicAfter==0 && r.forumAfter==0 && r.y420After==0x0C);
    assert(checksumValid(data));
    checkOnly(original,data,aAllowed,3);
    assert(apply(data,Variant::DeepColor8).result==Result::Already);
    memcpy(data,original,128);
    const unsigned bAllowed[]={3,31,46,63,127};
    r=apply(data,Variant::Rgb8);
    assert(r.result==Result::Applied && r.featureAfter==0xC1);
    assert(r.classicAfter==0 && r.forumAfter==0 && r.y420After==0);
    assert(checksumValid(data));
    checkOnly(original,data,bAllowed,5);
    assert(apply(data,Variant::Rgb8).result==Result::Already);
    memcpy(data,original,128);data[33]^=0x01;
    assert(apply(data,Variant::DeepColor8).result==Result::BadChecksum);
    memcpy(data,original,128);data[3]=0x71;data[127]=checksum(data);
    assert(apply(data,Variant::Rgb8).result==Result::BadCTA);
    memcpy(data,original,128);data[61]=0x0E;data[127]=checksum(data);
    assert(apply(data,Variant::Rgb8).result==Result::Unsupported);
    memcpy(data,original,128);data[31]=0x28;data[127]=checksum(data);
    assert(apply(data,Variant::Rgb8).result==Result::Mismatch);
    memcpy(data,original,128);
    assert(apply(data,Variant::None).result==Result::Skipped);
    assert(!memcmp(data,original,128));
    std::puts("PASS: original CTA, Deep8, RGB8, checksum, only expected byte changes, fail-closed");
}
