# Yoga A7A0 / E Video B — opt-in codec regression experiment

**Experimental, not validated on the physical Yoga. Keep the current working EFI and signed WhateverXe Graphics 0.4.0 unchanged.**

## Baseline and scope

This branch starts from `main` at `43f368492e89cbf3f3002aa66fca3bafe28d9e96`. The build first invokes the unmodified `e13/tools/prepare_rgb8.py`, which pulls in the E1.0 single-line eDP CTL2 fix, E1.1 opt-in HDMI600, and E1.3 opt-in native RGB8. It then applies ONE additional gated change inside `XE::wrapTGLAcceleratorStart()`.

The pinned donor is `Thatisjigen/WhateverXe` `f7b9bf2229d323e37e8b1dfb87182f005eb7a277`, and the local build overlay is `e14/tools/prepare_video_b.py`.

### Video B exact runtime difference

- Without `-wex-yoga-video-b`, preserve the original E behaviour: delete `IOVARendererID` on mobile Display13.
- **With** `-wex-yoga-video-b`, verify the accelerator provider is Intel **8086:A7A0** and the corrected `IOVARendererID` is **0x1080080**. Only then skip the original renderer-property removal.
- E's `IOGVAScaler` removal remains **unchanged** in both cases.
- No change to encoder registration, native VideoToolbox/AppleGVA/VA binaries, PCI ID spoofing, display clocks, display ports, EDID, or multi-output logic.

Check the following `IORegistry` properties for evidence that the opt-in reached the expected code path:

```bash
nvram boot-args
ioreg -p IOService -l -w0 | grep -E 'WEXYogaVideoB(Requested|Matched|RendererPreserved)|IOVARendererID|IOGVAScaler|IOGVAHEVCDecode'
```

All three of `WEXYogaVideoBRequested`, `WEXYogaVideoBMatched`, and `WEXYogaVideoBRendererPreserved` must be `Yes` before interpreting any video tests as a B-group comparison. The mere presence of a boot argument or `Requested=Yes` is insufficient.

## How to obtain the Kext

GitHub Actions workflow: `.github/workflows/yoga-video-b.yml`. It compiles a **Kext-only** RELEASE, validates the exact pinned overlay and original build tests, and uploads an artifact named `WhateverXe-Yoga-Video-B-Test-Kext`.

Extract `WhateverXe_Yoga_A7A0_Video_B_TEST_RELEASE.zip` inside the artifact to obtain `WhateverXe.kext`. **Do not install the ZIP itself or use the build without checking the build log and SHA256SUMS.**

## Safe A/B validation

1. Back up the existing EFI and keep a separate known-good recovery EFI. Ensure only one enabled graphics injection path; do **not** enable NootedGreen alongside WhateverXe.
2. Make a **duplicate test EFI**. Replace only `WhateverXe.kext` in that duplicate with the new RELEASE. Keep installed signed Graphics v0.4.0, other Kexts, and the monitor override unchanged.
3. **A-control:** boot test EFI without `-wex-yoga-video-b`. Confirm internal eDP, Metal, and the 1080p H.264 HW-required compression + H.264/HEVC HW-required decompression tests. This is expected to behave like E, but must be measured.
4. **B experiment:** add only `-wex-yoga-video-b` to the same test EFI, reboot, confirm all three IORegistry indicators `Yes`, and rerun exactly the same tests.
5. If encoder/decoder sessions recover, test sample frames and outputs, check Metal and external displays; only then consider deeper follow-up. No success is assumed before the hardware test.

**Risk:** E deliberately hides the VA renderer because previous devices crashed in `AVFPixelProcess`/native pixel transfers. Your D1.1 also has a documented 64x64 BGRA->NV12 crash in the signed VA binary. B can re-enable the same risky path. Save work, disconnect external accessories for first boot, and do **not** perform BGRA-direct encode or `VTPixelTransferSessionTransferImage` tests.

If unstable, reboot using the unaffected known-good EFI, or remove only `-wex-yoga-video-b` from the duplicate test EFI. This branch is not merged into `main`.

## Interpretation

- Hardware sessions still fail with `RendererPreserved=Yes`: renderer hiding is not sufficient to explain the regression; do not copy D's display stack.
- Hardware sessions recover but native pixel transfer crashes: test suggests a trade-off; not a production-safe fix.
- Both sessions and graphics stable: evidence supporting an opt-in compatibility change, not proof that all apps, sleep, HDMI 4K60, or HEVC hardware encoding work.
- HEVC **hardware encoding** was not supported in D1.1 and is explicitly out of scope.

The historical D1.1 H.264 HW encode and H.264/HEVC HW decode 180-frame success is evidence for comparison, not validation of this build.
