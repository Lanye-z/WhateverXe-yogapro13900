# WhateverXe 0.8.3 — Yoga Unified Wake V4（2026-11-21）

> **实机风险警告：旧 V4 B 组曾在首次启动进入桌面时三屏全黑，远程系统仍可访问。** 17:43 的诊断记录 HDMI HPD 变化、FB0/FB2 `kIOReturnNotReady`，但没有 V4 恢复事务 event4/110，故不能把该次启动故障直接归因于 SCDC 恢复。R3 尚未实机验证；请保留可回退 EFI，禁止旧 B 包用于日常运行。



**实验候选，不是已实机确认的唤醒修复。** 本分支从已通过 CI 的 [Yoga Unified RC1](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/integration/wex-0.8.3-yoga-unified-rc1) 的 **提交 `72ee3bca81c17f97382707ddf51b6818d295a3d7`** 派生。仅新增 `wexwakev4/` 的最小补丁和独立 CI；未覆盖 Unified RC1、原 V3、旧 `main` 或任何现有 EFI。

## V4 R3 — HDMI Session State Recovery（本分支最新修复候选）

**针对 18:45 日志的直接证据：**
- A 组 R2 的 `WakeRejectLast` 记录 `generation=25, pipe=1, pixelHz=533250000, status=10, flags=0xCB, maxKHz=0, armedPipe=3`；
- 同一次 `WakePowerLast` 显示 FB1 从 Doze(1)→Wake(2)，原生返回 0；该原生回调运行期间执行了上面的 status10 高速 CALL-site；
- 随后 `WakeLast` 已达到 CTA generation=29、maxTMDS=600000，但没有重新执行成功的高 TMDS SCDC 协商（`armedPipe` 仍为 3）；
- 因此**这次黑屏不等同于 GPU 无法 modeset**，而是高 TMDS 的 SCDC 能力缓存与原生模式设置时序错位。用户观察到“切 30Hz 仍黑，再切 60Hz 才亮”与此高度一致，但尚未采到 30Hz 那次 CALL-site。

**R3 修改两部分：**

1. 保留 R2 基于**同一 FB1 的原生 Doze→Wake 回调**的受限高 TMDS 重新协商候选：只有曾真实 `status=100`、开机后至少 90 秒、完成原生 Doze 至少 3 秒，并且重新获取与上次成功会话**逐字节相同**的 AOC 基本 EDID，原生当前 CTA 尚未就绪时，才可一次性用此前已经验证的能力执行原生 SCDC read/write/readback。B 组成功会返回 `status=110`。没有新 Hook、定时器、HPD 重置、PHY/PLL 修改或强制 modeset。
2. **补上 4K60 黑屏后转 4K30 的状态清理缺口**：V3/V2 为避免误操作，在 EDID 更新把 `armedPipe` 清为 3 时，会禁止无历史高速令牌的低速 SCDC 配置（`status=52`）。R3 只有在**同一次真实 Doze→Wake 中曾发生高模式 `status=10`、随后新 CTA 已恢复有效、同一已验证 AOC 128 字节 EDID 未变、现有源端寄存器仍带高速标志、原生 Wake 已成功完成**时，且距离原生 Wake 成功不超过 **5 分钟**，才允许现有 30Hz CALL-site 执行正常的低速 SCDC 重置读回和源端标志清理；成功记录 `event=7/status=101`。**不会自动把 60Hz 切换到 30Hz**，只是修复用户主动切 30Hz 时的清理路径。

