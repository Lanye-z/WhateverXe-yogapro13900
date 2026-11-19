# Yoga Pro 14s IRH8 A7A0：开机后首次 HDMI 热插拔诊断

**状态：本模块是 HPD 中断路径的诊断与有限次数事件转换实验，不是已实机确认的热插拔修复。**

这部分与 [U27P10 伪色已修复的 EDID Deep8 方案](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab) 是两个独立问题：**颜色修复已经在 4K30 上实机成功，不代表首次连接失败或 4K60 黑屏已解决。**

## 一、原始故障现象

在 Lenovo Yoga Pro 14s IRH8（82Y7 / A7A0）中，机身 HDMI DDI B 若开机前就接有显示器，可以进入系统并点亮；若仅以内屏启动，开机后第一次插入 HDMI 有时无法发现/点亮外屏。开机前接入的设备在后续拔插时有过正常工作的记录，但行为受具体显示器、模式和测试条件影响。

此前 WM_ONLY / 0.8.3 日志已经显示，故障状态下 PCH HDMI IRQ 相关位和 DDI HPD 检测器仍处于启用状态，因此不应简单地“再打开一次 HPD mask”作为修复。

## 二、已加入的两个实验开关

| 参数 | 作用 | 安全性及状态 |
| --- | --- | --- |
| `-wex-yoga-hdmi-hpdtrace` | 发布只读的 `WEXYogaHDMIHPDTrace`，用于分析 HPD 探测与 IRQ 计数 | 诊断开关 |
| `-wex-yoga-hdmi-first-hpd` | 仅在严格条件满足时，把首次 native HDMI-B 短 HPD 事件转换为一次长 HPD 事件 | **实验性候选修复，尚未证实有效** |

原生 Display13 的 `collect()` 路径中，DDI B 长脉冲对应 native bit 2，短脉冲对应 bit 3。提出的假设是：仅内屏启动后出现的是短 HPD，原生栈可能未将其按新增显示器处理。

`-wex-yoga-hdmi-first-hpd` 仅在设备限定、首次端口探测为断开、实际收到短 HPD 且没有长 HPD 等条件全部成立时转换**一次**事件；不会伪造不存在的中断，不会改写 EDID、显存寄存器或 HDMI 时钟。条件不成立时没有任何效果。

**没有捕获到短 HPD 事件之前，不应将该开关称为有效修复。**

## 三、诊断字段

`WEXYogaHDMIHPDTrace` 为 20 个小端序 `uint32`：

```text
[schema, firstB, lastB, probesB, irqCalls, deCalls,
 pchMasterHits, bLongHits, bShortHits, promotions,
 lastPCH, lastDDI, lastEvents, forwardedEvents, status,
 irqEnabled, irqFaulted, activePipes, admittedPipes, observations]
```

- `firstB=0`：首次探测 HDMI B 为断开；`firstB=2`：首次已连接。
- `bShortHits>0` 且 `bLongHits=0`：才支持短脉冲假设。
- 插入外屏后 `pchMasterHits=0`：可能根本没有观察到 PCH IRQ，需要向中断/供电上游排查。
- `bLongHits>0` 但屏幕未出现：说明故障可能在后续探测或 framebuffer 准入过程。
- `promotions=1`：只代表执行过一次事件转换，**不代表屏幕确实点亮**。

读取属性时序列化原子计数，不在中断处理程序中写 IORegistry，不通过采样器读取 MMIO，也不会自动重置端口。

## 四、谨慎的验证顺序

1. 保留已知可以启动的 EFI，复制独立测试 EFI；只替换该测试 EFI 的 `WhateverXe.kext`，保持 WhateverXe Graphics 0.4.4 不变。
2. 初次仅加入 `-wex-yoga-hdmi-hpdtrace`，保留 `-wex-yoga-edp120-admit -wex-yoga-edp120-wm`。开机前不接 HDMI，先以 eDP 单屏启动并记录基线。
3. 开机后接入机身 HDMI，分别采集插入前后的属性，比较中断计数变化。
4. 仅当确实观察到 B-short 而无 B-long，并且保留回退手段时，才考虑在另一份独立测试 EFI 验证一次性转换开关；必须同时确认 `promotions=1` 和显示器实际出现，才能判定有效。

```bash
ioreg -p IOService -l -w0 | grep -E 'WEXYogaHDMIHPDTrace|N97FBIRQEnableCheck|N97FBPortProbe(First2|Last)'
system_profiler SPDisplaysDataType
```

记录前后输出并比较计数**增量**，不要只看单次的绝对计数。测试期间若出现黑屏、WindowServer 无响应或内屏不亮，立即回退到原 EFI。

## 五、编译状态与问题边界

[该 HPD 实验构建记录](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44444094099) 包含官方回归、辅助测试、RELEASE 编译及打包。**构建通过不等于 HPD 方案获得实机验证。**

此实验未实现 4K60 的 HDMI TMDS 高速时钟与 SCDC 完整协商，也不是 GPU 颜色修复的必要组件。后续 Deep8 修复只作用于目标显示器的 EDID Deep Color 声明，未通过本模块的短/长 HPD 转换来解决伪色。