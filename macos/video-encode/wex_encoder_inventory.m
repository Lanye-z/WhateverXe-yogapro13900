#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#import <CoreMedia/CoreMedia.h>
// Pure read-only hardware encoder discovery; never creates an encoder session.
int main(void) {
    @autoreleasepool {
        CFArrayRef list=NULL;
        OSStatus st=VTCopyVideoEncoderList(NULL,&list);
        printf("ENCODER_LIST_STATUS = %d\n",(int)st);
        if(st!=noErr || !list) return 2;
        int h264hw=0,hevchw=0,hevcsoft=0;
        for(NSDictionary *v in (__bridge NSArray *)list) {
            NSNumber *n=v[(__bridge NSString *)kVTVideoEncoderList_CodecType];
            uint32_t codec=n.unsignedIntValue;
            if(codec!=kCMVideoCodecType_H264 && codec!=kCMVideoCodecType_HEVC) continue;
            NSNumber *hw=v[(__bridge NSString *)kVTVideoEncoderList_IsHardwareAccelerated];
            NSString *idstr=v[(__bridge NSString *)kVTVideoEncoderList_EncoderID];
            NSString *name=v[(__bridge NSString *)kVTVideoEncoderList_EncoderName];
            BOOL isHW=hw.boolValue;
            const char *fourcc=codec==kCMVideoCodecType_H264 ? "H264":"HEVC";
            printf("CODEC = %s | HARDWARE = %s | ID = %s | NAME = %s\n",fourcc,
                   isHW?"YES":"NO/UNMARKED",
                   idstr? idstr.UTF8String:"(missing)",
                   name? name.UTF8String:"(missing)");
            if(codec==kCMVideoCodecType_H264 && isHW)h264hw++;
            if(codec==kCMVideoCodecType_HEVC && isHW)hevchw++;
            if(codec==kCMVideoCodecType_HEVC && !isHW)hevcsoft++;
        }
        printf("H264_HW_REGISTERED = %s\n",h264hw?"YES":"NO");
        printf("HEVC_HW_REGISTERED = %s\n",hevchw?"YES":"NO");
        printf("HEVC_SW_CANDIDATES = %d\n",hevcsoft);
        printf("NOTE = HEVC decoder support and IORegistry capabilities do not imply a registered HEVC hardware encoder.\n");
        CFRelease(list);
    }
    return 0;
}
