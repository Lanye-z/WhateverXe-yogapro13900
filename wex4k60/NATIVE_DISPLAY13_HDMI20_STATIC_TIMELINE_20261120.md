# Yoga A7A0｜机身 HDMI 2.0 / 4K60 初始化阶段静态分析

**分析日期：2026-11-20。状态：仅源码与已上传 4K30 IORegistry 对照；未修改 EFI、Kext、雷电和 SST。尚未拿到本机 Apple Display13 驱动 Mach-O 的逐指令反汇编，本文中的原生偏移/结构体字段是“同 A7A0 参考实现的待验证假设”，不是经过本机反汇编确认的事实。**

## 0. 原生驱动身份已由本机 4K30 日志确认；字节级检验工具已加入

2026-11-20 17:26 的 `kmutil showloaded` 已明确列出：
- `com.apple.driver.AppleIntelTGLGraphicsFramebuffer (16.0.0)`
- 原生驱动 **UUID `B6078743-F795-3202-A55E-EA690FA40949`**
- 其映射镜像大小在 `kmutil showloaded` 中为 `0xC8000`
- 实际运行的 `org.b00t0x.WhateverXe 0.8.3`、`Lilu 1.7.3`
- 系统：macOS Tahoe 26.7.1（`25G241`）

**重要发现**：这个 UUID 与过去 `HDMI600` 静态研究和同 A7A0 参考实现使用的驱动 UUID 一致，因此参考的方法入口偏移具有实质核验价值。但仅凭加载 UUID 无法证明本机磁盘中的 Mach-O 与参考每个字节完全相同，更不代表安装任意 trampoline 安全。

为弥补字节证据，分支已经增加 **`wex4k60/native_macho_audit.py`**：只读扫描本机 `/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer`（或传入显式路径）。输出：
- 设备内本机文件 SHA-256、Mach-O UUID，与当前加载 UUID 的比较；
- 从 Mach-O `LC_SEGMENT_64` 文件映射转换参考 `image+0x...` 的字节偏移，不把镜像相对偏移误当文件偏移；
- `getOnlineInfo(+0x2E232)`、`setColorMode(+0x491F2)`、`LightUpTMDS(+0x50B22)`、`hwDoI2CRequest(+0x53A20)`、`hwDoGMBusRequest(+0x53A7C)` 的入口 8 字节匹配情况及局部机器码；
- 参考 `LightUpTMDS` return PC `image+0x4FFBB` 前的 direct CALL `E8 rel32` 与预期函数目标的匹配（若非 direct call，只标记无法由该检查确认，不武断认定调用错误）；
- 若保留相关符号表，则额外报告这些方法的符号相对地址。

运行（**只读、无需 sudo**）：

```bash
python3 wex4k60/native_macho_audit.py --out ~/Desktop/Yoga_Display13_NativeAudit.json
```

输出只包含目标函数的局部字节、UUID 与哈希，不拷贝整个 Apple 驱动。上传该 JSON 前仍应自行检查是否含不愿公开的数据。若自动定位失败，将本机实际二进制路径作为第一个位置参数，不应传 `WhateverXe.kext` 代替。

脚本通过 Github Actions 的合成 Mach-O、CALL 目标/地址映射和越界检查；**这不是原生驱动验证通过**，只有实机 JSON 返回后才能对本机原生指令做结论。

---
## 1. 研究证据和边界

**用户本人成功基线：** `Yoga_HDMI4K60_hdmi30_20261120_172654.zip`。macOS 26.7.1、A7A0、1536MB/Metal，内屏在本次记录中为 **60Hz**，27B2 1080p75，AOC U27P10 3840×2160@30Hz。目标 HDMI U27P10 当前绑定 **Pipe 2**（不能按旧双屏实验假定固定 Pipe 1）；像素时钟 297MHz、`TRANS_DDI_FUNC_CTL=0x90030200`、`PIPE_MISC=0x01800810`、YCbCr444 8bpc。HDMI600 准入上限 600MHz；EDID VIC93–97 包含 4K24/25/30/50/60，HF-VSDB `D8 5D C4 01 78 80 00` 声明 SCDC Present 及 Max TMDS 600MHz。GMBUS 报告有成功读取 EDID `0xA0` 的操作，4K30 状态没有观察到 SCDC `0xA8`，后者是正常低速模式的合理现象，**不能推导 4K60 时没有 SCDC 事务**。SST DDI5 首次 MST 缓存 1→0、训练成功，已有三屏/热拔插实机验证，HDMI 研究不能碰该路径。

**公开/已有代码依据：**

