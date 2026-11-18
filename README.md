# Yoga Pro 14s IRH8 (82Y7) — Apple Logo handoff glitch investigation

**Status (2026-11-18): INVESTIGATION PAUSED at user's request; NOT FIXED.** The Apple Logo to login handoff may briefly (<1 second) show garbling/red or repeated logo frames; normal desktop image appears afterward on the currently tested WM_ONLY / source-equivalent V2 3K120 configuration. Because the glitch is short and the user considers it low priority, further changes are deferred pending real-world 120Hz stability observation.

**Important distinction:** Admission-only V1 previously booted to a persistent black screen after saving 120Hz, with or without `-v`. That is **separate from the subsecond cosmetic handoff issue**. Subsequently, [WM_ONLY](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edp120-bootfix) succeeded on **one reboot directly into 120Hz**; post-reboot IORegistry confirmed `WEXYogaEDP120WMEnabled=Yes`, `IOFBCurrentPixelClock=775690000`, Metal 2 and 1536MB. The boot black-screen regression is thus provisionally addressed on WM_ONLY, whereas the brief logo glitch remains unresolved. Repeated cold boots, sleep/wake and long-term stability have **not** been tested yet.

## What this diagnostic branch contains

- **No modified Kext or display write fix.** The working WM_ONLY Kext remains unmodified.
- A read-only offline `N97Display13Boot` register decoder and a pinned Graphics 0.4.4 / official WhateverXe 0.8.3 source audit.
- Prior saved firmware GOP snapshot: native pipe A, `PLANE_CTL=0x94000008` (LINEAR), `PLANE_STRIDE=0xC0` = 12,288B/row, `PLANE_SURF=0`, `TRANS_DDI_FUNC_CTL2=0x8`.
- [Issue #131](https://github.com/b00t0x/WhateverXe/issues/131) diagnosed a GOP LINEAR / X-Tiled resource mismatch on **different** Intel hardware. The same failure mode is *not proved* on this A7A0 Yoga, and no tiling patch has been applied.
- The attempted `-v` A/B test is **inconclusive** because it was conducted under V1 with the saved 120Hz mode that also failed to reboot with `-v`. **Do not repeat that experiment on the working WM_ONLY just to eliminate a brief flash**.

See [the detailed research log and audit](wexboot/README.md). The unchanged 0.8.3 WM_ONLY test remains the preferred 3K120 candidate; retain the independent 60Hz recovery EFI.

**No further boot-logo work is planned until the user explicitly chooses to resume it.**
