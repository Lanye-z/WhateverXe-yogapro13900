# Yoga 82Y7 / A7A0 / U27P10 — native HDMI color policy experiments

**EXPERIMENTAL. Not a validated picture fix. Use independent recovery/test EFI.**
Base is *pinned* official WhateverXe 0.8.3 + Graphics 0.4.4 with existing
WM_ONLY/V2 internal 3K120, HDMI HPD tracing and successful ColorTrace sampler.
None of these existing paths is changed; default boot behaviour is unchanged.

## Evidence behind this work

At native HDMI **4K30**, U27P10 ColorTrace reported:
- physical pipe B / DDI B, TRANS_DDI_FUNC_CTL = 0x90130200, **10 bpc**
- PIPE_MISC = 0x01800830, **YCbCr / 10 bpc**
- VIDEO_DIP_CTL = 0x00001100, AVI enabled and GCP disabled
- Plane XRGB8888, framebuffer ARGB8888.
The working **27B2** was observed at 1080p75 but has **not** yet been sampled
with the new physical register tracer. Both monitors' DDC/EDID reads succeed.

Issue #74 (ADL-H) changed native DDC EDID to recover a similar picture.
Issue #120 (TGL-H35) showed a forced external 8 bpc workaround, but both
were on different paths. This branch does NOT modify EDID, CSC or MMIO
register writes and does not assume those reported fixes are portable.

## Control flags

Keep -wex-yoga-edp120-admit, -wex-yoga-edp120-wm,
-wex-yoga-hdmi-colortrace and their normal unrelated boot arguments.

**First, use only**
  -wex-yoga-hdmi-mode-audit

This hooks native AppleIntelFramebufferController::setColorMode and records
its actual input arguments: native 'mode' and 'depth', associated DDI/pipe,
and whether the A7A0/U27P10 qualification was satisfied.

The two MUTUALLY EXCLUSIVE flags below are for a later, explicit,
recoverable experiment. Do not enable either until mode-audit data has been
reviewed, especially the donor's numeric argument semantics:
  -wex-yoga-hdmi-bpc8-test
  -wex-yoga-hdmi-rgb8-test

Both target only: real A7A0 scoped WEX, HDMI DDI B, physical native
display path/FB association and exact EDID vendor 05E3/product 2710.
An unknown depth encoding, dual-test flags or incomplete path qualification
causes **no change**. These test flags still record mode calls.

- bpc8-test: leaves native mode argument alone and changes numeric
  10 -> 8 or 30 -> 24 (if native depth has the corresponding units).
- rgb8-test: the same depth experiment, plus native mode -> 1.
  **This is a test hypothesis from a related TGL/RPL-S report, not a proven
  AppleIntelTGLFramebuffer/A7A0 enum mapping.**

These only alter native *call arguments* before the donor runs; they never
manually write PIPE_MISC/TRANS_DDI_FUNC_CTL/AVI/GCP/clock. This is a much
less invasive location than changing registers after mode setup. However,
it has NOT been shown that all the color/clock calculation happens downstream
of setColorMode; ColorTrace readback MUST verify real output consistency.
Compilation cannot prove the right numeric call semantics.

## First A/B (passive) capture procedure

Preserve your currently working daily EFI. Do not overwrite it.
Only when CI is green, use the new RELEASE Kext in a separate test EFI,
retaining WhateverXe Graphics 0.4.4.

1. Connect U27P10 on **native laptop HDMI before boot**, no TB4 dock.
   Boot with -wex-yoga-hdmi-mode-audit and -wex-yoga-hdmi-colortrace.
2. Confirm -wex-yoga-hdmi-mode-audit in nvram boot-args.
3. Confirm WEXYogaHDMIColorModeHookReady = Yes in ioreg -p IOService -l -w0.
   If false/missing, stop; do not use policy flags.
4. Run bash collect_policy.sh from the extracted test Artifact directory.
5. For a directly comparable normal control, boot with 27B2 before startup
   and run the SAME script. Return the two generated Yoga_HDMI_Mode_*.zip.

If the new hook is installed but there are no qualifying U27P10 mode calls,
test an ordinary mode change once at 4K30, then collect again. Do not hotplug
during the actual dump, and do not test 4K60 at this stage.

If mode/depth call arguments demonstrate safe, specific semantics, then try
BPC8 in an independent EFI first, RGB8 separately. After EACH change, read
back the live port BPC/YUV, transcoder BPC, AVI and GCP. "Patch applied"
alone never means the picture is fixed or the output protocol is valid.
An inconsistent output is an immediate failure; restore the daily EFI.

## Caveats

- Even read-only hooks can alter timing on untested software.
- IORegistry native-call trace is a ring: only most recent 24 records.
- This is a staged **research/test implementation**, not a permanent
  driver-side color fix.
- 4K60 TMDS/SCDC and first-late-hotplug issues are different experiments.
- No system EDID override, original main, successful WM_ONLY or installed
  user EFI is modified by this branch.
