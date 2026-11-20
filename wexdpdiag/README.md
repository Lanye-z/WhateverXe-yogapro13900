# Yoga 82Y7 USB-C DP Alt Mode 失败条件诊断版（默认关闭）
**不要用它替换日常 EFI。之前的 HDMI2 Route Diagnostic 已造成核显加速丢失，本版绝不继承那个代码。**

## 唯一的稳定源基线
- 以已经实际验证的 `44520992061` **Deep8 + HDMI600 + eDP120/WM_ONLY** 为起点，完全不引入 SCDC/GMBUS/Display13 HDMI2 LightUpTMDS 实验。
- 采集的 2026-11-20 三份日志：`before 10:03:44`、`dock_after 10:04:17`、`dock_only 10:17:50` 显示，TC5 Mode 3、2 lane、DP 540MHz LinkRate 5.4Gbps（HBR2）准备成功，但原生训练第 1 次返回 `0xE00002D8`，后续训练 `0xE00002D5`。`TGLLease` 后续事件的 prepare error=1 表示软件前置检查拒绝，非 5 次物理训练均失败。没有机身 HDMI 时仍然复现，因此并非第三屏资源不足。
- 上游代码中 `display13SSTPort()` 在 ClockFaulted、ClockStopped、控制器、端口关联、Mode、Port status 等条件不满足时返回 null；`display13LeaseValidate()` 将这种拒绝传递为训练前置失败。具体拒绝条件之前没有逐项记录。

## 本版仅增加读取和诊断记录，不修复链路
使用唯一新参数 `-wex-yoga-usbc-dpdiag`。只对 Intel 8086:A7A0、Display13、明确映射的 Type-C DDI5 生效。默认不启用。**不安装新 Hook，不创建新 TMDS 包装器、不重试训练、不修改 MMIO/HPD/PLL/PHY/时钟、不清除 ClockFault、不改变函数返回值**。同时不涉及雷电/USB4。

- `WEXYogaUSBCDPDiagEnabled`：是否通过设备/端口门控。
- `WEXYogaUSBCDPTrainingFirst1..8` 和 `WEXYogaUSBCDPTrainingLast`：每次训练结束后，记录原返回值及软件前置错误。长度 24 个小端 `uint32_t`。字段下标（从零开始）：
  - 0 版本；1 物理 DDI=5；2 控制器一致；3 ClockFaulted；4 ClockStopped；5 MemoryFaulted；6 WatermarkFaulted；7 PanelFaulted；8 BridgeFaulted；9 BridgeSuspended；
  - 10 端口对象大小合格；11 `display13SSTPort` 返回有效；12 端口配置 DDI；13 原生 Port Mode；14 native DDI；15 Port `0x117` 标志；
  - 16 已选中物理拓扑；17 DDI5 是 DP Link；18 MMIO 关联匹配；19 Display13 Topology 控制器一致；
  - 20 本端口训练尝试序号；21 原训练返回码；22 是否具有训练 Lease；23 `tglPrepareTrainingLease` 返回的错误原因代码。
- `WEXYogaUSBCDPStopDetail`：当 `display13StopTranscoder` 原本要返回 false 时保存已经读取的寄存器，不进行额外 MMIO 读取。长度 16 个小端 `uint32_t`：
  - 0 版本；1 有效 SST 端口；2 Pipe 电源引用仍在；3 Pipe；4 DDI Buffer；5 PIPECONF；6 TRANS_DDI_FUNC_CTL；7 TRANS_CONF；8 Pipe Clock；
  - 9 延迟 Clock Stop 等待标志；10 延迟停止的端口一致；11 当前 DDI 电源引用；12 现有 ClockFaulted；13–15 保留。
  - 注：如果返回 false 发生在函数最早的无锁、无路径检查，或者无法证明端口有效，该字段可能缺失，不代表失败没有发生。

## 实机使用（**仅在前一个成功 EFI 可以恢复的条件下**）
1. 替换独立测试 EFI 中的 `WhateverXe.kext`，首次开机使用**原来验证可用的完整 boot-args**，不要添加新参数。确认核显 1536MB/Metal、内屏 120Hz 和已正常的机身 HDMI 4K30。
2. 上一步正常才追加 `-wex-yoga-usbc-dpdiag`；这次绝不加入此前造成 22MB 异常的 `-wex-yoga-hdmi4k60` 或 `-wex-yoga-hdmi2-route-only`、`-wex-yoga-hdmi2-link`。
3. 继续使用已经成功复现的“只接内屏 + HP G4 在 USB-C 兼容模式 + 一台 1080p60 外屏”的配置。一次插入即可，避免反复拔插。只检查原有状态与新增记录。
4. 采集：
```bash
ioreg -p IOService -l -w0 > ~/Desktop/Yoga_USBC_DPDiag_IORegistry.txt
system_profiler SPDisplaysDataType > ~/Desktop/Yoga_USBC_DPDiag_Displays.txt
```
回退需**同时**还原原先成功的 `WhateverXe.kext` 和移除本实验参数。

## 解释界限
CI 编译及 221 项测试通过不代表实机可用。读取/记录可能改变显示初始化的时序，因此先以兼容性基线方式验证。只读诊断尚不能直接修好 USB-C 输出。取得具体失败条件后，再讨论最小安全修复；不要强制把错误的训练返回值改为成功。
