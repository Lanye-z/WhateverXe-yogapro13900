# 借鉴 WhateverXe upstream Issues 的 Yoga A7A0 HDMI 2.0 方案（2026-11-20）

## 已经直接核实的公开源码及实机证据

### #41：时钟准入，不是 HDMI2 的完整实现
https://github.com/b00t0x/WhateverXe/issues/41
- ADL-S UHD770（0x4680）在 macOS Tahoe 26.7，通过 `getOnlineInfo` 将 300MHz 改为 600MHz 后，作者验证 533.12MHz/4K60 的正常输出。
- Issue 自己明确声明 **没有增加 SCDC、scrambling 或链路握手**。本机 `-wex-yoga-hdmi600` 已是相同类别的准入工作，不能再次仅移植 300→600。

### #82：真正的高 TMDS / SCDC / 时钟 / 硬件物理输出组合
https://github.com/b00t0x/WhateverXe/issues/82
https://github.com/gkostadinov/WhateverXe-RaptorLakeS/commit/98a22e3
https://github.com/gkostadinov/WhateverXe-RaptorLakeS/blob/main/WhateverXe/kern_hdmi_link.hpp
- 作者在 A780 Raptor Lake-S UHD770 iGPU **虚拟机直通**（非本机 A7A0 裸机）报告 3840×2160@60、594MHz TMDS、scrambling 开启、实际可见画面及 Metal。
- `HDMILink::plan` 按 `TMDS_kHz = pixel_kHz*bpp/24` 规划 RGB/444；>340MHz 设置 SCDC `0x20=0x03`，源端 `TRANS_DDI_FUNC_CTL` bit4|bit0=`0x11`。
- 在 `wrapADLSSetupClocks` 决定 24bpp 限制并在 `wrapADLSPllDivisors` 修正 deep-color PLL；`adlsHDMINoteDDC` 在 GMBUS EDID 后记录 sink 能力；`adlsHDMILinkBeforeEnable` 在 `wrapTGLEnablePort` 原生启用前操作 SCDC 和源端寄存器，`AfterEnable` 处理 GCP。
- **注意这个版本的不足：** `adlsHDMILinkBeforeEnable` 虽记录 SCDC readback，却没有以“读回与预期相同”作为源端置位的硬性门槛，不可原样复用；同时它根据已 enable 的 Transcoder 搜索并直接写 MMIO，时序必须按本机 Display13 重验。
- 相关提交 `1ecfe42` 对 ADL-S/RPL-S Combo PHY 电压摆幅作 VBT 修正；`a7d72a4` 跳过 DP-only HDCP 以避免固定 HDMI 掉链；这些都是平台专属，**禁止移植寄存器/PHY 常数到 Yoga**。
- 相关提交 `b97f677` 又把 10-bit Deep Color 改为默认关（已发生显示器黑屏）。本机 Deep8 已成功，强烈建议保留 24bpp/8bpc，不需要 GCP deep-color 扩展。

### 同为 8086:A7A0 的 Lenovo Air14 IRP8 实现：更接近 Yoga 结构
https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh
https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh/blob/main/sources/WhateverXe/WhateverXe/kern_display13_hdmi_scdc.hpp
https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh/blob/main/sources/WhateverXe/WhateverXe/kern_display13_hdmi_caps.hpp
- 作者报告内屏 120Hz + 机身 HDMI 2560×1440@144Hz 可用，但仓库明确记载 GPU hang、长期稳定性未解决，**并没有在该机上验证 4K60**。
- `Display13HDMI::negotiateSCDC`：按 sink 0x01 版本/0x02 source version/0x20 TMDS_CONFIG 读改写、读回，失败恢复旧值；只在 `complete=true` 时产出 sourceFlags=`0x11`。其 `scdcReadRequest` 使用指针写后 repeated-start 读，避免把 GMBUS indexed-read 当作所有场景通用方案。
- 它另设条件 `sourceSCDC`，sink EDID 自称 600MHz **不足以**说明 source SCDC 已可用。
- 参考工程确实将其接到 Display13 的 `LightUpTMDS` hook；我们早期 `route-only` 实机已发生 Metal 加速丢失，**不能直接移植该 hook/trampoline**。

