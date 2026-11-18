# WhateverXe 0.8.3 Yoga LEN145-3K 120Hz — V1 verified

**V1 HISTORIC REAL-HARDWARE RESULT (2026-11-18):** 3072×1920@120Hz, 775.69MHz, Metal 2 / 1536MB after desktop switching; **NOT reboot-safe** when 120Hz is saved: black screen after restart (with or without `-v`). **WM_ONLY, which applies the exact same source patch logic as this branch's V2 variant, has since succeeded on ONE reboot directly into 3K120**. Its post-reboot IORegistry and `system_profiler` reconfirmed `WEXYogaEDP120WMEnabled=Yes`, admission status 4, 775690000Hz, 120.00Hz and Metal 2 / 1536MB. Prefer the [actually tested WM_ONLY artifact](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44315637323/artifacts/14431873939). The original V2 binary was built separately but not separately tested. Stability over multiple boots, cold starts, display/system sleep and long-term use is still unverified. The brief boot-logo flash remains unresolved and its investigation has been intentionally paused.

## Real hardware test on the Yoga

- Hardware: Yoga Pro 14s IRH8 (82Y7), i9-13900H / A7A0 rev 04, LEN145-3K internal eDP; macOS 26.7.1 (25G241).
- Stack: official WhateverXe 0.8.3 + CTL2 panel bit 3 + V1 eDP admission opt-in; installed Graphics 0.4.4.
- **Runtime patch proves active**: `WEXYogaEDP120Scoped=Yes`, `WEXYogaEDP120AdmissionRequested=Yes`, `WEXYogaEDP120AdmissionReady=Yes`, `WEXYogaEDP120AdmissionStatus=4`.
- FB0 `IOFBTimingRange.maxPixelClock=800000000` (was 720000000); other framebuffer instances stayed at 720 MHz.
- macOS displays offered both 60 and 120 Hz. User selected 120 and the screen was immediately normal, without black-screen mode switch.
- `system_profiler SPDisplaysDataType`: `UI Looks like: 1536 x 960 @ 120.00Hz`, native 3072×1920, Metal 2, 1536 MB.
- `IOFBCurrentPixelClock=775690000`, close to DisplayID's 775.68 MHz. CoreGraphics `CGDisplayCopyDisplayMode(...).refreshRate=120.0`.
- This is system/driver-level proof of 120Hz timing, not external panel photodiode verification. Current HBR/DSC negotiation has not been captured.
- Known issue: a subsecond garbled Apple Logo flash during early boot (sometimes stronger with admission flag; baseline can also flash). It remains **unresolved and under separate investigation**.

## Version selection — current evidence

- **V1**: [original CI artifact](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44291923111/artifacts/14421917363). 120Hz desktop mode works but saved-120Hz restart repeatedly **black-screened**; not recommended as a daily high-refresh build.
- **Original V2**: [original CI artifact](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44291923111/artifacts/14422950304). Adds opt-in WM two-pixels/CDCLK correction to V1; built successfully but original archive itself was **not separately tested** on Yoga.
- **WM_ONLY**: [tested CI artifact](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44315637323/artifacts/14431873939), from [bootfix branch](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edp120-bootfix). The `WM_ONLY` patch generator calls the same `prepare(..., "V2")` used for original V2. Hardware confirmed **one successful boot** restoring saved 120Hz; post-reboot 775.69MHz, Metal 2 and 1536MB.
- **WM_GATE**: [separate CI-only candidate](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44315637323/artifacts/14431804529). WorkLoop Gate retry was **not** present in the successful WM_ONLY setup; not presently needed or hardware-tested.

## Original baseline diagnosis (now resolved by V1)

Original 0.8.3 + CTL2 ran 3072×1920@60, Metal 2 / 1536 MB. Full 384-byte EDID contained a 775.68 MHz DisplayID 120Hz mode, but macOS originally enumerated only 60 Hz and internal `IOFBTimingRange.maxPixelClock` was 720 MHz. The V1 scoped native `getOnlineInfo` patch raises the relevant eDP limit to 800 MHz. **This is the demonstrated mode-admission fix on this Yoga.**

## Reproducible donor proof
Built against the **exact official 0.8.3** commit f26a368.
The installed Tahoe Graphics 0.4.4 donor is verified against public payload SHA256
`115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`,
`AppleIntelFramebuffer::getOnlineInfo` at offset 0x2E232.

The native donor contains 3 separate 720MHz assignments. This V1 runtime patch
**only alters the eDP-specific `getOnlineInfo` branch at 0x2E58F**, inside a
byte-for-byte validated 31-byte instruction window at 0x2E583. The general
720MHz default at 0x2A123, the unrelated port/DPCD 720MHz branch at 0x2E90D,
and the HDMI 300MHz assignment at 0x2E779 are unchanged. The experimental
replacement is **800MHz**. If the eDP branch is not taken for this panel, the
range may **remain 720MHz**: that outcome is diagnostic, not a reason to
change every occurrence blindly. No native driver file on disk is edited.

## Independent variants

| Build | Boot flag | Behavior |
| --- | --- | --- |
| V1 | `-wex-yoga-edp120-admit` | eDP getOnlineInfo 720->800MHz, only when physical A7A0 + VBT eDP on Combo A |
| V2 | `-wex-yoga-edp120-admit` | same mode admission change as V1 |
| V2 | `-wex-yoga-edp120-wm` | additionally allow 2 pixels per CDCLK only on verified Display13 internal boot pipe 0 |

**Both flags default OFF**, so both packages should retain the proven CTL2
baseline after replacing only `WhateverXe.kext`.

**V1's 120Hz desktop mode was verified but its saved-120Hz reboot failed; source-equivalent WM_ONLY has one verified successful reboot.** All native clock, link,
watermark and framebuffer validation remains in place except the narrowly
scoped, explicitly enabled clock-budget condition. `-wex-yoga-edp120-wm`
does not change EDID enumeration or configure link speed/DSC.

## Current usage and safe rollback (no new tests requested)

The device is presently using the source-equivalent V2 **WM_ONLY** build with
`-wex-yoga-edp120-admit -wex-yoga-edp120-wm` (and its existing working
boot parameters). The user will report results after ordinary use. Do not
replace WM_ONLY with WM_GATE, merge it into the older `main`, or add #102/#104
changes without new evidence. Maintain an independently bootable CTL2-only
60Hz recovery EFI and preserve current Graphics 0.4.4. If a boot fails, use
that recovery EFI or disable `-wex-yoga-edp120-admit` to exclude the
120Hz mode. No Graphics reinstall or NVRAM reset should be necessary
for a Kext-only rollback.

## Status properties
`WEXYogaEDP120Scoped` means a physical A7A0 with VBT eDP DDI A was found.
`WEXYogaEDP120AdmissionRequested`, `WEXYogaEDP120AdmissionReady` and
`WEXYogaEDP120AdmissionStatus` describe the **in-memory instruction patch**:
0=off, 1=not scoped, 2=exact donor/symbol mismatch, 3=patch write failed,
4=installed. The V2 `WEXYogaEDP120WMEnabled` property describes opt-in
two-pixels-per-CDCLK mode on internal boot pipe0.

## Not changed
No HDMI, USB-C, Thunderbolt, HEVC, HDR, OLED brightness, sleep, DSC override,
EDID replacement, automatic 120Hz selection or macOS Graphics binary files.
