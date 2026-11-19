# Yoga 82Y7 external display investigation — WM_ONLY 0.8.3

**Scope (2026-11-19):** Preserve the source-equivalent 0.8.3 WM_ONLY 3K120 build, its scoped CTL2 / 720→800 MHz eDP admission / pipe-A WM fix and Graphics 0.4.4. **This branch is diagnostic groundwork, not a repaired HDMI Kext.** Type-C DP is diagnostics-only. No source changes to IRQ, hotplug, power, port probing, TC, CDCLK, DBUF or link training; no main merge.

## Verified failure evidence

In Yoga_Display_Failure.txt, HDMI B first and last observed PortState result are zero and the opt-in trace's probe count remains one. However, cumulative B long HPD is ten, short HPD zero, promotion zero, IRQ fault zero, ProcessDE continues, and active/admitted pipes are only 0x1. The trace counts only one wrapped PortState call site and does **not** prove that the native stack never reprobed. The capture shows only the internal display online and no system sleep cycle. These facts rule out **missing every HDMI HPD edge** and the short-only promotion hypothesis, not a native connector/EDID/pipe/lifecycle failure.

## Source comparison

Pinned upstream old E donor: Thatisjigen/WhateverXe f7b9bf2229d323e37e8b1dfb87182f005eb7a277.
Pinned upstream WM_ONLY 0.8.3: b00t0x/WhateverXe f26a36880c49ea1063393d943527808c0f38feca.

* kern_display13_output_wiring.hpp and kern_display13_fb_topology.hpp: identical blob hashes.
* kern_display13_fb_irq.hpp: different. Old armDetection()/restoreHotplug() have explicit S3/HPD-only recovery; 0.8.3 instead exposes restoreAfterPowerLoss()/deferRearm(). A direct transplant is **not justified** by a failed run with no S3 and pipe A still active.
* Both versions have nativeHotplug()/nativeDPAlt() mapping. HDMI uses PCH long/short event word, TC DP Alt uses north HPD events and independent link preparation.
* The 0.8.3 eDP120 WM patch is scoped to pipe A. The native HDMI failure existed before 120Hz in field tests.

## Immediate HDMI A/B procedure

1. Preserve independent bootable recovery EFI; do not replace the running Kext or flip power registers.
2. Use the existing 0.8.3 HDMI Trace Kext (optional trace flag) for **observation only**, keeping other Kexts and boot flags fixed. Boot with HDMI unplugged.
3. Run `bash wexexternal/collect.sh hdmi_before`. Plug one native HDMI screen, preferably 1080p60, do not involve a dock. Run `bash wexexternal/collect.sh hdmi_after`.
4. Repeat **separately** for immediate vs delayed first insertion; compare count deltas, final event word, IRQ ready/fault, controller topology and online displays.
5. If BLong increases but monitor remains absent, the next Kext must instrument **the return from native ProcessDE, PortState, modeset/EDID and Pipe admission** (not rewrite HPD). If BLong does not increase, inspect IRQ/power enable/readback and timing first. No synthetic long HPD or forced port reset until a concrete failed branch is observed.

## Type-C DP — observe only

Run before/after snapshots with labels `typec_before` and `typec_after` for one device. Record whether the connection is a direct USB-C DP Alt Mode or TB4 dock; the latter may not have native TB tunnel support (system profiler previously reported no Thunderbolt/USB4 drivers). Do not infer one transport from the other.

## Acceptance gates for any future patch

HDMI after panel-only cold boot, immediate and delayed first plug, then repeat unplug/replug; no regression to internal 3K120 Metal or restart. Only after HDMI is stable, separately validate Type-C/DP. No changes to main before repeated hardware verification.
