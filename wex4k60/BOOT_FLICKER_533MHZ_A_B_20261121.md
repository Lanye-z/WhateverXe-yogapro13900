# Yoga 82Y7：13:55 OrderFix 开机黑屏重亮的最新证据（2026-11-21）

## 日志依据
本地只读上传：
- \`Yoga_OrderFix_Startup_Flicker_20261121_135513.zip\`：故障开机，\`system.txt\` boot 13:49:23，本次采集 13:55:13；
- \`Yoga_HDMI4K60_hdmi30_20261120_201932.zip\`：用户此前已验证的三屏成功状态，但该 ZIP 的系统日志**不是**相同条件的完整开机追踪，所以不能凭它排除先前开机也有重配置。

### 核实的事件
| 本次时间 (CST) | 原始日志 |
|---|---|
| 13:49:35–36 | \`USB4206 Smart Hub\`、\`HP Thunderbolt Dock G4\` 通过 USB 连接正常枚举 |
| 13:49:58–13:50:03 | \`IOThunderboltFamily\` Root Switch \`IOThunderboltConfigReadCommand\` 多次 \`0xe00002d6\` 超时，最终 \`scanRootSwitch - ERROR\` |
| 13:51:05.297, 05.751, 06.145, 06.783 | \`AppleIntelTGLGraphicsFramebuffer\` FB1 在 \`PixelClock = 297000000\` 进行显示模式更新（AOC 正常 4K30 时钟） |
| 13:51:06.566 -> 07.565 | \`ddi 1 isHPDLow = 1 -> 0\`，真实记录到一次 HDMI B HPD 低/高变化 |
| **13:51:09.295, 13.659, 14.133, 14.563** | **FB1 PixelClock = 533250000**：对应此前黑屏的 4K60 时序；本次未启用任何 HDMI2 \`safe\`/ \`observe\` 参数 |
| 13:51:16.615 -> 17.245 | \`ddi 1 isHPDLow = 1 -> 0\`，再次 HDMI B HPD 变化 |
| 13:51:17.112, 19.058, 19.583 | FB1 \`PixelClock = 297000000\`，回到正常 4K30 对应时钟 |
| 13:51:04–18 | FB1 和 FB2 \`Connection status change\`、多次 WindowServer Reconfigure、反复发布 \`display0\`/\`AppleDisplay\` |
| 13:55:14 | 三屏最终在线，Intel 1536MB、Metal 2、内屏 120Hz、AOC 4K30、G4 下 27B2 1080p75 |

**非常重要的分析界限：** 原生 \`FB1: fActiveNumberOfLanes = 0, linkSymbolClock = 0 ... will lead to DivideByZero panic\` 是同一驱动的错误提示，在 297 MHz 和 533 MHz 都出现，**不能把这句话等同于已经发生 kernel panic**；采集时三屏与 Metal 均正常。533.25 MHz 表示驱动被请求处理该时序，**不证明链路已经以 4K60 稳定输出**。HPD 低/高与反复重配置是真实记录，但仅凭时序仍不能证明其唯一驱动因素。

### 与 2026-11-20 稳定日志的直接对照
- \`WEXDisplay13TCHooksReady=Yes\`、\`WEXYogaSSTCapabilityMasked=Yes\`、\`WEXYogaSSTHookStatus=4\`、\`WEXYogaHDMI600Status=4\`、\`WEXYogaHDMIEDIDABApplied=Yes\` 两次一致。
- \`WEXYogaUSBCDPTrainingFirst1\` 原始 96 字节**完全相同**，原生首次训练结果成功（index21=0）。
- \`WEXYogaUSBCDPTrainingLast\` 的训练尝试序号：11月20日=4、11月21日=1；由于日志采集时间及插拔操作不同，**不得据此判断哪版更稳定**。
- 11月20日成功录制的完整 IORegistry 里**已经存在** \`IOPersonalityPublisher=org.yoga.experimental.ThunderboltA73EProbe\`；不能只凭当前 A73E 超时就认定它是这次新增闪屏的根因。13:55 包没有当前 \`IOPersonalityPublisher\` 的完整树，须另行核验。
- 无 \`-wex-yoga-hdmi2-callsite-safe\` 或 \`observe\`，且当前无 \`WEXYogaHDMI2CallsiteStatus\`。OrderFix 的实验 CALL 未安装，此次闪屏不得归咎于它已经执行的主动 SCDC 操作。

## 当前最小 A/B（不改源代码、不重新编译）
仅在可安全回退的测试 EFI 中，**移除 boot-args 中的** \`-wex-yoga-hdmi600\`，保留 **同一个 Kext、SST、Deep8、eDP120、A73EProbe** 等所有其他条件；正常重启一次，先观察是否还有启动黑屏重亮。原生上限约 300 MHz、已成功的 AOC 4K30 PixelClock=297 MHz，理论上仍可使用；但不能事先保证系统全部正常。

- **关键成功检验**：\`WEXYogaHDMI600Status=0\`、AOC 仍为 4K30 且 Metal/SST 仍正常，开机原生日志中没有再出现 \`FB1 ... PixelClock=533250000\`，黑屏重亮显著减少。支持“macOS/Display13 启动时尝试了未经 SCDC 验证的高速模式→重配置”的解释。
- **若 533 MHz 没有出现但依旧闪屏**：独立研究 DDI5/USB-C 连接与 WindowServer 模式重配；A73E Probe 可以再作为下一次**单变量**对比，不能一次同时去掉 A73EProbe 与 HDMI600。
- **若 AOC 4K30 消失**：立即用稳定 EFI/原 boot-args 回退，不做额外补丁试验。

注意：这只是验证 **4K30 三屏启动稳定性**，不是修复 4K60；在关闭 HDMI600 状态下不能测试 4K60。为了恢复后续 4K60，必须另行完成 SCDC、源端 bit0/bit4、以及模式回切保护的完整验证。

建议的只读核查：
\`\`\`bash
nvram boot-args
ioreg -p IOService -l -w0 | grep -E 'WEXYogaHDMI600(Status|Requested|Ready)|WEXDisplay13TCHooksReady|WEXYogaSSTHookReady'
system_profiler SPDisplaysDataType
log show --last 8m --style compact --predicate 'process == "kernel" AND (eventMessage CONTAINS[c] "PixelClock = 533250000" OR eventMessage CONTAINS[c] "isHPDLow")' 2>/dev/null
\`\`\`

**不要修改现有可用的 WhateverXe 核显/HDMI/DP 代码，也不要启用仍未实机验证的 \`-wex-yoga-hdmi2-callsite-safe\`。**
