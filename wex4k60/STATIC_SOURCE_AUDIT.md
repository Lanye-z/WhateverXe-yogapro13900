# WhateverXe 0.8.3 HDMI 4K60：第一轮源码核对记录（2026-11-20）

## 1. 有明确源码依据的结论

**A. Display13 已有原生 GMBUS/DDC 观察路径，第一阶段不需要新增内核 Hook。**

在官方固定源码 `f26a36880c49ea1063393d943527808c0f38feca` 的 `WhateverXe/kern_xe.cpp` 中：

- `processDisplay13FramebufferOutput()`（约第 7217–7320 行）将
  `AppleIntelFramebufferController::hwDoGMBusRequest` 路由至
  `XE::wrapDisplay13GMBus`，并将安装状态记录在 `N97FBGMBusObservationReady`。
  同一个 Display13 安装阶段还有 `ReadRegister32`、`WriteRegister32`
  的观察/适配，不需要我们为取证另装 GMBUS 路由。
- `XE::wrapDisplay13GMBus()`（约第 7793–7828 行）会调用原生 GMBUS
  实现并记录 `N97FBGMBusEntry`、`N97FBGMBusLast`、
  `N97FBGMBusHistoryLast` 及前 16 次请求的 `N97FBGMBusFirstN`。
- `N97FBGMBusLast` 是 little-endian `uint64_t[21]`：
  `[0]` schema 3，`[1]` 请求序号，`[2]` GMBUS bus，
  `[3]` speed，`[6]` 原生请求偏移 0x28 的值，
  `[7]` 原生请求偏移 0x38 的值，
  `[8]` 原生返回状态，`[9]` IOI2CRequest.result，
  `[15]` 采样数、`[16]` 记录的错误数。
  在未独立核验结构体版本前，0x28/0x38 不强行命名为某种语义。
- 上述字段**可能是 EDID DDC 事务而非 SCDC**；最后一次观测不等于
  4K60 切换瞬间一定发生了新的 I2C 请求。比较前后的 `[1]` 序号，
  并将时刻、接口、显示器、实际画面记录一起核对；不得凭缺失记录
  断言 SCDC 肯定失败，也不得将 GMBUS 成功解释为 HDMI 4K60 成功。

源码：
https://github.com/b00t0x/WhateverXe/blob/f26a36880c49ea1063393d943527808c0f38feca/WhateverXe/kern_xe.cpp#L7292-L7304

https://github.com/b00t0x/WhateverXe/blob/f26a36880c49ea1063393d943527808c0f38feca/WhateverXe/kern_xe.cpp#L7793-L7829

**B. TGL 的通用 LightUpTMDS 观察路由不能等同于 Display13 HDMI 路由。**

官方代码的 `wrapTGLLightUpTMDS` 在约第 18977 行，
而该包装函数在第 13156–13166 行的 `TGLWEGRoutePathObservations`
路由集合中注册。旧版 `wexlink` 文档已经指出：
`N97FBOutputHooksReady=Yes` 不代表 Display13 的 HDMI LightUpTMDS
实际上会调用 TGL 包装函数；独立的 Display13 `LightUpTMDS` Hook
实验随后发生用户实机核显加速丢失。尚未证实其中具体是符号地址、
ABI、重入还是初始化其他条件触发，**在取得直接证据前禁止重新启用**。

源码：
https://github.com/b00t0x/WhateverXe/blob/f26a36880c49ea1063393d943527808c0f38feca/WhateverXe/kern_xe.cpp#L13156-L13167

https://github.com/b00t0x/WhateverXe/blob/f26a36880c49ea1063393d943527808c0f38feca/WhateverXe/kern_xe.cpp#L18977-L18986

历史事故：
https://github.com/Lanye-z/WhateverXe-yogapro13900/blob/experiment/wex-0.8.3-yoga-hdmi2-route-diag/wexlink/ROUTE_DIAG_README.md

**C. HDMI600 仅扩大模式准入，不是完整物理视频链路修复。**

在 `wex600/prepare_hdmi600_observe.py` 中，保护性补丁只将
`AppleIntelFramebuffer::getOnlineInfo` 的 `300000000`
立即数改成 `600000000`。它不执行 SCDC 协商，也不证明
源端或接收端使用了正确的高速 TMDS 配置。

历史分支：
https://github.com/Lanye-z/WhateverXe-yogapro13900/blob/experiment/wex-0.8.3-yoga-deep8-hdmi600-observe/wex600/README.md

## 2. 目前仍属于假设、需要下一步证据的部分

| 待确认 | 需要什么证据 |
| --- | --- |
| 4K60 是否实际请求 >340MHz 的 TMDS character rate | 目标像素时钟、色深、RGB/YCbCr 444/420，显示器 EDID/HF-VSDB |
| SCDC sink 端写 0x20 是否缺失或错误 | 明确的 HDMI DDC/SCDC 事务及读回；现有 GMBUS 记录不一定包含该操作 |
| source scrambling/1:40 ratio 是否匹配 sink | 原生 HDMI 控制和高速模式时序/状态；当前只读日志可能不具备该观察能力 |
| 4K60 黑屏后切回 4K30 是否有资源或时钟回滚缺陷 | 成功前、黑屏时、恢复后的 Pipe/PLL/DBUF/Clock 及真实 OSD 对照 |
| 物理线缆/显示器高速兼容是否影响结果 | 相同线缆、相同插口的稳定 4K30 和失败 4K60 对比，必要时用已知正常系统验证 |

Linux i915 的成熟实现将 sink SCDC 配置与 source 端时钟/扰码
作为组合条件；这提供研究路径，但不能把 Linux 写法或寄存器
地址未经验证就移植到 Apple Display13：

https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/235f2b548d7f4ac5931d834f05d3f7f5166a2e72/drivers/gpu/drm/i915/display/intel_hdmi.c

## 3. 已实施的安全研究动作

- 从 SST 实机成功分支创建独立的 HDMI4K60 分支，当前不改
  WhateverXe、EFI、Graphics、Lilu、Thunderbolt。
- `wex4k60/collect.sh` 只读采集，包含现成 `N97FBGMBus*`
  以及时钟、画面和系统日志；不自动切换刷新率。
- `wex4k60/compare.py` 解析 `N97FBGMBusLast` 的已知字段、
  对照模式与 clock 并报告未知项，不构造不存在的 SCDC 状态。
- 先要 4K30 正常样本和此前 4K60 失败样本；若无法安全
  保证恢复，不要求用户再次将屏幕切成 60Hz。

**当前判定：SST 功能已修复；HDMI4K60 仍处于定位阶段，不应发布或部署 HDMI 修复 Kext。**