1. Linux DRM i915 `intel_hdmi.c`：`intel_hdmi_compute_config` 先基于目标 `port_clock`、sink SCDC 与源端能力，决定 `hdmi_scrambling`、`hdmi_high_tmds_clock_ratio`。当需要 >340MHz TMDS 时应考虑两者；还提醒可能存在 *HDMI 1.4 retimer/VBT* 板级约束，不能因为 iGPU 支持就假定整个 HDMI 电路完全支持。
   - https://cos.googlesource.com/third_party/kernel/+/9a7cf3745fab2b8386673ec64349320fb7a844f1/drivers/gpu/drm/i915/display/intel_hdmi.c
2. Linux i915 `intel_ddi.c`：`intel_ddi_transcoder_func_reg_val_get` 在 HDMI 的 `TRANS_DDI_FUNC_CTL` 组合 source bit 0 Scrambling 和 bit 4 High TMDS Character Rate；`intel_enable_ddi_hdmi` 在开启 DDI buffer/output 前调用 `intel_hdmi_handle_sink_scrambling`。注意 Linux 的 Transcoder/Clock 部分可能在 SCDC 前已作准备，所以 **“在 HDMI 输出激活之前”不等于“在所有 PLL/Pipe 操作之前”**。
   - https://gbmc.googlesource.com/linux/+/4f5e249ec0ea8872e1644df23cffffbe28007188/drivers/gpu/drm/i915/display/intel_ddi.c
3. Linux i915 `intel_hdmi.c`：`intel_hdmi_handle_sink_scrambling` 依次设置 sink 的高 TMDS 比率、扰码；其注释明确指出需在 HDMI 2.0 输出激活前。传输开始后 `intel_hdmi_poll_for_scrambling_enable` 检查 sink Scrambling_Status（最长约 200ms）；关闭 HDMI 时 `intel_disable_ddi_hdmi` 清除 sink 配置。
4. 同为 Intel `8086:A7A0` 的 **Wtrwx Lenovo Air14 IRP8** 公开源码（基于 WhateverXe 0.7.0，系统 26.7.2）：其 README 报告机身 HDMI `2560×1440@144Hz` 实机可用，但也报告过 GPU 挂起，**不能将该工程直接视作本机长期稳定修复**。
   - https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh
   - https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh/blob/main/sources/WhateverXe/WhateverXe/kern_xe.cpp
   - https://github.com/Wtrwx/Lenovo-Air14-IRP8-Hackintosh/blob/main/sources/WhateverXe/WhateverXe/kern_display13_hdmi_scdc.hpp
5. 我们自己的早期高风险实验 `experiment/wex-0.8.3-yoga-hdmi2-route-diag`：仅启用 `-wex-yoga-hdmi2-route-only` 时实机出现**核显硬件加速丢失、机身 HDMI 不亮**。不能直接再次采用它的独立 TMDS trampoline，也不能因 CI 编译成功而判定安全。
   - https://github.com/Lanye-z/WhateverXe-yogapro13900/blob/experiment/wex-0.8.3-yoga-hdmi2-route-diag/wexlink/ROUTE_DIAG_README.md

## 2. 阶段与候选 Apple Display13 原生函数对应表

| 工作阶段 | 函数/对象 | 现在能确认的内容 | 仍需反汇编确认 |
| --- | --- | --- | --- |
| ① 连接/EDID | `AppleIntelPort::getDDCBlock`、`AppleIntelFramebuffer::getOnlineInfo`、DDI B | 当前已成功读取 `0xA0` EDID；`HDMI600` 只放宽 `getOnlineInfo` 的 300→600MHz 模式准入。 | 参考符号偏移 `getOnlineInfo +0x2E232`（是 *函数相对镜像起点* 而非方法内部偏移）；HF-VSDB 是否已传到原生模式设置路径、GMBUS 请求持锁状态 |
| ② Mode / 色彩 | `AppleIntelFramebufferController::setColorMode` 与时序/ClockParams | 4K30 当前为 8bpc YCbCr444；这是稳定先决条件。 | 参考同 A7A0 donor 方法入口 `+0x491F2`；`IODetailedTimingInformationV2::pixelEncoding`、`bitsPerColorComponent` 的值，4K60 的 `pixelClock`、真实 TMDS Character Rate |
| ③ sink 高速协商 | `AppleIntelFramebufferController::hwDoI2CRequest`，DDC/GMBUS | 本机当前 `N97FBGMBus*` 观察 Hook 已安装，EDID/普通 DDC 在 4K30 可用。SCDC 8-bit I²C 地址 `0xA8`、寄存器 `0x20` (bit 0 Scrambling_Enable、bit 1 TMDS_Bit_Clock_Ratio)。 | 参考方法入口 `+0x53A20`、原生 ABI、DDC pin/锁的安全上下文、read-modify-write/readback 是否能在输出激活前完成。**本次尚未观察到真实 SCDC 成功。** |
| ④ source 控制准备 | `AppleIntelDisplayPath` 缓存控制字→`TRANS_DDI_FUNC_CTL` | Linux i915 的 bit0=源端 Scrambling、bit4=High TMDS Character Rate；它们必须与 sink 高速状态匹配，在原生端口激活前准备。 | 同 A7A0 参考把 `path+0x12C` 称作进入 `TRANS_DDI_FUNC_CTL` 的 shadow，`path+0x128` 进入 `TRANS_CLK_SEL`；**本机 Apple 原生字段布局、落入 MMIO 的调用链尚未独立验证，禁止直接写 0x12C**。 |
| ⑤ 激活 TMDS | `AppleIntelFramebufferController::LightUpTMDS` | 参考 A7A0 源码明确在调用 original `LightUpTMDS` **之前**运行 `prepareDisplay13HDMISCDC`、完成后才调用原生输出。 | 参考函数入口 `+0x50B22`、参考调用点返回地址 `image+0x4FFBB`；两者必须用本机 **Apple donor Mach-O** 的符号与实际 call disassembly 证明，不能凭 WEX 版本/函数前缀即视为已证实。 |
| ⑥ 验证/回滚 | `LightUpTMDS` 之后、disable display / 恢复 4K30 | Linux 高速发送启动后检查 SCDC Scrambling_Status `0x21`；关闭时需清理 sink 高速配置。 | Apple 原生停止输出、清理 PLL/Pipe、连接代数和共享多屏资源的时序；目前尚未获取同条件 4K60 黑屏数据 |

