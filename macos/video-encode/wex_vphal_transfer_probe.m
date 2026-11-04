#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#import <CoreVideo/CoreVideo.h>
#import <CoreMedia/CoreMedia.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Deliberately exercises VTPixelTransferSession only: NO encoder is created.
// Risk: on some WhateverXe VA builds this native call can crash this process.
static CVPixelBufferRef buffer(OSType fmt, int width, int height) {
    CVPixelBufferRef b=NULL;
    NSDictionary *attrs=@{
       (__bridge NSString *)kCVPixelBufferPixelFormatTypeKey: @(fmt),
       (__bridge NSString *)kCVPixelBufferWidthKey: @(width),
       (__bridge NSString *)kCVPixelBufferHeightKey: @(height),
       (__bridge NSString *)kCVPixelBufferIOSurfacePropertiesKey: @{}
    };
    CVReturn rv=CVPixelBufferCreate(kCFAllocatorDefault,width,height,fmt,
                                    (__bridge CFDictionaryRef)attrs,&b);
    printf("CVPIXELBUFFER_CREATE format=0x%08x status=%d\n",(unsigned)fmt,(int)rv);
    return rv==kCVReturnSuccess ? b:NULL;
}
static int fillSource(CVPixelBufferRef b, int width, int height, BOOL isBGRA) {
    CVReturn rv=CVPixelBufferLockBaseAddress(b,0);
    if(rv != kCVReturnSuccess) return (int)rv;
    if(isBGRA) {
        uint8_t *base=(uint8_t *)CVPixelBufferGetBaseAddress(b);
        size_t stride=CVPixelBufferGetBytesPerRow(b);
        if(!base || stride<(size_t)width*4) { CVPixelBufferUnlockBaseAddress(b,0);return -1; }
        for(int y=0;y<height;++y) {
            uint8_t *row=base+(size_t)y*stride;
            for(int x=0;x<width;++x) {
                row[4*x+0]=(uint8_t)(x&255);
                row[4*x+1]=(uint8_t)(y&255);
                row[4*x+2]=64;
                row[4*x+3]=255;
            }
        }
    } else {
        if(CVPixelBufferGetPlaneCount(b)!=2){CVPixelBufferUnlockBaseAddress(b,0);return -2;}
        for(size_t plane=0;plane<2;++plane) {
            uint8_t *base=(uint8_t *)CVPixelBufferGetBaseAddressOfPlane(b,plane);
            size_t stride=CVPixelBufferGetBytesPerRowOfPlane(b,plane);
            size_t ph=CVPixelBufferGetHeightOfPlane(b,plane);
            size_t pw=CVPixelBufferGetWidthOfPlane(b,plane);
            // NV12 UV plane has two interleaved bytes per chroma sample.
            // The logical byte width of both planes is full frame width.
            size_t bytesPerRowNeeded=(size_t)width;
            if(!base || pw==0 || stride<bytesPerRowNeeded){CVPixelBufferUnlockBaseAddress(b,0);return -3;}
            for(size_t row=0;row<ph;++row) memset(base+row*stride, plane==0?90:128,bytesPerRowNeeded);
        }
    }
    CVPixelBufferUnlockBaseAddress(b,0);
    return 0;
}
int main(int argc, const char *argv[]) {
    setvbuf(stdout,NULL,_IONBF,0);
    setvbuf(stderr,NULL,_IONBF,0);
    @autoreleasepool {
        if(argc!=4) {
            fprintf(stderr,"Usage: %s <even-width> <even-height> bgra-nv12|nv12-nv12\n",argv[0]);
            return 2;
        }
        char *endw=NULL,*endh=NULL;
        long lw=strtol(argv[1],&endw,10),lh=strtol(argv[2],&endh,10);
        if(!endw||*endw||!endh||*endh||lw<2||lh<2||lw>4096||lh>4096||(lw&1)||(lh&1)){
            fprintf(stderr,"ERROR=Dimensions must be even and in [2,4096]\n");return 2;
        }
        BOOL bgra = !strcmp(argv[3],"bgra-nv12");
        if(!bgra && strcmp(argv[3],"nv12-nv12")){
            fprintf(stderr,"ERROR=Invalid mode\n");return 2;
        }
        int w=(int)lw,h=(int)lh;
        printf("PROBE=VTPixelTransfer only; no encoding; can crash in native VA driver\n");
        printf("PIXEL_TRANSFER_SIZE=%dx%d MODE=%s\n",w,h,argv[3]);
        printf("STAGE=SOURCE_CREATE_BEGIN\n");
        CVPixelBufferRef src=buffer(bgra?kCVPixelFormatType_32BGRA:kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,w,h);
        if(!src) return 3;
        printf("STAGE=SOURCE_FILL_BEGIN\n");
        int fillstatus=fillSource(src,w,h,bgra);
        printf("STAGE=SOURCE_FILL_RETURNED status=%d\n",fillstatus);
        if(fillstatus){CVPixelBufferRelease(src);return 3;}
        printf("STAGE=DESTINATION_CREATE_BEGIN\n");
        CVPixelBufferRef dst=buffer(kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,w,h);
        if(!dst){CVPixelBufferRelease(src);return 3;}
        VTPixelTransferSessionRef transfer=NULL;
        printf("STAGE=PIXEL_TRANSFER_SESSION_CREATE_BEGIN\n");
        OSStatus st=VTPixelTransferSessionCreate(kCFAllocatorDefault,&transfer);
        printf("STAGE=PIXEL_TRANSFER_SESSION_CREATE_RETURNED status=%d\n",(int)st);
        if(st!=noErr || !transfer){CVPixelBufferRelease(src);CVPixelBufferRelease(dst);return 4;}
        printf("STAGE=PIXEL_TRANSFER_BEGIN\n");
        st=VTPixelTransferSessionTransferImage(transfer,src,dst);
        printf("STAGE=PIXEL_TRANSFER_RETURNED status=%d\n",(int)st);
        if(st==noErr) {
            CVReturn lock=CVPixelBufferLockBaseAddress(dst,kCVPixelBufferLock_ReadOnly);
            if(lock==kCVReturnSuccess) {
                const uint8_t *ptr=(const uint8_t *)CVPixelBufferGetBaseAddressOfPlane(dst,0);
                printf("RESULT_FIRST_Y=%d\n",ptr?(int)*ptr:-1);
                CVPixelBufferUnlockBaseAddress(dst,kCVPixelBufferLock_ReadOnly);
            } else printf("DESTINATION_LOCK_STATUS=%d\n",(int)lock);
        }
        VTPixelTransferSessionInvalidate(transfer);
        CFRelease(transfer);
        CVPixelBufferRelease(src);
        CVPixelBufferRelease(dst);
        printf("RESULT=%s\n",st==noErr?"PIXEL_TRANSFER_PASS":"PIXEL_TRANSFER_FAIL");
        return st==noErr?0:4;
    }
}
