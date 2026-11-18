# WhateverXe 0.8.3 Yoga LEN145-3K 120Hz — guarded experiments

## Verified baseline
Yoga Pro 14s IRH8 (82Y7), Intel i9-13900H / A7A0 rev4, macOS 26.7.1 (25G241):
the **0.8.3 + CTL2 panel bit3** build already gives 3072x1920@60, Metal 2, VRAM 1536 MB.
The original EDID contains 3072x1920@120 (775.68 MHz), but CoreGraphics reports 60Hz only.
At FB0, `IOFBTimingRange.maxPixelClock = 720 MHz`.

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

V1 and V2 are **not hardware-verified 120Hz fixes**. All native clock, link,
watermark and framebuffer validation remains in place except the narrowly
scoped, explicitly enabled clock-budget condition. `-wex-yoga-edp120-wm`
does not change EDID enumeration or configure link speed/DSC.

## Testing order and safe rollback

1. Keep an **independently bootable untouched EFI / USB** with the proven
   0.8.3+CTL2 Kext, and duplicate it for testing. Do not replace `main`
   or modify the working macOS Graphics 0.4.4 installation.
2. In the duplicate test EFI, replace **only** `EFI/OC/Kexts/WhateverXe.kext`
   with the RELEASE Kext from V1. Boot **without** eDP120 flags; confirm
   60Hz/Metal 2/1536MB first.
3. Add **only** `-wex-yoga-edp120-admit` and reboot. Do **not** select 120Hz
   yet. Read:
   ```sh
   ioreg -lw0 -p IOService | grep -E 'WEXYogaEDP120|IOFBTimingRange'
   system_profiler SPDisplaysDataType
   ```
   Also enumerate modes with `CGDisplayCopyAllDisplayModes` or the previous
   `Yoga_eDP_120Hz_Diag` command. Confirm whether **120Hz appears**.
4. If the internal pixel clock is now 800MHz but no 120Hz mode exists, stop and
   diagnose additional DisplayID/AGDC mode filters. If range remains 720MHz,
   stop and determine which `getOnlineInfo` branch is actually executed.
   Do **not** blindly enable V2 in either case.
5. If V1 shows 120Hz in the list, proceed to **link-capability diagnostics**
   before any switch. At 775.68MHz, uncompressed 8bpc demands > HBR2×4 bandwidth.
   Determine actual DPCD rate/lanes, negotiated depth and DSC before a 120Hz
   mode switch.
6. Only after that, test V2 in a separate EFI by adding
   `-wex-yoga-edp120-wm` alongside the V1 argument.
   This opt-in permits the Display13 WM bound for the existing panel pipe.
7. To roll back, remove the new arguments; for any black screen use the
   untouched independent boot EFI and restore the known-good 0.8.3+CTL2 Kext.
   No removal/reinstall of Graphics 0.4.4 is required for Kext-only rollback.

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
