# WhateverXe Yoga integrated main — staged native EDID test

Target: Lenovo Yoga Pro 14s IRH8 (82Y7), i9-13900H, Intel Iris Xe A7A0,
macOS Tahoe 26.7.1 (25G241).

**Status: INTEGRATION CANDIDATE; NOT YET VALIDATED ON THE PHYSICAL YOGA.**
Do not replace the existing daily-use EFI. A successful CI build is not a
physical colour, acceleration, or 4K60 validation.

## What main now builds

- Pin \`Thatisjigen/WhateverXe\` \`acer/current\` at
  \`f7b9bf2229d323e37e8b1dfb87182f005eb7a277\`.
- Adapt the archived D1.1 **single-line** A7A0 eDP CTL2 bit-3 fix
  to that multi-output Display13 donor (E1.0).
- Include the existing opt-in \`-wex-yoga-hdmi600\` exact guarded
  300->600 MHz mode-admission patch (E1.1). It does **NOT** implement HDMI
  2.0 SCDC/Scrambling or resolve the reported 4K60 black screen.
- Include **NEW opt-in** \`-wex-yoga-rgb8\` at the already-routed native
  Display13 \`AppleIntelPort::getDDC\`-style port callback:
  \`wrapAlderLakeNPortDDC\`. After the original native DDC read succeeds,
  require all of:
  1. Raptor Lake mobile \`adlpDisplaySelected\` and Display13 existing hook;
  2. a validated selected output port with **TMDS / native HDMI** transport;
  3. EDID block 1 or 2 (the exact donor's 1-based block numbering);
  4. byte-for-byte match of the original 128-byte AOC U27P10 EDID block
     captured from the real hardware.
  Only then replace that block's 128 bytes with the **exact**
  RGB8_STRICT block that already fixed native HDMI 4K30 colour.

Because matching is exact, other monitors, altered EDID revisions, internal
eDP, USB-C DP and an HDMI dock with a different transport are unaffected.
The original EDID is returned without changes when disabled or mismatched.
The kernel header is generated from the exact documented fixture; there
are no arbitrary register writes, no CSC/Gamma patch, no changed display
clock and no runtime access to /Library/Displays.

## Distinguish build success from real success

**Do not remove the currently successful system RGB8_STRICT override before
a recovery EFI and a separate test Kext are ready.** If the macOS override
remains installed, normal colours do *not* prove the native Kext injection
worked. To validate correctly:

1. Back up both your known-good EFI and the existing
   \`/Library/Displays/Contents/Resources/Overrides/DisplayVendorID-5e3/DisplayProductID-2710\`.
2. Install only the **test** WhateverXe.kext into a *duplicate* EFI.
   Keep WhateverXe Graphics 0.4.0, installed system drivers and other
   Kexts untouched. Do not combine active WhateverXe and NootedGreen.
3. First test without the new flag, confirm eDP, Metal and 4K30 unchanged.
4. Then enable only \`-wex-yoga-rgb8\`, reboot and check:
   \`ioreg -p IOService -l -w0 | grep -E 'WEXYogaRGB8|N97FBEDID'\`.
   The RGB8Requested flag alone means nothing: look for
   \`WEXYogaRGB8Last\` with Applied=1 and block counters for both 1 and 2.
5. **Only after you have verified the native EDID DDC path is being
   replaced**, back up and temporarily remove the system override for a
   controlled test reboot. Use 4K30 first, do not force 4K60.
6. Check 4K30 colours with both Kext flag enabled and system override
   absent. If colour is wrong or display unavailable, restore the backed
   up system override and use the original EFI.
7. Record the original/native EDID, any \`N97FBEDIDBase\` / Extension,
   framebuffer status, metal, H.264 encode/decode and HEVC decode.
   Previously observed D-version video performance must not be assumed
   recovered in E without new hardware regression tests.

A 4K60 screen being detected but black does not show this EDID path is
broken. The 4K60 HDMI2.0 high-bandwidth signalling remains a separate bug.

## Build and verification

GitHub Actions workflow: \`.github/workflows/yoga-main.yml\`.
The branch/commit runs the exact pinned donor source pipeline, compiles
the production C++ helper with sanitizers, runs donor tests, builds the
release **Kext only**, packages a detailed source diff and checksums.
The workflow does not install anything.

For a local pinned source tree already checked out at the exact acer/current
revision, use \`python3 e13/tools/prepare_rgb8.py <clean-donor-dir>\`.
This internally runs the D/E and HDMI600 preparers. The generator refuses
unexpected donor hashes or anchor changes. The 256-byte sample fixture
includes the external monitor serial: do not print its raw bytes in CI
logs or public bug reports.

The repo retains the former \`patches/\` and
\`WhateverXe_A7A0_Diagnostic_0.7.0.patch\` as *historical* main diagnostics;
they are **not applied** in the new source-first build.

## Components intentionally not merged into the production driver

- D's \`-wex-a7a0-panel-only\` (blocks external displays)
- VideoToolbox BGRA->NV12 app-level workaround as a global VA fix
- HEVC hardware encode registration (not implemented)
- 4K60 SCDC/Scrambling and 120Hz eDP claims (not verified)
- Thunderbolt/USB4 dock fixes (not verified)
