// Real EDID fixture from AOC 05E3:2710. No macOS kernel runtime required.
#include "kern_yoga_rgb8.hpp"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <stdint.h>

static unsigned validChecksum(const uint8_t *block) {
    unsigned sum=0;for(unsigned i=0;i<128;++i)sum+=block[i];return sum & 255;
}
int main() {
    using namespace YogaRGB8;
    for(unsigned block=1;block<=2;++block) {
        const uint8_t *original=block==1 ? OriginalBase : OriginalCTA;
        const uint8_t *expected=block==1 ? StrictBase : StrictCTA;
        uint8_t copy[128] {};
        memcpy(copy,original,128);
        assert(!validChecksum(copy));
        assert(rewrite(block,copy)==Result::Applied);
        assert(!memcmp(copy,expected,128));
        assert(!validChecksum(copy));
        assert(rewrite(block,copy)==Result::Already);
        assert(!memcmp(copy,expected,128));
        memcpy(copy,original,128);
        copy[25]^=1;uint8_t bad[128]={0};memcpy(bad,copy,128);
        assert(rewrite(block,copy)==Result::Skipped);
        assert(!memcmp(copy,bad,128));
    }
    uint8_t other[128];memset(other,0xab,sizeof(other));
    assert(rewrite(1,other)==Result::Skipped);
    for(unsigned b : {0U,3U,4U,0xFFFFFFFFU})
        assert(rewrite(b,other)==Result::Skipped);
    assert(rewrite(1,nullptr)==Result::Skipped);
    assert(!memcmp(other,"\xab\xab\xab\xab",4));
    puts("PASS: exact 05E3:2710 EDID replacement; 128-byte block boundaries; idempotency; unknown-monitor no-op");
}
