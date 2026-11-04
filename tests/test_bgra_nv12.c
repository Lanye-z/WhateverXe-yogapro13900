// Regression tests for the pure-C BGRA-to-NV12 conversion.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "../macos/video-encode/wex_bgra_to_nv12.h"
static void solid(uint8_t b, uint8_t g, uint8_t r, int wantY, int wantU, int wantV) {
    uint8_t bgra[16]; for (int i=0;i<4;++i) {
        bgra[i*4+0]=b;bgra[i*4+1]=g;bgra[i*4+2]=r;bgra[i*4+3]=255;
    }
    uint8_t yy[4]={0},uv[2]={0};
    assert(wex_bgra_to_nv12(bgra,8,yy,2,uv,2,2,2)==0);
    for(int i=0;i<4;++i) assert(yy[i]==wantY);
    assert(uv[0]==wantU && uv[1]==wantV);
}
int main(void) {
    solid(0,0,0,16,128,128);
    solid(255,255,255,235,128,128);
    solid(0,0,255,63,102,240);
    // Padded rows must not be overwritten.
    uint8_t src[2*12],y[2*4],uv[4];
    memset(src,255,sizeof(src));memset(y,0xAB,sizeof(y));memset(uv,0xBC,sizeof(uv));
    assert(wex_bgra_to_nv12(src,12,y,4,uv,4,2,2)==0);
    assert(y[2]==0xAB && y[3]==0xAB && y[6]==0xAB && y[7]==0xAB);
    assert(uv[2]==0xBC && uv[3]==0xBC);
    assert(wex_bgra_to_nv12(src,12,y,4,uv,4,3,2)==-1);
    assert(wex_bgra_to_nv12(NULL,12,y,4,uv,4,2,2)==-1);
    printf("BGRA_TO_NV12_UNIT_TESTS_PASS\n");
    return 0;
}
