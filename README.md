# Yoga 82Y7 / A7A0 — 0.8.3 WM_ONLY + multi-display bring-up audit

**2026-11-18 STATUS: READ-ONLY PORT-QUALIFICATION EXPERIMENT, NOT A VERIFIED MULTI-MONITOR REPAIR.**

**CI passed:** [GitHub Actions run 44327816796](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44327816796) completed official 0.8.3 tests, RELEASE compilation, compatibility checks and test Kext packaging. [Download multi-display audit TEST Kext](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44327816796/artifacts/14438526678). This is **not** proof that an external display works; it adds only opt-in read-only port telemetry and retains WM_ONLY/V2 behavior.


This branch is based on the real-device-verified **WM_ONLY** 3K120 variant,
which is source-identical to the original 0.8.3 eDP120 V2 patch generator.
It includes **only one additional optional boot argument,
`-wex-yoga-multi-audit`, which publishes non-mutating Display13
board-wiring and hook-readiness evidence**. It does not claim to make a
previously unrecognized external display work.

## Why a blind E1.0 transplant would be misleading

A source comparison of the archived E1.0's pinned
`Thatisjigen/WhateverXe:acer/current` (SHA `f7b9bf2229d323e37e8b1dfb87182f005eb7a277`)
and official upstream 0.8.3
(`f26a36880c49ea1063393d943527808c0f38feca`) found:

- `display13BoardWiring()` selects physical mobile VBT ports **identically**
  in both; the core `kern_display13_output_wiring.hpp` and
  `kern_display13_fb_topology.hpp` have **identical Git blob SHA**.
- Both versions already contain `Display13FBTopology::multiOutputWiring`,
  separate display pipes and shared clock/DBUF/IRQ/hotplug paths.
- E1.0's unique modification on top of `acer/current` was the **eDP
  CTL2 bit-3** exception. WM_ONLY already includes that fix.
- E1.1's **HDMI 300→600MHz** and E1.2's RGB8 were **separate experiments**,
  not the basic multiple-display implementation. Neither is included here.
- 0.8.3 has changed various IRQ/lifecycle details compared with
  `acer/current`; replacing its `kern_xe.cpp` or IRQ header with the
  older E1.0 file would regress newer power/pipe management.

A 2026-11-18 saved `Yoga_EDP120_V1.zip` IORegistry capture on this exact
Yoga reports `N97NativeBootConnector=[1,1,0,1,2,0]` (VBT HDMI mask 0x2),
`XELPSharedProbeBound=Yes`, `N97FBTopologyHooksReady=Yes`,
`N97FBOutputHooksReady=Yes`, and `WEXDisplay13TCHooksReady=Yes`.
`N97FBConnectorPolicy` lists the native eDP, a DDI B HDMI connector, and
DDI TC1–4 port records. **Those are port declarations and route
preconditions, not proof of a working hotplug, trained DP link or external
display scanout.**

## Opt-in evidence and boot arguments

Leave the previously working flags in place:

```text
-v keepsyms=1 -vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-edp120-admit -wex-yoga-edp120-wm
```

For the **new, independently bootable test EFI only**, append:

```text
-wex-yoga-multi-audit
```

Boot first without connecting an external display, and verify the same
120Hz + Metal 2 / 1536MB. Then connect a single display by **native HDMI at
1080p60 or 4K30**, not 4K60, and do not involve the Thunderbolt dock initially
(it has a separate previously observed stability issue).

Collect a read-only snapshot both before and after plugging the monitor.
Use `wexmulti/collect_external.sh` while logged into macOS, once without
external monitor, then again while connected.

The new properties are arrays of 32-bit little-endian words:

- `WEXYogaMultiWiring`: [schema=1, valid, described, selected, panel,
  hdmi, dp, typeC, hotplug, links]
- `WEXYogaMultiHooks`: [schema=1, topology, output, TC hooks, TC probe,
  DP-alt probe, AUX, SST, IRQ, CDCLK hook, WM hooks, DBUF hooks]

The script captures `N97FBPortProbe*`, `N97FBConnectorPolicy`,
displayed mode/EDID, and recent relevant WindowServer/graphics messages.
It does not modify the machine.

**The missing behavior cannot be correctly patched until the physical
external-monitor failure is classified**: no EDID, HPD, invalid port/TC
ownership, failed AUX/link training, no display pipe, or output blanking.
This is a preparatory compatibility test build, not a claim that the
current 0.8.3 driver suddenly supports more screens.

## Recovery

Never overwrite the existing successful 3K120 WM_ONLY EFI.
Use an independently bootable clone; the only Kext change is the optional
read-only probe. If the display goes black, restore the original WM_ONLY
Kext and boot args using the untouched backup EFI. Do not enable
`-wex-yoga-hdmi600`, RGB8, DSC, eDP keep, Gate retry or panel admission
modifications in this test.

## Source / build

Source is pinned to official 0.8.3 and Graphics 0.4.4 donor (exact SHA256
`115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`).
The workflow `.github/workflows/yoga-wex083-multidisplay-audit.yml` runs
official tests, builds RELEASE and packages code diffs. The existing V1,
V2, WM_ONLY, main and EFI files are untouched.
