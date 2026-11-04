# WhateverXe A7A0 — D 版内屏单输出时钟隔离实验

> **实验性驱动：已有单台 A7A0 实机进入桌面且报告显存约 1.5 GB，但 Metal 运算、视频硬解、桌面稳定性和外接显示仍待系统检测。** Lenovo Yoga Pro 14s IRH8 / 82Y7，i9-13900H，8086:A7A0（rev 04），macOS Tahoe 26.7.1 (25G241)，内屏 eDP 3072×1920。此分支只用于独立 USB EFI 测试。

## 为什么制作 D 版

- A：接受 eDP GOP `TRANS_DDI_FUNC_CTL2` bit 3；原生启动前置检查通过，但内屏仍留在 `.Display_boot`。
- B：保留 A，并加入 `WEXDiag*` 诊断；发现 eDP `AppleIntelPort` 模式为 0，`display13SSTPort()` 要求 1。
- C：在 B 上加入受条件保护的端口模式修复；在 **19:37 / 19:40** 两次 macOS 启动中，原生显卡驱动开始初始化，但出现 `FB0: Hardware mode set failed, err = 0xe00002d8`、`FB0 is not enabled`，用户观察到啰嗦模式后黑屏。
- 上游 [Issue #22](https://github.com/b00t0x/WhateverXe/issues/22) 报告相同报错可能与多输出路径的 `adlnSetDualClock()` / `clockFaulted` 有关。**此机制在本机尚未被实机诊断直接证明。**

B 版诊断显示本机 `panel=0x01, dp=0x78, typeC=0x78, hdmi=0x02`。仅清除 DP/Type-C **不够**，`hdmi=2` 也会使 `multiOutputWiring` 保持为真。

## D 版新增改动

`patches/0004-A7A0-single-panel-clock-isolation-EXPERIMENTAL.patch` 位于 `XE::display13BoardWiring()`：

- **必须在 USB EFI 的 boot-args 中显式添加 `-wex-a7a0-panel-only` 才会启用。** 不添加参数时保留 C 的布线行为。
- 仅当 VBT 已描述有效、且恰好匹配 `panel=1, dp=0x78, typeC=0x78, hdmi=2` 时，将 `dp/typeC/hdmi` 清零，同时清零所有 `ddc[]` 引脚映射；再校验 `board.described()`、`selected()==1`、`multiOutputWiring()==false`。
- 校验不通过则恢复原始布线；不更改显示寄存器、GPU MMIO、EU 数量或原生驱动内部时钟逻辑。
- 设置 **IORegistry 根节点**诊断键 `WEXDiagDOriginalWiring`、`WEXDiagDResultWiring`、`WEXDiagDSinglePanelApplied`。这些属性仅在 D 版成功启动且启用 boot-arg 后可被读取；一次黑屏重启之后读取到的不是那次启动的数据。
- 实验模式将**关闭由 WhateverXe 管理的所有外接显示输出**（USB-C DP / HDMI）。只用于验证内屏路径，**不是永久解决方案**。

如果 D 版能点亮内屏并消除 `0xe00002d8`，下一步应排查 `adlnSetDualClock()` 的真正锁和时序问题，而不是永久关闭外接输出。

## GitHub 下载后在本地 Mac 编译

推荐使用 Intel macOS + Apple Command Line Tools：

```bash
git clone --branch experiment/a7a0-single-panel-clock-isolation --single-branch \
  https://github.com/Lanye-z/WhateverXe-yogapro13900.git
cd WhateverXe-yogapro13900
bash build_D_on_macos.command
```

也可以在 GitHub 中切换到本实验分支后使用 **Code → Download ZIP**，解压后执行 `bash build_D_on_macos.command`。仓库为私有时，下载仓库本身需要用户的 GitHub 登录权限。脚本仅下载公开上游源代码，且优先复用原 C 版 `work/` 缓存；缓存可用时不需要重新联网下载依赖。

脚本执行：

1. 克隆官方 **WhateverXe 0.7.0** 精确提交 `d0b7fb6275ca51fde088fa7e91595462bd457ec9`；下载固定版本的 MacKernelSDK 与 Lilu 1.7.2 开发文件。
2. **按顺序只应用** `WhateverXe_A7A0_Diagnostic_0.7.0.patch`（已同时包含 A+ B）、`patches/0003-B-to-C-eDP-software-port-mode.patch`、`patches/0004-A7A0-single-panel-clock-isolation-EXPERIMENTAL.patch`、`patches/0005-D-test-adapters.patch`。请不要另外重复应用 0001/0002。
3. 执行 `git diff --check`、上游 `python3 tools/test.py`、官方 RELEASE 编译及兼容版本检查。
4. 将产物保存到 `OUTPUT_D/WhateverXe_A7A0_D_PanelOnly_0.7.0_RELEASE.zip`；完整已修改源码保存在本地 `work_D/WhateverXe/`，补丁合并后的完整 Diff 在 `OUTPUT_D/WhateverXe_A7A0_D_FULL_SOURCE_DIFF.patch`。

仓库**保存了全部精确补丁和一键构建脚本**，但没有预先把上游全部源代码复制到 GitHub。脚本会下载固定提交，在本地保留完整源码，因此可以复现、编辑和二次构建。本分支已经同步本地 D 版通过编译所需的两处数组类型修复以及 2 项上游测试适配；用户报告修正后版本进入桌面。**GitHub 分支的构建流程仍需独立运行验证，不能把本地运行结果当成 CI 验证。**

## 安全测试与排查

**必须保留原始稳定 EFI，不要修改它。** 把新编译的 Kext 仅安装到独立 USB 测试 EFI，并在 USB EFI 的 `NVRAM -> Add -> 7C436110-AB2A-4BBB-A880-FE41995C9F82 -> boot-args` 中加入：

```text
-wex-a7a0-panel-only
```

同时保留原有需要的启动参数。没有此参数时，**D 实验不执行，行为近似 C 版，仍可能在启动时黑屏**。

如果能够进入 macOS，可用只读命令：

```bash
ioreg -p IOService -l -w0 | grep -E 'WEXDiagD|WEXDiagSSTPort|WEXDiagBootAdoption|N97FramebufferStartAccepted'
kmutil showloaded | grep -E 'WhateverXe|AppleIntelTGLGraphics'
system_profiler SPDisplaysDataType
```

优先比较 `WEXDiagDSinglePanelApplied` 是否为 Yes、`FB0: Hardware mode set failed` 是否消失以及屏幕是否能点亮。**即使能点亮，也不能直接宣称 Metal 和完整加速可用。**

上游参考：[Issue #22](https://github.com/b00t0x/WhateverXe/issues/22) · [Issue #32](https://github.com/b00t0x/WhateverXe/issues/32)。

## 2026-11-04 实机及构建进展

- 使用之前的离线缓存构建包，最初 203/203 CPU 测试通过，RELEASE 编译随后在 D 版 `before[]` / `after[]` const 数组传给 `IORegistryEntry::setProperty` 时失败。现已在 `0004` 将它们改为 `uint32_t[]`。
- 已新增 `0005-D-test-adapters.patch`，同步修改 `tests/fixtures/boot_argument_names.json` 和 `tests/adlp_fb_candidate.py` 的测试替身，使测试认得新启动参数及诊断属性。
- 用户报告经上述修正构建的 D 版可成功进入桌面，显存显示大约 1500+ MB。屏幕启动照片包括 `TGL accelerator start returned 1`，但登录后存在一段白色桌面、迟缓加载的问题，仍需要检查 Metal、WindowServer、视频硬解与启动日志。
- 照片里的 `com.apple.driver.IOVersatile` `OSBundleLibraries missing/invalid type` 是真实的独立 Kext 加载异常，目前不能认定其与 WhateverXe / 登录迟缓存在直接因果关系。
- **重要**：GitHub Actions 或本分支本地脚本的编译状态不得等同于用户实机通过全部功能验证；正式多屏修复还没有完成。
