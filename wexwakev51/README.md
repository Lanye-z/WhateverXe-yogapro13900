# WhateverXe R5.1 — SCDC 0x01 Native I²C Diagnostic (no behavior changes)

This is a **diagnostic-only** successor to the pinned, CI-verified R5-A dynamic HDMI-B FB binding. It is intentionally **not** a blind SCDC retry or delay patch.

## Motivation / existing real logs

On 2026-11-22, two R5-B captures recorded intermittent `status=34` on AOC U27P10 4K60 Display Sleep → Wake, for both FB1 (cold plugged) and FB2 (post-boot hotplug). The existing `YogaHDMI2::prepareSCDC` maps this to `SinkVersionReadFailed` at the first read of SCDC register `0x01`, before the source/sink configuration write.

The available `N97FBGMBusFirst*` journal includes `kIOReturnNotResponding=0xE00002ED` and GMBUS2 bit10 NAK/SATOER in native requests. **Some entries address devices other than SCDC** and the journal is not per-CALL synchronized. Thus those facts do not yet establish the exact native failure of each `status=34` event.

## Scope

Run after original V3 + Unified RC1 + V4 R4 + R5-A:

`python3 wexwakev51/prepare_scdc_trace.py Source`

Changes only the existing `YogaHDMI2Bus::send` in the already guarded native LightUpTMDS CALL-site and publishes a read-only snapshot **after the original native mode call returns**. It adds **no extra native I²C request, retry, delay, GMBUS polling, register access, HPD action or modeset**. The original short-circuit `!nativeStatus && !request.result && connected()` remains exactly equivalent. The trace is passed only if `-wex-yoga-hdmi2-wake-diag` is enabled.

Snapshot properties:

- `WEXYogaHDMI2SCDCI2CLast`
- `WEXYogaHDMI2SCDCI2CHist01..32` (bounded, keyed to the original HDMI callsite count)

Each little-endian `uint64[15]` contains:

| Index | Meaning |
|---|---|
| 0 | schema=1 |
| 1 | original CALL-site sequence |
| 2 | pipe 0..2 |
| 3 | final SCDC status (34, 100, 110, ...) |
| 4 | SCDC register (expected 1) |
| 5 | native function called? 1/0 |
| 6 | connected() was false before native I²C? 1/0 |
| 7 | native function return (raw IOReturn) |
| 8 | IOI2CRequest.result (raw IOReturn) |
| 9 | connected after I²C (0 false, 1 true, 2 unchecked because native errored) |
| 10 | framebuffer index |
| 11 | DDC bus number |
| 12 | native read started (mach_absolute_time ticks) |
| 13 | native read duration (ticks, NOT milliseconds) |
| 14 | armedPipe after the original modeset |

The public timestamp/time conversion is not attempted in kernel code; existing callsite timestamps already permit event sequencing. No extra physical state changes are made.

## Expected decision after one reproducible failure

- `nativeReturn=0xE00002ED` or nonzero `request.result`: native I²C/GMBUS transaction failure; compare contemporaneous GMBUS2 NAK/HW_RDY history without assuming display wake timing.
- `disconnectedBefore=1`: original same-connection/generation guard failed; this is not a sink read timeout.
- `nativeReturn=0, requestResult=0, connectedAfter=0`: connection/EDID generation changed during the transaction.
- A successful native read but later failure would contradict status34 and require code/trace reconciliation.

No auto retries, synthetic HPD, skipped readback, changed I2C speed, new timeout or patched source flag behavior are justified yet.

## CI and safety

The separate experimental workflow `.github/workflows/yoga-unified-wake-v51.yml` runs pinned V3/Unified/R4/R5 scripts, original R4+R5 safety tests, new R5.1 generated-source tests, 0.8.3 RELEASE/Compat and original regression suite. **CI cannot prove hardware 4K60 wakes or that screen flashes are fixed.**

Do not replace the only stable EFI. Keep Graphics 0.4.4, eDP120, SST, Deep8, HDMI600 unchanged. Test first on a separate EFI with existing A-group (no recovery), and B only with a reliable fallback. Existing `Yoga_HDMI2_DisplayWake_Diag.command` automatically captures the new IORegistry fields in `01_ioreg_full.txt` and `05_highlighted_properties.txt`.

A (diagnosis): `-wex-yoga-hdmi2-callsite-safe -wex-yoga-hdmi2-wake-diag`

B (existing bounded recovery + diagnosis): `-wex-yoga-hdmi2-callsite-safe -wex-yoga-hdmi2-wake-diag -wex-yoga-hdmi2-wake-recover`

Keep all unrelated boot-args exactly as your stable EFI. Stop immediately and roll back on multiple display failures.
