# WhateverXe for Lenovo Yoga Pro 14s IRH8 (82Y7), i9-13900H / A7A0

Experimental, reproducible macOS x86_64 build based on upstream **b00t0x/WhateverXe 0.7.0**, commit `d0b7fb6275ca51fde088fa7e91595462bd457ec9`.

## Machine and known baseline

- Lenovo Yoga Pro 14s IRH8 / 82Y7; Intel Core i9-13900H; Intel Xe LP `8086:A7A0`, revision 04
- Internal eDP 3072 × 1920; macOS Tahoe 26.7.1 (25G241)
- WhateverXe Graphics 0.4.0; Lilu 1.7.3 loaded on the test machine
- 60 MiB DVMT workaround configured on the test EFI
- **Confirmed**: patch 0001 changes `N97NativeBootSource` from `InvalidDPSource(11)` to `Ready(1)`, and sets `WEXDisplay13BootReady`, `N97NativePreflight`, `N97NativeStartAllowed`, `N97NativeReservedGGTT` to Yes.
- **Still broken with patch 0001 alone**: `AppleIntelFramebuffer@0/1/2` attach but the display stays under `.Display_boot`, `IntelAccelerator` is absent, VRAM 22 MB.

## Source changes

1. [`patches/0001-a7a0-edp-ctl2-bit3.patch`](patches/0001-a7a0-edp-ctl2-bit3.patch): proven, narrowly-scoped acceptance of firmware's `TRANS_DDI_FUNC_CTL2` bit 3 on the **internal eDP panel only**.
2. [`patches/0002-edp-boot-port-mode-EXPERIMENTAL.patch`](patches/0002-edp-boot-port-mode-EXPERIMENTAL.patch): experimental, guarded eDP SST boot-port mode handoff from [upstream issue #22](https://github.com/b00t0x/WhateverXe/issues/22). **Not yet verified on A7A0.** This patch may cause a black screen; retain a working recovery EFI.

Unlike an unpinned script, the exact upstream source revision and individual changes are committed here. The complete modified source is reproducible from the exact pinned upstream commit plus these committed patches. The repository currently tracks the **patches**, not a full copy of the upstream source tree. The existing CI workflow does not yet publish a source-snapshot branch. On a successful run, its artifact includes the compiled `WhateverXe.kext` ZIP, the combined patch and checksums.

## Build

Open [GitHub Actions](../../actions/workflows/diagnostic.yml) and run **WhateverXe Yoga Pro A7A0 experimental build**. The existing workflow also triggers on a pull request targeting `main`. Its current build uses the combined patch file in the pull request branch. A macOS 15 Intel runner fetches the official pinned source, MacKernelSDK and Lilu 1.7.2 development files; executes `tools/test.py`; compiles a RELEASE `WhateverXe.kext`; and uploads the ZIP.

`AppleIntelTGLGraphics` and `AppleIntelTGLGraphicsFramebuffer` are **not** embedded in this Kext ZIP. They must be separately provided by the installed WhateverXe Graphics package.

## Safety

Do **not** overwrite the current working EFI. Test the generated `WhateverXe.kext` on a separate USB OpenCore EFI with the rest of the boot stack unchanged. Neither building nor passing CPU tests confirms GPU acceleration or stable display initialization. If the display goes black, boot the original EFI.

Related: [Issue #18](https://github.com/b00t0x/WhateverXe/issues/18), [Issue #22](https://github.com/b00t0x/WhateverXe/issues/22), [Issue #32](https://github.com/b00t0x/WhateverXe/issues/32).
