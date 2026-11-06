# WhateverXe for Lenovo Yoga Pro 14s IRH8 (82Y7) — integrated A7A0 test build

**Experimental, tested on the Yoga A7A0, NOT a crash-free daily-use release.**
This repository's `main` GitHub Actions build integrates E multi-display fixes,
HDMI600 and native RGB8, plus optional **Video C** hardware-codec registration
restoration. It does not replace your known-good EFI, macOS system Graphics
bundle, or the user-space AppleIntelTGLGraphicsVADriver.

Target verified: Lenovo Yoga Pro 14s IRH8 (82Y7), Intel Core i9-13900H,
Intel GPU `8086:A7A0`, macOS 26.7.1 (25G241).
Source pipeline pins `Thatisjigen/WhateverXe`
[`f7b9bf2229d323e37e8b1dfb87182f005eb7a277`](https://github.com/Thatisjigen/WhateverXe/tree/f7b9bf2229d323e37e8b1dfb87182f005eb7a277)
and applies E1.0 -> HDMI600 -> RGB8 -> Video C overlays. **All optional
modifications are default OFF.**

## What is included

| Area | Behavior / activation | Current evidence |
| --- | --- | --- |
| A7A0 eDP + E Display13 multi-output | Built into the E integrated donor | Preserves E's multi-output code; external output modes still require physical testing |
| E1.1 HDMI 300->600 MHz mode-admission | `-wex-yoga-hdmi600` | **Not** a complete HDMI 2.0 4K60 fix; no SCDC Scrambling/High TMDS Clock Ratio implementation |
| Native AOC U27P10 RGB8_STRICT EDID | `-wex-yoga-rgb8` | Byte-exact AOC 05E3:2710 original EDID only, on native HDMI TMDS; other monitors excluded |
| **Video C: restore D-style GVA attributes** | **`-wex-yoga-video-c`** | Real H.264 hardware encode 1080p30 **180/180** with D's direct-NV12 probe; some other pixel-transfer paths crash |
| HEVC hardware encoding | No supported patch | Hardware encoder not registered; do not claim HEVC HW encode |
| H.264 and HEVC hardware decoding | Registration may be advertised | **Real decode on C remains unverified** (earlier test stopped before `VTDecompressionSessionCreate`) |

Video C only preserves *existing* `IOVARendererID=0x1080080` and
`IOGVAScaler=Gen10` when the explicit flag is set, Display13 is selected,
and the physical PCI device is Intel `8086:A7A0`. With the flag **absent**,
the original E behavior (hide both GVA keys) is unchanged. Video C does not
modify the Graphics 0.4.0 VA driver or fix its native crash.

**Known failure / real-world risk:** VideoToolbox's
`AVFPixelProcess_PrepareToTransferImages` can cause
`AppleIntelTGLGraphicsVADriver` `EXC_BAD_ACCESS` at image offset
`0x1336f3` (NULL+8). It was reproduced on C with an alternate H.264 NV12
test (single-frame and multi-frame). Successful direct NV12 encoding via
D's original program does **not** prove Safari, recording, conferencing,
BGRA transfer, or all VideoToolbox pipelines are safe. Do not enable Video C
on unattended or production machines.

## Get and install the integrated WhateverXe Kext

1. Open [GitHub Actions: Yoga main integration](../../actions/workflows/yoga-main.yml)
   and select a **successful `main` run**. Download its
   `WhateverXe-Yoga-Main-VideoC-Test-Kext` artifact.
   Inside, use `WhateverXe_Yoga_A7A0_Main_VideoC_TEST_RELEASE.zip`.
   The workflow builds **only the WhateverXe.kext**, not a complete EFI
   and not new user-space GPU/VA drivers.
2. Back up a **known-good, independently bootable EFI**, duplicate it to a
   test EFI, and replace **only** `EFI/OC/Kexts/WhateverXe.kext` in the
   duplicate. Keep the existing signed Graphics 0.4.0 package unchanged.
   Make sure OpenCore's `config.plist` references the installed Kext.
   **Do not load NootedGreen and WhateverXe simultaneously.**
3. First boot the duplicate EFI **without** Video C or extra display
   flags and verify internal screen / Metal. Then add the desired **opt-in**
   flags and reboot. Video C is independent of RGB8 and HDMI600.
4. On the tested Yoga configuration, one working Video C example (all
   other arguments are specific to that EFI, **not mandatory defaults**):

   ```text
   -v keepsyms=1 -vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-hdmi600 -wex-yoga-video-c
   ```

   To test the AOC native HDMI RGB8 path, additionally add
   `-wex-yoga-rgb8` **only if your monitor/EDID matches**. RGB8
   injection and the pre-existing system EDID override can mask each
   other; consult [E13 validation notes](e13/YOGA_MAIN_RGB8_README.md).
   Do not remove a working system EDID override without backing it up.
5. Verify the active Kext and Video C flags:

   ```bash
   kmutil showloaded | grep WhateverXe
   nvram boot-args
   ioreg -p IOService -l -w0 | grep -E 'WEXYogaVideoC|IOVARendererID|IOGVAScaler'
   ```

   With `-wex-yoga-video-c`, expect `WEXYogaVideoCRequested`,
   `WEXYogaVideoCMatched`, `WEXYogaVideoCPropertiesPreserved`, and
   `WEXYogaVideoCScalerPresent` all to be `Yes`;
   `IOVARendererID=17301632` (hex `0x1080080`) and
   `IOGVAScaler="Gen10"`.
   These **confirm registry activation**, not full codec stability.

### Roll back

**Simplest:** remove `-wex-yoga-video-c` from your test EFI's
`NVRAM -> Add -> 7C436110-AB2A-4BBB-A880-FE41995C9F82 -> boot-args`,
then reboot. On this C-capable Kext, absence of the flag restores default
E behavior for the two GVA properties. If you cannot boot, use the
untouched recovery EFI and restore the original WhateverXe Kext.
To disable HDMI600 or RGB8 independently, remove only their respective
flags. Never rely on the Video C boot-flag rollback as a substitute for
keeping a recovery EFI.

## Build from source

**The supported `main` RELEASE artifact is source-first and constructed
by [`.github/workflows/yoga-main.yml`](.github/workflows/yoga-main.yml).
It does not build the historical `src/` snapshot.** The workflow:

1. Checks out the *exact pinned* upstream donor, MacKernelSDK and Lilu.
2. Runs `python3 e15/tools/prepare_video_c.py Source`, which invokes
   `e13/tools/prepare_rgb8.py` and transitively E1.1/E1.0.
3. Runs the EDID/HDMI regression tests, pinned upstream test suite,
   then compiles the RELEASE Kext; archives source diff and checksums.
4. Packages a Kext test ZIP for a separate EFI. CI compilation does
   **not** prove functional macOS hardware stability.

To prepare an **exactly pinned clean donor tree** locally, from this repo
run `python3 e15/tools/prepare_video_c.py <clean-donor-directory>`;
the upstream version and source anchors are guarded. Building still
requires the pinned SDK, Lilu and the macOS build environment.

For Video C implementation, expected IORegistry values, and crash history,
see [`e15/VIDEO_C_README.md`](e15/VIDEO_C_README.md).
For HDMI/EDID exact-match limits, see
[`e13/YOGA_MAIN_RGB8_README.md`](e13/YOGA_MAIN_RGB8_README.md).

**Not included:** 4K60 SCDC/Scrambling repair, verified 120 Hz internal
eDP, Thunderbolt dock crash repair, HEVC HW encoder, or a global
VA/VPHAL NULL-pointer fix.
