# ⚠️ 2026-11-21 实机严重回归：V2 CALLSITE 禁止继续使用

**用户实机报告：** 未执行 observe 预检，直接用 `-wex-yoga-hdmi2-callsite-safe` 启动 V2 后，**核显硬件加速再次丢失，仅内屏亮，机身 HDMI 和扩展坞显示器不亮**。这与此前仅启用旧版 `LightUpTMDS` route-only 就丢失 Metal 的回归高度相似。**V2 标记为 REJECTED / UNSAFE，撤回所有实机测试建议；不要用 `-wex-yoga-hdmi2-callsite-observe` 进行第二次试验，因为它也会修改同一原生 CALL 指令。**

**优先恢复：** 使用先前验证成功的完整 EFI / WhateverXe.kext，移除所有 `-wex-yoga-hdmi2-callsite-safe`、`-wex-yoga-hdmi2-callsite-observe` 参数；不在运行中替换 kext、不重试 4K60。保存数据正常关机后用安全 EFI 启动。若当前内屏仍可操作，可选择性只读获取 `WEXYogaHDMI2CallsiteStatus`、`WEXYogaHDMI2CallsiteLast`、`kmutil showloaded` 和 `system_profiler SPDisplaysDataType`，但**不得延误回退**。

**已核实的代码风险，不当作定因：** V2 的 `prepare.py` 在 opt-in 时用 `patcher.routeBlock` 覆写 Apple framebuffer 镜像 `+0x4FFB6` 的五字节 CALL；即使模式仍为 4K30，该指令改写也已生效。V2 在 `yogaHDMI2ArmedPipe=3` 的正常低速路径会拒绝新增 SCDC，因此**不能把本次启动回归归咎于已经成功进行高速 SCDC 事务**。仍需当次 IORegistry 和已加载模块信息才能判断补丁是否真正生效以及 Metal 失效环节。221/221 软件测试全绿不代表内核二进制热修改安全。本实验包不应作为可部署的修复。

---

# Yoga A7A0 HDMI2 V2：单调用点原生协商（实验；不可作为生产修复）
2026-11-21

## 已证实的 V1 失败（来自用户实机 ZIP）
- **补丁确实已加载**：`WEXYogaHDMI2SafeStatus=3`、`WEXYogaHDMI2SafeReady=Yes`。
- **533.25 MHz 的 4K60 高速模式**，Pipe1 上 `WEXYogaHDMI2HighLast=[1,22,1,533250000,5,3]`。第 5 状态是 **WM callback 不是 native controller 的递归锁持有者**，因此 V1 SCDC 流程根本没执行，`armedPipe=3`。
- 源端 `TRANS_DDI_FUNC_CTL=0x90010200`，high TMDS 与 scrambling 位均为0。无 `WEXYogaHDMI2SourceLast`。
- Native GMBus 第11条是 Bus2 / SCDC `0xA8` 读取返回 `0xE00002ED`，但此条请求与 V1 新增协商无确认的因果关系（V1 被状态5挡住），其来源必须继续确认。
- 用户 AOC EDID CTA 的 HDMI Forum VSDB 声明最高 **600 MHz TMDS / SCDC present**，不能把失败误认为接收端 EDID 不支持 4K60。
- 回切到4K30后 AOC 在 macOS 消失：`IOFB0Hz=Yes`，外屏 IOFramebuffer 连接子节点消失，WindowServer 有 offline/remove 事件，需独立研究恢复路径。

## 与 V1 的关键变化
1. **禁用 WM 回调里新增的 I²C**。它不持有原生 controller owner lock。V2 WM 只返回状态55，不再触碰 SCDC。
2. **不使用曾经造成 22MB 显存/Metal 丢失的全局 LightUpTMDS 入口 Hook**。仅在指定 boot-arg 下、且经严格校验的用户机型/Apple25G241 native 机器码 `image+0x4FFB6: E8 67 0B 00 00` 处，将一个 caller CALL 指向本版桥接函数，原始 `image+0x50B22` 不改写。相对地址超出32位直接拒绝，原机器码、目标偏移不匹配也直接拒绝。
3. CALL 桥接首先验证端口、pipe、输入 timing、native owner lock。观察模式只记录。活跃模式才尝试 native SCDC（sink版本、source版本、0x20、回读），全部成功且连接代次相同，才在 native LightUp 前更新 `DisplayPath+0x12C` 的 `0x11` 位。源端 RegisterAccessManager 仍由现有 V1 wrapper 记录（没有新增主动 MMIO 写）。
4. 原生 LightUp 始终调用，原始返回码保留；没有任何状态伪造为成功。底层 `display13FBPower.lock` 改为 TryLock，避免同一模式设置路径重复上锁。
5. 高速回到低速时，允许对**同一物理 HDMI-B 接收端**恢复低速 SCDC，即使 native 选择了另一条 Pipe；但只对先前已 armed 的高速会话尝试，不对正常4K30添加 I²C。

## 实验安全范围

| boot-arg | 行为 |
|---|---|
| 都不添加 | 不安装新 CALL-site 补丁，不进行新增 SCDC 操作 |
| `-wex-yoga-hdmi2-callsite-observe` | 严格校验后接入**只观察**；不新增 SCDC 或源端写入 |
| `-wex-yoga-hdmi2-callsite-safe` | 允许在严格验证后实际修改 SCDC 与 HDMI shadow 控制位 |
| 两项同时添加 | 拒绝启动新 HDMI2 实验 |
| 旧版 `-wex-yoga-hdmi2-safe` | **V2 不识别，不再启用 V1 的 WM 路径** |

输出：`WEXYogaHDMI2CallsiteStatus`（0关闭、1基础条件不符、2字节检查失败、3指令超出可达、4patch失败、5已安装）；`WEXYogaHDMI2CallsiteLast` 是uint64[12]：版本、调用序号、端口有效、Pipe、pixelHz、是否持有native递归锁、尝试前armedPipe、准备状态、shadow前后、原生返回、尝试后armedPipe。

### 不满足软件检查即停止；V2 尚未验证任何 4K60 实机画面

这是一版内核 CALL-site 实验，**不是已确认成功的修复，也有启动/显示回归风险**。因旧TMDS Hook 曾导致 Metal 失效，单调用点方案虽缩小修改范围，也不保证避免类似问题。建议仅在**用户已经恢复稳定EFI、USB鼠标/拓展坞正常后**才考虑使用独立可启动 USB EFI。首次只带 `-wex-yoga-hdmi2-callsite-observe`，在**已经成功的4K30**下校验内屏/Metal/HDMI/SST，检查 `CallsiteStatus` 与 `CallsiteLast`；没有确认前**绝不切换4K60**。当下已有黑屏及扩展坞枚举故障，不建议直接安装启用 safe。

**上次失败原因已明确；V2 只是把实机时序不确定性移到可量化的、正确原生调用点上进行下一步验证。**

参考：Linux i915 intel_hdmi_handle_sink_scrambling；Apple IOI2CRequest API；本仓库 `wex4k60/V1_BLACK_20261120_225512_DIAG.md` 与 `wex4k60/POST_FALLBACK_20261121_012436_ANALYSIS.md`。
