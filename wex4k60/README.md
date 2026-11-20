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

## 补充：官方 0.8.3 已存在的 Display13 GMBUS 记录

源码静态核对已确认，官方 0.8.3 的 Display13 路径会安装 `wrapDisplay13GMBus()` 观察器（状态 `N97FBGMBusObservationReady`），并可记录 `N97FBGMBusLast`、`N97FBGMBusHistoryLast` 等。新采集脚本现已纳入这些字段，`compare.py` 能解析 `N97FBGMBusLast` 的原生返回码和请求状态。这些记录可能只是 EDID DDC，**不能直接当成 SCDC 事务**。

此外，现有 `wrapTGLLightUpTMDS` 位于 TGL 路由，而不是已证实在 Yoga A7A0 Display13 上安装的 HDMI TMDS Hook。旧版自定义 Display13 路由曾造成实机加速丢失；这次必须先做原生符号/ABI/调用路径静态鉴别，绝不直接把它移植到成功 Kext。

[详细源码位置、记录字段和风险边界](STATIC_SOURCE_AUDIT.md)

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