**A/B 含义与风险**：
- A 组：`-wex-yoga-hdmi2-callsite-safe -wex-yoga-hdmi2-wake-diag`。仅增加 R3 判据记录，不执行新的 fallback。该组本来就能开机正常显示，但 4K60 唤醒黑屏可能保持原状。
- B 组：A 组基础上加 `-wex-yoga-hdmi2-wake-recover`。只有它允许上述两种受限事务。**历史 B 组曾开机三屏全黑，且当时没有 status110，因此 R3 是否消除该启动异常仍未知。不能把 RELEASE 编译/221 项测试通过当作实机安全保证。先备份 EFI、确保远程访问可用，在确认新 A 组无启动回归后，才考虑受控 B 测试。**
- 之前 BootSafe R1、PowerWake R2、旧 V4 包请勿与本版混用。新的构建包名为 `WhateverXe_0.8.3_YOGA_UNIFIED_WAKE_V4_SESSION_R3_TEST.zip`。

事件判读：`WakeRejectLast` 的 flags 在 R3 新增 bit13（基本 EDID 与已验证会话完全一致）、bit14（新连接代次）、bit15（本代已经尝试过）；`WakeActionLast` 原有 event4=恢复开始、5=高速成功、6=高速失败之外，新增 **7=经过验证的低速 SCDC 清理成功**。状态 `110` 或 `101` 只证明 SCDC 事务成功，并不等于物理显示器一定恢复画面。

---

## V4 PowerWake R2 — 历史候选（由 R3 替代）

