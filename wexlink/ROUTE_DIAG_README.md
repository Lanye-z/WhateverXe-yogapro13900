# ⛔ STOP：该版本已在 Yoga 82Y7 实机出现严重回归，禁止继续使用

**2026-11-20 实机反馈：仅启用 `-wex-yoga-hdmi2-route-only`，首次重启后核显硬件加速丢失、机身 HDMI 外屏无法点亮。尚无原始故障 IORegistry，不能确认是路由地址、调用 ABI、重入还是显示初始化失败。此分支只保留用于复盘，绝非可用的诊断/4K60 修复包。**

立即恢复已验证的 `44520992061` Deep8 + HDMI600 构建中的原始 `WhateverXe.kext`，并从 boot-args 删除 `-wex-yoga-hdmi2-route-only` 和 `-wex-yoga-hdmi2-link`。单独删除参数不足以保证恢复，应一并还原 Kext。不要再尝试 60Hz 或直接替换此分支的任何后续构建。

---

# Yoga Pro 14s IRH8｜Display13 HDMI2 原生 TMDS 精确路由诊断版

**这是实验 Kext，不是已经修复 4K60 的稳定版本。请保留可独立启动的成功 EFI；不要直接覆盖日常 EFI。**

## 基线与定位

- 源基线：0.8.3 + 内屏 eDP120/WM_ONLY + 机身 U27P10 Deep8 伪色修复 + 300→600MHz 模式准入。对应此前已成功的 Actions 44520992061。
- 后续 SCDC/GMBUS 逻辑已在分支 `experiment/wex-0.8.3-yoga-hdmi2-gmbus` 中实现，但 Yoga 82Y7 实机 60Hz 黑屏后未记录任何 `N97FBHDMISCDC` 或 `N97FBHDMISCDCTransfer`。
- IORegistry 中存在 `N97FBOutputHooksReady=Yes`，却没有 `TGLWEGRoutePathObservations`。后者在 upstream 0.8.3 的另一条 TGL Framebuffer 路由安装，无法证明 Display13 已执行同一个 TMDS 包装器。
- 同 A7A0 参考机型将 Display13 原生 `LightUpTMDS` 定位于原生驱动镜像偏移 `0x50B22`。本版新增严格校验方法符号、8 字节指令前缀和硬件门控的精确路由。

## 本次实际修改

- 新增单独的 `XE::wrapDisplay13HDMI2TMDS`，**没有**复用 TGL 的通用 Path/Scanout 观察包装器，也不叠加第二个 Hook。
- 只有 `-wex-yoga-hdmi2-route-only` 或 `-wex-yoga-hdmi2-link` 存在、Intel A7A0、Display13、DDI B、成功的原输出路由和原函数精确指令匹配时，才安装此 Hook。
- **只观察模式：`-wex-yoga-hdmi2-route-only`；不添加 `-wex-yoga-hdmi2-link`。** 它只运行原生 LightUpTMDS，记录调用次数、像素时钟、原生返回值；绝不调用新增 SCDC 读写。
- **实际高速协商模式：`-wex-yoga-hdmi2-link`。** 仅在被调用的原生 HDMI 模式像素时钟高于 340MHz 时，进入原有 SCDC + GMBUS 逻辑，增加协商入口、所有权、能力、传输与结果分阶段标记。低速 HDMI 不会因 SCDC 失败而被拒绝。
- 不改动 eDP、内屏 120Hz、WM/DBUF、PLL、PHY、颜色和原有 EDID Deep8 补丁。
- Hotplug 首次接入故障暂未修复；本实验主要解决“已启用 SCDC 代码，但它根本没有被路由到 Display13 LightUpTMDS”的问题。

## CI 与实机测试原则

CI 能验证源码锚点、测试用例、驱动编译，却**不能证明实际硬件 Hook 在本机成功、源端 PLL/PHY 正常、SCDC 读写成功或切换后双屏恢复**。

**测试请分三个阶段，只有上一阶段保持内屏 120Hz / 4K30 Deep8 / Metal 1536MB 才继续。**

1. **A｜新 Kext 不添加新实验参数。** 保留原 `-wex-yoga-edp120-admit -wex-yoga-edp120-wm -wex-yoga-hdmi-edid-deep8 -wex-yoga-hdmi600` 等成功参数，不要加 `-wex-yoga-hdmi2-link`。
2. **B｜只诊断路由：** 末尾增加 `-wex-yoga-hdmi2-route-only`，**不要同时加** `-wex-yoga-hdmi2-link`。先在开机时接 HDMI 的条件下仅验证 4K30，不切换到 60Hz。预期 `WEXYogaHDMI2TMDSRouteStatus=4`，且在显示模式重新设置后出现 `WEXYogaHDMI2TMDSLast` 和 `WEXYogaHDMI2TMDSNativeLast`，没有新增 SCDC 记录。
3. **C｜真实高速协商：** 从 `boot-args` 移除 route-only，改为 `-wex-yoga-hdmi2-link`，启动后仍先验证 4K30。**仅在有可靠旧 EFI 和远程恢复手段、并可接受再次黑屏后重启时**才考虑一次 60Hz 实验。此时期待 `WEXYogaHDMI2TMDSHighSeen`、`WEXYogaHDMI2SCDCStage`、`N97FBHDMISCDCTransfer`/拒绝状态等。没有记录也需要分析，不表示成功。

绝不使用此前会出现 22MB 回归的旧 `-wex-yoga-hdmi4k60`。

## 新增观察字段与意义

| 字段 | 意义 |
|---|---|
| `WEXYogaHDMI2TMDSRouteStatus` | 0 未请求，1 条件不满足，2 找到安装阶段但符号/偏移未匹配，3 指令匹配但进入路由，4 精确 Hook 安装成功，5 路由失败，6 检测到已有 TGL 路由而拒绝重复安装 |
| `WEXYogaHDMI2TMDSRouteReady` | 仅表示路由安装成功 |
| `WEXYogaHDMI2TMDSLast` | 入口记录：次数、像素时钟、是否高速、标志和控制器匹配 |
| `WEXYogaHDMI2TMDSNativeLast` | 原生 LightUpTMDS 的返回值（仅在已调用原生时出现） |
| `WEXYogaHDMI2TMDSHighSeen` | 高速（高于 340MHz）入口是否触发 |
| `WEXYogaHDMI2SCDCStage` | 1 进入协商，2 所有权/环境前置检查失败，3 DDI 越界，4 EDID 能力或模式判据不通过，5 开始传输，6 传输/确认失败，7 协商成功 |
| `WEXYogaHDMI2SCDCCaps` | EDID 得出的 sink 能力、时钟、编码/位深及源端控制参数 |
| `N97FBHDMISCDCTransfer` | 真实 SCDC I²C 结果 |
| `WEXYogaHDMI2RouteHighRefused` | 高速 SCDC 前置协商失败时拒绝进入原生输出 |
| `WEXYogaHDMI2RouteLowReset` | 已启动过高速的情况下重新进入低速模式时的 SCDC 回退结果 |

采集命令（只读）：

```bash
ioreg -p IOService -l -w0 | grep -E 'WEXYogaHDMI2|N97FBHDMISCDC|WEXYogaHDMI600|WEXYogaHDMIEDIDAB'
system_profiler SPDisplaysDataType
```

严格不要把“路由安装成功”当作“4K60 已修复”；开机后插 HDMI 不识别仍属于另一项 HPD/枚举问题。
