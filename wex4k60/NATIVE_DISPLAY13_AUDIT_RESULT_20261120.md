# Yoga A7A0：本机原生 Apple Display13 HDMI 调用点实证核验（2026-11-20）

> **仅静态证据**：基于用户本地只读脚本生成并在对话中提供的 `Yoga_Display13_NativeAudit.json`。原生 Apple 驱动、WhateverXe、SST、HDMI600 与 EFI 未修改。此报告不包含任何主机序列号、完整 Apple 二进制、EDID 唯一标识或敏感信息。

## 1. 本机原生 Mach-O 身份

| 属性 | 实测值 |
| --- | --- |
| Mach-O 对象 | `AppleIntelTGLGraphicsFramebuffer` |
| 文件大小 | `2,943,600` bytes |
| SHA-256 | `115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e` |
| Mach-O UUID | `B6078743-F795-3202-A55E-EA690FA40949` |
| 本机 4K30 基线加载 UUID | `B6078743-F795-3202-A55E-EA690FA40949` |
| Match | **Yes** |
| `__TEXT` 镜像基址 | `0x0` |
| x86_64 架构切片大小 | `2,943,600` bytes |

与此前独立参考工程列出的 5 个入口偏移的 **本机实际符号表和前 8 字节**完全匹配：

| 原生方法 | 入口（相对 `__TEXT`） | 预期前缀 | 本机前缀 | 结果 |
| --- | --- | --- | --- | --- |
| `AppleIntelFramebuffer::getOnlineInfo` | `0x2E232` | `55 48 89 e5 41 57 41 56` | 相同 | PASS |
| `AppleIntelFramebufferController::setColorMode` | `0x491F2` | `55 48 89 e5 41 57 41 56` | 相同 | PASS |
| `AppleIntelFramebufferController::LightUpTMDS` | `0x50B22` | `55 48 89 e5 41 57 41 56` | 相同 | PASS |
| `AppleIntelFramebufferController::hwDoI2CRequest` | `0x53A20` | `55 48 89 e5 48 83 ec 20` | 相同 | PASS |
| `AppleIntelFramebufferController::hwDoGMBusRequest` | `0x53A7C` | `55 48 89 e5 41 57 41 56` | 相同 | PASS |

与光核验固定地址不同，本次本机原生 Mach-O 的 **符号表**也直接将这些 C++ 方法映射到以上入口；因此已经确认这些位置不是误匹配到别的函数。

## 2. 反汇编 `LightUpTMDS` 的实证 CALL

用户 JSON 给出的 `image+0x4FF7B` 至 `image+0x4FFFB` 128-byte 邻域中，x86-64 disassembly（短片段）：

```asm
0x4FFA6   lea    rcx, [rbp-0x108]   ; timing object address
0x4FFAD   mov    rdi, r12
0x4FFB0   mov    rsi, r14
0x4FFB3   mov    rdx, r15
0x4FFB6   call   0x50B22           ; E8 67 0B 00 00
0x4FFBB   jmp    0x4FFD9           ; native return-PC confirmed
0x4FFD9   xor    r13d, r13d
0x4FFDC   jmp    0x4FFEB
```

这直接证明本机至少存在一个真实调用边：`image+0x4FFB6 → image+0x50B22`，返回位置是 `image+0x4FFBB`。参考 A7A0 工程使用的 return-PC 匹配目标在本机**有真实机器码依据**。

另外在同一小段调度代码中可观察到两个别的原生调用：`0x4FF95 → 0x5063E` 和 `0x4FFD4 → 0x508C4`，都用相似的四参数准备。**本 JSON 没有这两个函数的符号信息或完整分支条件，不能将它们猜成 DP/HDMI 模式。**

`LightUpTMDS` 函数前 64 字节解码：

```asm
0x50B2D   mov    r12, rcx
0x50B30   mov    rbx, rdx
0x50B33   mov    r14, rsi
0x50B36   mov    r15, rdi
0x50B40   call   0x6CCB4
0x50B45   mov    rdi, [r15+0xC40]
0x50B53   mov    eax, [rbx+0x3640]
```

这与 `LightUpTMDS(controller, framebuffer, displayPath, detailedTiming)` 的 4 个参数寄存器分配相容（并有直接执行位置依据），**但不能仅凭入口和前 64 字节证明完整函数的锁顺序、所有权检查或所有调用路径安全。**

