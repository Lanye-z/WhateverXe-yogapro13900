# Yoga 82Y7 / WhateverXe 0.8.3: USB-C DDI5 SST compatibility

## 2026-11-20 实机验证更新 — SST 已成功（保留成功版本）

**用户实机确认**：在最新 0.8.3 Yoga SST 实验 Kext 中启用 `-wex-yoga-tc5-sst` 后，HP Thunderbolt G4 拓展坞通过 USB-C 兼容模式恢复视频输出；**内屏 + 机身 HDMI + 拓展坞可使用三个独立画面**；拓展坞热拔插恢复正常。该结果证明 **SST 使用目标已达到**，尚不证明原生 MST 多显示流扩展或 TB4 控制器已经工作。

**冻结现有成功显示路径**：不要为改善 4K60 引入旧版 `-wex-yoga-hdmi2-route-only`、`-wex-yoga-hdmi2-link`、`-wex-yoga-hdmi4k60` 或修改 DDI5/TC Hotplug/训练/时钟；4K60 必须在从本成功分支创建的独立实验分支研究。继续保留经实机验证的 Kext 和整份 EFI。

**仍未解决、与 SST 点亮相互独立的限制**：

| 连接路径 | 2026-11-20 实际情况 | 现阶段判断 |
| --- | --- | --- |
| 4K 屏 → HP G4 DP（USB-C fallback） | macOS 只显示 4K30 选项 | 已有 DDI5 记录为 DP Alt Mode、2 lanes、HBR2；4K60 8-bit 4:4:4 超过 8.64 Gbps 有效带宽；是否存在 24/25Hz 仍由 EDID 和模式枚举决定，不是物理固定 30Hz |
| 同一 4K 屏 → 机身 HDMI | 能看到 4K60 选项，实际画面黑屏 | HDMI600 只放宽 300→600MHz 准入，未实现 SCDC/高速 TMDS 完整握手；仍需区分 TMDS 编码、PLL/PHY、模式回滚问题 |
| HP G4 两路输出 | SST 单流；旧版曾观察到两路镜像 | **未实现**真正 MST 两路独立画面 |

**解释界限**：实机成功已确认，但尚未收到本轮 `WEXYogaSSTFirstDPCD` / `WEXYogaSSTCapabilityMasked` 的运行时原始记录，因此不能据此断言每次重插都实际触发了 `port+0x1E` 屏蔽；现象与该修复机制一致。长时稳定、睡眠唤醒、TB4 模式尚未验证。

相关 HDMI 研究：`wex600/README.md` 和独立 HDMI4K60 实验分支（从本成功 SST 基线派生，禁止在本分支覆盖当前成功 Kext）。

---

## Purpose and boundaries

Successfully restored HP Thunderbolt Dock G4 display output in USB-C DP Alt Mode compatibility mode on 2026-11-20 with the explicit SST flag. This is **SST single-stream compatibility**, not native MST multi-stream support. Two displays behind the dock may mirror one SST stream; they are not independent desktops.

Source chain (all fixed):
- Official WhateverXe 0.8.3 commit: f26a36880c49ea1063393d943527808c0f38feca.
- Existing Yoga source overlay: wexdpdiag/prepare.py -> wex600/prepare_hdmi600_observe.py -> wexedid/prepare_edid_ab.py. Includes the eDP120 WM_ONLY, HDMI Deep8/HDMI600 and existing USB-C DDI5 diagnostics.
- EFI uploaded on 2026-11-20: WhateverXe executable SHA-256 e9a3d6b4cc38ef1b64dc390aba87a79ee0a7f4a3c6ec2d8603a267917f7eba13. The historical DP diagnostic CI executable was subsequently compared byte-for-byte with that uploaded EFI executable, and the SHA-256 matched.
- Installed Graphics 0.4.4 remains untouched. Current EFI has Lilu 1.7.3; the established build workflow uses Lilu 1.7.2 development headers. Do not replace the installed Lilu or Graphics as part of this test.
- No ThunderboltA73EProbe, AppleThunderboltNHI, HAL Type4, USB4, HDMI2 LightUpTMDS, SCDC, PHY, PLL, HPD or MMIO experiments are added.

## Exact modification

From Thatisjigen/WhateverXe acer/current at f7b9bf2229d323e37e8b1dfb87182f005eb7a277, transplant **only** the concept of AppleIntelPort::getDPCDInfo MST-cache masking:

