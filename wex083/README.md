# Yoga Pro 14s IRH8 (82Y7) — WhateverXe 0.8.3 CTL2 test

**2026-11-18 STATUS: SUCCESSFULLY TESTED ON HARDWARE (INTERNAL eDP @ 60Hz).**
Official 0.8.3 initially showed 22 MB / no Metal; the narrow panel-only
CTL2 bit 3 exception restored normal acceleration: **1536 MB, Metal 2,
3072×1920 @ 60Hz** on Yoga i9-13900H / A7A0 rev 04, macOS Tahoe
26.7.1 (25G241), Graphics 0.4.4. CI [run 44270166468](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44270166468)
also succeeded. This is a **real device test**, not merely a successful
compile. A direct new live CTL2 register read was not recorded.

**Not fixed on this branch:** 120Hz, HDMI 4K60, Thunderbolt dock, boot logo
handoff flash, sleep, HEVC or external output. A **separate follow-on**
[Yoga eDP120 branch](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edp120)
has since achieved 3K120 on the same hardware (see its README). Do not
treat that result as included in this CTL2-only Kext.

## Why this exists

On 2026-11-18 the Yoga i9-13900H, Intel A7A0 (rev 04) boots official WhateverXe **0.8.3** with signed Graphics **0.4.4** and AMFIAnchor **0.1.2**, but reports 22 MB and no Metal. The relevant IORegistry statuses are:

```text
N97NativeBootSource = <0100000000000000020000000b00000000000000>
N97NativeProbeBlocked = Yes
N97NativePreflight = No
N97NativeStartAllowed = No
WEXDisplay13BootReady = No
```

The `0b` word is decimal 11, `InvalidDPSource`. Previous 0.7.0-based Yoga experiments identified firmware `TRANS_DDI_FUNC_CTL2=0x00000008` (CMTG_SECONDARY_MODE), and a guarded panel-only exception was used to bring up Metal. **This new log does not independently measure CTL2**, so it is a strong leading explanation, not a proven exclusive root cause.

## What is built

The workflow [yoga-0.8.3-a7a0-ctl2.yml](../.github/workflows/yoga-0.8.3-a7a0-ctl2.yml) checks out the **real upstream 0.8.3** source at pinned commit `f26a36880c49ea1063393d943527808c0f38feca`; it does **not** build the repo's historic 0.7.0 donor or merely change a version string. It applies `0001-a7a0-edp-ctl2-bit3-083.patch` to `WhateverXe/kern_alderlake_n.hpp`.

Old rule: `!ctl2` (reject all CTL2 bits). New rule: `!(ctl2 & ~(panel ? (1U<<3) : 0U))`.

* Internal eDP (panel=true): accept CTL2 = 0 or 8 only.
* External DP/HDMI (panel=false): CTL2 must still be zero.
* Every other preflight, VBT, clock, DDI, PHY, framebuffer, GGTT, Metal and sleep check remains **official 0.8.3**.

The workflow guards the exact upstream SHA and source syntax, runs upstream tests, builds a RELEASE Kext and uploads an artifact. CI was followed by a real Yoga hardware test confirming **Metal 2, 1536 MB and 3072×1920 @ 60 Hz**. It does **not** validate the unrelated external display or sleep paths.

## Installation and rollback

1. Open the GitHub Actions workflow for this branch and download its successful **WhateverXe-0.8.3-Yoga-A7A0-CTL2-TEST** artifact. Use `WhateverXe_0.8.3_Yoga_A7A0_CTL2_TEST_RELEASE.zip` inside it.
2. Back up the bootable USB test EFI currently using **official 0.8.3**. In a separate test copy, **replace only** `EFI/OC/Kexts/WhateverXe.kext` with the built Kext. Do not replace the whole EFI, do not mix NootedGreen with WEX, and do not add old `-wex-yoga-video-c`/RGB8/HDMI600 flags.
3. Keep the working test configuration: Lilu 1.7.3, AMFIAnchor 0.1.2 and Injector, `csr-active-config=03080000`, `-allow3d -disablegfxfirmware -igfxdvmt`, 60MB stolenmem patch, **Graphics 0.4.4 installed in macOS**. This build does **not** include Graphics or AMFIAnchor.
4. Boot **without external monitors or Thunderbolt dock**. Check:

```sh
kmutil showloaded | grep -Ei 'WhateverXe|AppleIntelTGL|AMFIAnchor'
system_profiler SPDisplaysDataType
ioreg -lw0 -p IOService | grep -E '"(N97NativeBootSource|N97NativeProbeBlocked|N97NativePreflight|N97NativeStartAllowed|WEXDisplay13BootReady|N97NativeReservedGGTT)"'
```

Only if 1536 MB/Metal is restored, proceed to display sleep testing; avoid system sleep until stable.

**If it fails:** boot from the independent untouched EFI or restore the official 0.8.3 `WhateverXe.kext` in your USB test EFI. Because this test changes only the WEX Kext, it does **not** require reinstalling Graphics 0.4.4 merely to return to official 0.8.3. Backing out to earlier Graphics 0.4.0 / other GPU stacks is a different procedure.

## Not addressed

MST / dock independent displays, HDMI 4K60 SCDC, RGB8, Video C, 120Hz, full system sleep, or the possibility that more than one `dpSource` admission check is failing. The CTL2-only build is verified on this Yoga at 60Hz. On other systems, if it still reports `InvalidDPSource`, get a CTL2 register snapshot and remaining per-register conditions before broadening any safety checks.
