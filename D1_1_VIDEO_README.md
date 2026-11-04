# D1.1 — video encode compatibility experiment (NOT a system-wide driver fix)

Based on WhateverXe D (`experiment/a7a0-single-panel-clock-isolation`, commit `d7350766`). **Do not replace your working D EFI/Graphics setup.** D1.1 experiments are kept separate from kernel/framebuffer patches.

## Evidence from Lenovo Yoga Pro 14s IRH8 / i9-13900H / A7A0 / Tahoe

- Metal compute and 1080p H.264/HEVC hardware **decode**: verified on-device.
- H.264 **hardware encode**, direct NV12/420v: 180/180 compressed samples, 4,025,912 bytes, zero callback errors.
- H.264 hardware encode, **BGRA** source: crash (`EXC_BAD_ACCESS` at `0x8`) in `AppleIntelTGLGraphicsVADriver` on VideoToolbox's `preparationQueue`, called through `AppleGVA → AVFPixelProcess_PrepareToTransferImages → VTPixelTransferSessionTransferImage`.
- HEVC hardware encode: `SESSION_CREATE_STATUS=-12908`; `VTCopyVideoEncoderList` reports **only** `Apple HEVC (SW)`, whereas H.264 (HW) is registered. `IOGVAHEVCEncodeCapabilities` in IORegistry is insufficient evidence of HEVC hardware encoder registration.

## D1.1 changes and realistic scope

**1. BGRA crash: working application-level bypass (candidate).** `wex_bgra_to_nv12.h` performs a CPU, limited-range Rec.709 8-bit conversion from BGRA to NV12/420v. `wex_bgra_compat_encode.m` generates BGRA input, converts it to NV12 and passes NV12 directly into `VTCompressionSessionEncodeFrame` with `RequireHardwareAcceleratedVideoEncoder=true`. This avoids the `AVFPixelProcess` BGRA conversion for applications that **integrate the compatibility helper**. It does not patch AppleGVA or solve BGRA crashes in other apps. The converter's C unit tests pass on a Linux host; the macOS encoding integration **has not been tested on the target laptop**.

**2. HEVC: diagnostic, not a fake hardware driver.** `wex_encoder_inventory.m` enumerates VideoToolbox encoder registrations without starting a session. The actual HEVC hardware encoder is **not registered** on the target. We deliberately do not forge an `IOGVAHEVCEncodeCapabilities` property or advertise a non-functional encoder. A real fix would require confirming working HEVC encode in the user-space VA/AppleGVA bridge and implementing the missing registration/initialization path, with signed payloads and safety tests. That is **not implemented yet**.

### Reference project findings

[JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe — experimental encode README](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/macos/vadriver/encode-experimental/README.md)

The referenced author's experimental H.264 VDENC changes are **not included in their normal install**. They state that enabling VPHAL scaler support may cause 1080p pixel-transfer crashes **system-wide**, and that P-frame prediction hangs can occur. This is close to our observed BGRA path but is not evidence that their binary patches will work on WhateverXe Graphics 0.4.0. HEVC **encode** is not implemented by those H.264-only experimental scripts. Applying those binary offsets to a differently patched, signed VA payload would be unsafe. The baseline D graphics kernel/EFI is unchanged here.

### How to use on macOS (no sudo / EFI change)

```bash
cd macos/video-encode
bash inspect_video_encoders.command
bash run_bgra_compat.command 1
# Only after the 1-frame test succeeds:
bash run_bgra_compat.command 180
```

**Warning:** This test invokes the native H.264 hardware encoder and could still crash while the new integration is unverified; save open work first. Output logs go to `macos/video-encode/output/`. It is not an installer or a system-wide fix.

For the pure C converter test on a development machine:

```bash
cc -std=c11 -Wall -Wextra -Werror tests/test_bgra_nv12.c -o /tmp/wex_bgra_test
/tmp/wex_bgra_test
```

### Acceptance criteria for an actual future driver fix

- BGRA inputs no longer crash without requiring app changes: 1 and 180 frame H.264 encode with system VideoToolbox; pixel transfer regression (1080p/4K); safe sleep and desktop usage.
- HEVC encoder appears as `HARDWARE=YES` in `VTCopyVideoEncoderList`; `RequireHardwareAcceleratedVideoEncoder=true` session succeeds; 180 compressed HEVC frames are output and decoded to confirm correctness.
- Neither path introduces GPU reset, WindowServer stalls, or display regressions.

**Current status:** D1.1 delivers a code-level app-side workaround plus HEVC registration diagnostics, **NOT** the two requested system-wide driver repairs. No claims of HEVC hardware encoding support or arbitrary-app BGRA repair are made.
