#import <Foundation/Foundation.h>
#import <VideoToolbox/VideoToolbox.h>
#import <CoreMedia/CoreMedia.h>
#import <CoreVideo/CoreVideo.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <pthread.h>
#include <math.h>
#include "wex_bgra_to_nv12.h"

// D1.1 BGRA app-level compatibility ENCODE test. This does not modify any system file.
// H.264 requires hardware; HEVC_SW explicitly selects the registered software encoder.
// We verify that the encoder returns real compressed sample buffers, not just
// that VideoToolbox advertises hardware support.

static const int kWidth = 1920;
static const int kHeight = 1080;
static const int kFPS = 30;

typedef struct {
    pthread_mutex_t lock;
    CMVideoCodecType expectedCodec;
    unsigned long outputSamples;
    unsigned long outputBytes;
    unsigned long callbackErrors;
    unsigned long emptySamples;
    unsigned long wrongCodec;
    unsigned long keyframes;
    int outputWidth;
    int outputHeight;
    OSStatus lastCallbackError;
} EncoderStats;

static void encodedSampleCallback(void *refcon,
                                  void *sourceFrameRefCon,
                                  OSStatus status,
                                  VTEncodeInfoFlags infoFlags,
                                  CMSampleBufferRef sample) {
    (void)sourceFrameRefCon;
    (void)infoFlags;
    EncoderStats *stats = (EncoderStats *)refcon;
    pthread_mutex_lock(&stats->lock);
    if (status != noErr || !sample) {
        stats->callbackErrors++;
        stats->lastCallbackError = status;
        pthread_mutex_unlock(&stats->lock);
        return;
    }

    CMBlockBufferRef block = CMSampleBufferGetDataBuffer(sample);
    size_t length = block ? CMBlockBufferGetDataLength(block) : 0;
    if (!CMSampleBufferDataIsReady(sample) || length == 0) {
        stats->emptySamples++;
        pthread_mutex_unlock(&stats->lock);
        return;
    }

    CMFormatDescriptionRef format = CMSampleBufferGetFormatDescription(sample);
    if (!format || CMFormatDescriptionGetMediaSubType(format) != stats->expectedCodec) {
        stats->wrongCodec++;
        pthread_mutex_unlock(&stats->lock);
        return;
    }
    CMVideoDimensions dims = CMVideoFormatDescriptionGetDimensions((CMVideoFormatDescriptionRef)format);
    stats->outputWidth = dims.width;
    stats->outputHeight = dims.height;
    stats->outputSamples++;
    stats->outputBytes += (unsigned long)length;

    CFArrayRef attachments = CMSampleBufferGetSampleAttachmentsArray(sample, false);
    if (attachments && CFArrayGetCount(attachments) > 0) {
        CFDictionaryRef d = (CFDictionaryRef)CFArrayGetValueAtIndex(attachments, 0);
        CFTypeRef notSync = CFDictionaryGetValue(d, kCMSampleAttachmentKey_NotSync);
        if (notSync != kCFBooleanTrue) stats->keyframes++;
    }
    pthread_mutex_unlock(&stats->lock);
}

