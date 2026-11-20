# Yoga 82Y7 / A7A0 HDMI 2.0 guarded candidate Kext — V1

> **Experimental hardware build. Not yet tested on Yoga 82Y7.** It is *not* a confirmed HDMI 4K60 fix. This is the first Kext candidate with a real SCDC/MMIO path and two explicit boot modes, compiled against pinned 0.8.3 and the verified Deep8/HDMI600/SST overlay.

## Critical history

- The earlier **standalone** `-wex-yoga-hdmi2-route-only` experiment broke Metal and native HDMI. **Do not use that Kext or either old `-wex-yoga-hdmi2-route-only` / `-wex-yoga-hdmi2-link` flags.**
- This build does **not** install any `LightUpTMDS`, `setColorMode`, or `getOnlineInfo` route.
- It inherits the same pinned macOS Tahoe donor, Deep8/HDMI600/eDP120 source overlay and USB-C SST hook as the last working version. The added logic lives in the already-installed Display13 WM, DDC, and RegisterAccessManager callbacks.

## Build modes

| boot-arg | Behavior |
|---|---|
| Neither | Exact pre-existing operational behavior. No extra DDC traffic or HDMI2 control writes (additional code is never entered). |
| `-wex-yoga-hdmi2-observe` | On physical HDMI B, inspect the pending CRTC clock and cached CTA information. **Never** issue extra SCDC I2C or modify `TRANS_DDI_FUNC_CTL`. |
| `-wex-yoga-hdmi2-safe` | On qualified physical A7A0 DDI B, 8bpc native HDMI high-clock condition, use native I2C to read SCDC version, set source version, read-modify-write and confirm SCDC `TMDS_Config`; only on success arm the existing register write wrapper to OR `0x11` into HDMI B's **enabled** `TRANS_DDI_FUNC_CTL` write. Other pipe/port writes passed through. Low speed tries to restore sink low mode. |
| Both | Conflict: experimental features disabled. |

New source files `wexhdmi2/kern_yoga_hdmi2_candidate.hpp`, `wexhdmi2/kern_display13_hdmi_caps.hpp`, `wexhdmi2/prepare.py` and self-contained `wex4k60/hdmi2_*.hpp`. Native I2C helper symbol is gated to exact donor offset `0x53A20` and entry bytes.

## Limitations and first-hardware-test rule

The last working **4K30** capture: DDI B/pipe2 `FUNC_CTL=0x90030200`, 297MHz, 8bpc, eDP 775.69MHz, other external display 148.5MHz. This does **not** identify the actual 4K60 black-screen cause.

This first candidate is not hardware tested. The existing Display13 WM callback is expected to run before the HDMI native FUNC_CTL write and hold the native display owner lock; neither timing nor lock ownership has yet been demonstrated during a 4K60 transition. If those conditions fail, it leaves the source bits unchanged and records a reason. HDMI2 beyond 340MHz may still fail for independent CDCLK/PHY/PLL/WM causes.

**For actual machine testing only after CI succeeds:** prepare an independent OpenCore USB EFI, preserving a complete bootable stable backup and physical recovery. Install Kext only in the test EFI, **without any new HDMI2 argument**, boot and verify eDP120, Metal 1536MB, native HDMI 4K30, Deep8 colours and SST external monitor. If any regression, immediately restore stable EFI; do not enable HDMI2.

Then test only `-wex-yoga-hdmi2-observe` at normal 4K30. Read status:
```bash
ioreg -p IOService -l -w0 | grep -E 'WEXYogaHDMI2|WEXYogaHDMI600|WEXYogaSST'
```
Expected: `WEXYogaHDMI2SafeStatus=3`, `WEXYogaHDMI2SafeReady=Yes`, `WEXYogaHDMI2SafeWriteRequested=No`. `WEXYogaHDMI2WMEvent` may report low-speed reason 51. **Do not interpret installation of a hook as success of 4K60.**

Actual `-wex-yoga-hdmi2-safe` and 4K60 switching is a higher-risk **later test only** after observable 4K30 stability and recovery are confirmed. If the debug records show that the intended WM callback does not retain owner lock before HDMI setup, do not proceed; instead revise hook strategy.

Source link: [experimental integration branch](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-hdmi2-integration). The **main branch / installed EFI is unchanged**.
