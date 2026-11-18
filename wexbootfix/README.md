# Yoga A7A0: 3K120 cold-start black-screen experiments

**Status: build/test candidates, not proven fixes.** Do not replace the known-good EFI or merge into main. Builds use pinned WhateverXe **0.8.3** and independently byte-verified Graphics 0.4.4. The previously successful V1 120Hz kext, code and main are unchanged.

## Real machine evidence

The current 60Hz boot with V1 kext but without `-wex-yoga-edp120-admit` works: Metal 2, 1536MB. With admission, the user could change 60→120Hz at the desktop, with actual `IOFBCurrentPixelClock=775690000` and CoreGraphics 120.0Hz. After rebooting in that saved mode, both with/without `-v`, a black internal screen followed. In failed boots at 20:22 and 20:25 WindowServer requested mode `0x80001001` and logged thousands of `Fallback GPU Display Pipe transaction submission failed` errors. A 20:50 failed boot had no identical error flood. With admission off, working 20:54 boot requested `0x80001000`. This points to 120Hz cold-mode restore, but the exact failure register remains unidentified.

## Two isolated variants

| Artifact | Boot flags | Purpose |
| --- | --- | --- |
| **WM_ONLY** | `-wex-yoga-edp120-admit -wex-yoga-edp120-wm` | Prior V2 two-pixels/CDCLK WM `clockFits` adjustment, with V1 admission |
| **WM_GATE** | Same plus `-wex-yoga-edp120-gateretry` | Adds an optional bounded WorkLoop gate retry, modeled on [upstream #102](https://github.com/b00t0x/WhateverXe/issues/102) |

All flags default OFF. **WM_GATE** executes the retry only when the physical Yoga A7A0/eDP qualification succeeds, the explicit flag is set and the dual-output `adlnSetDualClock` branch actually tries to close the WorkLoop gate. It releases the owner lock during at most 50 × 1ms retries; writes the count to `N97FBClockWMAll[27]`. `WEXYogaEDP120GateRetryEnabled` indicates opt-in, **not** proof that retries actually executed. If the Yoga chooses the single-output branch, gate retry is inert. Neither candidate changes EDID, link rate/DSC, plane memory, installed Graphics, HDMI or macOS preferences.

## Test carefully and sequentially

1. Keep your current **bootable 60Hz recovery EFI** untouched. Preserve `-v` for diagnostics. Verify current macOS display setting is **60Hz**.
2. Copy recovery EFI to another USB/test EFI; install **WM_ONLY** kext *in the copy*, replacing just `EFI/OC/Kexts/WhateverXe.kext`.
3. First boot that copy **with no new eDP flags**: verify 60Hz/Metal. Then add the two WM_ONLY flags. First verify it boots while saved mode is 60Hz. Only then select 120Hz; if stable, and you have independent recovery access, test **one** reboot with 120Hz saved.
4. If black again, use the recovery EFI, remove admission flag, preserve logs. **Do not repeat the same failing startup.** Only consider WM_GATE if `N97FBClockWMAllFirstFailure` or other evidence makes workloop contention plausible, in a separate EFI copy.
5. Inspect `ioreg -lw0 -p IOService | grep -E 'WEXYogaEDP120|N97FBClockWM|N97FBClockWMAllFirstFailure'` on any successful boot. A CI pass alone **never** establishes that cold 120Hz restart works.

This research intentionally leaves the unproven GPU plane/tiling rewrite from issue #131 and unsupported eDP retraining modifications out of both packages.

## Build / rollback

[GitHub Actions bootfix workflow](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/workflows/yoga-edp120-bootfix.yml) uploads the release kext, exact source diff, build manifest and hashes for each candidate. If a trial fails, boot the independently known-good 60Hz USB/EFI, or remove `-wex-yoga-edp120-admit` from the trial's boot args; do not reset NVRAM or overwrite system Graphics 0.4.4.
