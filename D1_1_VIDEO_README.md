# D1.1 — video encode compatibility experiment (NOT a system-wide driver fix)

Based on WhateverXe D (`experiment/a7a0-single-panel-clock-isolation`, commit `d7350766`). **Do not replace your working D EFI/Graphics setup.** D1.1 experiments are kept separate from kernel/framebuffer patches.

## Evidence from Lenovo Yoga Pro 14s IRH8 / i9-13900H / A7A0 / Tahoe

- Metal compute and 1080p H.264/HEVC hardware **decode**: verified on-device.
- H.264 **hardware encode**, direct NV12/420v: 180/180 compressed samples, 4,025,912 bytes, zero callback errors.
- H.264 hardware encode, **BGRA** source: crash (`EXC_BAD_ACCESS` at `0x8`) in `AppleIntelTGLGraphicsVADriver` on VideoToolbox's `preparationQueue`, called through `AppleGVA → AVFPixelProcess_PrepareToTransferImages → VTPixelTransferSessionTransferImage`.
- HEVC hardware encode: `SESSION_CREATE_STATUS=-12908`; `VTCopyVideoEncoderList` reports **only** `Apple HEVC (SW)`, whereas H.264 (HW) is registered. `IOGVAHEVCEncodeCapabilities` in IORegistry is insufficient evidence of HEVC hardware encoder registration.

## D1.1 changes and realistic scope

**1. BGRA crash: working application-level bypass (candidate).** `wex_bgra_to_nv12.h` performs a CPU, limited-range Rec.709 8-bit conversion from BGRA to NV12/420v. `wex_bgra_compat_encode.m` generates BGRA input, converts it to NV12 and passes NV12 directly into `VTCompressionSessionEncodeFrame` with `RequireHardwareAcceleratedVideoEncoder=true`. This avoids the `AVFPixelProcess` BGRA conversion for applications that **integrate the compatibility helper**. It does not patch AppleGVA or solve BGRA crashes in other apps. The converter's C unit tests pass; the macOS integration **has now passed on the target laptop**: 1/1 and 180/180 H.264 HW samples via BGRA->CPU NV12, with zero callback errors. This remains application-scoped and does not repair system VideoToolbox.

**2. HEVC: software fallback and diagnostics, not a fake hardware driver.** `wex_encoder_inventory.m` enumerates VideoToolbox encoder registrations without starting a session. The actual HEVC hardware encoder is **not registered** on the target. We deliberately do not forge an `IOGVAHEVCEncodeCapabilities` property or advertise a non-functional encoder. A real fix would require confirming working HEVC encode in the user-space VA/AppleGVA bridge and implementing the missing registration/initialization path, with signed payloads and safety tests. That is **not implemented yet**.

### Reference project findings

[JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe — experimental encode README](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/macos/vadriver/encode-experimental/README.md)

The referenced author's experimental H.264 VDENC changes are **not included in their normal install**. They state that enabling VPHAL scaler support may cause 1080p pixel-transfer crashes **system-wide**, and that P-frame prediction hangs can occur. This is close to our observed BGRA path but is not evidence that their binary patches will work on WhateverXe Graphics 0.4.0. HEVC **encode** is not implemented by those H.264-only experimental scripts. Applying those binary offsets to a differently patched, signed VA payload would be unsafe. The baseline D graphics kernel/EFI is unchanged here.

### How to use on macOS (no sudo / EFI change)

```bash
cd macos/video-encode
bash inspect_video_encoders.command
bash run_bgra_compat.command H264 1
# Only after the 1-frame test succeeds:
bash run_bgra_compat.command H264 180
```

For **HEVC output without hardware encoding**, the opt-in `HEVC_SW` mode requests Apple's currently registered HEVC **software** encoder. It may be slower and cannot be counted as hardware support:

```bash
bash run_bgra_compat.command HEVC_SW 1
```

