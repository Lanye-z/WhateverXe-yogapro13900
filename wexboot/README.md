# Yoga 0.8.3 3K120 Apple Logo flash — independent investigation

**Status (2026-11-18): DIAGNOSIS, NOT A FIX.** Forked from hardware-verified
[3K120 V1](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edp120).
The working V1 Kext is deliberately unchanged. This branch contains only
**read-only offline scripts** and a macOS GitHub Action for exact public donor
symbol inspection; no untested framebuffer writes are enabled.

## Symptoms and observations (not yet complete causal proof)

On the Yoga Pro 14s IRH8 (i9-13900H / Intel A7A0 rev4; macOS 26.7.1), the
Apple Logo flickers/garbles briefly (< 1 second) just before the login screen.
It also occurs on 0.8.3 builds without `-wex-yoga-edp120-admit`, but appeared
over a larger area when the 800MHz mode-admission flag was enabled.
The subsequent 3072x1920 @ 120Hz graphics are normal, with 1536MB / Metal 2.

The user previously uploaded a **10MB IORegistry capture** in
`Yoga_EDP120_V1.zip`. Read-only decoding of its saved
`N97Display13Boot` (early pre-driver GOP register snapshot) gives:

| Early GOP register | Actual saved value |
| --- | --- |
| Status / active pipe | Complete / pipe A |
| `PIPESRC_A` | `0x0bff077f` => 3072 x 1920 |
| `PLANE_CTL_1_A` | `0x94000008` (mode bits `(ctl>>10)&7 = 0`) |
| `PLANE_STRIDE_1_A` | `0x000000c0` => 192 × 64 = **12,288 B/row**, equal to 3072×4 |
| `PLANE_SIZE_1_A` | `0x077f0bff` => 3072 x 1920 |
| `PLANE_SURF_1_A` | `0x00000000` |
| `TRANS_DDI_FUNC_CTL2_A` | `0x00000008` (the previously suspected CTL2 secondary-mode bit now directly captured) |

This is **strong evidence of a correctly configured linear firmware GOP boot
buffer**, as hypothesized by [WhateverXe issue #131](https://github.com/b00t0x/WhateverXe/issues/131).
It is **NOT proof of later tiling mismatch**: #131's actual defect arose after
the native donor and WindowServer started using/reading the console buffer.

Critical differences and precautions:

- #131 was verified on **ADL-S/A78B**, not Yoga RPL-H/A7A0.
- #131's guarded *write* fix was explicitly inert with `-v`. The Yoga's current
  boot arguments **include `-v`**, so blindly copying that fix would not
  address the presently observed boot path.
- Another #131 tester found that rewriting `res+0x194` **on every creation**
  corrupted shutdown; a first-creation-only condition is essential if the
  mechanism is proved and a real patch is attempted.
- Do **not** change 120Hz, EDID, WM, HDMI, DSC, system Graphics binaries,
  plane surfaces/tiling or framebuffer resource descriptions at this stage.

## Exact Graphics 0.4.4 donor audit — CI passed

[GitHub Actions run 44300608445](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44300608445)
successfully inspected the pinned public Graphics 0.4.4 Tahoe files without modifying them.

- `AppleIntelTGLGraphics` SHA256: `6c8ab6cce50b9529679ee4fdf5b1c37d091677d945076f41cb4b7f8196c51449`.
- `AppleIntelTGLGraphicsFramebuffer` SHA256: `115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`.
- Exported symbol `IGAccelDisplayPipe::initFramebufferResource` at `0x7F160`, and `IGAccelDisplayPipe::initResourceInfo` at `0x7EE9A`. These correspond to the functions described in #131, including a report that the same offsets also matched Graphics 0.4.4 on an A78B device.
- This is a **code match**, not proof of an X-Tiled **runtime** resource descriptor on the Yoga.
- [Download raw symbol/source audit](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44300608445/artifacts/14425364213).

## Reproducible safe research

The new `analyze_boot_capture.py` reads a **local** `ioreg.txt` or existing
`Yoga_EDP120_V1.zip`. The script does not access hardware:
```sh
python3 wexboot/analyze_boot_capture.py /path/to/Yoga_EDP120_V1.zip
```
The `yoga-bootlogo-audit.yml` workflow independently inspects the **exact**
public 0.8.3 C++ source and Graphics 0.4.4 Tahoe binaries for the functions
referenced by issue #131; it does not create a Kext.

## First physical A/B experiment (no source changes)

Keep the currently verified V1 USB/EFI safe. Make a **second test EFI copy**,
with the same 0.8.3 eDP120 V1 Kext and all other boot arguments unchanged.
In the second test EFI only, remove the standalone `-v` argument. Observe
whether the Apple Logo flash (1) disappears, (2) displays duplicated logos or
white noise, or (3) is unchanged. If recording, use phone slow-motion video
and compare *at the exact stage between logo and login*.

This single-variable test is important because #131 explicitly excludes
`-v`/text-boot from its reference patch. Changing `-v` is a diagnostic
configuration comparison, **not** a confirmed root-cause repair.

## Next code decision

Only after separating GOP (firmware plane LINEAR) and donor/WindowServer
resource tiling/first-flip state, consider a **separately flagged**, strictly
fingerprinted, one-time resource-description fix (not a masked timer), with
both boot and shutdown regression tests. Do not replace the proven eDP120 V1
until a new CI artifact and an independent test EFI exist.
