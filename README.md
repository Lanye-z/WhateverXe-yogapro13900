# Yoga Pro 14s IRH8 (82Y7) — WhateverXe 0.8.3 / A7A0 eDP CTL2

**Status (2026-11-18): HARDWARE-VERIFIED for the internal panel at 3072×1920 @ 60 Hz, 1536 MB VRAM, Metal 2.** This branch was successfully built in GitHub Actions [run 44270166468](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44270166468) and then tested on the Yoga i9-13900H, A7A0 rev 04, macOS 26.7.1 (25G241) with Graphics 0.4.4. It is **not** a tested 120 Hz fix.

## Outcome

Official 0.8.3 without this fix: the internal eDP failed native adoption (`InvalidDPSource`), only 22 MB and no Metal.

This branch changes the *panel-only* eDP CTL2 condition from `!ctl2` to `!(ctl2 & ~(panel ? (1U<<3) : 0U))`. On the target Yoga, the modified 0.8.3 **successfully adopted the internal panel** and macOS reported full Metal 2 / 1536 MB. The original one-time diagnostic did not separately read the live CTL2 word, so the cause is inferred from the precise code change and the A/B result, not from a new independent register dump.

### Remaining problems

The internal display ran at **60 Hz only** with this driver, despite EDID's 120 Hz timing; native 4K60/HDMI and Thunderbolt dock output were not fixed. A brief Apple Logo / WindowServer handoff flash was observed on the subsequent 0.8.3-derived experiments and has **not** yet been diagnosed or fixed. Do not conflate a successful Kext build with a full-machine release.

### Follow-on successful 120 Hz branch

[experiment/wex-0.8.3-yoga-edp120](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edp120)
preserves this CTL2 adjustment and adds **opt-in** `-wex-yoga-edp120-admit`. On 2026-11-18, the Yoga's native `IOFBTimingRange` increased from 720 MHz to 800 MHz, and the internal display successfully switched to **3072×1920 @ 120.00 Hz** with `IOFBCurrentPixelClock = 775690000`, Metal 2 and 1536 MB. V1 then showed a **saved-120Hz reboot black-screen regression**. A subsequent **WM_ONLY** build (source-equivalent to the original V2; CTL2 + 800MHz + opt-in two-pixels/CDCLK WM) has now completed **one successful reboot directly into 3K120**, with post-reboot `IOFBCurrentPixelClock=775690000`, Metal 2 / 1536MB and `WEXYogaEDP120WMEnabled=Yes`. See the [tested WM_ONLY build](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edp120-bootfix). Multi-reboot and sleep stability remain unverified; original CTL2-only driver stays a 60Hz recovery baseline.

See [this branch's focused CTL2 notes](wex083/README.md) for technical details, tested installation and rollback. The repository's separate `main` remains its earlier integrated 0.7.0-based HDMI/RGB8/Video-C experiment — this 0.8.3 test has **not** been merged there.

## Install / rollback

Only replace `EFI/OC/Kexts/WhateverXe.kext` in a **duplicate independently bootable test EFI**, retain Graphics 0.4.4 and the installed AMFIAnchor stack, keep a known-good recovery EFI, and avoid combining WhateverXe and NootedGreen. Do not use external display or sleep stability as implied proof. If anything fails, restore the known-good EFI/Kext.
