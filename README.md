# Lenovo Yoga Pro 14s IRH8（82Y7）— HDMI 原生颜色策略审计分支

**状态：原生 `setColorMode` 审计已实机验证有效；旧数字位深测试不适合本机，最终伪色修复位于后续 EDID Deep8 分支。**

本分支从已正常采集的 ColorTrace 版本继承 WhateverXe 0.8.3、内屏 120Hz WM_ONLY/V2、HDMI HPD 和颜色寄存器读取，新增可选的原生颜色模式调用审计。

## 关键发现（2026-11-19）

在 U27P10 机身 HDMI DDI B 上：

```text
WEXYogaHDMIColorModeHookReady = Yes
setColorMode: mode = 0x100 (256), depth = 0
物理输出：YCbCr 4:4:4，10 bpc（伪色）
```

旧实验参数 `-wex-yoga-hdmi-bpc8-test` / `-wex-yoga-hdmi-rgb8-test` 原先假设位深直接用 8/10/24/30 表示；实机返回 `depth=0`，保护逻辑会跳过，因此**不建议继续使用它们尝试修复颜色**。

真正有效的方法是后续独立分支的 `-wex-yoga-hdmi-edid-deep8`：仅限制 U27P10 EDID 中 Deep Color 能力，使 macOS 原生驱动将 YCbCr 10 bpc 改为 YCbCr 8 bpc。2026-11-19 已在 U27P10 的 4K30 上实测恢复正常画面；本 ColorPolicy 分支**不包含这一新增参数**。

## 文档与运行

- [原生 `setColorMode` 审计详细说明](wexrgb/README.md)
- [ColorTrace 寄存器采集说明](wexcolor/README.md)
- [继承的 HPD 诊断说明](wexhdmi/README.md)
- [后续 Deep8 成功修复分支](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab)

本分支审计参数：

```text
-wex-yoga-edp120-admit -wex-yoga-edp120-wm -wex-yoga-hdmi-colortrace -wex-yoga-hdmi-mode-audit
```

可运行 `bash collect_policy.sh` 采集 `Yoga_HDMI_Mode_*.zip`。仅在独立测试 EFI 使用，勿修改日常启动 EFI 或误将审计成功解读为色彩问题修复。

4K60 高速链路、首次 HDMI 点亮与热插拔尚需独立验证，相关代码没有合并至 `main`。