#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#import <CoreMedia/CoreMedia.h>
#include <string.h>
#include <stdio.h>

// Process-local VideoToolbox HEVC encoder discovery.
// No system settings are modified. --professional asks VideoToolbox to load
// professional-workflow encoder registrations only in this process.
static void dumpEncoders(const char *phase) {
    CFArrayRef list = NULL;
    OSStatus st = VTCopyVideoEncoderList(NULL, &list);
    printf("%s_LIST_STATUS = %d\n", phase, (int)st);
    if (st != noErr || !list) return;
    int h264hw=0, hevchw=0, hevcsoft=0;
    for (NSDictionary *entry in (__bridge NSArray *)list) {
        NSNumber *num = entry[(__bridge NSString *)kVTVideoEncoderList_CodecType];
        const CMVideoCodecType codec = (CMVideoCodecType)num.unsignedIntValue;
        if (codec != kCMVideoCodecType_H264 && codec != kCMVideoCodecType_HEVC) continue;
        NSNumber *hardware = entry[(__bridge NSString *)kVTVideoEncoderList_IsHardwareAccelerated];
        BOOL isHardware = hardware != nil && hardware.boolValue;
        NSString *identifier = entry[(__bridge NSString *)kVTVideoEncoderList_EncoderID];
        NSString *name = entry[(__bridge NSString *)kVTVideoEncoderList_EncoderName];
        printf("%s_CODEC=%s HARDWARE=%s ID=%s NAME=%s\n", phase,
               codec == kCMVideoCodecType_H264 ? "H264" : "HEVC",
               isHardware ? "YES" : "NO_OR_UNMARKED",
               identifier ? identifier.UTF8String : "(unknown)",
               name ? name.UTF8String : "(unknown)");
        if (codec == kCMVideoCodecType_H264 && isHardware) ++h264hw;
        if (codec == kCMVideoCodecType_HEVC && isHardware) ++hevchw;
        if (codec == kCMVideoCodecType_HEVC && !isHardware) ++hevcsoft;
    }
    printf("%s_H264_HW_COUNT=%d\n", phase, h264hw);
    printf("%s_HEVC_HW_COUNT=%d\n", phase, hevchw);
    printf("%s_HEVC_UNMARKED_COUNT=%d\n", phase, hevcsoft);
    CFRelease(list);
}

// Querying supported properties is not the same as encoding a frame. It may
// still load provider code, which is why this path is explicitly opt-in.
static void probeSupportedProperties(BOOL requireHardware, int32_t width, int32_t height) {
    NSDictionary *spec = @{
        (__bridge NSString *)kVTVideoEncoderSpecification_RequireHardwareAcceleratedVideoEncoder:
            @(requireHardware)
    };
    CFStringRef selectedID = NULL;
    CFDictionaryRef properties = NULL;
    OSStatus st = VTCopySupportedPropertyDictionaryForEncoder(width, height,
        kCMVideoCodecType_HEVC, (__bridge CFDictionaryRef)spec, &selectedID, &properties);
    printf("HEVC_PROPERTIES_HARDWARE_REQUIRED=%s STATUS=%d\n", requireHardware ? "YES" : "NO", (int)st);
    if (selectedID) {
        NSString *n = (__bridge NSString *)selectedID;
        printf("HEVC_PROPERTIES_ENCODER_ID=%s\n", n.UTF8String);
        CFRelease(selectedID);
    }
    if (properties) {
        printf("HEVC_PROPERTIES_DICTIONARY_COUNT=%ld\n", (long)CFDictionaryGetCount(properties));
        CFRelease(properties);
    }
}

int main(int argc, const char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    @autoreleasepool {
        BOOL professional=NO, properties=NO;
        for (int i=1;i<argc;++i) {
            if (!strcmp(argv[i],"--professional")) professional=YES;
            else if (!strcmp(argv[i],"--properties")) properties=YES;
            else {
                fprintf(stderr, "Usage: %s [--professional] [--properties]\n", argv[0]);
                return 2;
            }
        }
        printf("PROBE=VideoToolbox encoder registration, process-local\n");
        printf("PROFESSIONAL_REGISTRATION=%s\n", professional ? "YES" : "NO");
        printf("ENCODER_PROPERTIES_QUERY=%s\n", properties ? "YES" : "NO");
        dumpEncoders("BEFORE");
        if (professional) {
            printf("STAGE=REGISTER_PROFESSIONAL_VIDEO_WORKFLOW_ENCODERS_BEGIN\n");
            VTRegisterProfessionalVideoWorkflowVideoEncoders();
            printf("STAGE=REGISTER_PROFESSIONAL_VIDEO_WORKFLOW_ENCODERS_RETURNED\n");
            dumpEncoders("AFTER");
        }
        if (properties) {
            probeSupportedProperties(YES,1920,1080);
            probeSupportedProperties(NO,1920,1080);
        }
        printf("NOTE=Only a hardware-flagged HEVC entry or a successful hardware-required encode can establish actual HEVC HW availability.\n");
        return 0;
    }
}
