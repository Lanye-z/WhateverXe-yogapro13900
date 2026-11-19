# Yoga Pro 14s IRH8 · HDMI2 高速链路独立实验（默认关闭）

**基线：Actions 44520992061 / a508938a 的 WM_ONLY + U27P10 Deep8 + HDMI600。原 main 和经过实机验证的分支均未修改。**

## 为什么必须重做

实机已确认：在 HDMI600 开启、机身 HDMI 开机前已连接时，4K30 / Deep8 / 内屏 120Hz 正常；4K60 选项出现，但切换后外屏无信号，随后切回 30Hz 导致内外屏同时黑屏，拔线也不能恢复。故障状态下 macOS 仍能远程连接。这不仅是 SCDC 问题，还可能涉及 Display13 时钟/Pipe 回滚。此前另一个 -wex-yoga-hdmi4k60 实验曾导致 22MB/内屏缩放回归，禁止使用旧参数和旧 Kext。

**本分支是源代码验证阶段，CI 通过也不代表实机可用。当前增强版与不含 GMBUS 补丁的 `experiment/wex-0.8.3-yoga-hdmi2-link-safe` 分支分开，不覆盖任何稳定版本。所有新增逻辑都只在显式指定 -wex-yoga-hdmi2-link 时启用。**

## 具体差异

1. 完整复用已验证的 `wex600/prepare_hdmi600_observe.py`：600 MHz 模式准入、Deep8、内屏 120Hz、水位/时钟/颜色补丁全部保持不变。
2. 复用 upstream 自带的 `wrapTGLLightUpTMDS` 观察包装器，**不重新安装 LightUpTMDS 或 getOnlineInfo Hook**；避免旧实验的重复 Hook 问题。
3. HDMI-DDC 捕获 EDID CTA/HDMI Forum VSDB、SCDC present 和接收端能力；读取与缓存有连接代数检查，替换显示器后不复用旧能力。
4. 仅当本机 A7A0 / DDI B 严格门控通过、像素时钟 **高于 340MHz**，才调用本机原生 I2C 路径访问 SCDC 0x20，按高 TMDS 时钟配置接收端 high ratio + scrambling，读回成功后再修改原生控制结构中的对应源端位；失败则拒绝该高速 LightUp。
5. 一旦曾经启用高速链路，下一次低速 LightUp 尝试先清除接收端高速配置，但低速 SCDC 复位失败**不会阻止**原有低速 LightUp；原生高速 LightUp 失败时也尽力复位接收端。
6. 不新增 SDR 颜色转换、深色覆盖、GCP/MMIO 直写；不修改 eDP/DBUF/WM、GPU 资源分配和 Thunderbolt/DP 路径。
7. 严格筛选标准 SCDC 请求，扩展原生 GMBUS 状态轮询以处理 sink 的硬件就绪等待，50ms 有界超时，拒绝不匹配的驱动指令位置。

## 关键风险及尚未完成

- **已在本分支补充 SCDC 所需的 GMBUS HW_RDY 有界轮询**，限定于本机 HDMI2 开关、原生 DDI B、标准 SCDC 0xA8 读写请求和准确的两个调用位置。原 EDID 轮询保持不变；仅在源码字节匹配时启用，观察字段为 `WEXYogaHDMI2GMBusWaitReady`。这一功能已做模拟测试，但尚未在 Yoga 82Y7 的真实 DDC 总线上验证。即便 GMBUS 轮询成功也不保证 PLL/PHY 和 4K60 出图。
- 这里的源端字段位置和时钟逻辑来自同 GPU 但不同 Lenovo 机器的工程，未在 Yoga 82Y7 实测确认。
- 共享时钟、Pipe 和模式切换失败后恢复均尚未通过实机验证；可能仍出现需要重启才能恢复的黑屏。**本版本不能作为日常主 EFI。**
- 600MHz 版本已有的“必须插 HDMI 开机才能识别”的热插拔问题没有被本分支修复。
- 物理视频是否成功只能靠显示器 OSD + 视频实际输出验证，不能只看 `Status=4` 或 macOS 的刷新率选项。

## 测试条件

**使用独立 EFI、完整备份旧 WhateverXe.kext；恢复 EFI 能够不依赖当前显示器独立启动，远程操作可用后再开始。**

第一次换 Kext **不添加新参数**：保留 `-wex-yoga-hdmi-edid-deep8`、内屏 120Hz 和 `-wex-yoga-hdmi600`，只测试已验证的 4K30 和 Metal。第二次仅增加 `-wex-yoga-hdmi2-link`，仍然先停在 4K30；确保没有新的黑屏或加速回归。不要添加 `-wex-yoga-hdmi4k60`。

观察字段：`WEXYogaHDMI2LinkEnabled`、`WEXYogaHDMI2I2CReady`、`N97FBHDMISCDC`、`N97FBHDMISCDCTransfer`、`WEXYogaHDMI2HighRefused`、`WEXYogaHDMI2LowReset`、`WEXYogaHDMI600Status`。

**除非旧 EFI 可直接恢复且不介意再次出现需要重启的双黑屏，否则不要尝试 60Hz。** 如果 60Hz 再次无信号，保留远程访问数据，优先通过删除高速参数并正常重启恢复，而不要连续多次切换显示模式。

参考：<https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh> 的源码及 <https://github.com/b00t0x/WhateverXe/issues/41>。该参考机型并不等同于 Yoga 82Y7，已有能力只能作为移植依据，不能替代本机实测。