**重要区别**：参考 `AppleIntelFramebufferController::setColorMode +0x491F2` 等数值是*镜像内函数入口偏移*，不是“源码改到该绝对内存地址”。只有当前实际的 Apple Driver UUID、函数符号、机器码和调用边校验一致，才可能安全用于后续诊断。

## 3. 针对 HDMI 4K60 的推荐执行顺序（设计而非实机已验证）

1. **枚举期（无 HDMI 输出写操作）**：使用 EDID HF-VSDB、最大速率和 VBT 板级约束确定 HDMI 2.0 能力；只允许有效模式进入候选表。`-wex-yoga-hdmi600` 已完成候选模式准入。
2. **模式计算期**：以实际选择的 3840×2160@60 详细时序为依据，确定 RGB/YCbCr444/YCbCr420、8bpc 以及真正的 TMDS Character Rate；不得简单认定 4K60 必然是 594MHz。仅当目标高于 340MHz、sink 有 SCDC 能力、source/线路也经过验证时，计划高速配置。
3. **已有原生 Display13 时钟与模式对象准备好、HDMI 发送端尚未激活的窗口**：在已经确认 HDMI B 实际所有权/连接代数、DDC 通路与锁顺序的情况下，读取 SCDC sink version `0x01`，按需更新 source version `0x02`，读取 `TMDS_CONFIG(0x20)` 并设置 `Scrambling_Enable=1`、`TMDS_Bit_Clock_Ratio=1`，再读回确认。**不得在未知锁下发起阻塞 GMBUS**，且避免过早协商后延迟很久才启动高速 TMDS（sink 可能复位）。
4. **同一模式对应的源端准备期**：在原生将 shadow 控制写入 `TRANS_DDI_FUNC_CTL` 之前，为该 HDMI 输出计算设置 Scrambling / High-TMDS 标志（参考 bit0|bit4=`0x11`）；必须保留 DDI、Pipe、BPC、使能等原有位，不把整字 `0x90030211` 写死，也不直接写 Pipe2 MMIO。
5. **原生 `LightUpTMDS` / HDMI port activation**：使用原生 PHY、PLL、Clock、Pipe 与 InfoFrame 路径；**先验证原生写入行为再做额外改动**。SCDC 成功不等于 CLK/PHY 也成功。
6. **发送后验证**：如果上层安全允许，读取 SCDC `Scrambling_Status`（常见 offset `0x21`）验证真正生效；任何失败都必须记录阶段和真实硬件回执，不能伪造 `kIOReturnSuccess`。
7. **模式切换/失败回滚**：停用高速输出时恢复 sink TMDS_CONFIG 的低速设置，并使后续 source flags 匹配；同时遵循原生时钟/Transcoder 资源释放顺序。低速 4K30 的已验证路径不应被一次失败的高速事务锁死；尤其不能操作共享 eDP、另一外屏或 SST 链路。

## 4. 与 Wtrwx 同 A7A0 实现的精确静态对应

其公开 `kern_xe.cpp` 中：

