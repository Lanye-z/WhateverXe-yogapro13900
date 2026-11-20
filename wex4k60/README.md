# Yoga Pro 14s IRH8 / A7A0 — 机身 HDMI 4K60 黑屏研究

> **2026-11-20 · 第一阶段：已建立安全的只读取证工具；尚未生成 HDMI2 修复 Kext。**
> 此分支直接从已实机成功的 `experiment/wex-0.8.3-yoga-usbc-sst-compat` 派生，保持 HP G4 USB-C SST 三屏扩展和热拔插正常的源代码不变。当前无需更换 WhateverXe，更不能将旧 HDMI2 实验版替换到日常 EFI。

## 当前可复现的事实

| 接线与模式 | 已观察到的结果 | 解释范围 |
| --- | --- | --- |
| 4K 屏接 HP G4 DP、USB-C 兼容模式 | macOS 只提供 4K30，用户已成功使用 SST 三屏及热插拔 | 历史 DDI5 日志记录为 2 lanes HBR2（有效视频带宽 8.64Gbps）；不能由此推断 EDID 一定提供 25/24Hz，也不能断言 HP G4 在其他连接模式下不支持 4K60 |
| 同一 4K 屏接机身 HDMI，DDI B | 4K60 选项出现，但切换后外屏黑屏 | **模式准入成功 ≠ 高速 TMDS 链路建立成功** |
| 机身 HDMI 4K30 / Deep8 | 先前已验证颜色正常、YCbCr 4:4:4 / 8bpc | 作为安全对照模式 |
| 内屏 3K120、GPU Metal、SST 外屏 | 在当前 SST 成功版保持正常 | 所有新试验必须避免使它们回归 |

历史证据：`wex600/README.md` 中的 `-wex-yoga-hdmi600` 仅将 `AppleIntelFramebuffer::getOnlineInfo` 的 HDMI 像素时钟准入 300MHz 改成 600MHz（精确机器码匹配）。此补丁**没有进行** SCDC 读写、high TMDS clock ratio、源端 scrambling 控制或 PHY/PLL 链路重配置。

早期实验出现过严重失败：
- `experiment/wex-0.8.3-yoga-hdmi2-link-safe`：曾尝试 HDMI Forum EDID 能力、SCDC I2C 和源端控制字段，但尚未经本机验证。
- `experiment/wex-0.8.3-yoga-hdmi2-route-diag`：单独的 Display13 TMDS 原生函数路由观察版，用户实机反馈仅启用 route-only 就出现核显加速丢失、机身 HDMI 不亮；绝不可把旧路由代码直接重新启用。
- 更早 4K60 切换后外屏黑屏，返回 30Hz 时曾出现内外屏同时黑屏，存在模式失败回滚风险。

## 研究假设（尚未确认根因）

1. **Sink 端高速 HDMI 2.0 协商**：如果实际 TMDS character rate 高于 340MHz，需要结合 EDID/HF-VSDB 的 SCDC 能力判断是否要求 SCDC `TMDS_CONFIG` (0x20) 的 scrambling / high TMDS bit，以及 Source 与 Sink 双端状态是否一致。不能用“macOS 列出 60Hz”推断已经完成。
2. **实际 4K60 的链路时钟与像素格式**：常见 3840×2160@60Hz 8-bit 4:4:4 需要约 594MHz TMDS，若是带减少消隐的模式可能约 533MHz；但 YCbCr 4:2:0 可以使用显著更低的 TMDS 速率。因此务必先核对正在请求的像素时钟、YCbCr 444/420、8/10 bpc，不能先验认定一定需要高比率。
3. **macOS 原生 GMBUS/DDC 操作能力**：若 SCDC 需要写/读回 0x20，必须确认实际物理 HDMI DDI B 的 I2C 事务协议、锁和引用生命周期；旧工程的模拟通过不等于原生请求成功。
4. **源端 Combo PHY / TMDS / PLL / Pipe 的进入与退出**：当 4K60 选择失败时，可能未在正常时序设置 source scrambler、高 TMDS 比率，或时钟/水位/资源状态没有回滚，导致再选 4K30 仍黑屏。不得在没有对照日志时强行写 PLL/PHY、覆盖原生返回码。
5. **线缆与显示器模式协商**：虽然同一 HDMI 路径的低刷新率成功，但还需要用显示器 OSD 与相同线缆/接口确认问题是否仅发生在高时钟。

