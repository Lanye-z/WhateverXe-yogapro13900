# Yoga A7A0 3072x1920@120 on WhateverXe 0.8.3

**Separate experimental branch.** Base: confirmed working 0.8.3 + narrow panel CTL2 bit3 exception, branch `experiment/wex-0.8.3-a7a0-ctl2`, commit `6c452313961ffd9e30fd31f291f863421d54958e`.

Measured on Yoga Pro 14s IRH8 (82Y7): internal panel 3072x1920@60 with Metal 2 / 1536 MB, full 384-byte EDID containing DisplayID 3072x1920@120 (775.68 MHz). macOS CoreGraphics reports 60Hz modes only; current `IOFBTimingRange.maxPixelClock=720MHz`.

## Plan and guardrails

1. Inspect pinned, publicly released Tahoe WhateverXe Graphics 0.4.4 framebuffer to identify the actual **720 MHz eDP mode-admission assignment**. Never assume the HDMI 300MHz branch from issue #41 is the eDP branch.
2. If a single, explainable exact native site is proven, add an opt-in, exact-image guarded panel-only mode-admission patch raising a limit to **800 MHz** (still not a hardware link change). Report patch status and prove it only targets eDP. **If there is no conclusive target, leave V1 unimplemented and report the blocker.**
3. Add a separate opt-in Display13 WM `clockFits()` two-pixels-per-CDCLK adaptation based on the measured fixes from issue #53 and LG gram Style 16, preserving other validation and not modifying the global behavior without the flag.
4. Build 0.8.3 RELEASE binaries and regression tests in GitHub Actions. First boot in an independent EFI with **no opt-in flags**; confirm 60Hz, Metal 2, then turn on only the admission flag and inspect mode enumeration, without automatically selecting 120Hz.
5. Before any 120Hz switch, measure current DPCD link rate, lane count and DSC. Uncompressed 8bpc requires more than 4-lane HBR2 capacity; HBR3 or valid DSC/other constrained mode must be demonstrated.

No system graphics package changes, EDID overrides, HDMI, Thunderbolt, HEVC or system sleep fixes in this branch.
