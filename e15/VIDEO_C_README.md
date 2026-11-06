# WhateverXe E-Video-C — D-style VA property restoration experiment

**High-risk diagnostic build; not a production fix.** This is the A/B/C continuation after the physical Yoga A7A0 showed hardware codec regression on E/main and a repeatable VPHAL NULL+8 crash on Video B. The existing signed Graphics 0.4.0, EFI, and main branch remain unchanged.

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

This is an independent branch, not a modification of the original Video B branch. **Do not use `-wex-yoga-video-b` in a C test EFI.**

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

**Stop after this and report the values before initiating any video compression/decompression.** The known crash can also occur during video generation in VideoToolbox—even when a test requests a software codec. Stage 3 is therefore **NOT a safe first test for C**; do not run it to see whether the crash is gone without a reason to reproduce the fault.

If the desktop becomes unstable, boot the untouched recovery EFI; otherwise remove the `-wex-yoga-video-c` flag to return to E behavior on the C Kext. No change to existing EFI or Graphics is part of this experiment.

## Evidence and limitations

CI confirms source matching and compilation on its Intel macOS runner, not functional safety on the Lenovo hardware. Even if a VideoToolbox hardware session can be created, that does not prove a full H.264/HEVC frame has been correctly processed. Neither Video B nor Video C fixes the native VPHAL NULL pointer access `0x1336f3`.

Workflow: `.github/workflows/yoga-video-c.yml`; output artifact: `WhateverXe-Yoga-Video-C-Test-Kext`.