Linux i915 的成熟参考实现将 sink SCDC 状态、高 TMDS 比率和 Source 端 HDMI 寄存器配置分开处理，见：
- https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/235f2b548d7f4ac5931d834f05d3f7f5166a2e72/drivers/gpu/drm/i915/display/intel_hdmi.c
- https://github.com/b00t0x/WhateverXe/issues/41 （另一个 ADL-S 平台仅放宽 300MHz 已有实际成功；不适用于推断本机）
- https://github.com/Lanye-z/WhateverXe-yogapro13900/blob/experiment/wex-0.8.3-yoga-hdmi2-route-diag/wexlink/ROUTE_DIAG_README.md （本机危险旧实验，**仅供复盘**）

## 本机 Mach-O 首轮结果已确认：5/5 函数、真实 TMDS CALL

用户已成功执行 `native_macho_audit.py` 并提供 `Yoga_Display13_NativeAudit.json`。实际 Apple 驱动 UUID **`B6078743-F795-3202-A55E-EA690FA40949`**、SHA-256 **`115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`**。`getOnlineInfo`、`setColorMode`、`LightUpTMDS`、`hwDoI2CRequest`、`hwDoGMBusRequest` **5/5 个真实符号入口、前 8 字节均符合此前 A7A0 参考**。

更重要的是：本机 `image+0x4FFB6` 的指令 `E8 67 0B 00 00` 实际 `call 0x50B22`，也就是原生 `LightUpTMDS`；`image+0x4FFBB` 正是参考中写的 return PC。近邻指令按照 x86-64 ABI 传入 controller、framebuffer、display path 和 timing。**这只解决了入口和一条调用边，不能证明旧 TMDS Hook 安全，也不能证明 SCDC/源端控制已工作。**

另一个值得查明的细节：在这条分支 `LightUpTMDS` 后的指令是 `jmp 0x4FFD9; xor r13d,r13d`，没有直接将 `EAX` 用作该分支的返回状态。要进一步跟踪父方法状态返回与失败回滚，不能凭此声称 macOS 已错误返回成功。

[查看完整原生机器码实证和旧 Route 风险分析](NATIVE_DISPLAY13_AUDIT_RESULT_20261120.md)。

### 下一个只读步骤：进一步定位源端控制字段

为确认参考的 `DisplayPath+0x12C` 能否映射到本机 `TRANS_DDI_FUNC_CTL`，已经新增 `native_macho_deep.py`，严格检查当前 Apple 原生 Mach-O 的 **UUID 和 SHA-256 都完全匹配** 才进行导出。它仅从驱动文件提取少量有边界的函数及调用点机器码，不修改任何设备状态：

```bash
cd ~/Downloads/Yoga_HDMI4K60_Audit
git pull --ff-only
python3 wex4k60/native_macho_deep.py --out ~/Desktop/Yoga_Display13_NativeDeepTrace.json
```

仅需提供 `Yoga_Display13_NativeDeepTrace.json`，无需重新切换 4K60、运行旧 HDMI2 Route 或上传整个 Apple 二进制。若驱动 SHA/UUID 不匹配，脚本会拒绝执行，而不是错误应用参考偏移。

---

## 下一轮只读验证：原生 Apple Mach-O（不用再次切 4K60）

最新 4K30 日志的 `kmutil showloaded` 已确认当前加载的 Apple 显示驱动 UUID 为 **`B6078743-F795-3202-A55E-EA690FA40949`**，与旧 HDMI600 研究的 Apple donor UUID 一致。要进一步确认原生 TMDS/SCDC 函数和调用指令，现有分支增加了 `native_macho_audit.py`（Python 标准库、无需 sudo、不依赖额外安装包）：

```bash
python3 wex4k60/native_macho_audit.py --out ~/Desktop/Yoga_Display13_NativeAudit.json
```

该脚本只从实际安装的 Apple Mach-O 读取文件字节，输出 UUID、SHA-256、所需 5 个函数的局部 64 字节及 `image+0x4FFBB` 调用邻域的 128 字节。它不更换 WhateverXe、不读取整个驱动上传、不写硬件寄存器、不切换显示模式，**不是 EFI 修改脚本**。

如提示找不到目标文件，请确认实际安装位置后传入完整路径作为位置参数，例如：

```bash
python3 wex4k60/native_macho_audit.py "/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer" --out ~/Desktop/Yoga_Display13_NativeAudit.json
```