### 特别值得研究：这个 CALL 之后没有直接使用 `EAX` 返回值

在上述 **这一条调用分支**，`call 0x50B22` 之后先 `jmp`，再 `xor r13d,r13d`，没有将 `EAX` 直接保存成该分支的状态。附近其他分支 `call 0x5063E` 则含 `mov r13d,eax`。

**结论严格限定**：该分支没有直接传播 `LightUpTMDS` 的 `EAX`。这值得研究 4K60“模式被接受但物理黑屏”的报告与回滚路径，但仅凭 128-byte 邻域还不知道该调用结果在更高层如何被使用、`r13d` 的最终含义，因此不能据此宣称 Apple 错误地返回了成功。

## 3. 本机 I²C 与颜色模式入口的新证据

- `hwDoI2CRequest +0x53A20` 真实入口下，前 64 字节有 `mov rdi,[rdi+0x9C8]`、若空则跳过、否则使用虚函数派发的片段；这说明它并不是可以无条件调用的通用 I²C 原语。参考 SCDC 补丁在调用前对 controller 的所有权、DDC 针脚和互斥锁做检查，其必要性增加。
- `hwDoGMBusRequest +0x53A7C` 具有另一套入口/参数寄存器；**两个入口不是同一函数**，不能把正常 4K30 `N97FBGMBusLast` 中没有 `0xA8` 的事实等同于所有可能的 `hwDoI2CRequest` SCDC 通路均未被调用。
- `getOnlineInfo +0x2E232` 的前 64 字节含 `mov r14,[rsi+0x3648]`，与 `DisplayPath` 内部端口字段的同 A7A0 参考映射相容。
- `setColorMode +0x491F2` 的前 64 字节含 `mov [rsi+0x45A8],ecx`、`cmp r8d,0x2` 等操作；未从中证明特定的 8bpc/YCbCr420 参数语义。
- **`DisplayPath+0x12C → TRANS_DDI_FUNC_CTL` 未经本机实证**；本轮仅截取入口 64B，无法反向证明 Shadow 控制字段或 SCDC/1:40 bit 的最终写入。

## 4. 对旧 route-only 回归的影响

本次验证消除了旧实验的部分疑点：方法符号、入口 8B、`LightUpTMDS` 的预期 CALL 边都**真实存在**。因此，旧 `-wex-yoga-hdmi2-route-only` 导致硬件加速丢失，**不能简单归咎于函数入口错误或没有这个调用点**。

更值得继续调查的是：
- 旧补丁在 Display13 输出 Hook 组已经完成安装后又单独通过 `routeMultipleShort` 装了 TMDS trampolines，而同 A7A0 参考工程将 TMDS 方法放进统一的输出安装组；该差异可能重要，但没有直接证据证明它就是旧回归根因。
- 路由策略可能改变原生 Prologue/trampoline 行为、相邻初始化时序或函数返回处理；没有旧实验失败机的有效 IORegistry/panic 堆栈，仍是未证实假设。
- 只有一个已验证的 CALL 边，不说明不存在其它调用点。**不能基于这份报告复活原旧 Hook。**

## 5. 下一步的必要证据

在本机实际 Mach-O、UUID、SHA 已锁定的前提下，下一轮只读导出：
- `LightUpTMDS` 完整函数中与 `DisplayPath+0x12C` 有关的指令和源端 `TRANS_DDI_FUNC_CTL` 写入链路；
- 发起 `0x4FFB6` 的父函数完整分支、`r13d` 的最终使用方式、是否执行/跳过色彩、时钟准备；
- `hwDoI2CRequest` 的原生调用上下文，验证 SCDC 新事务应在何种锁/所有权前提下接入；
- Apple 原生是否已在 HDMI 2.0 模式下调用 SCDC 操作，不能因为 4K30 GMBUS 中没有 `0xA8` 就断言缺失。

这些信息需要原生方法的**更多指令字节**，不是只重复运行现有 `native_macho_audit.py`。目前不修改 WhateverXe 及 EFI，不触发 4K60，不发布修复 Kext。

参考历史报告：[HDMI 2.0 初始化时序](NATIVE_DISPLAY13_HDMI20_STATIC_TIMELINE_20261120.md)、[失败的单独 TMDS 路由实验](https://github.com/Lanye-z/WhateverXe-yogapro13900/blob/experiment/wex-0.8.3-yoga-hdmi2-route-diag/wexlink/ROUTE_DIAG_README.md)。
