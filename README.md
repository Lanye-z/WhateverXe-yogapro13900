# WhateverXe D1.1 — single source-first development branch

Target: Lenovo Yoga Pro 14s IRH8 (82Y7), i9-13900H, Intel 8086:A7A0, Tahoe 26.7.1.

**No new standalone patches.** D1.1 now stores the full **C++ source** of the four modified files in `src/`. The source contains the previously tested A/B/C/D kernel/display modifications, including the opt-in `-wex-a7a0-panel-only` path. Build checkout is pinned to upstream WhateverXe commit `d0b7fb6`; this branch directly copies versioned source files into that checkout. No `git apply` or binary code-cave patching is involved.

On a Mac with Xcode command-line tools:

```bash
git clone --branch D1.1 --single-branch https://github.com/Lanye-z/WhateverXe-yogapro13900.git
cd WhateverXe-yogapro13900
bash build_D_on_macos.command
```

The builder emits one D1.1 Kext ZIP in `OUTPUT_D/`, does **not** install it and does **not** modify EFI. GitHub Actions builds that same native source and uploads a **Kext + Graphics baseline manifest**, not a modified Graphics installer.

## Graphics responsibility and limits

Graphics is pinned to the upstream signed [WhateverXe Graphics 0.4.0](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.0). See [Graphics baseline](graphics/BASELINE.md) for known VA issues and the source/signing limitation. The connected account has read-only rights in that upstream repository. **A C++ Kext edit cannot directly repair the crashing user-space VADriver or create a missing HEVC hardware encoder.**

## Real hardware results so far

| Feature | Status |
| --- | --- |
| D internal display 3072×1920 @ 60 Hz, opt-in panel-only | Works; external displays disabled in this mode |
| Metal compute | Tested passing |
| H.264 / HEVC hardware decode | Both passed 180/180 |
| H.264 NV12 hardware encode | Passed 180/180 |
| Application-level BGRA→CPU NV12→H.264 hardware encode | Passed 180/180 |
| Native system BGRA→NV12 VTPixelTransfer | **Crashes** at VADriver NULL pointer write |
| HEVC hardware encode | **Unregistered/unavailable**, hardware-required -12908 |
| HEVC software encode | 1 sample passed; not hardware |

The `0xAC0` code cave audit on Graphics v0.4.0 returned **REFUSED**. This is a correct safety stop; all independent binary-patch generators have been retired from the current branch (available only in Git history). No system-wide video driver fix is claimed.

Optional VideoToolbox diagnostics are in `macos/video-encode/`. They are not installers. Keep the working D EFI/Graphics installation as your recovery baseline; the build result must be tested in a separate EFI before use.
