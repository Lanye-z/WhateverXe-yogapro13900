# Yoga Pro 14s IRH8 (82Y7) — WhateverXe 0.8.3, 3K120 WM boot recovery

**Status — 2026-11-18: WM_ONLY (source-equivalent to V2) passed one real-device reboot with the previously selected 3072×1920 @ 120Hz mode restored; 775.69MHz pixel clock, Metal 2 and 1536MB verified AFTER that reboot.** The original V1 admission-only test could enter 120Hz from the desktop but repeatedly booted to black with the high-refresh mode saved.

**This is a promising candidate, NOT a long-term stable release.** Repeated warm/cold boots, display sleep/wake and full system sleep, external outputs and dock are **not yet validated**. The user is using the current driver normally before providing further stability results. A brief (<1s) Apple Logo flash remains visible; investigation is **deferred**, not fixed. No new unrelated patches should be added at this stage.

## Exact real-hardware evidence

| Evidence after the successful WM_ONLY reboot | Result |
| --- | --- |
| Machine | Lenovo Yoga Pro 14s IRH8, i9-13900H, Intel 8086:A7A0 rev 04, macOS 26.7.1 (25G241), Graphics 0.4.4 |
| Display | Native 3072×1920 eDP, `UI Looks like 1536×960 @ 120.00Hz` |
| `IOFBCurrentPixelClock` | **775690000** |
| Hardware acceleration | **1536MB VRAM / Metal 2** |
| `WEXYogaEDP120Scoped` | Yes |
| `WEXYogaEDP120AdmissionRequested / AdmissionReady` | Yes / Yes |
| `WEXYogaEDP120AdmissionStatus` | **4** |
| `WEXYogaEDP120WMEnabled` | **Yes** |

This demonstrates one successful **system-level** reboot and 120Hz timing, not a photodiode measurement, repeated-start stability proof or proof of the exclusive root cause. The earlier V1 tests confirmed the 800MHz scoped admission fix; the additional WM `clockFits()` change is strongly implicated in the successful boot A/B.

## Which build to use

- **WM_ONLY — real-device-verified candidate**: [CI artifact](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44315637323/artifacts/14431873939). Implements V1 CTL2 bit-3 and scoped eDP `getOnlineInfo` 720→800MHz, plus the scoped 2-pixels/CDCLK Display13 WM check when enabled.
- **WM_GATE — CI-only, not hardware tested and not currently needed**: [separate artifact](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44315637323/artifacts/14431804529). Adds optional WorkLoop gate retry from upstream issue #102. It was **not present** in the successful WM_ONLY reboot.

[CI run 44315637323](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44315637323) passed the official 0.8.3 regression suite, RELEASE build and compatibility checks for both packages. **WM_ONLY uses the same source patching logic as the earlier V2 `wex120/prepare_120.py` variant.** The separately compiled original V2 archive was not itself tested on the physical machine; compiled binaries need not be byte-identical.

**Not included in WM_ONLY:** eDP Keep, SetupTimings workarounds, DSC changes, issue #102 gate retry, issue #104 deferred-clock or panel-admission modifications, issue #131 GOP/tiling flash fix, HDMI/Thunderbolt repair.

## Active working configuration

```text
-v keepsyms=1 -vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-edp120-admit -wex-yoga-edp120-wm
```

Do not add `-wex-yoga-edp120-gateretry` or substitute WM_GATE on this successful setup. The two 120Hz flags default off on installations that do not request them.

## Safety and next steps

Keep an independently bootable, untouched 60Hz CTL2 recovery EFI and do not merge the 0.8.3 experiments into the older 0.7.0-based `main` without deliberate integration. **No further forced stress testing is requested now.** In ordinary use, monitor accidental black screens, screen doze recovery, brightness and reboot stability, then update this README only when new device data arrive.

The original V1 cold-restart failure has logs of repeated WindowServer `Fallback GPU Display Pipe transaction submission failed` (one boot also lacked the error flood). The successful WM_ONLY reboot is strong evidence of the needed clock/WM budget correction, but no failed-run hardware state directly proved `clockFits()` was the only blocker.

For exact source patching, safeguards and CI, see [wexbootfix/README.md](wexbootfix/README.md).
