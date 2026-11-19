#ifndef KERN_YOGA_HDMI_EDID_AB_HPP
#define KERN_YOGA_HDMI_EDID_AB_HPP
#include <stdint.h>
#include <string.h>

// Tight, opt-in CTA-861 input experiment. Never changes EDID base identity,
// serial, DTD/timings, audio, HDMI physical address or the 600 MHz TMDS limit.
// Pure and host-testable: caller must independently qualify physical A7A0,
// native HDMI DDI B and vendor 05E3/product 2710 using a fresh base read.
namespace YogaHDMIEDIDAB {
enum class Variant : uint32_t { None=0, DeepColor8=1, Rgb8=2 };
enum class Result : uint32_t {
    Skipped=0, BadCTA=1, BadChecksum=2, Unsupported=3,
    Ambiguous=4, Mismatch=5, Applied=6, Already=7
};
struct Outcome {
    Result result;
    uint8_t featureBefore,featureAfter;
    uint8_t classicBefore,classicAfter;
    uint8_t forumBefore,forumAfter;
    uint8_t y420Before,y420After;
    uint8_t checksumBefore,checksumAfter;
};
inline bool checksumValid(const uint8_t *d) {
    if (!d)return false;
    uint32_t sum=0;
    for(unsigned i=0;i<128;++i)sum+=d[i];
    return !(sum&0xFF);
}
inline uint8_t checksum(const uint8_t *d) {
    uint32_t sum=0;
    for(unsigned i=0;i<127;++i)sum+=d[i];
    return uint8_t(0U-sum);
}
inline Outcome apply(uint8_t *data, Variant variant) {
    Outcome out {Result::Skipped,0,0,0,0,0,0,0,0,0,0};
    if(!data || variant==Variant::None)return out;
    if(data[0]!=0x02 || data[1]!=0x03 || data[2]!=0x40 ||
       (data[3]!=0xF1 && data[3]!=0xC1)) {
        out.result=Result::BadCTA;return out;
    }
    if(!checksumValid(data)){out.result=Result::BadChecksum;return out;}
    unsigned classic=128,forum=128,y420=128;
    unsigned classicCount=0,forumCount=0,y420Count=0;
    for(unsigned off=4;off<data[2];) {
        const unsigned len=data[off]&31, tag=data[off]>>5;
        if(!len || off+len>=data[2]){out.result=Result::BadCTA;return out;}
        if(tag==3 && len>=6 && data[off+1]==0x03 &&
           data[off+2]==0x0C && data[off+3]==0x00) {
            classic=off;++classicCount;
        }
        if(tag==3 && len>=7 && data[off+1]==0xD8 &&
           data[off+2]==0x5D && data[off+3]==0xC4) {
            forum=off;++forumCount;
        }
        if(tag==7 && len>=1 && data[off+1]==0x0E) {
            // Cannot safely keep a 4:2:0-only video block in RGB-only mode.
            if(variant==Variant::Rgb8){out.result=Result::Unsupported;return out;}
        }
        if(tag==7 && len>=3 && data[off+1]==0x0F) {
            y420=off;++y420Count;
        }
        off+=len+1;
    }
    if(classicCount!=1 || forumCount!=1 || y420Count>1) {
        out.result=Result::Ambiguous;return out;
    }
    out.featureBefore=data[3];out.featureAfter=data[3];
    out.classicBefore=data[classic+6];out.classicAfter=out.classicBefore;
    out.forumBefore=data[forum+7];out.forumAfter=out.forumBefore;
    out.y420Before=y420<128?data[y420+3]:0;out.y420After=out.y420Before;
    out.checksumBefore=data[127];out.checksumAfter=out.checksumBefore;

    // Only the observed U27P10 CTA capability layout is supported. Refuse
    // unknown vendor-block variants instead of damaging CTA data.
    const bool isOriginal=data[3]==0xF1 &&
        (data[classic+6]&0x78)==0x38 && (data[forum+7]&0x07)==0x03;
    const bool isDeep8=data[3]==0xF1 &&
        (data[classic+6]&0x78)==0 && (data[forum+7]&0x07)==0;
    const bool isRgb8=data[3]==0xC1 &&
        (data[classic+6]&0x78)==0 && (data[forum+7]&0x07)==0 &&
        (y420==128 || (!data[y420+2] && !data[y420+3]));
    if(!isOriginal) {
        out.result=((variant==Variant::DeepColor8 && isDeep8) ||
                    (variant==Variant::Rgb8 && isRgb8)) ?
                   Result::Already : Result::Mismatch;
        return out;
    }
    // Keep high 128-byte CTA layout and every detailed timing unchanged.
    // Strip DC_48/DC_36/DC_30/DC_Y444; retain other HDMI VSDB capabilities.
    data[classic+6]&=uint8_t(~0x78U);
    // HF-VSDB: strip optional 4:2:0 deep-colour capabilities only.
    data[forum+7]&=uint8_t(~0x07U);
    if(variant==Variant::Rgb8) {
        // CTA header bits 5:4 advertise YCbCr 4:4:4/4:2:2.
        data[3]&=uint8_t(~0x30U);
        // 4:2:0 capability map: clear map bytes without changing block sizes.
        if(y420<128){data[y420+2]=0;data[y420+3]=0;}
    }
    data[127]=checksum(data);
    if(!checksumValid(data)){out.result=Result::BadChecksum;return out;}
    out.featureAfter=data[3];
    out.classicAfter=data[classic+6];
    out.forumAfter=data[forum+7];
    out.y420After=y420<128?data[y420+3]:0;
    out.checksumAfter=data[127];
    out.result=Result::Applied;
    return out;
}
}
#endif