### 失败案例用于排除“加上开关必定有效”
- https://github.com/b00t0x/WhateverXe/issues/155：另一 TGL 设备试过 `-wex-hdmi-clock600` / `-wex-hdmi-scdc-write` 仍损坏；不同的 Combo PHY 布线、色彩/时钟可能是根因。
- https://github.com/b00t0x/WhateverXe/issues/74：一个 HDMI 紫色/伪色故障，先于 donor 消费 EDID 阶段修正 8bpc/色彩能力，和 Yoga 已成功的 Deep8 思路一致。

## 对 Yoga 82Y7 / A7A0 的最小方案（静态设计）
本机成功基线：
- Mac macOS Tahoe 26.7.1、WEX 0.8.3、Graphics 0.4.4，A7A0；
- 机身 HDMI U27P10 在 4K30/297MHz YCbCr444 8bpc 正常；
- EDID HF-VSDB 最大 600MHz、SCDC_Present=1；
- `-wex-yoga-hdmi600` **已经**允许高像素时钟模式；
- 原生 `LightUpTMDS 0x50B22 -> 0x48BB6`；`0x4904A–0x4905C` 将 `[DisplayPath+0x12C]` 写入 `TRANS_DDI_FUNC_CTL`，原生回读/重写路径也存在。

### 建议独立、默认关闭的新功能路径
1. 沿用已成功的 Deep8 (8bpc/24bpp)、HDMI600 和 SST，不再重写 EDID 颜色，且只作用于物理 HDMI DDI B 的有效连接。
2. 由真实 detailed timing + 实际 encoding / bpp 决定 TMDS character rate。仅对 **4:4:4 或 RGB 8bpc 且 rate>340MHz**，且 EDID/sink/source/port 均通过校验时要求 SCDC；YCbCr420、DVI 或状态不明确时不可盲设。
3. 采用 Air14 的严格 SCDC 顺序和失败恢复，不在未知 GMBUS 锁下阻塞；遵从 `controller+0x9C8` 原生 I2C/GMBUS 分支生命周期。必须以 sink 回执成功作为 source bit0/4 设置的先决条件。
4. 源端优先在原生 `DisplayPath+0x12C` shadow 即将被 `0x48BB6` 消费前做掩码 `(value & ~0x11U) | (high ? 0x11U : 0)`，不能固定 Pipe2、不能整字覆盖、不能在已经启用的 Pipe 上无时序写 MMIO。
5. 借鉴 #82 的 PLL/clock 思路，但在本机 **8bpc** 下 `TMDS=pixel_clock`，第一轮不必引入 deep-color 的 PLL 乘数，也不引入 HDCP/PHY 电压修改。
6. 如果当前已安装 Display13 寄存器/GMBUS 观察器没有足够的安全预激活入口，就先单独验证新的 route ABI；旧的 `LightUpTMDS` Route-only 会导致丢加速，不能合并到工作 EFI。
7. 实机验收：真实显示器 OSD/画面 4K60、源端 FUNC_CTL bit0/4=1、sink SCDC 0x20=3、稳定返回 4K30、内屏 120Hz、三屏 SST+hotplug、Metal 均保持；CI 构建只验证代码，**不证明 4K60 修复**。

## 修复 compare.py 文件路径提示
用户执行 `~/Desktop/Yoga_HDMI4K60_hdmi30_20261120_172654.zip` 报 `Capture must be a folder or ZIP`，本质上是该路径无法被脚本确认存在/为有效 ZIP，**不是 HDMI 寄存器故障**。
先本机只读查询：
```bash
find "$HOME/Desktop" "$HOME/Downloads" -maxdepth 4 -type f \( -iname '*HDMI4K60*hdmi30*.zip' -o -iname '*hdmi30*.zip' \) -print
```
用找到的 **真实路径** 执行 `python3 wex4k60/compare.py "/absolute/path/actual.zip"`；如果没有旧文件，直接在 **正常 4K30** 下 `bash wex4k60/collect.sh hdmi30`，不切换 4K60。
