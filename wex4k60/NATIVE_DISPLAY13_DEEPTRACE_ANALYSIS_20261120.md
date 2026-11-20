# Yoga A7A0 Apple Display13 原生 HDMI 深度反汇编｜第 2 轮（2026-11-20）

**素材：** 用户上传 `Yoga_Display13_NativeDeepTrace.json`，包含与当前实际加载的 AppleIntelTGLGraphicsFramebuffer 相同 UUID / SHA-256 的 **六个只读 x86-64 代码窗口**。在隔离环境使用 GNU `objdump -D -b binary -m i386:x86-64 -M intel --adjust-vma` 反汇编；所有结论仅针对所提供的镜像代码，不代表实机 4K60 已成功。没有改变 EFI、WhateverXe、内屏120Hz、SST 三屏、雷电或 HDMI600。

## 0. 二进制身份与边界

- Mach-O UUID：`B6078743-F795-3202-A55E-EA690FA40949`。
- 原生 SHA-256：`115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`。
- 报告 `matches_baseline=true`，六个代码窗口：父方法调度 `0x4FE80+0x220`、`LightUpTMDS 0x50B22+0x1300`、`setColorMode 0x491F2+0x500`、`hwDoI2CRequest 0x53A20+0x180`、`hwDoGMBusRequest 0x53A7C+0x380`、`getOnlineInfo 0x2E232+0x400`。
- **注意**：`0x50B22+0x1300` 的窗口包含 `LightUpTMDS` 后续的数个**其他函数**；不能把 4,864 字节误写成 `LightUpTMDS` 单个函数长度。它在本机从 `0x50B22` 开始、至 `0x50BE9 ret` 结束。

## 1. 父方法如何分流到 HDMI（机器码证据）

```asm
0x4FF66   mov rax, [rbx+0x548]
0x4FF6D   mov eax, [rax+0x8]
0x4FF70   cmp eax, 0x2
0x4FF73   je  0x4FF9F
...
0x4FFA6   lea rcx, [rbp-0x108]  ; detailed timing object
0x4FFAD   mov rdi, r12          ; controller
0x4FFB0   mov rsi, r14          ; framebuffer
0x4FFB3   mov rdx, r15          ; displayPath
0x4FFB6   call 0x50B22         ; LightUpTMDS
0x4FFBB   jmp 0x4FFD9
0x4FFD9   xor r13d, r13d
```

这表明 **原生配置结构体中的 `[cfg+8]==2` 对应这一条 HDMI 调用分支**，无需把物理 Pipe 1/2 写死。另一条 `cfg==0` 调 `0x5063E` 后将 EAX 保存到 R13D，而 HDMI 分支无条件清 R13D。不能据此断言显示链路物理成功或失败。

## 2. `LightUpTMDS` 主函数完全解码：始终返回 0，并有多个内部辅助函数

```asm
0x50B22   push rbp
0x50B2D   mov r12, rcx
0x50B30   mov rbx, rdx
0x50B33   mov r14, rsi
0x50B36   mov r15, rdi
0x50B40   call 0x6CCB4       ; 候选时钟/前置初始化，具体语义待核验
0x50B53   mov eax, [rbx+0x3640]
0x50B59   lea esi, [rax*4+0x46140]
0x50B60   mov edx, [rbx+0x128]
0x50B69   call [rax+0x130]   ; 原生寄存器接口
0x50B78   call 0x1108        ; 辅助过程，语义未确认
0x50B87   call 0x65FD4       ; 辅助过程，语义未确认
0x50B98   call 0x48BB6       ; HDMI 输出配置关键候选
0x50BB4   call [rax+0x140]   ; 端口虚函数
0x50BCB   call [rax+0x128]   ; 端口虚函数
0x50BDA   call 0x52106       ; HDMI 完成辅助过程
0x50BDF   xor eax, eax
0x50BE9   ret
```

**直接可证**：
- `0x46140 + 4 * [DisplayPath+0x3640]` 对应 Intel `TRANS_CLK_SEL` 家族；写入值直接来自 `[DisplayPath+0x128]`。
- 此顶层函数**没有**在已解码指令中直接读取 `[DisplayPath+0x12C]` 或直接写 `0x60400`。这**不证明**其子函数也没有访问该字段。
- 返回前 `xor eax,eax`，函数本身不以上层可见返回值区别 4K60 物理画面正常与黑屏。它内部是否有有效链路握手，在子函数反汇编前不能断言。

## 3. `setColorMode` 其实写的是 MSA_MISC，不是 HDMI 2.0 高 TMDS 控制

本机精确指令：

```asm
0x493D5   mov r13d, [r15+0x134]
...
0x494C2   mov [r15+0x134], r13d
0x494D4   add r12d, 0x60410  ; 之前 r12d=[r15+0x3640]<<12
0x494E5   mov rsi, r12
0x494E8   mov edx, r13d
0x494F9   jmp rax            ; 实际通过原生 RegisterAccessManager 写寄存器
```

