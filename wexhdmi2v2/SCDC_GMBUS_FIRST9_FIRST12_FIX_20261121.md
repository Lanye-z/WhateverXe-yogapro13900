# Yoga 82Y7 | SCDC GMBUS History First9 / First12：解码与 V3 修复范围

日期：2026-11-21。用户提供的只读文件：`Yoga_SCDC_GMBUS_History.txt`，完整原始记录分别包含 First9 29 条、First12 27 条 `uint64_t[4]` (write, native caller offset, register address, value)。`HistoryLast` 为空，不表示之前的两条记录无效。

## 一、实际硬件访问顺序

以下均为 Native GMBUS helper 相对于函数入口的 offset，`GMBUS2=0xC5108`、`GMBUS1=0xC5104`。

| Native 偏移 | First9 | First12 | 解读 |
|---|---|---|---|
| +0x247、+0x270 | 0x0800、0x8800 | **0x0400、0x8400** | First12 一开始已经读到历史/粘滞 NAK；初始化阶段的清除行为尚未从源码证实 |
| +0x3B8 | GMBUS1=0x420100A8 | 同 | 物理 SCDC 7-bit slave=0x54、写方向8-bit=0xA8 |
| +0x45C | GMBUS2=0x8A00 | 同 | 写阶段 HW_RDY 已置位 |
| +0x790 | GMBUS1=0x420100A9 | 同 | **Apple native 已正确把 SCDC 的读取方向写为 A9**；无需也不应盲改上层 `IOI2CRequest.replyAddress=A8` |
| +0x7B3 | GMBUS2=0x8200 | GMBUS2=**0x8600** | First9 未 HW_RDY、未 NAK；First12 NAK bit10=1 |
| +0x7E8 | GMBUS2=0x8200 | 跳过 | First9 仍未就绪且未 NAK；然后原生例程进入终止路径 |
| +0x8E0 | STOP=0x48000000 | 同 | 原生结束当前请求 |
| +0x90C | GMBUS2=0x8A00 | GMBUS2=0x8600 | First12 停止时依然报告 NAK |
| 第二次尝试 | 类似 First9 | 类似 First12 | 重复上述步骤（后续均未成功） |

GMBUS2 bit11=HW_RDY；bit10=NAK；bit9=ACTIVE/INUSE。0x8200 无 HW_RDY 也无 NAK，不是完成。First9 在读取阶段没能等到真实的成功/失败终态；First12 已有设备 NAK，不能靠加长等待把 NAK 伪造成成功。

## 二、为什么当前版本没有等候

当前 WhateverXe 0.8.3 的 `wrapDisplay13GMBusRead()` **仅在 exact native caller offset=0x7E8、且 `o.edid` 具备128B EDID条件时** 调用 `Display13GMBus::waitReady()`。对该 SCDC 的 `sendType=replyType=1, sendAddress=replyAddress=A8, sendBytes=replyBytes=1` 请求，`o.edid=false`，因此不会得到额外的 `HW_RDY/NAK` 轮询。

`Display13GMBus::waitReady` 是已有、通过现有单元测试的有限等待实现，最多 50ms / 10µs采样，直到真实 HW_RDY 或 NAK；不会伪造成功。上游独立参考 `Wtrwx/Lenovo-Air14-IRP8-Hackintosh` 的 `kern_tgl_gmbus.hpp` 也将写阶段 +0x45C、读阶段 +0x7E8 用作原生 native GMBUS 精确等待点。**参考存在不意味着已经通过用户机器实测**。

## 三、此次新建的 V3 实验分支

分支：`experiment/wex-0.8.3-yoga-hdmi2-scdc-gmbus-wait-v3`，基于已经通过 TC 初始化回归的 `...hdmi2-v2-orderfix`。

仅在 V2 现有代码的 `wexhdmi2v2/prepare.py` 里最小化增加：

1. 增加 `Display13GMBusScope.scdcRead` 标志，按执行线程隔离。
2. 只在 `-wex-yoga-hdmi2-callsite-safe` 真正启用、Intel A7A0 HDMI B 已选、保留的 controller/DDC2、speed 0，并且 **send/reply 都为1、地址A8/A8、长度1/1、subaddress=0、commFlags=0** 时为该 scope 打开 SCDC 等待。
3. +0x45C 仅允许 `scdcRead`；+0x7E8 保留原 EDID 行为并允许 `scdcRead`。两者仅调用原有 `waitReady` 和原有 RegisterAccessManager 读操作，**不新增 SCDC 请求、不重发地址、不改 GMBUS1、不改变源端 shadow/PHY/PLL 或 4K30 逻辑**。
4. First12 那类真正 NAK 仍直接返回原生错误；不重试、不覆盖返回码。
5. 添加 `wexhdmi2v2/test_scdc_gmbus_wait.py` 静态回归检查；另继续运行 WhateverXe 固有的 GMBUS waiting tests、221 项完整回归。

**工程边界**：该软件缺口是直接从本次硬件记录定位出的，但目前并不能证明加等待即可令 AOC U27P10 在 4K60 亮屏。若 NAK 持续或 SCDC 事务返回新的错误，下一步应分析 GMBUS NAK 清除/目标设备对 SCDC 的物理应答，不能自动延长至无限时限或重试任意 I2C 命令。

**安全要求**：不要把此分支当成已经验证稳定的日常 EFI；不要再次为了采集日志而重复黑屏切换。用户稳定版应保留 `-wex-yoga-hdmi2-callsite-observe` 或不启用任何 HDMI2 参数，active safe/4K60 仍是硬件试验。
