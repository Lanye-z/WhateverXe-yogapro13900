// Copyright (c) 2026. D1.1 experimental, MIT-style use permitted.
// App-level CPU fallback for BGRA -> 8-bit NV12, limited-range Rec.709.
// This does not patch VideoToolbox, AppleGVA, or any signed system binary.
#ifndef WEX_BGRA_TO_NV12_H
#define WEX_BGRA_TO_NV12_H
#include <stdint.h>
#include <stddef.h>

static inline uint8_t wex_sat(int v, int lo, int hi) {
    if (v < lo) return (uint8_t)lo;
    if (v > hi) return (uint8_t)hi;
    return (uint8_t)v;
}
static inline int wex_div256_round(int v) {
    return v < 0 ? -((-v + 128) / 256) : (v + 128) / 256;
}
// Return 0 on success. Requires even positive width/height; row strides in bytes.
// Y: 16-235, Cb/Cr: 16-240. Coefficients approximate Rec.709 in integer arithmetic.
static inline int wex_bgra_to_nv12(const uint8_t *bgra, size_t src_stride,
                                    uint8_t *yplane, size_t ystride,
                                    uint8_t *uvplane, size_t uvstride,
                                    int width, int height) {
    if (!bgra || !yplane || !uvplane || width <= 0 || height <= 0 ||
        (width & 1) || (height & 1) ||
        (size_t)width > SIZE_MAX / 4 || src_stride < (size_t)width * 4 ||
        ystride < (size_t)width || uvstride < (size_t)width) return -1;
    for (int row = 0; row < height; row += 2) {
        const uint8_t *src0=bgra + (size_t)row*src_stride;
        const uint8_t *src1=src0+src_stride;
        uint8_t *dst0=yplane + (size_t)row*ystride;
        uint8_t *dst1=dst0 + ystride;
        uint8_t *uv=uvplane + (size_t)(row/2)*uvstride;
        for (int col=0; col<width; col+=2) {
            const uint8_t *p[4]={src0+(size_t)col*4,
                                  src0+(size_t)(col+1)*4,
                                  src1+(size_t)col*4,
                                  src1+(size_t)(col+1)*4};
            int sumr=0,sumg=0,sumb=0;
            for (int i=0;i<4;++i) {
                int b=p[i][0],g=p[i][1],r=p[i][2];
                sumr+=r;sumg+=g;sumb+=b;
                int yy=16+((47*r+157*g+16*b+128)/256);
                (i<2?dst0:dst1)[col+(i&1)]=wex_sat(yy,16,235);
            }
            int r=(sumr+2)/4,g=(sumg+2)/4,b=(sumb+2)/4;
            int cb=128+wex_div256_round(-26*r-86*g+112*b);
            int cr=128+wex_div256_round(112*r-102*g-10*b);
            uv[col]=wex_sat(cb,16,240);
            uv[col+1]=wex_sat(cr,16,240);
        }
    }
    return 0;
}
#endif