**Warning:** This test invokes the native H.264 hardware encoder; past runs passed but future native-driver crashes are still possible. Save open work first. Output logs go to `macos/video-encode/output/`. It is not an installer or a system-wide fix.

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

## 2026-11-04 D1.1 on-device results (Yoga A7A0, Tahoe 25G241)

- `inspect_video_encoders.command`: H.264 HW registered (two GVA entries); HEVC **only SW** (`com.apple.videotoolbox.videoencoder.hevc.vcp`); `HEVC_HW_REGISTERED=NO`.
- **Important**: IORegistry already advertises `IOGVAHEVCEncodeCapabilities` (profile 1, max encode level 183), but VideoToolbox still has *no registered HEVC hardware encoder*. Adding the same accelerator property is not a demonstrated fix; investigate AppleGVA/VA plugin discovery and matching instead.
- BGRA source -> CPU BT.709 NV12 -> H.264 HW: one frame produced 196759 bytes, `HARDWARE_USED=YES`, no errors. 180/180 frames produced 34186663 bytes, zero callback errors/empty samples, `HARDWARE_USED=YES`, wall time 10.123 s (includes CPU generation + BGRA conversion). **App-level workaround passed, not system-wide VPHAL repair**.
- BGRA source -> CPU NV12 -> explicitly selected `hevc.vcp` **software** encoder: 1/1 output frame, 198076 bytes, `RESULT=SOFTWARE_ENCODE_PASS`. The `UsingHardwareAcceleratedVideoEncoder` property query returned -12900/unknown, but this does **not** turn a software encoder into hardware; the code's diagnostic wording has been corrected.
- Previously direct NV12 H.264 HW 180/180 passed. Previously direct NV12 HEVC **hardware-required** session creation failed (-12908). BGRA-direct H.264 crashes within `AppleIntelTGLGraphicsVADriver` / `AVFPixelProcess_PrepareToTransferImages`.
- **No binary VA driver or EFI modifications in this branch.** Verify source compile and behavior on Mac; do not infer real-world screen recording or video export is fixed based on these isolated tests.

## D1.1.1 driver-level localization tools

See [D1_1_VIDEO_ADVANCED.md](D1_1_VIDEO_ADVANCED.md). Added native-source probes for (a) process-local professional HEVC encoder registration vs current encoder-list registration, (b) encoder property negotiation without submitting frames, and (c) **isolated VTPixelTransferSession** BGRA->NV12 and NV12->NV12 to localize the crashing VPHAL path independently from H.264 encoding. An installed VA bundle fingerprint tool collects hash/UUID/signing/dependency metadata without modifying it.

These are diagnostic code paths, **not** new VA binaries, fake HEVC HW entries or EFI changes. The 1080p native pixel transfer has an explicit opt-in crash warning. The separate GitHub workflow `video-encode-d11.yml` checks compile/shell/C tests on a macOS Intel runner but cannot validate graphics hardware.

The former D EFI and Graphics install remain baseline. Earlier 180-frame BGRA->CPU NV12->H.264 HW pass and HEVC-SW-only registration remain unchanged as observed facts.

## D1.1.4: exact VPHAL crash-site research and offline safety checks

[See research report](D1_1_4_VPHAL_RESEARCH.md). The 64x64 transfer and direct-BGRA encoder crash at the same `0x1336f3` NULL write. Reverse engineering of the original Apple Tiger Lake 16.0.32 Mach-O shows this NULL comes from a renderer subcomponent at `+0x910`. JulioNectar's independent `patch_vpnull2.py` targets **exactly** the same RVA and also guards `+0x920`.

Added a **read-only strict SHA256+Mach-O+byte-signature+code-cave audit**, a separately gated *unsigned offline candidate* (never an installer), and read-only heuristic HEVC backend string inventory. The original driver passes the static guard tests; the **installed signed WEX Graphics v0.4.0 Tahoe payload still needs read-only preflight**. These research tools have not repaired BGRA system transfer or HEVC HW encoding, and the unsigned experimental binary must NOT be installed.
