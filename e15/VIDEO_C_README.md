# WhateverXe E-Video-C — D-style VA property restoration experiment

**High-risk optional test feature integrated into the main build; not a production fix.** This is the A/B/C continuation after the physical Yoga A7A0 showed hardware codec regression on E/main and a repeatable VPHAL NULL+8 crash on Video B. The existing signed Graphics 0.4.0 and user EFI remain unchanged; source and build workflow are now integrated into main with an opt-in flag.

## Why test two properties?

The original E donor hides both `IOGVAScaler` and `IOVARendererID` on mobile Display13. The archived D1.1 keeps both. Video B restored only `IOVARendererID=0x1080080` and H.264 HW-required session creation recovered, but its Stage 3 sample-creation process crashed with `EXC_BAD_ACCESS at 0x8` in `AppleIntelTGLGraphicsVADriver` at **image offset `0x1336f3`**.

The 2026-11-06 `decoder_probe-2026-11-06-224216.ips` crash was in `com.apple.videotoolbox.preparationQueue`, called through `VTPixelTransferSessionTransferImage` / `AVFPixelProcess_PrepareToTransferImages`. Its VA image UUID `00204000-0263-4092-B483-CC2544D26350` matches the archived D1.1 binary where the same `0x1336f3` crash was documented.

**Therefore restoring `IOGVAScaler` is *not expected to cure* the known crash merely by itself.** This build isolates a comparison; do not interpret it as a VPHAL null-pointer patch.

## Exact implementation

Build starts from E/main commit `43f368492e89cbf3f3002aa66fca3bafe28d9e96`, pinned `acer/current` donor `f7b9bf2229d323e37e8b1dfb87182f005eb7a277`, and the unchanged E + HDMI600 + RGB8 preparation script. New overlay: `e15/tools/prepare_video_c.py`.

A single new boot flag is used:

```
-wex-yoga-video-c
```

- **Flag absent:** original E removes both keys.
- **Flag present AND** provider matches Intel `8086:A7A0`, mobile Display13 is selected, and renderer is `0x1080080`: skip BOTH existing key removals.
- **Any guard fails:** original E behavior.
- `IOGVAScaler` must already exist to be retained; this patch does not fabricate any value. It does **not** modify the signed VA driver or implement HEVC hardware encoding.
- Existing opt-in `-wex-yoga-hdmi600` and `-wex-yoga-rgb8` are unaffected.

Originally developed in an independent branch; now prepared for integration into main. The Video B branch remains untouched. **Do not use `-wex-yoga-video-b` in a C test EFI.**

## Prepare safe comparison

Keep recovery EFI; only replace WhateverXe.kext in a **separate test EFI**. First boot the C Kext without the new flag to confirm original E behavior. Then add only `-wex-yoga-video-c` and reboot with no external monitors.

Run a read-only registry check:

```bash
nvram boot-args
ioreg -p IOService -l -w0 | grep -E 'WEXYogaVideoC|IOVARendererID|IOGVAScaler'
```

Look for:

- `WEXYogaVideoCRequested = Yes`
- `WEXYogaVideoCMatched = Yes`
- `WEXYogaVideoCPropertiesPreserved = Yes`
- `WEXYogaVideoCScalerPresent = Yes`
- `IOVARendererID = 17301632` (`0x1080080`)
- `IOGVAScaler` exists

The listed properties have been verified on the Yoga A7A0. **Do not assume this proves every VideoToolbox path is stable.** The known crash can also occur during video generation in VideoToolbox—even when a test requests a software codec. Stage 3 is therefore **NOT a safe first test for C**; do not run it to see whether the crash is gone without a reason to reproduce the fault.

If the desktop becomes unstable, boot the untouched recovery EFI; otherwise remove the `-wex-yoga-video-c` flag to return to E behavior on the C Kext. No change to existing EFI or Graphics is part of this experiment.

## Current Yoga A7A0 real-hardware evidence

- With Video C, H.264 hardware-required compression session creation succeeds, and `UsingHardwareAcceleratedVideoEncoder=YES`.
- Running the original D direct-NV12 H.264 program on C yielded **1/1, 30/30 and 180/180** valid 1920x1080 compressed output samples, zero callbacks errors (180-frame output 3,945,719 bytes).
- The alternate C `hw_encode_nv12.m` single-frame and multi-frame tests **crashed** at `AppleIntelTGLGraphicsVADriver+0x1336f3`, in the VPHAL pixel transfer path. The working input path does **not** fix the crash.
- Real hardware H.264/HEVC **decoding on C is not confirmed**: prior file-based probe terminated while extracting compressed format metadata, before `VTDecompressionSessionCreate`.
- Video C does not enable HEVC hardware **encoding**.

## Evidence and limitations

CI confirms source matching and compilation on its Intel macOS runner, not functional safety on the Lenovo hardware. Although the original D direct-NV12 test proved real H.264 encoded output on C, no safe system-wide pixel-transfer or C hardware-decoding guarantee follows. Neither Video B nor Video C fixes the native VPHAL NULL pointer access `0x1336f3`.

Main RELEASE workflow: `.github/workflows/yoga-main.yml`; output artifact: `WhateverXe-Yoga-Main-VideoC-Test-Kext`. The historical experiment workflow `.github/workflows/yoga-video-c.yml` remains available for the experiment branch.