1. Call the native DPCD getter first and preserve its original return value.
2. Require Intel 8086:A7A0, Display13 and mapped Type-C physical DDI5.
3. Optionally clear **only** internal port byte +0x1E, which caches MST capability, after the native read. Never directly change MST mode +0x117.
4. Install the native route only if the exact function symbol, offset 0x1DE0E and first eight instruction bytes match. A mismatch refuses the hook.
5. Limit IORegistry observations to the first eight qualified reads; no training retry or successful-result fabrication.

Legacy reference: https://github.com/Thatisjigen/WhateverXe/blob/f7b9bf2229d323e37e8b1dfb87182f005eb7a277/WhateverXe/kern_xe.cpp#L7304-L7328

## A/B boot flags (same exact Kext)

| Added boot argument | Action |
| --- | --- |
| Neither new flag | No extra DPCD hook or new IORegistry writes; established baseline |
| -wex-yoga-tc5-sst-observe | Installs read-only DPCD observation hook; does not hide MST |
| -wex-yoga-tc5-sst | Installs the hook and masks DDI5 cached MST capability |
| Both flags together | Refused (no new Hook, no masking), diagnostic status 5 |

Keep all current boot arguments as-is (especially -wex-yoga-edp120-admit, -wex-yoga-edp120-wm, -wex-yoga-hdmi-edid-deep8, -wex-yoga-hdmi600 and -wex-yoga-usbc-dpdiag); add only one new flag for a test. Do not add the abandoned -wex-yoga-hdmi4k60 or -wex-yoga-hdmi2-link experiments.

## Diagnostic properties

- WEXYogaSSTRequested, WEXYogaSSTObserveRequested: requested boot mode.
- WEXYogaSSTHookReady: whether the native DPCD route installed.
- WEXYogaSSTHookStatus: 0=off; 1=platform/path gate rejected; 2=donor symbol/bytes mismatch; 3=route failed; 4=installed; 5=conflicting flags.
- WEXYogaSSTFirstDPCD and WEXYogaSSTLastDPCD: little-endian uint32[9], indexed as version=1, qualified sequence number, DDI=5, MST cache before, MST cache after, native MST mode +0x117, low 32 bits of native result, did-mask flag, cumulative masks.
- WEXYogaSSTCapabilityMasked: true after the first actually masked read.

The additional XE runtime fields are appended at the end of the class so existing member offsets are preserved. Neither new flag means no extra Hook and no extra registry properties. Only first eight qualified reads publish diagnostics. A missing value does not imply MST absence; the hook may never have executed.

For a successful boot, collect:

    ioreg -p IOService -l -w0 | grep -E 'WEXYogaSST|WEXYogaUSBCDPTraining'
    system_profiler SPDisplaysDataType

## Reproduction procedure, regression guard and rollback (historical test checklist)

1. Keep the *entire* current EFI unchanged as recovery. Copy it to a separate test EFI. Replace only WhateverXe.kext, not other Kexts, ACPI, boot arguments, A73E/Type4 options or the macOS Graphics install.
2. Boot the new Kext without either SST flag. Confirm Metal, 1536MB VRAM, internal 3072x1920 @120Hz, and current chassis HDMI 4K30 output and color.
3. Test one 1080p60 monitor through HP G4, USB-C fallback, with -wex-yoga-tc5-sst-observe. Capture HookStatus, MST cache, native training results. A black screen is possible.
4. Remove observe mode; use -wex-yoga-tc5-sst. Verify actual first read was masked, macOS enumerated an external monitor, and a real picture appeared. HookStatus=4 alone is not a successful display.
5. Only if the single display works: test dock HDMI+DP mirror, then chassis HDMI + dock separate desktops, and finally gentle hotplug/reconnect. USB mouse disconnects and native clock cleanup remain separate hypotheses.

If masking happens but DP training remains NotReady/Busy, the patch is insufficient; use existing WEXYogaUSBCDPTrainingFirst1..8 and WEXYogaUSBCDPTrainingLast data for the next diagnosis.

The workflow builds with pinned MacKernelSDK, WhateverXe 0.8.3, Graphics 0.4.4 headers, and Lilu developer headers; runs the complete upstream test suite, source-safety checks and RELEASE/Compat tests. **Compilation does not prove actual video output**.

If internal display, HDMI or GPU acceleration regresses, immediately boot the unmodified original EFI, restore the old WhateverXe.kext in the experimental copy and remove the additional SST argument.

Do not merge into main before successful real-machine validation.
