# Lenovo Yoga Pro 14s IRH8 (82Y7) — WhateverXe 0.8.3, 3K 120Hz

**Status (2026-11-18): V1 VERIFIED ON REAL HARDWARE at 3072×1920 @ 120.00Hz, Metal 2, 1536 MB VRAM.** This branch is the **recommended working internal-display test baseline**, but it is not a release validated for long-term sleep/wake, video codecs, external displays or dock operation.

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

- [V1 — confirmed 3K120 on Yoga](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44291923111/artifacts/14421917363) (**recommended**).
- [V2 — built only, not needed/tested on device](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44291923111/artifacts/14422950304).

V2 contains optional `-wex-yoga-edp120-wm`, a Display13 `clockFits()` two-pixel CDCLK budget adjustment. **The verified V1 success used no V2 flag.** Do not infer that WM changes, DSC or link-rate overrides were needed.

See [full reproducible research and rollback guide](wex120/README.md).

## Keep the verified 120Hz driver isolated

Work only in an independently bootable test EFI, replacing its `WhateverXe.kext` while keeping the known-good copy of the working 0.8.3 CTL2 EFI. A full motherboard sleep/resume regression and external 4K60/Thunderbolt remain unverified. Do not mix WhateverXe and NootedGreen, and do not merge this branch into the earlier 0.7.0-based `main` without a deliberate integration plan.

### Next experiment: Apple Logo boot flash

Investigate GOP/Framebuffer/WindowServer scanout handoff, keeping the working V1 unchanged. [WhateverXe issue #131](https://github.com/b00t0x/WhateverXe/issues/131) demonstrates one **different hardware family's** linear GOP versus X-tiled resource mismatch, but its reference fix is gated off with `-v`, whereas this Yoga currently boots with `-v`. The symptom is similar, **not yet a proven common root cause**; first collect A7A0-specific evidence. No “boot flash fixed” claim has been made.
