# R5-Clamshell — opt-in lid-transition guard for cached HDMI 4K60 wake

**EXPERIMENTAL. This is not yet a verified fix for the three-displays-black problem.**

## Evidence from the 2026-11-22 15:28:56 black-state capture

- Before: FB0 eDP 3072x1920@120, FB1 AOC 4K60, FB2 dock 1080p75.
- Display Sleep at 15:29:10; `AppleClamshellState` changes from No to Yes by 15:29:13.
- Display Wake notification at 15:29:29; R5 caches HDMI native FB1 Doze->Wake and performs `status=110` at 15:29:31.
- WindowServer then recreates a stale/invalid multi-display system state, AOC goes offline; subsequent native HDMI calls have low-mode clocks and `status=10` (no fresh current CTA).
- Black snapshot shows only dock 27B2 at 1080p60 is logically online, but physically not lit.
- No evidence of a complete system sleep in this window. A correct SCDC readback is **not** proof that the display has rendered an image.

**Hypothesis, not established cause:** cached wake qualification from the *open-lid three-display* configuration may run before macOS has rebuilt the *closed-lid two-display* configuration.

## Exact change

Apply after pinned R5-A:

```sh
python3 wexclamshell/prepare_clamshell_guard.py Source
```

New optional boot argument: `-wex-yoga-hdmi2-clamshell-guard`. Only active when the existing `-wex-yoga-hdmi2-wake-recover` is also enabled.

- When an already proven HDMI-B framebuffer completes its native Wake(2)->Doze(1) transition, sample IOPMrootDomain `AppleClamshellState` and store a tri-state lid epoch: 0=open, 1=closed, 2=unknown.
- On the matching native Doze(1)->Wake(2) callback, sample it again **before** the original native SetPowerState. An unchanged and known lid permits normal R5 wake eligibility. Changed or unknown lid denies only the **optional cached SCDC/CTA restoration** during that native power callback; the unchanged original native modeset still executes. The same-lid state also prevents stale low-mode recovery eligibility on changed-lid transitions.
- Do not change the already verified FB1/FB2 dynamic identity guards, current-generation EDID/CTA checks, native SCDC `0x01` readback, HDCP, HPD, PLL, PHY, DBUF, WM, DP/SST, 120Hz internal panel, WindowServer or physical panel power.
- No new native hooks, I2C calls, timers, delays, HPD pulses or forced modesets.
- The guard is **disabled by default**. Existing R5 is byte-for-byte equivalent in function when the new argument is absent, besides the added dormant code.
- The diagnostic-only properties `WEXYogaHDMI2ClamshellGuardEnabled`, `WEXYogaHDMI2ClamshellLast` and 32-slot `WEXYogaHDMI2ClamshellHistNN` record what the guarded R5 power callback actually did when R5 diagnostics and guard are both active.

Clamshell history: 11 little-endian uint64 values:
`[schema1, seq, mach_ticks, FBindex, previousPower, targetPower, nativeResult, lidAtDoze, lidAtWake, lidSame, cachedWakeWindowOpened]`.

## Testing safely

A usable backup EFI, SSH and/or remote access are mandatory for this experiment. Do not modify the stable R5-B EFI in place.

**Control R5-B, as tested**:
```text
-vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-hdmi2-callsite-safe -wex-yoga-hdmi2-wake-diag -wex-yoga-hdmi2-wake-recover
```

**R5-Clamshell experimental treatment**: same arguments plus
`-wex-yoga-hdmi2-clamshell-guard`. Retain any other existing args unchanged. Do not re-add verbose `-v` unless intentionally debugging.

Recommended staged tests, stop after failure:
1. Cold boot, all three screens; verify 4K60+1080p+eDP120.
2. With lid OPEN, Display Sleep/Wake once. Existing `110` should still be permitted.
3. Close lid while displays are already active, use stable external two-screen wake once. `110` should still be permitted if lid was closed before Doze.
4. Only on the separate test EFI with reliable remote access, attempt the prior failing ordering once: three-display Doze -> lid closes -> external wake. `WEXYogaHDMI2ClamshellLast` should record 0->1, lidSame=0 and no cached 110 in that wake window.

A black screen in step 4 does **not** mean the guard is incorrectly installed; it means the root problem also involves the native display topology/WindowServer. Collect the existing LidDoze black diagnostic without switching modes first. Never loosen the current CTA/EDID identity check or force an HPD to make a passing test.

Rollback: revert only the experimental WhateverXe.kext and remove this one boot arg. Baseline R5-B is unchanged on its own branch.