只需将生成的 JSON 提供给研究分析，不需要提交完整 Apple 驱动二进制；脚本会报告入口机器码是否匹配，但 ABI、返回地址以及 DisplayPath 控制字段还需要据此进一步解释。**在本机真实指令尚未核验前，旧 HDMI2 Route Hook 仍禁止测试。**

[原生 Mach-O 校验与静态调用顺序完整记录](NATIVE_DISPLAY13_HDMI20_STATIC_TIMELINE_20261120.md)

---

## Display13 HDMI 2.0 的静态调用顺序已经建立（尚未写驱动补丁）

根据 **Linux i915 + 同 A7A0 的 Air14 参考源码 + 本机正常 4K30 日志**，高速 HDMI 的候选阶段顺序应为：

`EDID/getOnlineInfo` → `setColorMode/ClockParams` → **（在 TMDS 物理输出启用前）sink SCDC 0x20 协商与读回** → **准备 source Scrambling/High TMDS ratio 控制字段** → 原生 `LightUpTMDS` 启用 → sink Scrambling_Status 验证；失败/降到 4K30 时恢复 sink/source 状态。

官方 0.8.3 的 Display13 **没有注册**与 TGL dispatcher 相同的 `wrapTGLLightUpTMDS` 路由，参考 A7A0 则在 Display13 输出安装组中增加了这一函数。我们过去的独立 route-only Hook 曾引起实机加速丢失，因此 **不得直接照搬该路由/偏移/结构体字段**。

已读取本次用户 `hdmi30` IORegistry：`N97FBOutputHooksReady=Yes`、`N97FBGMBusObservationReady=Yes`，但 `TGLWEGRoutePathObservations` 与旧自定义 `WEXYogaHDMI2TMDSRouteStatus` **未发布**。这与目前代码分流路径一致，并非证明 Apple 原生从未调用 HDMI LightUp。

[详细函数映射、控制位、风险与下一步原生 Mach-O 验证方案](NATIVE_DISPLAY13_HDMI20_STATIC_TIMELINE_20261120.md)

---

## 补充：官方 0.8.3 已存在的 Display13 GMBUS 记录

源码静态核对已确认，官方 0.8.3 的 Display13 路径会安装 `wrapDisplay13GMBus()` 观察器（状态 `N97FBGMBusObservationReady`），并可记录 `N97FBGMBusLast`、`N97FBGMBusHistoryLast` 等。新采集脚本现已纳入这些字段，`compare.py` 能解析 `N97FBGMBusLast` 的原生返回码和请求状态。这些记录可能只是 EDID DDC，**不能直接当成 SCDC 事务**。

此外，现有 `wrapTGLLightUpTMDS` 位于 TGL 路由，而不是已证实在 Yoga A7A0 Display13 上安装的 HDMI TMDS Hook。旧版自定义 Display13 路由曾造成实机加速丢失；这次必须先做原生符号/ABI/调用路径静态鉴别，绝不直接把它移植到成功 Kext。

[详细源码位置、记录字段和风险边界](STATIC_SOURCE_AUDIT.md)

## 2026-11-20 17:26 已完成机身 HDMI 4K30 成功基线分析

用户上传了完整 `hdmi30` 采集包并完成静态解码，**没有要求再次切换 4K60**。重点结果：

- 当前 macOS 26.7.1 三屏：内屏 3072×1920 **60Hz**（120Hz 补丁准入就绪但本次实际是 60Hz）、27B2 1080p75、U27P10 3840×2160@30Hz；FrameBuffer@2 的 HDMI 像素时钟 **297MHz**，时钟准入上限 **600MHz**。
- **机身 U27P10 HDMI 使用 Pipe 2**，`TRANS_DDI_FUNC_CTL=0x90030200`、`PIPE_MISC=0x01800810`（YCbCr 4:4:4 / 8bpc）。不能按旧双屏状态把 HDMI 固定映射为 Pipe1。
- 当前 U27P10 有效 EDID 中 VIC93–97 分别声明 4K24/25/30/50/60；HDMI Forum VSDB `D8 5D C4 01 78 80 00` 声明 **Max TMDS 600MHz**、**SCDC Present**。排除本轮机身 HDMI 的 EDID 未声明 4K60 或 SCDC。
- Display13 GMBUS 成功读取 EDID I²C 地址 `0xA0`；部分 `0x74` DDC/CI 风格请求返回 `kIOReturnNotResponding`、其他无效参数返回 `kIOReturnBadArgument`。**正常 4K30 本来就有这些错误，不得作为 4K60 的 SCDC 故障证据**；该轮 GMBUS 请求 1–17 没有 `0xA8` SCDC 请求。
- SST 补丁的 `FirstDPCD` 首次缓存 **1→0**、累计屏蔽 4 次，DDI5 训练前四次返回 0，直接支持三屏/热拔插修复的已确认结果。
- `USER_OBSERVATION.txt` 未填写 OSD，不能用软件报告代替显示器物理输入时序确认；**尚无黑屏 4K60 同条件对照**。

