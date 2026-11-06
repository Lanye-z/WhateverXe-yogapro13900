# WhateverXe for Yoga Pro 14s IRH8 — Integrated Test Build

**Status: experimental native EDID integration; do not replace the known-good EFI.**

- Full details, source revisions, safe test and rollback:
  [e13/YOGA_MAIN_RGB8_README.md](e13/YOGA_MAIN_RGB8_README.md)
- New native EDID patch (optional, default OFF): \`-wex-yoga-rgb8\`.
  Exact-match original AOC U27P10 05E3:2710 EDID -> proven
  RGB8_STRICT 256-byte variant at Display13 native HDMI DDC read.
- Existing optional E1.1 HDMI600: \`-wex-yoga-hdmi600\`. The 4K60
  black-screen issue remains unresolved; this does not implement SCDC.
- Baseline: pinned acer/current + D1.1 eDP CTL2 one-line acceptance.
  WhateverXe Graphics v0.4.0 stays unchanged.
- Build artifact: [.github/workflows/yoga-main.yml](.github/workflows/yoga-main.yml).

Earlier research and archive artifacts remain available in the repository.
The new EFI/Kext has not been installed on the target Mac by this commit.
