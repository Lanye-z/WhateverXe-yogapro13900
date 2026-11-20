# HDMI2 V1：4K60 黑屏 → 选择 4K30 → AOC 不再出现在 macOS

**用户最新实机现象（2026-11-20）：** 切回 30 Hz 后，AOC 4K 显示器不再列于系统设置/显示器，另外两块屏幕继续工作。这是与“4K60 黑屏、系统仍识别”不同的第二阶段，**目前尚无 post-fallback IORegistry 包**。此文件不得把 HPD 已丢失、EDID 已失败、PLL 未释放或显卡硬件异常当作事实。

## 已建立事实（来自 22:55 的 V1 黑屏原始采集）
- macOS macOS Tahoe 26.7.1，WEX 0.8.3，原生 Display13，eDP 120Hz 与另外外屏有效。
- 4K60 实际 timing 533250000 Hz / **Pipe1**、`WEXYogaHDMI2HighLast status=5`（WM callback 未持有 controller+0x9B8 的原生 IORecursiveLock），armed=3，实验新增的 SCDC 交易根本没开始。
- `WEXYogaHDMI2SourceLast` 不存在，Pipe1 `TRANS_DDI_FUNC_CTL=0x90010200`：bit0/4 均为 0，不存在成功的源端高速改写证据。
- First11 GMBus DDC bus2 send/reply 0xA8，返回 `0xE00002ED`（not responding），初始 EDID 0xA0 曾成功。First1..16 与 Last 是有界样本，中间不完整；不能归属请求源，也不能说明每次请求都失败。
- 先前正常 4K30 测试显示物理 HDMI 管线在 Pipe2；这次 4K60 为 Pipe1。**不要固定管线编号**。

## 第二阶段需从当前还在运行的系统捕获（完全被动）

脚本 [collect_postfallback_missing.sh](collect_postfallback_missing.sh) 获取：
- 当前 `system_profiler SPDisplaysDataType`（确认系统是否确实不枚举 AOC），包含 JSON。
- 现场 `ioreg -p IOService -l -w0`、`AppleDisplay`、`IODisplayConnect`、`IOFramebuffer` 树、IOFBOnline、时钟、各 N97FB/WEX 属性。
- 20 分钟内 HPD、DDC、EDID、HDMI、framebuffer/WindowServer 日志，及已加载 Kext、当前 bootargs。
- 用户手工填写的 **显示器 OSD 是 No Signal 还是通电但黑屏**、HDMI 是否仍插着、是否重启；不能用 system_profiler 代替物理观察。
- 只读取不发起 HPD、不切模式、不重启、不发送 SCDC、不要求用户拔线。包含机器标识/EDID/日志，上传前复核隐私。

如果 AOC 已经从 system_profiler 消失，但旧 `WEXYogaHDMIColorLive` 或 EDID 仍在根 IORegistry 中，不等于屏幕仍连接——旧属性可能持久存在。新的 IOFramebuffer/IODisplayConnect 实例和物理 OSD 更有鉴别力。

## 区分故障的证据矩阵（仅做判断，不进行危险操作）

| 待验证 | 线索 | 下一步工作 |
|---|---|---|
| HDMI HPD / 重新枚举退出 | AOC 不在 AppleDisplay 和 IODisplayConnect、IOFBOnline 改变、HPD 事件/连接中断日志 | 审计 HPD/Online 回调与 PortHAL disable/enable 的生命周期，不先动 PLL |
| HPD 仍在线但 EDID/DDC 失败 | 连接对象存在但新 EDID 失败、PortDDC return 非零、0xA0 读取错误、OSD No Signal | 优先分析原生 GMBus 对 DDC/SCDC 的不同等待条件 |
| 检测到但模式状态损坏 | AppleDisplay/连接仍在、像素时钟与实际模式冲突、退出/恢复日志 | 对照 N97FBClockStop、N97FBPipeWM、Power/IRQ/DBUF 分析失败回滚 |
| macOS UI 缓存/WindowServer 逻辑残留 | 原生连接仍存在，显示器设置不列出，其他数据显示器 online | 分析 WindowServer/IOFramebuffer 枚举，不强制新 modeset |

## 下一版内核试验的明确门槛

1. **不要用 WM 回调绕过 native owner lock**；WM entry 被证实不持锁。高 TMDS 控制必须拆出到正确 owner/DDC 生命周期时序。
2. 先确认原生 `0xA8` 读取失败的请求方向、call-site 与 GMBus HW_RDY 语义，避免单纯按 Linux 名称复制寄存器。AOC EDID 0xA0 成功不代表 SCDC 0xA8 必然能读。
3. HDMI2 的源端高位在真正 `TRANS_DDI_FUNC_CTL` 写入之前应用，与当前动态 pipe 绑定，完成 sink 读回后才允许，高速失败时要有正确低速恢复/HPD 重新探测。
4. Linux i915 2026-01-14 的 patch v2 实测某些 HDMI2 sink 在成功 SCDC 协商后需要处理延迟（示例 150ms），否则仍不能识别 scrambled 信号，但**本机当前在 SCDC 之前失败**，现在加入盲目延时无帮助：https://www.mail-archive.com/dri-devel@lists.freedesktop.org/msg584154.html
5. 不再要求用户重复进入 4K60；先凭本次在线 post-fallback 采集研究。日常恢复只在备份、安全关机并使用稳定 EFI 情况下进行。

## 已有源码入口

- `XE::wrapDisplay13GMBus()` 是既有 Display13 GMBus 的只观察 wrapper，能记录 `0xA8` 事务返回，但缺乏调用者 owner-lock 状态与全序列；适合新增 **可选且不追加硬件读写** 的观测字段。
- `XE::wrapAlderLakeNPortDDC()` 已发布 `N97FBPortDDCLast`（含某次 DDC 返回，但可能是旧值）。
- `XE::wrapDisplay13GMBusWrite()` 已接入原生 RegisterAccessManager，未来可增加对真实输出启用前写的被动观测，不应在没有 sink 协商前强写 0x11。
- `N97FBIRQ` 与 `N97FBIRQEnableCheck` 存在但属性是旧时刻状态，不等于 live HPD 电平。

**工程操作：保留目前稳定 EFI。V1 safe 在 4K60 失败已明确，先停止重复测试。**