[完整脱敏证据表与逐项解码](BASELINE_20261120_HDMI30.md)

---
## 阶段 A：使用现有成功 Kext 完成只读取证

**当前分支只增加脚本和文档，完全不更改 WhateverXe 生成器、Kext、NHI/雷电、Graphics、EDID 覆盖、OpenCore 配置或现有启动参数。**

1. 保留当前真正能用的 SST EFI，保持 `-wex-yoga-tc5-sst`，内屏 120Hz 和 HDMI Deep8/HDMI600 参数原样。
2. 同一 4K 显示器、同一 HDMI 线接机身 HDMI，停在**实际能正常显示**的 4K30，采集：
   ```bash
   bash wex4k60/collect.sh hdmi30
   ```
3. **只有在内屏或远程恢复入口可靠、能接受再次黑屏时**，才单次手动切到 4K60，并在黑屏时从仍可用的内屏/远程终端采集。脚本本身绝不会切换刷新率：
   ```bash
   bash wex4k60/collect.sh hdmi60black
   ```
   如果之前已经有同一环境下的失败日志，优先复用，不必为了采集而再次触发黑屏。
4. 如果成功切回 4K30，采集 `bash wex4k60/collect.sh hdmi_recovered`；若内屏也黑，停止尝试，使用已保留的恢复 EFI，不要重复模式切换。
5. 捕获保存在桌面 `Yoga_HDMI4K60_<stage>_<timestamp>.zip`，本地可比较：
   ```bash
   python3 wex4k60/compare.py ~/Desktop/Yoga_HDMI4K60_hdmi30_*.zip ~/Desktop/Yoga_HDMI4K60_hdmi60black_*.zip
   ```
   若有多个文件，**应传入明确的那两个路径**，不要用可能匹配多个 ZIP 的通配符。

`compare.py` 仅对比已有 IORegistry、system_profiler、模式和时钟记录。它无法凭空读出未公开的真实 SCDC 事务、源端 HDMI Scrambling、PLL 现场值；此类信息缺失必须如实标为**尚无证据**。

采集后优先核查 `IOFBCurrentPixelClock`、`WEXYogaHDMI600Status`、`WEXYogaHDMIEDIDABApplied`、`WEXYogaHDMIColorModeLive`、`N97FBClock*`、`N97FBPipe*`、`N97FBDBUF*`、内外屏实际反馈。注意系统显示 60Hz 不代表屏幕实际有信号。ZIP 可能含 EDID、NVRAM 启动参数、设备序列号等，请上传前检查隐私信息。

## 阶段 B：在源代码中定位真正缺失的高速 HDMI 步骤

拿到 A 阶段证据后，只进行**源码/反汇编静态比对**，选出最小可验证修改：
- 比对 `getOnlineInfo` 模式准入与 Display13 原生 HDMI LightUp 函数实际调用路径；**不要再安装上次导致 22MB/无加速的重复 Hook**。
- 从已存在的安全包装层寻找可以不增加新原生路由的观察点；若实在需要新的包装器，先通过完整符号、ABI、offset、寄存器偏移、锁顺序与 Mock/CI 验证，默认关闭。
- 分离 HDMI sink SCDC 能力、SCDC 写/读回、source 高 TMDS ratio/scramble、PLL/PHY 模式、失败后的 4K30 回滚，每个都要独立证据。
- 只有确认模式属于高时钟 4:4:4/8bpc 且 sink 报告支持的情况下，才研究完整的 SCDC 高速路径；不得把 SCDC 当作唯一原因。

## 验收和回退

只有同时满足**4K60 画面真实出现（显示器 OSD/实际画面）**、内屏 3K120、Metal/1536MB、机身 HDMI 4K30/60 来回切换、SST 三屏与热插拔都保持正常，才可称作修复成功。GitHub CI 和 IORegistry 的 60Hz 状态都不能代替实机验收。

未来的内核补丁必须来自**独立新增开关、默认关闭**的实验版本，先在另一份 EFI 中测不带新参数，再进行高度受控的 4K60 测试；不得覆盖 SST 成功 EFI，不触碰 `main`。
