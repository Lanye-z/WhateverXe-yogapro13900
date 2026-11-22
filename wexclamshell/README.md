# R5-Clamshell A/B — Diagnostic only (2026-11-22)

**Starting point:** known R5-B code (independent branch `experiment/wex-0.8.3-yoga-hdmi2-wake-v5`). This branch intentionally contains **no changed kext code**, no new boot-args, and does not touch `main`, the working R5 kext, the eDP 120 Hz panel, HDMI 4K60, HP G4 SST, DBUF, WM, PLL or PHY.

## Grounded failure capture

Source: `Yoga_R5_LidDoze_20261122_152856_black.zip` uploaded by the tester.

- At 15:28:56+0800 the run was armed. Baseline `system_profiler` enumerated three active outputs: internal 3072x1920@120, AOC U27P10 3840x2160@60 on HDMI FB1/Pipe1, and dock 27B2 1920x1080@75 on FB2.
- `pmset`: 15:29:10 display off; `WindowServer` emitted `Fallback GPU Display Pipe transaction submission failed` at 15:29:11; lid-closing notifications at 15:29:13 specify `closed=1, shouldSleepWhenClosed=0`; display turned on at 15:29:29. No complete system Sleep->Wake pair was observed in this window.
- Framebuffer action: later R5 callsite records on Pipe1: `#4 533250000Hz status=110`, then `#5/#6 40000000Hz status=10`, `#7 25180000Hz status=10`; the original donor's modeset return was zero. The power observer logged exactly one native FB1 Doze and one FB1 Wake, with a matched Wake window.
- Snapshot after recovery failed: `system_profiler` enumerated only dock 27B2 at 1920x1080@60 even though the **physical** two external displays were reported black by the user. `system_profiler` alone is not proof of display illumination.
- Corroboration from other R5 logs: the same `Fallback GPU Display Pipe transaction submission failed` appears many times in general display doze/wake captures; thus that message **is not unique to the clamshell failure and cannot be attributed as its primary cause**.
- A successful SCDC status=110 confirms *SCDC readback*, **not** successful HDMI video or entire multi-output GPU display transaction.

## Critical difference to isolate

**Known-working order:** all three screens ON -> close lid -> two external screens ON -> lock, display sleep -> wake both external screens.

**Reproduced failure order:** all three screens ON -> lock -> display sleep -> close lid while displays already Doze -> wake; both external outputs black. These are different state transitions, not merely different brightness or refresh settings.

## Acquire a successful-path log, no code modification

Use existing read-only `Yoga_R5_LidDoze_ReadOnly_Diagnostic.sh` that was used successfully for the black capture; retain identical kernel, boot-args, graphics, cables, screen modes and external power.

1. With lid OPEN and three displays physically awake, run `bash ~/Downloads/Yoga_R5_LidDoze_ReadOnly_Diagnostic.sh arm` and wait for `ARM READY`.
2. **While all three still have an image**, CLOSE lid (do **not** lock or ESC before closing). Wake by external keyboard/mouse if required, and verify both external outputs show a physical picture.
3. Then LOCK and put the **two** external displays to sleep; wait approximately 10 seconds; wake by external keyboard/mouse. Avoid unplugging cables or switching Hz.
4. On the working external desktop, run `bash ~/Downloads/Yoga_R5_LidDoze_ReadOnly_Diagnostic.sh recovered`. This creates `~/Desktop/Yoga_R5_LidDoze_<timestamp>_recovered.zip`.
5. Upload the **ZIP** and note if both AOC 4K60 and dock 1080p really lit without additional flashes. Do not send only `active_path.txt`.

The monitor collects 8-second snapshots; individual transitions may fall between these. Trust timed unified logging for ordering, and compare hist arrays to state at capture. The `recovered` mode does not change hardware power state, write to NVRAM or alter Kexts.

## Diagnosis before modifying R5

Compare `pmset` events, lid-closure timestamp, `WEXYogaHDMI2CallsiteHist##` (pipe, clock, status, result, current binding), `WEXYogaHDMI2WakePowerHist##` (real FB index and state), CTA/session generation, FB0/FB1/FB2 online/modeset and any HPD or output mode changes.

Do not implement an HDMIB recovery-eligibility bypass, force an extra `LightUpTMDS` call, synthesize HPD, or reset shared GPU clocks until differences in a successful path justify it. If the dock also remains physically black with AOC gone, an HDMI-only SCDC adjustment cannot on its own be considered a complete fix.

**Safety:** perform only the known-working ordering for daily use; avoid repeating the known all-black order outside a backed-up diagnostic session with SSH access.