从 Linux i915/Intel Display Register 定义可确认：
- `0x60410` 是 **`TRANS_MSA_MISC`**（各 Transcoder 可能有 `0x1000` 跨度）。
- `0x60400` 才是 **`TRANS_DDI_FUNC_CTL`**；后者的 HDMI Scrambling 与 High TMDS Clock Ratio bit0/bit4 由源端处理。
- `0x46140` 是 `TRANS_CLK_SEL`。

因此，`[DisplayPath+0x134]` 在原生 `setColorMode` 中代表其 MSA_MISC 配置缓存；**不得将这段代码或 `+0x134` 的位操作当作源端 SCDC/1:40 控制**。此前参考工程将 `DisplayPath+0x12C` 描述为 DDI Func Ctl shadow，目前本轮主函数和 setColorMode 窗口都没有直接访问该字段，**它仍未经本机数据流验证**。

参考：
https://linux.googlesource.com/linux/kernel/git/tip/tip/+/refs/heads/x86/urgent/drivers/gpu/drm/i915/display/intel_display_regs.h

## 4. 原生 I²C 调用是有状态的，不是无条件透传 GMBUS

```asm
0x53A20   push rbp
...
0x53A40   mov rdi, [rdi+0x9C8]
0x53A47   test rdi,rdi
0x53A4A   je 0x53A69
0x53A61   call [rax+0x1C0] ; 控制器现成 I2C 对象路径
0x53A69   lea rdx,[rbp-0x18]
0x53A70   call 0x53422     ; 对象不存在时的原生另一条路径
0x53A75   add rsp,0x20
0x53A7A   ret
```

这说明 `hwDoI2CRequest` 在 `[controller+0x9C8]` 非空时通过原生对象虚函数、为空时回落到 `0x53422`。这不能直接证明哪一路通过 GMBUS、哪一路通过 AUX，也没有证明它已经执行对 SCDC 地址 `0xA8` 的 I²C 请求；本机 4K30 下不存在观察到的 `0xA8` 不能证明 4K60 的行为。

**实现风险**：旧参考的 SCDC 请求若未经完整持锁/对象生命周期验证就直接调用本原生入口，可能在显示模式切换、热插拔、多屏共享资源时卡住甚至崩溃。不能仅因为函数位置和 prologue 匹配就启用旧 HDMI2 链路补丁。

## 5. 现在可以确定的顺序与仍须查证的顺序

**已有直接原生证据**：

1. 模式分流 `cfg+8==2` → `LightUpTMDS`；
2. `LightUpTMDS` 首先调用 `0x6CCB4`，然后从 `path+0x128` 写 `TRANS_CLK_SEL`；
3. 再进入未知作用的 `0x65FD4`、`0x48BB6`，及两个端口虚函数，最后调用 `0x52106`；
4. 无条件返回 `0`；
5. 独立的 `setColorMode` 将 `path+0x134` 写入 `TRANS_MSA_MISC`。

**仍未获得直接本机证据**：

- `path+0x12C` 是否由上述辅助方法读出并写到 `TRANS_DDI_FUNC_CTL(0x60400)`；
- 在 Display13 原生输出启动前是否已有 Apple SCDC 事务；
- `0x48BB6`、`0x52106`、`0x6CCB4` 分别负责什么硬件初始化、失败如何回滚；
- HDMI 4K60 的真实详细时序 / TMDS Character Rate / 1:40 / Source Scrambling 状态；
- Windows 4K60 正常是否说明本机板级完全支持 594MHz；本轮仅为 macOS 二进制静态研究。

## 6. 下一轮：直接导出真实 CALL 对应的辅助函数指令（不修改显卡驱动）

本分支增加 `wex4k60/native_macho_linktrace.py`（默认不调用任何设备接口、不需要 sudo；通过当前 Mach-O **UUID + SHA** 才导出）。它只读取原生 Mach-O 文件中 5 个已存在的辅助调用目标附近的有界指令：

- `0x48BB6`：`LightUpTMDS` 主配置阶段；
- `0x52106`：TMDS 输出后段；
- `0x6CCB4`：TMDS 初始调用；
- `0x65FD4`：输出辅助；
- `0x4D34C`：显示分流前调用。

命令：

```bash
cd ~/Downloads/Yoga_HDMI4K60_Audit
git pull --ff-only
python3 wex4k60/native_macho_linktrace.py \
  --out ~/Desktop/Yoga_Display13_HDMI_HelperTrace.json
```

下一轮重点是**真实验证 `+0x12C` 字段的消费与 `0x60400` 源端控制写入**，而不是先修 SCDC 的读写时序。只有发现数据流并确认 bit0/4 与锁/调用阶段正确，再讨论默认关闭的新 HDMI2 试验设计。

**安全门槛**：当前仅静态分析；冻结 SST 成功代码、内屏/HDMI Deep8/HDMI600、原 EFI。禁止启用旧 `-wex-yoga-hdmi2-route-only`、旧 HDMI2 link route 或固定 Pipe 2 的 MMIO 写入。CI 通过不能替代真实 4K60 硬件验证。
