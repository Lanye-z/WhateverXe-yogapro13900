# Yoga Pro 14s IRH8 · WhateverXe 0.8.3 HDMI 4K60 实验

> **尚未完成 Yoga 实机 4K60 验证。只能在独立测试 EFI 上使用。**
> 本分支从已验证的 0.8.3 WM_ONLY V2 + HDMI Trace 派生；不修改 main。

## 已验证基线（原样保留）

- 内屏 3072×1920 @120Hz：保留 -wex-yoga-edp120-admit 和 -wex-yoga-edp120-wm。
- 机身 HDMI 3840×2160 @30Hz：**完整编入已实机确认有效的 U27P10 EDID Deep8 补丁（wexedid）**。必须继续保留原启动参数 -wex-yoga-hdmi-edid-deep8；不会写入或替换 macOS 显示器覆盖文件。此前实测输出是 YCbCr 4:4:4 / 8 bpc，并非 RGB 8 bpc。
- 当前 HDMI Trace 可以保留 -wex-yoga-hdmi-hpdtrace；未经证实的 -wex-yoga-hdmi-first-hpd 保持关闭。
- 不修改 Graphics 0.4.4、Type-C DP、Thunderbolt 或系统安装。

## 本次增加的功能

修订说明：首个 4K60 测试 ZIP 遗漏了实机成功的 EDID Deep8 源码，导致即使没有启用 4K60 也出现伪色回归。旧 ZIP 已停用；本版构建必须先通过 Deep8 源码存在检查和颜色单元测试。

4K60 新功能默认关闭。**U27P10 颜色修复与 4K60 是两个独立启动参数，二者需要同时保留：-wex-yoga-hdmi-edid-deep8 -wex-yoga-hdmi4k60。** 仅后者控制高速 HDMI 2.0 实验，且必须同时满足实体 PCI 8086:A7A0、移动 Display13、已核准的 eDP 基线、Combo HDMI B。

1. 在 HDMI 原生 DDC 流程缓存当前连接器的 EDID 能力，解析 CTA HDMI VSDB / HDMI Forum VSDB，识别 SCDC 和最大 TMDS。
2. 通过 getOnlineInfo 原生模式计算路径调整 HDMI 源端 300MHz 上限；只有显示器明确支持 SCDC 且原生 I²C 适配器就绪时，才有条件允许高于 340MHz 的模式。
3. 已确认颜色正常的 U27P10 通过 EDID Deep8 限制原生深色模式（实际可为 YCbCr 4:4:4 / 8 bpc）；高速模式中的 SDR 8 bpc 规范化不强制把 YCbCr 改成 RGB。
4. 原生 LightUpTMDS 之前，通过 I²C 对 SCDC TMDS_Config 0x20 协商并回读，成功后同时更新源端 Transcoder 的 1/40 高时钟比率与 Scrambling 标志。失败时不启用高速链路。
5. 在显示器断开、EDID 重读、I²C 失败时拒绝沿用旧状态；不伪造显示器能力或 HPD。
6. 不对 PLL / PHY 写入未经机器验证的电压摆幅或时序参数；如果 4K60 仍黑屏，使用结果记录继续判断源端 PLL/PHY。

## 与历史实验的区别

以前 E1.1 只做 300→600MHz，能让 60Hz 选项出现，不等于有可用视频信号。此实验叠加 Display13 SCDC 适配，并对源端同步设置 0x11 高速 TMDS 标志；参考已经在 8086:A7A0 联想机器上测试过的 Display13 HDMI 2.0 代码，但没有宣称整机适配可直接通用。

参考：
- [WhateverXe Issue #41](https://github.com/b00t0x/WhateverXe/issues/41)：300→600MHz 的单独实验。
- [WhateverXe Issue #82](https://github.com/b00t0x/WhateverXe/issues/82)：594MHz TMDS、SCDC、PHY 实际测试（桌面 RPL-S / 虚拟机）。
- [Lenovo Air14 IRP8](https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh)：相同 A7A0 移动平台的 Display13 SCDC/HDMI 代码与单元测试。
- [Dynabook G83 HDMI 4K60](https://github.com/xiananliu/wex-modified-edition)：clock600 与 scdc-write 配套使用。

## 构建状态与测试顺序

必须先查看本分支的 GitHub Actions 工作流 yoga-hdmi4k60.yml 是否成功。**构建与测试未通过，禁止将新 Kext 复制进正在使用的 EFI。** 成功时只下载 Kext-only RELEASE 测试产物。

保留原 EFI 的恢复入口，在独立测试 EFI 里更换 WhateverXe.kext；第一次仅继续使用原参数 -wex-yoga-hdmi-edid-deep8（**不开启** -wex-yoga-hdmi4k60），先确认内屏 120Hz、HDMI 1080p 和 HDMI 4K30 颜色正常，再添加新参数尝试 4K60。只有显示器 OSD 与 macOS 同时显示 3840×2160 @60Hz、画面真实正确，才可判定 4K60 成功。

诊断命令：
    nvram boot-args
    ioreg -p IOService -l -w0 | grep -Ei 'WEXYogaHDMI4K60|N97FBHDMISCDC|N97FBHDMISourceLimit|WEXYogaEDP120'
    system_profiler SPDisplaysDataType

WEXYogaHDMI4K60HooksReady / I2CReady 只说明钩子是否安装；N97FBHDMISCDC 的结果只说明协商是否发生；均不代表显示器物理链路稳定。

任何模式切换造成持续黑屏、内屏异常、GPU 重启时，直接切换回未修改的 EFI，暂不再尝试增加默认延时、伪造 SCDC 回读值或盲写 PHY。