**18:21 最新 A 组证据**：macOS 于 18:21:06 将 FB0/FB1/FB2 从 Wake 转入 Doze；18:21:14 DDI1 HPD 低→高；18:21:24 FB1 恢复 533250000 Hz 4K60 的 V3 CALL-site 返回 **status=10**。记录 \`WEXYogaHDMI2WakeRejectLast\` 显示 generation=25、flags=0x0B、maxKHz=0、armedPipe=3（相同物理 HDMI-B、AOC 有效 EDID 基本块、先前存在真实成功会话，**当前 CTA 能力未形成**）。稍后 \`WakeLast\` 为 generation=29、flags=0x1F、maxKHz=600000，但此时原生高速 modeset 已结束。

这直接支持 **EDID/CTA 高速能力就绪晚于原生 4K60 LightUpTMDS** 的竞态；仅在 30Hz 与 60Hz 间切换可再次触发成功模式设置，但第一次切 30Hz 未必重建完整的接收端高速状态。问题不是用户主动刷新率设置错误。

R1 原门控“观察到 HDMI-B transcoder bit31 清零”在 Display Sleep 的 Doze 流程中并非可靠信号；R2 改为直接观察**已有的** \`XE::wrapDisplay13SetPowerState\` 中原生 FB1 电源状态：

1. 只有成功经历本机原生 4K60 SCDC 准备 \`100\` 后，才记录一份同一 AOC 的已验证能力缓存；
2. FB1 原生 Wake(2)→Doze(1) 电源回调**返回成功**后记录 Doze 时刻；
3. 只有 FB1 原生 Doze(1)→Wake(2) 的回调正在运行、距离首次高速成功 **>=90 秒**、距离 Doze **>=3 秒**，才临时允许经过完整 EDID 比较的缓存协商候选；
4. 之前的全部硬条件保留：同一物理 HDMI-B、完全相同 128 字节 EDID、当前仅已重取基本块而没有新 CTA、一次/代、原生 controller owner lock、原生 SCDC version/config 读写读回；失败必须沿用 V3 原始结果而不能伪造原生 modeset 成功；
5. 改动只落在 WhateverXe **已经使用的 Framebuffer Power callback** 与现有 V3 CALL-site 的资格判断，**没有安装新 Hook，没有定时器、没有后台线程、没有主动触发 modeset，也没有在 DDC 回调中重入 I2C**；
6. 删除 R1 推测性 MMIO-output-off 观察逻辑。新增 \`WEXYogaHDMI2WakePowerLast\` 记录最后一次 FB1 原生 Doze/ Wake 电源回调；\`WakeRejectLast\`、\`WakeActionLast\` 继续保留。诊断 flags 的 bit6 表示高速成功满 90 秒，bit7 表示至少 3 秒的**已确认原生 Doze→Wake**（不再代表 MMIO 输出关闭）。

新 RELEASE 构建名：\`WhateverXe_0.8.3_YOGA_UNIFIED_WAKE_V4_POWERWAKE_R2_TEST.zip\`，包含原 Unified RC1 的五项默认配置和 V3 HDMI2 Callsite Safe。**R2 目前仅为软硬件隔离的修复候选，尚无实机结果**。

**风险说明：** 上一个 B 组开机三屏全黑时根本没有记录到恢复动作（没有状态 110），所以即使 R2 在开机阶段拒绝使用旧 CTA，也不能保证不再触发 Display13/DBUF/WM 多屏异常。首先用 **R2 A 组（只诊断）**启动并采集一次 Doze/Wake，看 \`WEXYogaHDMI2WakePowerLast\` 是否确实记录成功的 FB1 Power(2→1→2)；在确保 A 组三屏正常、有外置 EFI 回退和远程访问的前提下，才考虑 B 组。**不要复用旧 V4 B/R1 的包做混合对比**。

---

## V4 BootSafe R1 — 历史候选（已由 R2 替代）

基于 17:27 A 组和 17:43 B 组原始诊断 ZIP，B 组**重启后首次进入桌面就三屏全黑**，并非显示器休眠之后发生。B 组仅记录到一次 V3 CALL-site `status=100`，**没有恢复尝试事件 4 或恢复状态 110**；随后 DDI1 HPD 抖动，FB0/FB2 记录 `0xe00002d8`，且 `N97FBDBUFLayoutFailure` / WM Failure Inputs 出现。不能因此声称新 SCDC 重试导致或修好了三屏全黑。

此 R1 修改仅为 **启动隔离和取证强化**，没有启用新的自动 HPD 重置、强制 modeset 或伪造 SCDC ACK：

- 只有在本次启动已经存在真实的**同一 HDMI-B 4K60 原生 SCDC 成功准备记录**之后，才开始计时；
- 从首次成功准备经过 **至少 90 秒**，并且已有**该 HDMI-B transcoder 的 enable=0 原生寄存器写入**且关闭至少 **3 秒**，才允许进入一次性重验证的后续判断；
- 新监视只读取原 V3 MMIO-write wrapper 的输入 `reg/value`，没有额外硬件读写、没有新的 Hook；**若低功耗过程中没有观测到该写入，保持拒绝，不尝试恢复**；
- 原有同一物理端口、AOC EDID **完整 128 字节逐字节一致**、当前 CTA 缺失、仅一代一次、owner lock、native SCDC readback 等限制**全部保留**；
- 新增 `WEXYogaHDMI2WakeRejectLast`（最后一次 status=10 的失败快照）、`WEXYogaHDMI2WakeActionLast`（候选行动快照），避免被稍后的 CTA EDID 事件覆盖；
- 诊断标志 `flags`：bit6 表示首次高速会话已满 90 秒，bit7 表示同一 HDMI-B 输出已关闭至少 3 秒，bit8/9/10/11 表示有效 CTA、HDMI、SCDC、>340MHz 能力，bit12 表示请求了恢复；这些标志仍不证明物理显示器真正点亮。

**关键限制：** 如果开机三屏全黑发生时恢复事务根本未运行，这个门控更改只能降低新逻辑过早介入的机会，**不能宣称从根本上修好了启动时的共享 DBUF/WM 失败**。此分支仍是实验分支；旧 B 组 ZIP 不应继续安装，必须识别新的 `BootSafe R1` 文件名。建议先用 A 组确认稳定启动，再考虑 B 组严格受控测试，当前无法保证 B 组能正常点亮。

- 预期新构建文件：`WhateverXe_0.8.3_YOGA_UNIFIED_WAKE_V4_BOOTSAFE_R1_TEST.zip`
- 对照旧构建：`WhateverXe_0.8.3_YOGA_UNIFIED_WAKE_V4_TEST.zip`（**停止使用**）

## 功能基线：一份 Kext，不恢复旧启动参数

| 功能 | 本 V4 默认行为 |
| --- | --- |
| 内屏 3K120 | 默认启用 **eDP120 Admit + WM_ONLY** |
| AOC HDMI 伪色 | 默认启用 **Deep8**，精确 EDID 匹配 |
| HDMI 4K60 模式准入 | 默认启用 **HDMI600** |
| HP G4 USB-C 外屏 | 默认启用 **DDI5 SST**；不代表 TB4/MST 修复 |
| HDMI 4K60 高速握手 | 保留 V3 `-wex-yoga-hdmi2-callsite-safe`，仍需显式开启 |
| 唤醒诊断 | 新增可选 `-wex-yoga-hdmi2-wake-diag` |
| 唤醒恢复候选 | 新增可选 `-wex-yoga-hdmi2-wake-recover`，**默认关闭** |

过去的正向开关 `-wex-yoga-edp120-admit`、`-wex-yoga-edp120-wm`、`-wex-yoga-hdmi-edid-deep8`、`-wex-yoga-hdmi600`、`-wex-yoga-tc5-sst` **仍不需要**。

## 这次实验基于真实的 Display Wake 对照

2026-11-21 用户两份 ZIP：
- `Yoga_HDMI2_DisplayWake_black_wake2_20261121_162700.zip`
- `Yoga_HDMI2_DisplayWake_recovered60_20261121_163041.zip`

16:19 左右第二次 **Display Sleep / Display Wake** 后，AOC U27P10 灯变黄、无有效画面，macOS 仍识别 4K60。手工切 4K30 未恢复，再切 4K60 重新点亮。黑屏时 `CallsiteLast`：`status=10`、`armedPipe=3`；恢复时 `status=100`、`armedPipe=1`。在两种状态下，HDMI 高速 source bit4/bit0 均已设置。

V3 中的 `status=10` 是 **当前物理 HDMI-B 接收端的 EDID/CTA/SCDC 能力缓存检查失败**，并不等于已经发送了 SCDC NAK。不能仅凭此推断具体哪个字段失效；V4 要先记录真实缓存代次，再受控验证修复候选。

## V4 只读诊断

仅在 `-wex-yoga-hdmi2-callsite-safe` 已成功安装（`CallsiteStatus=5`）时，`-wex-yoga-hdmi2-wake-diag` 才发布：

- `WEXYogaHDMI2WakeDiagEnabled`：是否成功启用；
- `WEXYogaHDMI2WakeLast`：最新 12×uint64 小端事件；
- `WEXYogaHDMI2WakeFirst1..16`：前 16 条有界事件；
- `WEXYogaHDMI2CallsiteLast`：保留最新的 `status=10`（即使调用序号超过 16）。

事件格式：

```text
[schema=1, sequence, mach_absolute_time, event, connectionGeneration,
 pipe, pixelClockHz, status, flags, maxTMDSKHz, attemptedGeneration,
 armedPipe]
