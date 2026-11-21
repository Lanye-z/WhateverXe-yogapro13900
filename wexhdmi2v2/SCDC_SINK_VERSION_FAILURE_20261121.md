# Yoga 82Y7 / HDMI2 safe 实机失败报告（2026-11-21 14:40）

证据：`Yoga_HDMI2_Safe_Failure_20261121_144015.zip`。用户于切到4K60黑屏，再恢复4K30、所有三屏正常显示后采集，**没有再重现此前切回后外屏彻底消失的问题**。

## 已有直接证据

- 当前 macOS 25G241，WhateverXe 0.8.3 + Lilu 1.7.3。GPU 1536 MB、Metal 2、内屏120Hz、AOC 4K30、SST 外屏1080p75；三屏全部在线。
- `WEXDisplay13TCHooksReady=Yes`、`N97FramebufferBackendReady=Yes`、`N97SharedRegisterPrerequisites=Yes`：上次 22MB Metal 启动退化未重现。
- `WEXYogaHDMI2CallsiteStatus=5`、`WriteEnabled=Yes`、`First1..8`和`Last`均存在，证明 CALL 安装且实际进入并返回原生函数。
- `First2,3,6,7`: `clock=533250000`, `pipe=1`, `qualified=1`, `native owner lock=1`, `prepare_status=34`, `armedBefore/After=3`, `nativeResult=0`; `shadowBefore=shadowAfter`（`0x90030200` 或 `0x90010200`），源端 bit0/bit4 未更改。
- `First1,4,5,8`及`Last9`: `clock=297000000`, `prepare_status=52`（正常4K30回退无需SCDC，未曾 armed）；原生函数返回0、三屏实际恢复。
- `34=30+SCDCError::SinkVersionReadFailed(4)`，失败点为 `prepareSCDC()` 第一个 `io.read(0x01,s.sinkVersion)`。因此尚未到 `Source Version=0x02`、`TMDS_Config=0x20` 写入，以及源端 shadow `0x11` 设置阶段。
- `N97FBGMBusFirst9`/`First12`：`bus=2`, `sendTransactionType=1`, `replyTransactionType=1`, `sendAddress=0xA8`, `replyAddress=0xA8`, `sendBytes=1`, `replyBytes=1`，原生调用和 `request.result` 都是 `0xE00002ED` (kIOReturnNotResponding)；确实有相关地址的 I2C 请求失败。GMBUS 记录没有原始时间戳，不能一一对应 First2/3/6/7。
- 另 `N97FBGMBusFirst1-4`（DDC bus2 EDID `0xA0`）成功；说明物理 DDC EDID 路径可用，但不能证明同线上 SCDC 地址 `0x54` 总是可达。

## 高优先级的地址假设及重要限制

SCDC 使用7位 slave `0x54`，对应8位写`0xA8`、读`0xA9`。此前版本 `YogaHDMI2Bus::send`：
```cpp
request.sendAddress=0xA8;
...
request.replyAddress=0xA8; // suspect
```
独立分支只尝试将 `replyAddress` 改成 `0xA9`，保留原 sendAddress、锁、控制路径和读取顺序。Apple `IOI2CRequest` 将发送与回复地址分别定义（Apple header）；Linux及 HDMI 文档确认 A8/A9 对应 write/read。

**关键反证/不确定性：** 这个 Apple 原生驱动在正常 EDID 成功请求中有 `replyAddress=0xA0`（并非按8位方向位的0xA1）；因此它也许依据 `replyTransactionType` 自动设置读位。**不得把 A9 修改称为已经确定的根因或已验证的 4K60 修复。** 其结果可能是无变化，亦可能引入新的错误，只有真实的 native transaction 支持和硬件结果才能最终判定。

另：source 使用 `replyTransactionType=1` 的独立读，与原注释声称的 repeated-start 读之间是否一致，也未通过本机原生 I2C 执行机制确认。不得同时更改事务类型、时间、DDI 寄存器、HPD/锁和 A9，以免无法归因。

## 工程实现与测试边界

- 先前 OrderFix 分支保留；本分支 `experiment/wex-0.8.3-yoga-hdmi2-scdc-read-a9` 仅在生成器内 `c=once(c,'request.replyAddress=0xA8;', 'request.replyAddress=0xA9;',...)`。
- 额外软件检查 `wexhdmi2v2/test_scdc_read_address.py` 保证本次生成代码为A8写/A9读，并未改变原有TC先验校验与CALL安装顺序。
- 可编译/221项回归仅说明软件完整性，不代表显示器SCDC通信成功；无论CI结果如何，**禁止向日常EFI推广该分支**。
- 在用户已经复现黑屏后，不要求再切4K60获取相同日志。继续研究应从原始 GMBUS driver 的 send/reply 地址归一化、repeated-start/STOP 行为，以及实际 SCDC 0x01 响应入手。仅当SCDC transaction complete且源端0x11实际写入后，再看PLL、PHY、时钟和成功显示路径。
