# WhateverXe 0.8.3 — Yoga Unified HDMI2 Wake V4

> **V4 独立实验分支，基于精简启动参数的 Unified RC1（不是原始 V3）**。已有内屏 120Hz、AOC Deep8、HDMI600、HP G4 SST 默认启用；V3 的 `-wex-yoga-hdmi2-callsite-safe` 仍为显式开关。
>
> V4 新增 `-wex-yoga-hdmi2-wake-diag`（诊断）和 `-wex-yoga-hdmi2-wake-recover`（严格限次恢复候选）。**两项默认均关闭**，不得认为 V4 已经通过实机唤醒验证。用于复盘第二次 Display Wake 后 AOC 4K60 黑屏、随后手动 30→60Hz 可恢复的问题。
>
> **安全更新（2026-11-21）：旧 V4 B 组发生过开机三屏全黑，当时日志没有记录到恢复事务。现有 R3 在真实 FB1 Doze→Wake 中使用严限次的原生 SCDC 重新验证，并补足失败后 4K30 的受控清理；RELEASE 和 221 项软件测试通过，但未完成实机验证。请使用独立测试 EFI，优先核实 A 组能正常启动，不能直接将 B 组作为日常 EFI。**
>
> [V4 R3 HDMI Session 状态恢复说明](wexwakev4/README.md) · [R3 RELEASE + 221/221 软件回归通过](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44896752393) · [R3 独立 Kext 构建包](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44896752393/artifacts/14704845641) · [原 Unified RC1](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/integration/wex-0.8.3-yoga-unified-rc1)

---

## 以下保留来自 Unified RC1 的已验证基线与整合说明

# WhateverXe 0.8.3 — Yoga Pro 14s IRH8 Unified RC1

> **2026-11-21 当前集成候选版（一个 Kext、一套源码）**。目标硬件：Lenovo Yoga Pro 14s IRH8（82Y7），Intel Iris Xe `8086:A7A0`；实机系统 macOS 26.7.1（25G241），WhateverXe Graphics 0.4.4。**不等于已通过长期稳定性验证的正式日常版。**
>
> 本分支基于 [HDMI2 V3](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-hdmi2-scdc-gmbus-wait-v3) 的源码，不使用旧 `main` 的 0.7.0/E1.0/Video C 集成方案。只构建 **一个** `WhateverXe.kext`，没有 Daily/HDMI2 两套构建。

## 一、功能与补丁依赖（最重要）

| 实际功能 | V3 原始测试版所需参数 | 本 Unified RC1 行为 | 证据与边界 |
| --- | --- | --- | --- |
| 内屏 **3072×1920 @120Hz** | **`-wex-yoga-edp120-admit` + `-wex-yoga-edp120-wm`** | 两项默认启用 | admit 负责 720→800 MHz 模式准入；WM_ONLY 改善保存 120Hz 后的启动恢复，两项组合已实机工作 |
| AOC U27P10 **HDMI 伪色修复** | `-wex-yoga-hdmi-edid-deep8` | 默认启用，仅精确匹配显示器/端口/EDID | 限制 Deep Color 能力，使实际输出从 10 bpc 降到 8 bpc；**不是强制 RGB** |
| 机身 HDMI **4K60** | **`-wex-yoga-hdmi600` + `-wex-yoga-hdmi2-callsite-safe`** | HDMI600 默认启用；Callsite Safe **仍须显式添加** | 前者仅放开 300→600 MHz 模式准入，后者负责 V3 原生 SCDC/GMBUS 等待及高速源端配置；缺少后者不能保证 4K60 |
| HP G4 扩展坞 **外屏 SST** | `-wex-yoga-tc5-sst` | 默认启用 | DDI5 缓存 MST 能力屏蔽使 USB-C DP Alt Mode 兼容输出可用；**不是原生 TB4/USB4 修复，也不支持真正 MST 多路独立输出** |

**对本机的完整 4K60 + 正常色彩配置**：`HDMI Deep8 + HDMI600 + HDMI2 V3 Callsite Safe`。Deep8 解决颜色兼容性；HDMI600 和 Callsite Safe 才分别负责高速模式准入与链路准备。所有补丁仍保留 A7A0/Display13、端口、EDID、原生机器码等安全门控，失配时拒绝修改。

## 二、精简后的 boot-args（只适用于本集成版）

在独立测试 EFI 上保留此前已工作的其他兼容参数，**要启用 V3 4K60 再加最后一个参数**：

```text
-vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-hdmi2-callsite-safe
```

前五项 Yoga 功能开关已内置为默认启用，不再需要写：
`-wex-yoga-edp120-admit`、`-wex-yoga-edp120-wm`、`-wex-yoga-hdmi-edid-deep8`、`-wex-yoga-hdmi600`、`-wex-yoga-tc5-sst`。

不需要常驻调试时，可不加：`-wex-yoga-hdmi-colortrace`、`-wex-yoga-hdmi-mode-audit`、`-wex-yoga-usbc-dpdiag`、`tblog=577619`、`-v`、`keepsyms=1`。这不代表驱动内所有诊断代码已删除；只是不再默认启用对应观察功能。

**重要**：HDMI600 虽默认启用，但不添加 `-wex-yoga-hdmi2-callsite-safe` 时，仍可能出现系统请求高速模式却未准备好高速链路的情况；不应把这种状态称作“自动稳定 4K60”。

## 三、实测状态与未解决问题

- **原 V3 实机已验证**：AOC OSD 确认 3840×2160@60Hz 实际点亮；Metal 2 / 1536 MB 正常；SCDC 准备出现 `status=100`；源端 bit4/bit0 启用；回退 4K30 `status=101` 且两位清除。
- **仍有问题**：Apple 标志阶段多个显示器会反复黑屏/亮屏；启动日志记录了 FB0/FB1/FB2 多次 modeset、FB1 HPD/连接事件，仍有个别 SCDC NAK。长期稳定、睡眠唤醒和扩展坞在这一版 Kext 上的回归需要继续实测。
- **本 Unified RC1**：新整合代码通过 GitHub Actions 的 **221/221 软件回归测试、RELEASE 编译和 ZIP 校验**；**尚未等同于 Unified RC1 实机验证成功**。

## 四、构建、下载与回退

- [统一版 CI：221/221 通过（run 44881256951）](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44881256951)
- [统一版构建包（artifact 14698092112）](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44881256951/artifacts/14698092112)
- [详细设计、紧急禁用参数与验证步骤](wexintegrated/README.md)
- [V3 原版实机 4K60 成功记录](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-hdmi2-scdc-gmbus-wait-v3)
- [V3 SCDC/GMBUS 技术机制](wexhdmi2v2/SCDC_GMBUS_FIRST9_FIRST12_FIX_20261121.md)
- [SST 兼容修复机制](wexsst/README.md)

**只在可独立启动的测试 EFI 中替换 WhateverXe.kext**；不要修改已工作的 Graphics 0.4.4、Lilu 或直接覆盖日常 EFI。可用 `-wex-yoga-disable-integrated` 关闭五项默认集成能力（不会关闭显式添加的 Callsite Safe），也可使用详细文档中的逐项禁用参数。出现启动黑屏时优先用原来完整的可启动 EFI 回退。

旧 `main` 仍是历史实验主线；**本分支目前未合并进 `main`**。
