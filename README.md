# Lenovo Yoga Pro 14s IRH8 (82Y7) — WhateverXe 0.8.3, 3K 120Hz

**Historical V1 status (2026-11-18):** The admission-only V1 successfully displayed **3072×1920 @ 120Hz**, pixel clock 775.69MHz, Metal 2 / 1536MB, after a *desktop* mode change. However, **rebooting with 120Hz saved repeatedly black-screened**, whether `-v` was present or not. V1 is **not** the recommended reboot-safe build.

**Follow-on WM_ONLY (source-equivalent to the original V2) has now passed one real reboot directly into 120Hz.** After that successful boot the Yoga reported `WEXYogaEDP120WMEnabled=Yes`, admission status 4, `IOFBCurrentPixelClock=775690000`, 120.00Hz, Metal 2 and 1536MB. The relevant *tested* binary is [WM_ONLY from the bootfix branch](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44315637323/artifacts/14431873939), **not this branch's V1 Kext**. The original separately compiled V2 archive contains the same source changes but was not separately tested. Repeated cold/warm boots, doze/wake and longer-term stability remain **pending** while the user uses the machine normally.

The short Apple Logo display glitch is still unresolved, but its investigation is **deferred**. Keep a separate verified 60Hz recovery EFI. No eDP Keep, SetupTimings, DSC, #102 gate retry, #104 deferred-clock/panel-admission or #131 tiling patch is needed in the successful WM_ONLY test.

## Tested configuration

| Item | Actual Yoga test |
| --- | --- |
| Device | Yoga Pro 14s IRH8 (82Y7), i9-13900H, Intel 8086:A7A0 rev 04 |
| OS / graphics | macOS 26.7.1 (25G241), WhateverXe 0.8.3 + Graphics 0.4.4 + tested CTL2 panel bit-3 exception |
| Internal eDP panel | Lenovo LEN145-3K, native 3072×1920 |
| V1 flag | `-wex-yoga-edp120-admit` |
| Scope and runtime status | `WEXYogaEDP120Scoped=Yes`, `Requested=Yes`, `Ready=Yes`, `Status=4` |
| Native framebuffer max pixel clock | **720 MHz → 800 MHz** (only internal FB0; other FBs remain 720 MHz) |
| Actual 120Hz state | `system_profiler: UI Looks like 1536×960 @ 120.00Hz`; CoreGraphics `refreshRate=120.0`; `IOFBCurrentPixelClock=775690000` |
| Acceleration | **1536 MB / Metal 2** verified after switching to 120Hz |
| 60Hz fallback | Still available from Displays settings |
| Known display artifact | **Brief (<1 s) Apple-logo-to-login flash / garbling** on boot; also observed without eDP120 flag at smaller extent; cause and repair not verified |

The V1 result is **real system-level 120Hz evidence**, not just a visible mode menu. It is not an instrument-measured scan rate and does not establish complete eDP link / DSC / HBR3 negotiation or long-term reliability.

## Downloads and CI

Both V1 and V2 passed official 0.8.3 source tests and RELEASE compile in
[GitHub Actions run 44291923111](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44291923111).

- [V1 — desktop 120Hz proven, but reboot into saved 120Hz black-screened](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44291923111/artifacts/14421917363) (**not recommended for daily 3K120**).
- [Original V2 — same patch logic as successful WM_ONLY; original archive not independently tested](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44291923111/artifacts/14422950304).

V2 adds opt-in `-wex-yoga-edp120-wm` to the V1 admission fix. **One successful reboot directly into 120Hz occurred on source-equivalent WM_ONLY with that WM flag enabled**, strongly indicating the additional clock/WM correction matters at startup. Do not infer that DSC, eDP retraining or Gate retry was enabled. [Actual tested WM_ONLY artifact](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44315637323/artifacts/14431873939).

See [full reproducible research and rollback guide](wex120/README.md).

## Keep the successful WM_ONLY test isolated

Work only in an independently bootable test EFI, replacing its `WhateverXe.kext` while keeping the known-good copy of the 0.8.3 CTL2 60Hz recovery EFI. A full motherboard sleep/resume regression and external 4K60/Thunderbolt remain unverified. Do not mix WhateverXe and NootedGreen, and do not merge this branch into the earlier 0.7.0-based `main` without a deliberate integration plan.

### Deferred: Apple Logo boot flash

No further active investigation is planned while the user observes WM_ONLY in daily use. If resumed later, investigate GOP/Framebuffer/WindowServer scanout handoff in a separate branch, without changing the WM_ONLY baseline. [WhateverXe issue #131](https://github.com/b00t0x/WhateverXe/issues/131) demonstrates one **different hardware family's** linear GOP versus X-tiled resource mismatch, but its reference fix is gated off with `-v`, whereas this Yoga currently boots with `-v`. The symptom is similar, **not yet a proven common root cause**; first collect A7A0-specific evidence. No “boot flash fixed” claim has been made.
