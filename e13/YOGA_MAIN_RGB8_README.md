# Yoga A7A0 原生 EDID RGB8 集成试验（历史方案）

**目标设备：** Lenovo Yoga Pro 14s IRH8（82Y7）、i9-13900H、Intel Iris Xe A7A0；当时使用 macOS Tahoe 26.7.1。  
**状态：** 本分支为早期集成候选，不能按 2026-11-19 新的 Deep8 实机结果追认本分支已验证成功。

## 一、此历史分支实现的功能

- 固定 `Thatisjigen/WhateverXe` 的 `acer/current` 提交 `f7b9bf2229d323e37e8b1dfb87182f005eb7a277`，复用多输出 Display13 路径。
- 移植早期 D1.1 的 A7A0 eDP CTL2 bit 3 判断修正。
- 继承 `-wex-yoga-hdmi600` 的 300→600MHz 模式准入实验，但**没有** HDMI 2.0 的完整 SCDC/scrambling 逻辑。
- 新增 `-wex-yoga-rgb8`，在 `wrapAlderLakeNPortDDC` 原生 DDC 返回路径，针对 A7A0、HDMI/TMDS、精确 U27P10 05E3:2710 EDID 匹配，将 EDID 基本块/扩展块替换为此前准备的 `RGB8_STRICT` 数据。
- 当时使用 WhateverXe Graphics 0.4.0，并非后续 0.8.3 / Graphics 0.4.4 的组合。

匹配失败、未启用开关或目标不是该 HDMI 设备时不修改 EDID。旧版本的严格匹配依赖预制 EDID 字节；不是一个通用的颜色模式协商策略。

## 二、与后续成功修复的区别

| 项目 | 此历史集成分支 | 2026-11-19 实机成功方案 |
| --- | --- | --- |
| 驱动代际 | `acer/current` / 早期 E1 | WhateverXe 0.8.3 |
| 色彩开关 | `-wex-yoga-rgb8` | `-wex-yoga-hdmi-edid-deep8` |
| 修改内容 | 严格匹配并替换预制 `RGB8_STRICT` EDID 块 | 仅限制现有 CTA 的 Deep Color 声明，重新校验 |
| 目标输出 | 引导 RGB 8 bpc | **实测保留 YCbCr 4:4:4，只降为 8 bpc** |
| 本机 4K30 伪色验证 | 未以该集成构建独立确认 | **已确认画面正常，寄存器支持** |

本次成功结果说明 U27P10 不必禁用所有 YCbCr 能力；因此正式修复应优先参考 [EDID A/B 分支](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab)，而不是继续扩展历史 RGB8_STRICT 整体替换。

## 三、原先设计的验证与回退

历史实验的前提是保留原有 EFI 并备份系统覆盖文件：

```text
/Library/Displays/Contents/Resources/Overrides/
  DisplayVendorID-5e3/
    DisplayProductID-2710
```

如果 macOS 中原本已安装 RGB8_STRICT 系统级覆盖，那么颜色正常**不能证明** Kext 的 `-wex-yoga-rgb8` 生效。应分别检查原生 DDC 诊断结果（例如 `WEXYogaRGB8Last`、`N97FBEDIDBase` / `N97FBEDIDExtension`），只有确认驱动侧应用后，才能在有回退手段的前提下独立移除系统覆盖并复测。

当时的安全步骤是：先在独立测试 EFI 验证内屏、Metal 与 4K30；只启用 `-wex-yoga-rgb8`；查明驱动应用状态；最后单独复测无系统覆盖时的 4K30。发生黑屏立即恢复原 EFI 与覆盖文件。不可将历史 D 版视频硬件编解码性能直接推断为 E 版已继承。

## 四、编译与文件说明

此分支的 GitHub Actions 工作流为 `.github/workflows/yoga-main.yml`，用固定源代码版本生成补丁、运行辅助测试、编译 RELEASE Kext 并打包变更。生成器在对应源码目录中运行：

```bash
python3 e13/tools/prepare_rgb8.py <clean-donor-dir>
```

对上游版本或函数锚点不匹配的源码应拒绝修改。测试夹具中可能包含显示器序列号，不要在公开仓库日志、Issue 或文档里粘贴完整未脱敏原始 EDID。

历史 `patches/` 与 `WhateverXe_A7A0_Diagnostic_0.7.0.patch` 不参与这个新的生成式构建。未合并的功能包括旧 D 版的 `-wex-a7a0-panel-only`、VideoToolbox 应用级 BGRA→NV12 作为全局修复、HEVC 硬件编码声明以及 4K60 SCDC/雷电 USB4 驱动等。

**注意：这份说明保留的是早期实现逻辑，非当前最佳修复指南。**