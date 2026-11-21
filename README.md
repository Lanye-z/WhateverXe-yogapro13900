# WhateverXe 0.8.3 — Yoga HDMI2 V3 GMBUS Wait（2026-11-21）

> **本分支为 V3 原始实验基线（所有 Yoga 功能仍通过正向 boot-args 选择），不是默认内置修复的 Unified RC1。**
>
> 最新单一集成候选版（五项已验证修复默认开启，HDMI2 V3 仍保留 opt-in）：[Yoga Unified RC1](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/integration/wex-0.8.3-yoga-unified-rc1)。

基于固定的 WhateverXe **0.8.3** + WhateverXe Graphics **0.4.4**，目标 Lenovo Yoga Pro 14s IRH8（82Y7）、Intel `8086:A7A0`，macOS 26.7.1（25G241）。V3 GitHub Actions [run 44877735459](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44877735459) 已通过 **221/221 软件测试**。本分支**不是长期稳定性认证版本**。

## 一、功能组合与依赖（V3 原版）

| 功能 | 必需的 V3 正向启动参数 | 修复机制及结论 |
| --- | --- | --- |
| **内屏 3072×1920 @120Hz** | **`-wex-yoga-edp120-admit` + `-wex-yoga-edp120-wm`** | admit：eDP 模式准入 720→800 MHz；wm：WM_ONLY 的两像素/CDCLK 条件，已帮助保存 120Hz 后的启动恢复；完整组合已实机工作 |
| **AOC HDMI 伪色修复** | **`-wex-yoga-hdmi-edid-deep8`** | 对精确匹配 U27P10 的 EDID 关闭部分 Deep Color 能力，原生驱动选择 **8 bpc**；实机证明颜色正常；不是强制 RGB |
| **机身 HDMI 3840×2160 @60Hz** | **`-wex-yoga-hdmi600` + `-wex-yoga-hdmi2-callsite-safe`** | HDMI600 仅准入 300→600 MHz；V3 在原生 HDMI LightUpTMDS 调用点完成 SCDC/GMBUS 有界等待、接收端读写/读回并配置高速源端；缺任何一项不能声称完整修复 |
| **HP G4 扩展坞外屏点亮（SST）** | **`-wex-yoga-tc5-sst`** | DDI5/Type-C DP Alt Mode 路径隐藏缓存 MST 能力，恢复单流 SST 输出及此前实测热拔插；**不等于 TB4/USB4 Root Switch 修复或真正 MST** |

**针对当前 AOC 的 4K60 正常颜色**：还要同时启用 Deep8。Deep8 修颜色而非代替 HDMI2 链路协商；HDMI600 也不单独提供 scrambling / high TMDS 时钟比率。

### V3 原始可用参数示例（无常驻诊断）

```text
-vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-edp120-admit -wex-yoga-edp120-wm -wex-yoga-hdmi-edid-deep8 -wex-yoga-hdmi600 -wex-yoga-tc5-sst -wex-yoga-hdmi2-callsite-safe
```

其他 EFI 参数应以本机当前可用配置为准；`-v`、`keepsyms=1`、`tblog=577619`、`-wex-yoga-hdmi-colortrace`、`-wex-yoga-hdmi-mode-audit`、`-wex-yoga-usbc-dpdiag` 主要用于排错/观察，**不是上表实际修复的必要开关**。本分支所有上述功能的正向参数仍须保留；**只有 Unified RC1 让其中五项默认生效**。

## 二、V3 实机验证（与旧阶段“4K60 黑屏”区分）

2026-11-21 的 `stable60` / `rollback30` 两份采集日志及 AOC OSD 确认：

| 项目 | 4K60 | 回退 4K30 |
| --- | --- | --- |
| AOC U27P10 实际显示 | 3840×2160@60Hz，画面正常 | 3840×2160@30Hz，画面正常 |
| 像素时钟 | 533.25 MHz | 297 MHz |
| `TRANS_DDI_FUNC_CTL` | `0x90030211` | `0x90030200` |
| 高速 bit4 / scrambling bit0 | 均为 1 | 均为 0 |
| V3 CALL-site 准备状态 | **100：SCDC 准备成功** | **101：低速恢复成功** |
| Metal | Metal 2，1536 MB 正常 | 正常 |

原生 GMBUS 读取曾记录 `0x8200`（未就绪）→有界等待→`0xCA00`（就绪）的成功路径，同时仍留有个别 **NAK / `0xE00002ED`**。V3 解决“未就绪时提前返回”的一部分问题，**不伪造 ACK，也不等于所有 SCDC 请求都成功**。

与更早的 HDMI2 V2 不同，V3 继承了 **OrderFix：Display13 TC 原字节校验在 CALL-site 改写之前完成**，以避免此前 22 MB VRAM/Metal 丢失问题。本次实机的 Metal 正常且 OSD 4K60 已点亮，但只能证明测试时有效。

## 三、启动闪屏仍未解决

Apple 标志阶段出现**多个显示器**反复黑屏/亮屏，而非只有 AOC HDMI。早期启动日志记录 FB0 内屏、FB1 HDMI、FB2 外屏多次 `modeset`，FB1 还存在 HPD/连接状态变化；部分高速 SCDC 调用失败后又成功。

**不能据此认定 V3 是所有闪屏的根因**：更早未启用 HDMI2 Callsite Safe 的 OrderFix 对照也记录了高速模式尝试和显示重配置。实际冷启动、睡眠唤醒、SST 热拔插和长时间可靠性需要继续独立验证；不应通过盲目增加 GMBUS 等待、强制 HPD 或移植旧全局 `LightUpTMDS` Route 来“修复”。

## 四、源码、构建与安全回退

- [V3 CI 与原始 221/221 软件验证](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44877735459)
- [V3 SCDC GMBUS 等待准确范围与失败闭锁](wexhdmi2v2/SCDC_GMBUS_FIRST9_FIRST12_FIX_20261121.md)
- [V2 CALL-site 安装顺序回归及 OrderFix](wexhdmi2v2/ORDERFIX_20261121.md)
- [内屏 WM_ONLY 冷启动记录](wexbootfix/README.md)
- [AOC EDID Deep8 实测记录](wexedid/README.md)
- [USB-C SST 原理及边界](wexsst/README.md)
- [历史 HDMI4K60 调研与抓取工具](wex4k60/README.md)
- [统一版（单一集成 Kext）](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/integration/wex-0.8.3-yoga-unified-rc1)

**仅在可独立启动的测试 EFI 上验证**。保留原完整 EFI 和已工作的 Graphics 0.4.4。现有 V3 用的是正向参数；要停止主动 SCDC，只移除 `-wex-yoga-hdmi2-callsite-safe`，但这并不阻止 HDMI600 在开机时让系统尝试高速时序。若出现开机黑屏，应使用原完整 EFI 回退，不应只依赖能否进入 macOS 修改 NVRAM。

旧 `wexhdmi2v2/README.md` 顶部的 **V2 rejected / unsafe** 事件是历史记录，不应误认为 V3 也未实现 4K60；V3 的真实结果与仍有的问题以本文为准。
