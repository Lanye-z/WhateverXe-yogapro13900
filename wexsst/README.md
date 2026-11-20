# Yoga 82Y7 / WhateverXe 0.8.3: USB-C DDI5 SST compatibility

## Purpose and boundaries

Restore HP Thunderbolt Dock G4 display output in USB-C DP Alt Mode compatibility mode. This is **SST single-stream compatibility**, not native MST multi-stream support. Two displays behind the dock may mirror one SST stream; they are not independent desktops.

Source chain (all fixed):
- Official WhateverXe 0.8.3 commit: f26a36880c49ea1063393d943527808c0f38feca.
- Existing Yoga source overlay: wexdpdiag/prepare.py -> wex600/prepare_hdmi600_observe.py -> wexedid/prepare_edid_ab.py. Includes the eDP120 WM_ONLY, HDMI Deep8/HDMI600 and existing USB-C DDI5 diagnostics.
- EFI uploaded on 2026-11-20: WhateverXe executable SHA-256 e9a3d6b4cc38ef1b64dc390aba87a79ee0a7f4a3c6ec2d8603a267917f7eba13. Its embedded strings match the diagnostic overlay, **but byte-exact reproducibility from CI has not been established**.
- Installed Graphics 0.4.4 remains untouched. Current EFI has Lilu 1.7.3; the established build workflow uses Lilu 1.7.2 development headers. Do not replace the installed Lilu or Graphics as part of this test.
- No ThunderboltA73EProbe, AppleThunderboltNHI, HAL Type4, USB4, HDMI2 LightUpTMDS, SCDC, PHY, PLL, HPD or MMIO experiments are added.

## Exact modification

From Thatisjigen/WhateverXe acer/current at f7b9bf2229d323e37e8b1dfb87182f005eb7a277, transplant **only** the concept of AppleIntelPort::getDPCDInfo MST-cache masking:

1. Call the native DPCD getter first and preserve its original return value.
2. Require Intel 8086:A7A0, Display13 and mapped Type-C physical DDI5.
3. Optionally clear **only** internal port byte +0x1E, which caches MST capability, after the native read. Never directly change MST mode +0x117.
4. Install the native route only if the exact function symbol, offset 0x1DE0E and first eight instruction bytes match. A mismatch refuses the hook.
5. Limit IORegistry observations to the first eight qualified reads; no training retry or successful-result fabrication.

Legacy reference: https://github.com/Thatisjigen/WhateverXe/blob/f7b9bf2229d323e37e8b1dfb87182f005eb7a277/WhateverXe/kern_xe.cpp#L7304-L7328

## A/B boot flags (same exact Kext)

| Added boot argument | Action |
| --- | --- |
| Neither new flag | No extra DPCD hook; established baseline |
| -wex-yoga-tc5-sst-observe | Installs read-only DPCD observation hook; does not hide MST |
| -wex-yoga-tc5-sst | Installs the hook and masks DDI5 cached MST capability |

Keep all current boot arguments as-is (especially -wex-yoga-edp120-admit, -wex-yoga-edp120-wm, -wex-yoga-hdmi-edid-deep8, -wex-yoga-hdmi600 and -wex-yoga-usbc-dpdiag); add only one new flag for a test. Do not add the abandoned -wex-yoga-hdmi4k60 or -wex-yoga-hdmi2-link experiments.

## Diagnostic properties

- WEXYogaSSTRequested, WEXYogaSSTObserveRequested: requested boot mode.
- WEXYogaSSTHookReady: whether the native DPCD route installed.
- WEXYogaSSTHookStatus: 0=off; 1=platform/path gate rejected; 2=donor symbol/bytes mismatch; 3=route failed; 4=installed.
- WEXYogaSSTFirstDPCD and WEXYogaSSTLastDPCD: little-endian uint32[9], indexed as version=1, qualified sequence number, DDI=5, MST cache before, MST cache after, native MST mode +0x117, low 32 bits of native result, did-mask flag, cumulative masks.
- WEXYogaSSTCapabilityMasked: true after the first actually masked read.

Only first eight qualified reads publish diagnostics. A missing value does not imply MST absence; the hook may never have executed.

For a successful boot, collect:

    ioreg -p IOService -l -w0 | grep -E 'WEXYogaSST|WEXYogaUSBCDPTraining'
    system_profiler SPDisplaysDataType

## Real hardware test and rollback

1. Keep the *entire* current EFI unchanged as recovery. Copy it to a separate test EFI. Replace only WhateverXe.kext, not other Kexts, ACPI, boot arguments, A73E/Type4 options or the macOS Graphics install.
2. Boot the new Kext without either SST flag. Confirm Metal, 1536MB VRAM, internal 3072x1920 @120Hz, and current chassis HDMI 4K30 output and color.
3. Test one 1080p60 monitor through HP G4, USB-C fallback, with -wex-yoga-tc5-sst-observe. Capture HookStatus, MST cache, native training results. A black screen is possible.
4. Remove observe mode; use -wex-yoga-tc5-sst. Verify actual first read was masked, macOS enumerated an external monitor, and a real picture appeared. HookStatus=4 alone is not a successful display.
5. Only if the single display works: test dock HDMI+DP mirror, then chassis HDMI + dock separate desktops, and finally gentle hotplug/reconnect. USB mouse disconnects and native clock cleanup remain separate hypotheses.

If masking happens but DP training remains NotReady/Busy, the patch is insufficient; use existing WEXYogaUSBCDPTrainingFirst1..8 and WEXYogaUSBCDPTrainingLast data for the next diagnosis.

The workflow builds with pinned MacKernelSDK, WhateverXe 0.8.3, Graphics 0.4.4 headers, and Lilu developer headers; runs the complete upstream test suite, source-safety checks and RELEASE/Compat tests. **Compilation does not prove actual video output**.

If internal display, HDMI or GPU acceleration regresses, immediately boot the unmodified original EFI, restore the old WhateverXe.kext in the experimental copy and remove the additional SST argument.

Do not merge into main before successful real-machine validation.