- `processDisplay13FramebufferOutput` 第 7237–7255 行：精确查找 `getOnlineInfo(+0x2E232)`、`setColorMode(+0x491F2)`、`LightUpTMDS(+0x50B22)`、`hwDoI2CRequest(+0x53A20)`，使用固定函数前缀匹配。该符号表是**参考源代码声称的地址假设**。
- 第 7290–7303 行：与官方 0.8.3 不同，参考代码把 `LightUpTMDS` **并入** Display13 输出层的同一组 `routeMultipleShort`；官方 0.8.3 的 Display13 路由组当前**没有该函数**，而通用的 `wrapTGLLightUpTMDS` 只出现在另一 TGL 调度路径。因此仅修改通用 TGL wrapper 而不确认实际路由，可能根本没有执行。
- 第 8372–8416 行：`prepareDisplay13HDMISCDC` 完成 sink I²C 协商，然后在 `complete` 时更新参考 `DisplayPath+0x12C` 的 shadow 字段 `(control & ~0xD1) | sourceFlags`。参考 `sourceFlags=0x11` 代表 High TMDS Ratio + Source Scrambling。**它不是本机已验证的偏移。**
- 第 19307–19321 行：`wrapTGLLightUpTMDS`（参考已经在 Display13 安装）首先检验调用地址 `image+0x4FFBB`，调用 `prepareDisplay13HDMISCDC`，成功后再调用 native `LightUpTMDS`。这种用 return PC 拒绝所有非指定调用点的策略本身也可能造成兼容性问题；**不得直接移植**。
- 其 `kern_display13_hdmi_scdc.hpp` 的 `negotiateSCDC` 包含 `0xA8` 8-bit DDC I²C、SCDC `0x20`、设置读回和事务失败后 sink 回滚。然而它所用的 Apple `IOI2CRequest` ABI 与 native GMBUS 锁所有权仍应在**本机**确认。

**过去的失败教训**：我们旧实验 `wexlink/prepare_route.py` 同样试过独立安装 `LightUpTMDS(+0x50B22)`，即使只是 route-only，也出现丢失 GPU 加速的问题。其原因尚未由崩溃/IORegistry 证实，可能是短跳转 trampoline/ABI、重入、时序或原有路径冲突。不能把同 A7A0 参考成功当成修复该旧回归的证据。

## 5. 当下可以判断与尚不能判断的事情

- **已确定（由公开源码）：** i915 先计算模式/时钟与 Scrambling 标志，sink SCDC 在 HDMI 输出激活前配置，source 在输出激活前有匹配控制位，发送后应核验状态，停用时应复位高速配置。
- **已确定（由同 A7A0 参考代码）：** 参考工程在调用原生 `LightUpTMDS` 前执行 SCDC 协商，并将 source 配置准备在 DisplayPath shadow，而非直接给 live MMIO 写固定值。
- **已确定（由本机基线）：** 297MHz/4K30、Deep8/HDMI600 有效；EDID 声明 4K60/SCDC；没有本机 4K60 成功传输或 SCDC 事务证据。
- **尚不能确定：** Apple 原生 Display13 是否已在 4K60 自动发 SCDC；`+0x50B22`/调用点是否匹配本机 Apple donor；`path+0x12C` 的确切字段布局；是否还有 PHY/PLL/板级 HDMI retimer 限制；旧 route-only 为什么丢加速。**这些都不能通过 4K30 的 IORegistry 和其它机型源码直接证明。**

## 6. 后续最安全的静态验证任务

在当前成功 EFI **不变**的情况下，拿到本机**实际加载的 AppleIntel Graphics Framebuffer donor Mach-O 文件及其 UUID**（不是 WhateverXe.kext 插件）。基于该确切文件：

1. `nm` / 符号表 / `otool` 反汇编 `getOnlineInfo`、`setColorMode`、`LightUpTMDS`、`hwDoI2CRequest` 以及发起 `LightUpTMDS` 调用的方法；核对其镜像偏移、参数寄存器/栈与 callsite；
2. 静态追踪 `LightUpTMDS` 周围 `TRANS_DDI_FUNC_CTL` 写入的读值来源，只有确证 Apple `DisplayPath` shadow 与 `path+0x12C` 对应时才设计更改；
3. 确认原生驱动本身是否已发出 SCDC 读/写；区分“不存在”“被门控跳过”“时序失败”和“原生已有但仍黑屏”，防止重复配置；
4. 对照 Linux i915 的 PLL/PHY/Combo B 编码路径和源端比率配置，确认板级 VBT/固件是否支持高速模式；
5. **仅在以上条件满足时**，从已成功的 SST 研究分支建立一个真正修改 HDMI 的新实验补丁，默认关闭并使用独立测试 EFI。此前的旧 `-wex-yoga-hdmi2-route-only`/ `-wex-yoga-hdmi2-link` **不得复用为默认行为**。

**本报告仅静态分析，不声称已经修复 HDMI 4K60，也不要求用户再次触发危险的黑屏模式。**