// Generate a BGRA test image in CPU memory as a stand-in for app-created BGRA frames.
// Apps can use wex_bgra_to_nv12() before VTCompressionSessionEncodeFrame.
static void makeBGRA(uint8_t *buf, int frameNo) {
    for (int y=0; y<kHeight; ++y) {
        uint8_t *row=buf+(size_t)y*(size_t)kWidth*4;
        for (int x=0; x<kWidth; ++x) {
            row[(size_t)x*4+0]=(uint8_t)((x*5+y*3+frameNo*11)&255); // B
            row[(size_t)x*4+1]=(uint8_t)((x/3+y*7+frameNo*5)&255); // G
            row[(size_t)x*4+2]=(uint8_t)((x*3+y/2+frameNo*13)&255); // R
            row[(size_t)x*4+3]=255; // A
        }
    }
}
static CVReturn makeFrame(VTCompressionSessionRef session, int frameNo, const uint8_t *bgra,

                          CVPixelBufferRef *result) {
    (void)frameNo;
    *result = NULL;
    const OSType fmt = kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange; // NV12 / 420v
    CVPixelBufferPoolRef pool = VTCompressionSessionGetPixelBufferPool(session);
    CVReturn st = kCVReturnError;
    if (pool) {
        st = CVPixelBufferPoolCreatePixelBuffer(kCFAllocatorDefault, pool, result);
        if (st == kCVReturnSuccess && *result && CVPixelBufferGetPixelFormatType(*result) != fmt) {
            printf("POOL_PIXEL_FORMAT_MISMATCH = 0x%08X (creating NV12 manually)\n",
                   (unsigned)CVPixelBufferGetPixelFormatType(*result));
            CVPixelBufferRelease(*result);
            *result = NULL;
        }
    }
    if (!*result) {
        NSDictionary *attrs = @{
            (__bridge NSString *)kCVPixelBufferPixelFormatTypeKey: @(fmt),
            (__bridge NSString *)kCVPixelBufferWidthKey: @(kWidth),
            (__bridge NSString *)kCVPixelBufferHeightKey: @(kHeight),
            (__bridge NSString *)kCVPixelBufferIOSurfacePropertiesKey: @{}
        };
        st = CVPixelBufferCreate(kCFAllocatorDefault, kWidth, kHeight, fmt,
                                 (__bridge CFDictionaryRef)attrs, result);
    }
    if (st != kCVReturnSuccess || !*result) return st;
    if (CVPixelBufferGetPixelFormatType(*result) != fmt || CVPixelBufferGetPlaneCount(*result) != 2) {
        printf("INVALID_NV12_BUFFER = format 0x%08X planes %lu\n",
               (unsigned)CVPixelBufferGetPixelFormatType(*result),
               (unsigned long)CVPixelBufferGetPlaneCount(*result));
        CVPixelBufferRelease(*result);
        *result = NULL;
        return kCVReturnInvalidPixelFormat;
    }
    st = CVPixelBufferLockBaseAddress(*result, 0);
    if (st != kCVReturnSuccess) {
        CVPixelBufferRelease(*result);
        *result = NULL;
        return st;
    }
    uint8_t *ybase = (uint8_t *)CVPixelBufferGetBaseAddressOfPlane(*result, 0);
    uint8_t *uvbase = (uint8_t *)CVPixelBufferGetBaseAddressOfPlane(*result, 1);
    size_t ystride = CVPixelBufferGetBytesPerRowOfPlane(*result, 0);
    size_t uvstride = CVPixelBufferGetBytesPerRowOfPlane(*result, 1);
    size_t yh = CVPixelBufferGetHeightOfPlane(*result, 0);
    size_t uvh = CVPixelBufferGetHeightOfPlane(*result, 1);
    if (!ybase || !uvbase || ystride < (size_t)kWidth || uvstride < (size_t)kWidth ||
        yh < (size_t)kHeight || uvh < (size_t)(kHeight/2)) {
        printf("INVALID_NV12_PLANES = Ystride %lu UVstride %lu Yheight %lu UVheight %lu\n",
               (unsigned long)ystride, (unsigned long)uvstride,
               (unsigned long)yh, (unsigned long)uvh);
        CVPixelBufferUnlockBaseAddress(*result, 0);
        CVPixelBufferRelease(*result);
        *result = NULL;
        return kCVReturnError;
    }
    // CPU conversion avoids VideoToolbox's crashing BGRA -> 420v AVFPixelProcess path.
    int conv = wex_bgra_to_nv12(bgra, (size_t)kWidth*4, ybase, ystride,
                                uvbase, uvstride, kWidth, kHeight);
    if (conv != 0) {
        printf("BGRA_CONVERSION_FAILED = %d\n", conv);
        CVPixelBufferUnlockBaseAddress(*result, 0);
        CVPixelBufferRelease(*result);
        *result = NULL;
        return kCVReturnError;
    }
    CVPixelBufferUnlockBaseAddress(*result, 0);
    CVBufferSetAttachment(*result, kCVImageBufferYCbCrMatrixKey,
                          kCVImageBufferYCbCrMatrix_ITU_R_709_2,
                          kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(*result, kCVImageBufferColorPrimariesKey,
                          kCVImageBufferColorPrimaries_ITU_R_709_2,
                          kCVAttachmentMode_ShouldPropagate);
    CVBufferSetAttachment(*result, kCVImageBufferTransferFunctionKey,
                          kCVImageBufferTransferFunction_ITU_R_709_2,
                          kCVAttachmentMode_ShouldPropagate);
    return kCVReturnSuccess;
}

static void printEncoderProperty(VTCompressionSessionRef session) {
    CFTypeRef idValue = NULL;
    OSStatus st = VTSessionCopyProperty(session, kVTCompressionPropertyKey_EncoderID,
                                        kCFAllocatorDefault, &idValue);
    if (st == noErr && idValue && CFGetTypeID(idValue) == CFStringGetTypeID()) {
        char ident[512] = {0};
        if (CFStringGetCString((CFStringRef)idValue, ident, sizeof(ident), kCFStringEncodingUTF8))
            printf("ENCODER_ID = %s\n", ident);
        else printf("ENCODER_ID = (not representable in UTF-8)\n");
    } else {
        printf("ENCODER_ID = UNKNOWN (query OSStatus %d)\n", (int)st);
    }
    if (idValue) CFRelease(idValue);
}

static int testCodec(CMVideoCodecType codec, const char *name, int frames, BOOL requireHardware) {
    printf("\n========== %s ENCODE (1080p30) ==========\n", name);
    printf("HARDWARE_REQUIRED = %s\n", requireHardware ? "YES" : "NO (explicit software fallback)");
    printf("SOURCE_FORMAT = BGRA 1920 x 1080 @ 30 fps\n");
    printf("ENCODER_INPUT_FORMAT = NV12/420v (CPU BT.709 conversion, bypass GPU pixel transfer)\n");
    printf("REQUESTED_FRAMES = %d\n", frames);

    EncoderStats stats = {0};
    stats.expectedCodec = codec;
    pthread_mutex_init(&stats.lock, NULL);
    // HEVC_SW is a deliberately labelled software fallback: there is no
    // registered hardware HEVC encoder on the tested A7A0 machine.
    NSDictionary *spec = requireHardware ? @{
        (__bridge NSString *)kVTVideoEncoderSpecification_RequireHardwareAcceleratedVideoEncoder: @YES
    } : @{
        (__bridge NSString *)kVTVideoEncoderSpecification_RequireHardwareAcceleratedVideoEncoder: @NO,
        (__bridge NSString *)kVTVideoEncoderSpecification_EncoderID: @"com.apple.videotoolbox.videoencoder.hevc.vcp"
    };
    NSDictionary *imageAttrs = @{
        (__bridge NSString *)kCVPixelBufferPixelFormatTypeKey: @(kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange),
        (__bridge NSString *)kCVPixelBufferWidthKey: @(kWidth),
        (__bridge NSString *)kCVPixelBufferHeightKey: @(kHeight),
        (__bridge NSString *)kCVPixelBufferIOSurfacePropertiesKey: @{}
    };

    VTCompressionSessionRef session = NULL;
    OSStatus st = VTCompressionSessionCreate(kCFAllocatorDefault, kWidth, kHeight, codec,
                                             (__bridge CFDictionaryRef)spec,
                                             (__bridge CFDictionaryRef)imageAttrs,
                                             NULL, encodedSampleCallback, &stats, &session);
    printf("SESSION_CREATE_STATUS = %d\n", (int)st);
    if (st != noErr || !session) {
        printf("ENCODER_CREATE_FAILED (required hardware=%s)\n", requireHardware ? "YES":"NO");
        printf("RESULT = %s\n", requireHardware ? "HARDWARE_ENCODE_FAIL" : "SOFTWARE_ENCODE_FAIL");
        if (session) { VTCompressionSessionInvalidate(session); CFRelease(session); }
        pthread_mutex_destroy(&stats.lock);
        return 1;
    }

    // Optional properties: absence does not invalidate the hardware test.
    SInt32 bitrate = 5 * 1000 * 1000;
    CFNumberRef bitrateValue = CFNumberCreate(NULL, kCFNumberSInt32Type, &bitrate);
    OSStatus rateStatus = VTSessionSetProperty(session, kVTCompressionPropertyKey_AverageBitRate, bitrateValue);
    CFRelease(bitrateValue);
    (void)VTSessionSetProperty(session, kVTCompressionPropertyKey_RealTime, kCFBooleanFalse);
    SInt32 frameRate = kFPS;
    CFNumberRef frameRateValue = CFNumberCreate(NULL, kCFNumberSInt32Type, &frameRate);
    (void)VTSessionSetProperty(session, kVTCompressionPropertyKey_ExpectedFrameRate, frameRateValue);
    CFRelease(frameRateValue);
    printf("BITRATE_SET_STATUS = %d (optional)\n", (int)rateStatus);

    printf("STAGE = PREPARE_BEGIN\n");
    OSStatus prepStatus = VTCompressionSessionPrepareToEncodeFrames(session);
    printf("PREPARE_STATUS = %d\n", (int)prepStatus);
    if (prepStatus != noErr) {
        printf("RESULT = %s\n", requireHardware ? "HARDWARE_ENCODE_FAIL" : "SOFTWARE_ENCODE_FAIL");
        VTCompressionSessionInvalidate(session);
        CFRelease(session);
        pthread_mutex_destroy(&stats.lock);
        return 1;
    }

    printEncoderProperty(session);
    uint8_t *bgra=(uint8_t *)malloc((size_t)kWidth*(size_t)kHeight*4);
    if (!bgra) {
        printf("ERROR = BGRA_ALLOC_FAILED\n");
        VTCompressionSessionInvalidate(session);
        CFRelease(session);
        pthread_mutex_destroy(&stats.lock);
        return 1;
    }
    int submitted = 0;
    int frameCreateError = 0;
    OSStatus submissionStatus = 0;
    CFAbsoluteTime begin = CFAbsoluteTimeGetCurrent();
    for (int i = 0; i < frames; ++i) {
        printf("STAGE = FRAME_%d_BUFFER_CREATE_BEGIN\n", i);
        CVPixelBufferRef pixelBuffer = NULL;
        makeBGRA(bgra, i);
        CVReturn cv = makeFrame(session, i, bgra, &pixelBuffer);
        if (cv != kCVReturnSuccess || !pixelBuffer) {
            frameCreateError = (int)cv;
            printf("SOURCE_PIXEL_BUFFER_ERROR = %d at frame %d\n", frameCreateError, i);
            break;
        }
        printf("STAGE = FRAME_%d_BUFFER_READY format=0x%08X\n", i, (unsigned)CVPixelBufferGetPixelFormatType(pixelBuffer));
        CMTime pts = CMTimeMake(i, kFPS);
        CMTime duration = CMTimeMake(1, kFPS);
        printf("STAGE = FRAME_%d_SUBMIT_BEGIN\n", i);
        submissionStatus = VTCompressionSessionEncodeFrame(session, pixelBuffer, pts, duration,
                                                             NULL, NULL, NULL);
        CVPixelBufferRelease(pixelBuffer);
        printf("STAGE = FRAME_%d_SUBMIT_RETURNED status=%d\n", i, (int)submissionStatus);
        if (submissionStatus != noErr) {
            printf("ENCODE_SUBMISSION_ERROR = %d at frame %d\n", (int)submissionStatus, i);
            break;
        }
        submitted++;
    }
    printf("STAGE = FLUSH_BEGIN\n");
    OSStatus flushStatus = VTCompressionSessionCompleteFrames(session, kCMTimeInvalid);
    printf("STAGE = FLUSH_RETURNED status=%d\n", (int)flushStatus);
    CFAbsoluteTime elapsed = CFAbsoluteTimeGetCurrent() - begin;

    CFTypeRef hwValue = NULL;
    OSStatus hwStatus = VTSessionCopyProperty(session,
        kVTCompressionPropertyKey_UsingHardwareAcceleratedVideoEncoder,
        kCFAllocatorDefault, &hwValue);
    BOOL hardwareYes = (hwStatus == noErr && hwValue && CFGetTypeID(hwValue) == CFBooleanGetTypeID() &&
                        CFBooleanGetValue((CFBooleanRef)hwValue));
    BOOL hardwareNo = (hwStatus == noErr && hwValue && CFGetTypeID(hwValue) == CFBooleanGetTypeID() &&
                       !CFBooleanGetValue((CFBooleanRef)hwValue));
    if (hardwareYes) printf("HARDWARE_USED = YES (query OSStatus %d)\n", (int)hwStatus);
    else if (hardwareNo) printf("HARDWARE_USED = NO (query OSStatus %d)\n", (int)hwStatus);
    else printf("HARDWARE_USED = UNKNOWN (query OSStatus %d; %s)\n", (int)hwStatus,
                requireHardware ? "hardware-required session was created" : "explicit HEVC software encoder selected");
    if (hwValue) CFRelease(hwValue);

    pthread_mutex_lock(&stats.lock);
    unsigned long outputSamples = stats.outputSamples;
    unsigned long outputBytes = stats.outputBytes;
    unsigned long errors = stats.callbackErrors;
    unsigned long empty = stats.emptySamples;
    unsigned long wrong = stats.wrongCodec;
    unsigned long keyframes = stats.keyframes;
    int outputWidth = stats.outputWidth, outputHeight = stats.outputHeight;
    OSStatus lastCallbackError = stats.lastCallbackError;
    pthread_mutex_unlock(&stats.lock);

    printf("SUBMITTED_FRAMES = %d\n", submitted);
    printf("OUTPUT_COMPRESSED_SAMPLES = %lu\n", outputSamples);
    printf("ENCODED_BYTES = %lu\n", outputBytes);
    printf("OUTPUT_FRAME_SIZE = %d x %d\n", outputWidth, outputHeight);
    printf("KEYFRAMES_OBSERVED = %lu\n", keyframes);
    printf("CALLBACK_ERRORS = %lu (last OSStatus %d)\n", errors, (int)lastCallbackError);
    printf("EMPTY_OUTPUT_SAMPLES = %lu\n", empty);
    printf("WRONG_OUTPUT_CODEC = %lu\n", wrong);
    printf("FLUSH_STATUS = %d\n", (int)flushStatus);
    printf("WALL_TIME_SEC = %.3f (includes CPU generation of input frames)\n", (double)elapsed);
    if (elapsed > 0.0) printf("OVERALL_THROUGHPUT_FPS = %.1f\n", submitted / (double)elapsed);
    printf("NOTE = This fixes input handling in THIS test/application only; it does not modify system-wide VideoToolbox.\n");
    printf("NOTE = Encoded byte counts prove compressed output; playback/decoding requires separate validation.\n");

    BOOL ok = (submitted == frames && outputSamples == (unsigned long)frames &&
               outputBytes > 0 && errors == 0 && empty == 0 && wrong == 0 &&
               outputWidth == kWidth && outputHeight == kHeight &&
               flushStatus == noErr && !frameCreateError && submissionStatus == noErr &&
               (requireHardware ? !hardwareNo : !hardwareYes));
    if (requireHardware) {
        if (hardwareYes && ok) printf("RESULT = HARDWARE_ENCODE_PASS\n");
        else if (ok && !hardwareNo) printf("RESULT = HARDWARE_ENCODE_PASS_BY_REQUIRED_SESSION (hardware-used property unavailable)\n");
        else printf("RESULT = HARDWARE_ENCODE_FAIL\n");
    } else {
        if (ok && !hardwareYes) printf("RESULT = SOFTWARE_ENCODE_PASS (NOT hardware encode)\n");
        else printf("RESULT = SOFTWARE_ENCODE_FAIL_OR_HW_MISMATCH\n");
    }

    free(bgra);
    VTCompressionSessionInvalidate(session);
    CFRelease(session);
    pthread_mutex_destroy(&stats.lock);
    return (ok && (requireHardware ? !hardwareNo : !hardwareYes)) ? 0 : 1;
}

int main(int argc, const char *argv[]) {
    setvbuf(stdout, NULL, _IONBF, 0); // retain every stage even if driver crashes
    setvbuf(stderr, NULL, _IONBF, 0);
    @autoreleasepool {
        if (argc != 3) {
            fprintf(stderr, "Usage: %s H264|HEVC_SW <frames 1..180>\n", argv[0]);
            return 2;
        }
        CMVideoCodecType codec;
        const char *codecName;
        BOOL requireHardware=YES;
        if (strcmp(argv[1], "H264") == 0) { codec=kCMVideoCodecType_H264; codecName="H.264"; }
        else if (strcmp(argv[1], "HEVC_SW") == 0) { codec=kCMVideoCodecType_HEVC; codecName="HEVC (software fallback)"; requireHardware=NO; }
        else { fprintf(stderr, "Unknown codec: %s\n", argv[1]); return 2; }
        char *end = NULL;
        long count = strtol(argv[2], &end, 10);
        if (!end || *end || count < 1 || count > 180) {
            fprintf(stderr, "Frame count must be between 1 and 180.\n"); return 2;
        }
        printf("WEX D1.1 BGRA-to-NV12 app-level encoder compatibility, %s, codec=%s, frames=%ld\n",
               requireHardware ? "hardware required" : "explicit software encoder", codecName, count);
        printf("This test does not modify EFI, Kexts, SIP or macOS settings.\n");
        printf("PROBE = BGRA frames converted on CPU to NV12 before VideoToolbox; system BGRA path unchanged.\n");
        return testCodec(codec, codecName, (int)count, requireHardware);
    }
}
