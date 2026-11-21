# WhateverXe 0.8.3 Yoga Unified RC1 — single build

**Research candidate, not yet a validated long-term release.** One 0.8.3 Kext only; no
Daily/HDMI2 dual packaging, no changes to `main`, installed macOS graphics,
or any existing EFI. Starting source is the *exact* November 21 V3 commit
`f302b39e79ad6be37b4ded52c6c89dd6e01a9142` and the pinned WhateverXe
0.8.3 / WhateverXe Graphics 0.4.4 baseline.

## What is now automatic, with original safety gates intact

| Patch | Integrated default | Existing HW and code validation |
| --- | --- | --- |
| eDP120 mode admission | ON | A7A0 / eDP DDI A; exact Tahoe 25G241 donor byte match |
| eDP120 WM_ONLY | ON | A7A0 / internal pipe 0 only |
| HDMI Deep8 EDID capability | ON | exact AOC U27P10 identity / HDMI B / valid CTA EDID |
| HDMI600 mode admission | ON | A7A0 / HDMI B / exact getOnlineInfo donor bytes |
| HP G4 USB-C SST cache mask | ON | DDI5 / DP link / native DPCD symbol and prologue match |
| HDMI2 V3 SCDC GMBUS wait + native CALL-site | **OFF until** `-wex-yoga-hdmi2-callsite-safe` | same V3 narrow opt-in and donor/lock/SCDC checks |

There is **one** Kext build and the V3 HDMI2 behavior is kept exactly unchanged.
The other five patches no longer require positive `-wex-yoga-...` flags.
This deliberate choice follows the user's agreed boot-arg cleanup screenshot.

**Important interaction**: HDMI600 is default ON, but the high-speed SCDC
path is still explicitly opt-in. Boot with HDMI2 safe omitted for conservative
4K30 operation; do not assume an automatically offered 4K60 can light up in
this configuration. The prior baseline had 4K60 cold-boot attempts and
multiple FB/HPD reconfigurations even without safe. Startup flicker and
long-term stability remain unresolved. Keep a separate verified fallback EFI.

## Minimal boot-args for this one Kext

With the user's **currently proven V3 HDMI 4K60** behavior enabled:

```text
-vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-hdmi2-callsite-safe
```

For the same Kext **without** active HDMI2 (4K30-oriented baseline), omit
only `-wex-yoga-hdmi2-callsite-safe`. No Kext change is needed. This is a
configuration choice on one build, not a second build.

No longer needed for default patch activation:
`-wex-yoga-edp120-admit`, `-wex-yoga-edp120-wm`,
`-wex-yoga-hdmi-edid-deep8`, `-wex-yoga-hdmi600`,
`-wex-yoga-tc5-sst`.

Routine diagnostics can be omitted:
`-wex-yoga-hdmi-colortrace`,
`-wex-yoga-hdmi-mode-audit`, `-wex-yoga-usbc-dpdiag`,
`tblog=577619`, `-v` and `keepsyms=1`.
These are *not removed from the driver code paths*; the first three
remain dormant unless requested. Retain a debugging EFI for detailed logs.

`-vi2c-force-polling`, `-ibtcompatbeta` and `-igfxdvmt` have **not**
been independently justified or removed here. They are unrelated to the
five source changes. Do not modify Lilu, VoodooI2C, Intel Bluetooth or
other EFI components as part of this test.

## Fail-safe opt-outs for the now-default patches

| Boot arg | Effect |
| --- | --- |
| `-wex-yoga-disable-integrated` | Turn off **all five** default-on patches (not HDMI2 V3 itself) |
| `-wex-yoga-disable-edp120-admit` | Disable eDP 720→800 MHz admission |
| `-wex-yoga-disable-edp120-wm` | Disable WM_ONLY pixel/CDCLK adjustment |
| `-wex-yoga-disable-hdmi-deep8` | Disable default AOC Deep8 restriction |
| `-wex-yoga-disable-hdmi600` | Restore unmodified HDMI clock admission |
| `-wex-yoga-disable-tc5-sst` | Do not install DDI5 SST DPCD masking |

For a full emergency rollback remove `-wex-yoga-hdmi2-callsite-safe` too
(or boot the untouched backup EFI). Never depend solely on an NVRAM
parameter for recovery from a pre-login black screen.

## Build path

`.github/workflows/yoga-unified-rc1.yml` is an adapted copy of the V3
pinned CI, preserving the original baseline tests. It performs:

1. Exact pinned WhateverXe 0.8.3 + Graphics 0.4.4 source preparation.
2. The original V3 SCDC GMBUS scope and TC-before-CALL regressions.
3. `python3 wexintegrated/prepare_unified.py Source` after V3 generation.
4. Fail-closed string/fixture/static tests, official full regression suite,
   RELEASE build, manifest and hash checks.
5. A single `Yoga-0.8.3-UNIFIED-RC1-TEST` Actions artifact.

The integration overlay changes **five boot-argument expressions only**,
not PHY/PLL, SCDC commands, GMBUS wait timing, native CALL-site or TC
ordering. It leaves the V3 active HDMI2 selection *off by default*.

## Test order (test EFI ONLY)

- Keep a separately bootable previously working EFI.
- Copy EFI and replace **only** WhateverXe.kext from a confirmed successful
  unified CI artifact. Keep WhateverXe Graphics 0.4.4, Lilu and the rest
  unchanged.
- Remove old five feature-enable args. Start with **safe OFF** and confirm
  Metal 2 / 1536 MB, internal 120 Hz, correct AOC 4K30 color, dock SST.
- Then enable `-wex-yoga-hdmi2-callsite-safe` **only if desired**, and verify
  AOC OSD 3840×2160@60, GMBUS readiness, bit4/bit0, rollback 4K30.
- Compare normal reboot flashing and test plug/unplug, display sleep/wake.
  If failed, restore previous EFI rather than guessing another delay.

**Do not merge to main or replace the daily EFI until this new build
passes real-machine regression.** GitHub 221/221 passing is not physical
screen or reliability validation.
