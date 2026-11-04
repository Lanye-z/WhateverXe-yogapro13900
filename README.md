# WhateverXe A7A0 — D1.1 封存记录（2026-11-05）

> **状态：研究暂停 / Archived — 不再主动开发 D1.1。** 当前电脑的日常使用暂时不依赖 HEVC 硬件编码，现阶段优先保持已能工作的显示和视频解码环境。**封存不代表两项视频问题已修复，也不代表本次重构后的 D1.1 Kext 通过了新的实机验收。**

| 项目 | 封存信息 |
| --- | --- |
| 设备 | Lenovo Yoga Pro 14s IRH8（82Y7）、Intel Core i9-13900H、Iris Xe PCI 8086:A7A0 rev 04 |
| 测试系统 | macOS Tahoe 26.7.1，Build `25G241` |
| 实验分支 | [`D1.1`](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/D1.1)（此分支保留，仅供后续恢复研究） |
| 日期快照 | [`archive/D1.1-2026-11-05`](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/archive/D1.1-2026-11-05)（保存本次 README 与源码状态） |
| Kext 上游基线 | [WhateverXe](https://github.com/b00t0x/WhateverXe) 0.7.0，固定提交 `d0b7fb6275ca51fde088fa7e91595462bd457ec9` |
| Graphics 基线 | [WhateverXe Graphics v0.4.0](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.0)，使用上游已签名发行包 |
| 约定 | **不再维护额外二进制补丁，不修改当前稳定 EFI，不把未验证代码称为已修复。** |

## 1. 封存时已确认的实机能力

以下结果来自此前已经实际运行的 **D 版 Kext + Graphics 0.4.0 环境**。D1.1 最新提交仅做源码整合与诊断开发，**尚无单独的新版完整回归验证**。

| 功能 / 测试 | 结果 | 证据范围 |
| --- | --- | --- |
| 内屏 eDP | **可进入桌面**，3072×1920 @ 60 Hz | D 版加入 `-wex-a7a0-panel-only`；此模式屏蔽外接显示输出 |
| Metal / GPU compute | **通过** | 已执行的 GPU 计算测试 |
| H.264 硬件解码 | **通过** | 1080p30，180/180 帧 |
| HEVC 硬件解码 | **通过** | 1080p30，180/180 帧 |
| H.264 硬件编码（直接 NV12/420v） | **通过** | 1080p30，180/180 帧；`HARDWARE_USED=YES`，4,025,912 字节压缩输出 |
| H.264 硬件编码（BGRA→CPU NV12） | **应用级绕过通过** | 1080p30，180/180 帧；`HARDWARE_USED=YES`，34,186,663 字节输出；**不是系统级 BGRA 修复** |
| HEVC 软件编码 | **通过** | 1/1 帧；`hevc.vcp`，198,076 字节；**不属于硬编** |
| 原生 BGRA→NV12 的 `VTPixelTransferSession` | **失败：SIGSEGV** | 64×64 即能复现；与 BGRA H.264 编码崩溃落在同一 VA 驱动指令 |
| HEVC 硬件编码 | **不可用 / 未注册** | `HEVC_HW_COUNT=0`；强制硬件会话和属性查询 `-12908` |
| 120 Hz、外接显示、全应用视频工作流 | **未通过完整验证 / 不支持据此推定** | D 的 panel-only 实验不支持外接显示；不能由单独探针推断所有软件都正常 |

上述测试的 FPS 包含生成测试画面及数据转换开销，不能视为纯 GPU 编码器峰值性能；输出非空压缩样本也不等于完成了文件回放/画质验收。

## 2. 尚未解决的两项视频问题（研究暂停）

### A. 原生 BGRA→NV12 崩溃

- 用户态故障组件：`/Library/GPUBundles/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver`。
- 已安装 VA 二进制的 **SHA256**：`a972cdb7ddd56bcf38c3ab71e874b73efc34bc683d30e49f0a1a1919625a726d`；Mach-O **UUID**：`00204000-0263-4092-B483-CC2544D26350`。
- LLDB：`EXC_BAD_ACCESS (address=0x8)`，`rdi=0`，崩溃指令 `movq %rdx,0x8(%rdi)`，VA 映像相对偏移 `0x1336f3`。与参考项目中子渲染器 `+0x910` 空指针处理点对应。
- 已确认该问题**不依赖编码会话**：独立 64×64 `VTPixelTransferSessionTransferImage` 即可崩溃。
- 参考：[JulioNectar `patch_vpnull2.py`](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/macos/vadriver/encode-experimental/patch_vpnull2.py)。**不得直接套用**：对已安装 Graphics 0.4.0 执行的离线检查返回 `REFUSED: code cave at 0xAC0 is OCCUPIED`。即使跳过空指针写入，也尚未证明后续 GPU 路径安全。
- 临时方案：在**自行集成该处理的应用程序内**先用 CPU 将 BGRA 转为 NV12，再调用 H.264 硬编；此方式已测试，但不会自动修复系统录屏或其他应用。

### B. HEVC 硬件编码未注册

- `VTCopyVideoEncoderList`：H.264 **HW 有 2 个条目**，HEVC **HW 为 0**，只有 `com.apple.videotoolbox.videoencoder.hevc.vcp`（软件）。
- `VTCopySupportedPropertyDictionaryForEncoder`：`RequireHardware=YES` 返回 `-12908`；不强制硬件则选中 HEVC 软件编码器。
- `IOGVAHEVCEncodeCapabilities` **已存在**（Profile 1，最大级别 183），但该属性不等于硬件编码实现或有效注册；加载专业视频工作流编码器后，列表也没有变化。
- 原始 VA 驱动字符串扫描出现 HEVC 解码路径，没有明确的 HEVC 编码后端标识；这**只是线索，不能据此断言硬件不支持或实现绝对不存在**。
- 需要真正可用的 Graphics/AppleGVA/VA 编码实现及注册支持；**修改 Kext 的显示代码不足以直接解决**。

## 3. 当前仓库如何组织

**源码优先（source-first），不再发放单独补丁包。**

- `src/WhateverXe/kern_xe.cpp`、`src/WhateverXe/kern_alderlake_n.hpp`：D 版内屏与诊断的完整 C++ 源码。
- `src/tests/`：随 D 修改的两份上游测试适配文件。
- `build_D_on_macos.command`：固定上游源代码与依赖、直接覆盖上述完整源码、运行测试和编译 Kext；**不安装**，不修改 EFI。
- `graphics/BASELINE.md`：Graphics v0.4.0 版本边界、精确故障定位和签名/源码限制。
- `macos/video-encode/`：H.264/HEVC、BGRA 转换、VideoToolbox 探针与诊断脚本；**仅供研究**，已知崩溃测试不必重复。
- `D1_1_VIDEO_README.md` / `D1_1_VIDEO_ADVANCED.md`：历史实验说明；其中旧版本路径、已移除补丁的描述只用于追溯，以**本 README 与当前源码树**为准。
- `.github/workflows/diagnostic.yml`：源码构建与编译检查；**尚未确认封存提交对应 CI 成功**。

**注意：** 上游 Graphics 仓库主要提供已签名载荷与安装工具，未提供完整可复现的 Apple VA 驱动源码、修改与 Mod 签名流水线。本仓库无权直接向官方 Graphics 上游推送代码。已移除的独立二进制补丁脚本可在 Git 历史查看，但**不是当前构建输入**。

## 4. 将来继续研究时从哪里开始

1. 从封存快照创建**新的实验分支**，不直接修改 `D1.1` 或 `archive/D1.1-2026-11-05`；先确认新的 WhateverXe 和 Graphics 版本及签名/依赖是否变化。
2. 先复核现有稳定 EFI 与 0.4.0 版本，检查新 Graphics 是否已经修复 BGRA 原生转换或注册 HEVC HW；不要因为 `IOGVAHEVCEncodeCapabilities` 存在便宣称 HEVC 硬编可用。
3. 如果上游有实际的 Graphics 用户态源实现、明确授权的构建与签名流程，再研究子渲染器的初始化/生命周期；**不要从旧偏移强行注入二进制补丁**。
4. 对任何未来版本执行 H.264/HEVC 解码、H.264 NV12 编码、原生像素传输、HEVC HW 注册及实际输出校验；确保不引入桌面卡顿、GPU 挂起、显示回归。**已知会崩溃的测试仅在有明确调试目的且备份工作后运行。**

### 安全构建入口（以后需要时）

```bash
git clone --branch archive/D1.1-2026-11-05 --single-branch https://github.com/Lanye-z/WhateverXe-yogapro13900.git
cd WhateverXe-yogapro13900
bash build_D_on_macos.command
```

该命令只尝试构建 **Kext**，不会生成已修复 Graphics 安装包。请始终保留原来已通过实机测试的 D 版 EFI，任何新 Kext 均先使用独立 USB EFI 验证。

---

**封存结论（2026-11-05）：** D 版显示和主要视频解码、H.264 硬件编码路径已验证可用；**BGRA 系统级像素转换崩溃与 HEVC 硬编未注册仍未解决**，但暂不妨碍当前以稳定使用为优先的选择。D1.1 本轮研发到此暂停。
