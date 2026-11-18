# Yoga Pro 14s IRH8 — Apple Logo flash research, based on proven 3K120 V1

**STATUS: DIAGNOSTIC ONLY (2026-11-18).** No boot-flash fix is claimed or installed. The **working 0.8.3 3K120 V1 Kext is unchanged** in this branch: the modifications are research documentation, an offline early-GOP register decoder and a *read-only* GitHub Actions binary/source audit.

## What was confirmed

- The original [V1 3K120 experiment](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edp120) is real-hardware verified at **3072×1920@120.00Hz, Metal 2, 1536 MB**.
- The Apple Logo glitches for under one second during startup, even without the 800 MHz option (smaller extent). The boot artifact is unresolved.
- The saved IORegistry `N97Display13Boot` record proves **firmware/GOP LINEAR scanout** on pipe A: `PLANE_CTL=0x94000008`, `PLANE_STRIDE=0xC0` (12,288 bytes/row), `PLANE_SURF=0`, native 3072×1920.
- Issue [#131](https://github.com/b00t0x/WhateverXe/issues/131) found a later LINEAR-GOP vs X-tiled resource mismatch on another Intel backend (A78B), but the user's actual Yoga **A7A0 and `-v` boot** have not been proven to exhibit the same later defect.
- [Source audit run 44300608445](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44300608445) **passed**; exact Graphics 0.4.4 Tahoe accelerator has `IGAccelDisplayPipe::initFramebufferResource@0x7F160` and `initResourceInfo@0x7EE9A`, as referenced by #131. This confirms relevant code exists, **not** that the runtime bug is the same.

## First safe A/B test

In a *duplicate test EFI only*, remove **exactly the standalone `-v`** from your current boot args; keep `-vi2c-force-polling`, all graphics arguments, the V1 120Hz Kext, and `-wex-yoga-edp120-admit` unchanged. Compare whether the short Apple Logo flash disappears, changes shape, or remains. A slow-motion phone recording can distinguish repeated/tiled logos from a normal mode-reset blink. Do not mistake a cleaner boot animation for proof that the buffer/resource mismatch is corrected.

For the register decoder, reproducibility, exact donor audit and **rollback precautions**, see [wexboot/README.md](wexboot/README.md).

No changes have been made to `main`, Graphics installation, HDMI, Thunderbolt, EDID, 120Hz admission, WM, or physical eDP programming in this boot-logo branch.