```

事件编号：`1` 原生 EDID 基本块、`2` CTA 扩展块、`3` 能力检查拒绝、`4` 准备一次性恢复、`5` 恢复完成、`6` 恢复事务失败。标志位：bit0 当前端口/基本块可用、bit1 目标 AOC 身份/有效基本块、bit2 本次已读取 CTA、bit3 有上一成功高速会话、bit5 符合恢复候选条件。

日志输出不发送额外 I2C 命令、不改变 HPD 或唤醒策略。诊断增加的 IORegistry 写入本身可能影响启动时序，因此对照实验建议先仅采集一次，无须反复睡眠复现。

## V4 有界恢复候选（严格 opt-in）

`-wex-yoga-hdmi2-wake-recover` **不安装新 Kext Hook、不强制生成模式切换**。它只在原有 V3 `LightUpTMDS` CALL-site **已经执行一次高速 HDMI 模式设置**，而当前 CTA 缓存仍为空时，考虑一次额外的原生 SCDC 重验证。

只允许：V3 的 Callsite Safe 已正常工作；原生 controller owner lock 已持有；同一物理 HDMI-B / A7A0；本次新读取的 128 字节**完整基本 EDID**校验有效、AOC `05E3:2710` 且与**此前一次真实成功 SCDC 高速会话**的基本 EDID 字节完全相同；该成功会话此前已有有效的 SCDC/高速 CTA；本次尚未收到 CTA；本次连接代次此前未尝试恢复；GPU 电源/时钟状态检查全部通过。

满足后，把先前**已由本机成功高速事务验证过**的 CTA 链路上限用于这**一次** SCDC read/write/readback；读回仍由原生控制器执行，遵守连接代次锁。如果读回失败，不设置 source flags、不重试。成功用状态码 `110` 表示，V4 才允许按原 V3 `100` 的逻辑设置 source bit4/bit0。

**不允许**在新 EDID 不同、目标接收端改变、没有此前成功会话、CTA 已重新读取、当前高速时序不支持、原生 owner lock 缺失或当前硬件有故障时继续。不会禁用 `status=10` 检查，不会绕过 `prepareSCDC`，也不会修改 Display13 PHY/PLL/HPD/睡眠电源管理。

**局限**：此候选只有在系统已经请求原生高速 modeset 且符合非常具体的“新基本块先于 CTA”竞态时才可能修复黑屏。如果 V3 的 `status=10` 由其他原因引起，V4 仍会拒绝并仅记录，不能保证自动点亮；这是刻意设计的安全边界。

## 建议的两轮实验参数（独立测试 EFI）

**A：仅添加诊断，不启用恢复候选**

```text
-v keepsyms=1 -vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-hdmi2-callsite-safe -wex-yoga-hdmi2-wake-diag
```

**B：已出现三屏全灭实机回归，暂停启用（仅保留历史记录）**

```text
-v keepsyms=1 -vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-hdmi2-callsite-safe -wex-yoga-hdmi2-wake-diag -wex-yoga-hdmi2-wake-recover
```

不要一开始就上 B；不要在黑屏状态反复连续切 30/60Hz，不能认为测试软件全绿就是实机已经解决。

只读取证（无需改 EFI）：

```bash
ioreg -p IOService -l -w0 | grep -E 'WEXYogaHDMI2(Wake|Callsite|Source)'
system_profiler SPDisplaysDataType
pmset -g log | grep -E 'Display is turned|DarkWake|Wake|Sleep'
```

如果曾安装过独立诊断脚本，也可以复用 `Yoga_HDMI2_DisplayWake_Diag.command` 采集黑屏/正常状态 ZIP；上传前检查系统序列号等隐私信息。

## 构建与验收

CI `.github/workflows/yoga-unified-wake-v4.yml`：先精确生成 V3 → 套用 Unified RC1 默认配置 → 应用 V4，随后检查 V3 TC-before-CALL 的 Metal 安全顺序、SST/Deep8/eDP/HDMI600 的默认条件、V4 纯策略单元测试、源代码守卫、WhateverXe 原版回归及 RELEASE 打包。

通过 CI **仅代表软件检查**。实机至少需要 Metal/1536 MB、3K120、AOC 4K30/4K60、HP G4 SST、启动阶段显示是否回归以及显示器关屏/唤醒两轮的状态对照。

- [V4 GitHub Actions 工作流](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/workflows/yoga-unified-wake-v4.yml)
- [Unified RC1 已成功的构建](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44881256951)
- [原始 V3 基线](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-hdmi2-scdc-gmbus-wait-v3)

**不动原 `main`、Unified RC1、V3、macOS Graphics 0.4.4 和现有日常 EFI。** 新版先保留为独立研究分支；出现异常直接回退原 USB/EFI。
