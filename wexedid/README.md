# Yoga 82Y7 A7A0 HDMI-B U27P10: native EDID capability A/B

**Experimental test Kext. Not a verified fix. Always keep a bootable recovery EFI.**
The pinned WhateverXe 0.8.3 + Graphics 0.4.4 source retains existing eDP120
WM_ONLY, HDMI HPD trace, ColorTrace register reader and native color-mode audit.
No changes to main or any existing installed EFI.

## Evidence and exact planned EDID deltas

Two current U27P10 captures (2560x1440@59 and 3840x2160@30) both show
10bpc / YCbCr444 on physical DDI B, Pipe B, GCP not enabled.
The native setColorMode call reports mode=0x100 and depth=0.
The old bpc8-test/rgb8-test mode-argument methods are thus inapplicable.
CTA base in the actual live capture, not the older e13 test fixture:
extension header 02 03 40 F1, HDMI VSDB DC flags 38,
HDMI Forum 4:2:0 DC flags 03, 4:2:0 Capability Map 00 0C.
This branch uses normal EDID DDC block #2, not an all-bytes EDID override.

Experiment A: -wex-yoga-hdmi-edid-deep8
- Retain CTA YCbCr444/422 advertisement and 4:2:0 map.
- Clear HDMI VSDB DC_48, DC_36, DC_30, DC_Y444.
- Clear HDMI Forum YCbCr420 deep-colour bits 0..2.
- Recalculate the extension checksum.
- Never changes resolution timings, HDMI address or 600MHz max TMDS.
- On the observed sample, only offsets 31, 46, 127 change.

Experiment B: -wex-yoga-hdmi-edid-rgb8
- Includes Experiment A changes.
- Clears CTA feature flags for YCbCr444 and YCbCr422 (F1 -> C1).
- Clears the YCbCr420 capability map bytes, preserving block length.
- Rejects a 420-only video block when encountered.
- On the observed sample, only offsets 3, 31, 46, 63, 127 change.

These are ALTERNATIVES: never enable both. Neither is on by default.
Existing -wex-yoga-hdmi-mode-audit and -wex-yoga-hdmi-colortrace remain usable.
Unknown EDID format, checksum error, duplicate/missing expected vendor data
blocks or unqualified physical port cause no modification.
The original EDID base block (including serial) is never rewritten or
published by this experiment. The internal eDP and other monitors are excluded.

## Startup arguments

First A (replace other color-test flag; preserve all your remaining bootargs):
-wex-yoga-edp120-admit -wex-yoga-edp120-wm
-wex-yoga-hdmi-colortrace -wex-yoga-hdmi-mode-audit
-wex-yoga-hdmi-edid-deep8

Only if A does not give a stable and valid picture, in a separate reboot:
remove -wex-yoga-hdmi-edid-deep8, add -wex-yoga-hdmi-edid-rgb8.

Do not enable legacy -wex-yoga-hdmi-bpc8-test or
-wex-yoga-hdmi-rgb8-test; this branch does not depend on them.
Do not enable HDMI600, first-HPD event rewriting or EDID OS overrides.
Connect U27P10 to native laptop HDMI before cold boot; do not use TB4 dock.
Start at a known working QHD/4K30 mode; 4K60 needs separate TMDS/SCDC work.

## Verify after every boot

- nvram boot-args: confirm exactly one new test flag.
- ioreg -p IOService -l -w0 | grep -E WEXYogaHDMIEDIDAB
- Run bash collect_edid_ab.sh with decode_edid_ab.py, decode_color.py,
  decode_modes.py placed together in the same directory.
- Upload Yoga_HDMI_EDID_AB_*.zip. Include a note if colors improved,
  blacked out or continued to be magenta.
- Examine HDMI pipe bpc, YUV flag, AVI and GCP, not just EDID echo.
- EDIDAB Applied=Yes means the donor received modified EDID;
  it does NOT prove that native color mode or physical HDMI output changed.
- If no Applied=Yes, treat it as NO OP, not as proof RGB8 does not work.
- Any boot loop, display hang or unstable output: restore known-good EFI.

## Scope and risk

This is a limited experiment for one physical A7A0 / native DDI B / U27P10
and one observed CTA layout. It does not patch the macOS display driver,
force Display13 MMIO registers, or guarantee 4K60/HPD behavior.
A successful C++ compiler, x86_64 architecture and CI test are prerequisites,
not proof of field reliability.
