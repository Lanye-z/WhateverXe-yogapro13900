# Yoga Unified Wake V5 — Dynamic HDMI-B Framebuffer Binding

**Experimental R5 (2026-11-21)**. Derived from the pinned V4 R4 code; no change to `main`, R4, Unified RC1, macOS Graphics 0.4.4 or any installed EFI.

## Grounded hardware evidence

- Cold boot **without** HDMI followed by hot-plug: AOC U27P10 3840x2160@60 appears at **FB2/Pipe2**; HP G4 SST 1080p75 uses FB1. R4 B never enters 110 and collects only the unrelated FB1 power callbacks. On later attempts, native modeset statuses 10 and 100 alternate.
- Cold boot **with** HDMI connected: AOC uses **FB1/Pipe1**, dock uses FB2; R4 B performs multiple SCDC recovery transactions **110**. Some are followed by HDMI HPD low-high and a second native SCDC **100**, with additional visible flashes. Thus successful 110 does *not* prove the panel relit immediately.
- Fast Doze intervals around 2 seconds demonstrate that the old artificial 3-second gate was invalid; R4 already removed both it and the arbitrary 90-second gate.

## R5 change (R5-A: correctness / secure fallback)

Overlay order: pinned upstream 0.8.3 -> original V3 HDMI safe -> Unified RC1 -> V4 R2/R3/R4 -> `wexwakev5/prepare_dynamicwake_r5.py`.

1. The verified physical HDMI-B (wiring `hdmi==2`) and successful genuine AOC high-rate SCDC/CTA session establish the current HDMI FB binding. Native power observation dynamically matches the proven FB index (FB1 **or** FB2), not a fixed FB1 index.
2. The power observer records the exact native framebuffer object's identity on successful **Wake→Doze**, and requires the same object for **Doze→Wake** and for the in-callback recovery window. A dock FB1 callback cannot authorize an AOC FB2 SCDC fallback.
3. R3's user-initiated 4K60→4K30 SCDC state-reconcile eligibility now follows that same known HDMI pipe; the original same-controller/same-EDID/fresh-CTA/attempt-per-generation/high-source-bits checks all remain mandatory.
4. Power history slot 4 (zero-based index 3) now records the **actual FB index** (1 or 2). R4 32-entry callsite and 32-entry native power history remains usable; statuses 10/100/110/101 maintain the original meaning.
5. No new I2C operations, HPD pulses, hardware register writes, modeset calls, display-power hooks or timers. No edits to eDP120, Deep8, HDMI600, HP G4 SST, PLL, PHY, DBUF or WM.

**R5-B is not asserted complete:** real 110 readback and optional subsequent native 100 do not establish physical image, so do not auto-generate a second modeset or synthetic HPD without stronger evidence and a separately gated safety design. In this build the CTA/SCDC generation and single-use authorization safeguards are preserved, and the logs can differentiate immediate 110 from HPD/re-enumeration followed by 100. This is the safe implementation of the first, independently supported part of the R5 plan.

## CI and EFI

Workflow `.github/workflows/yoga-unified-wake-v5.yml` runs the existing R4 source guards *before* applying R5, R5 pure-policy unit tests, R5 generated-source safety guards, native RELEASE build, original regression suite and package checks. No CI result proves a real monitor lights.

Maintain backup EFI and reliable rollback. This build is research-only, not suitable as an unverified daily-driver replacement.

**A group** (observe only):

```text
-v keepsyms=1 -vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-hdmi2-callsite-safe -wex-yoga-hdmi2-wake-diag
```

**B group** (controlled power-cycle recovery test; backup EFI required):

```text
-v keepsyms=1 -vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-hdmi2-callsite-safe -wex-yoga-hdmi2-wake-diag -wex-yoga-hdmi2-wake-recover
```

After installing the matching R5 kext, first test A and collect one awake/Doze/wake log for cold-plug and post-boot hotplug. For B, test at most one short wake per boot, record whether each physical screen lit immediately and whether there was a flash, then collect the diagnostic ZIP without changing HDMI cables/refresh rates first.

**Important:** `status=100` or `110` means a successful native SCDC readback, not a validated link/video scanout. Three-screen black or repeated flickering warrants immediate rollback; do not disable hardware safety gates just to induce a 110.
