# Yoga 0.8.3 3K120 Apple Logo flash — independent investigation

**Status (2026-11-18): INVESTIGATION DEFERRED BY THE USER; DIAGNOSIS ONLY, NOT A FIX.** Forked from hardware-verified
[3K120 V1](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edp120).
The last proven WM_ONLY / source-equivalent V2 Kext is deliberately unchanged. This branch contains only
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
- Do **not** modify the working WM_ONLY 120Hz baseline, EDID, HDMI, DSC, system Graphics binaries,
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

## Previous `-v` A/B test — now understood as inconclusive

An earlier admission-only **V1** test removed `-v` after the desktop had
saved 120Hz. Two black-screen boots followed; restoring `-v` still black-
screened when `-wex-yoga-edp120-admit` was present. Removing admission
restored normal 60Hz startup. Thus the evidence points to a **saved-120Hz
V1 cold-recovery problem**, not a proved verbose-boot cause of the short
logo glitch. Do **not** repeat no-`-v` testing on the working WM_ONLY as
an assumed flash repair.

WM_ONLY (source-equivalent to the original V2) later passed one saved-120Hz
reboot; post-reboot `WEXYogaEDP120WMEnabled=Yes`, `IOFBCurrentPixelClock=
775690000`, 120.00Hz and Metal 2 / 1536MB were recorded. This does not
resolve the cosmetic Apple Logo flash or establish long-term stability.
The user is now using WM_ONLY normally and has asked to **defer** this
investigation.

## Next code decision

Only after separating GOP (firmware plane LINEAR) and donor/WindowServer
resource tiling/first-flip state, consider a **separately flagged**, strictly
fingerprinted, one-time resource-description fix (not a masked timer), with
both boot and shutdown regression tests. Do not replace the proven eDP120 V1
until a new CI artifact and an independent test EFI exist.

## New real-hardware A/B result — no `-v` (2026-11-18)

With the V1 3K120 Kext and `-wex-yoga-edp120-admit` retained, after selecting
120Hz in macOS the user removed only `-v` and attempted two boots. Both showed
the first Apple logo, dimming, a brief red-logo flash, a second normal Apple
logo, then a black internal panel. No successful login/display was observed.
This is **not yet a root-cause diagnosis**: the comparison changed verbose mode
while the saved 120Hz mode remained active, and there is no matched boot of the
same saved 120Hz mode with `-v` restored yet. Do not repeat no-`-v` boots for now.

### A7A0-specific upstream precedent

[WhateverXe issue #104](https://github.com/b00t0x/WhateverXe/issues/104) reports
an early dark internal eDP on another **8086:A7A0** Raptor Lake-P system, with
Metal/Framebuffer initialization otherwise appearing successful. Its author
identified startup clock-gate contention, a deferred-clock write that could be
reported as handled without being queued, and an over-strict panel admission
check. The proposed fix was validated on that author's 0.8.0 / Graphics 0.4.x /
Sequoia setup, **not** on this Yoga / 0.8.3 / Graphics 0.4.4 / Tahoe setup.
The pinned official 0.8.3 source inspected for this branch still has the
single-attempt dual-clock gate path and the pre-existing deferred-clock logic;
this makes #104 a strong candidate to investigate, not proof of this incident.

[Issue #131](https://github.com/b00t0x/WhateverXe/issues/131) remains a second,
distinct candidate for a no-`-v` GOP-to-WindowServer resource-layout mismatch.
The Yoga's saved early GOP snapshot is LINEAR, but no later Yoga resource
modifier / first-blit receipt has yet been captured.

### Current decision — no additional edits or tests

Keep the current successful WM_ONLY configuration and an independent 60Hz
CTL2 recovery EFI. The brief logo flash may be revisited only if it starts
affecting desktop output, causes persistent black screens or the user elects
to pursue it. No GPIO/plane writes, resource-tiling hooks, EDID changes,
`-v` switching or other issue patches are recommended now.

**Status: issue still open, intentionally deferred.**
