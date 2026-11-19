# Lenovo Yoga Pro 14s IRH8（82Y7）— HDMI 首次热插拔实验分支

**状态：HPD 首次连接的诊断/候选修复，尚未实机证明该修复有效。**

基于 WhateverXe 0.8.3 / WhateverXe Graphics 0.4.4 和已验证的内屏 120Hz WM_ONLY/V2 补丁。本分支重点研究：**如果仅以内屏开机，之后第一次连接机身 HDMI，外接显示器可能没有响应。**

## 主要内容

- `-wex-yoga-hdmi-hpdtrace`：只读采集 HDMI B 端口探测、PCH/HPD IRQ 及事件转换计数。
- `-wex-yoga-hdmi-first-hpd`：在严格限定场景下，将首次 HDMI B 短 HPD 事件转换为一次长 HPD 的实验性方案；未证实能修复实机。
- 不更改 HDMI 时钟、不修改 EDID、不强制 RGB8，也不处理 4K60 的 SCDC。
- [完整的中文 HPD 技术说明与测试步骤](wexhdmi/README.md)。
- [本分支 CI 编译记录](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44444094099)。

## 与 HDMI 伪色修复的关系

**2026-11-19：U27P10 的 4K30 伪色已在后续分支获得实机修复，但不是由本分支的 HPD 参数完成的。**

在 [最新 EDID Deep8 实验分支](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab) 中，`-wex-yoga-hdmi-edid-deep8` 限制目标显示器的 Deep Color 声明，使原生 HDMI 输出从 YCbCr 10 bpc 回到 YCbCr 8 bpc，实际颜色恢复正常。**本热插拔分支不包含该修复开关。**

首次点亮、开机后首次热插拔、4K60 黑屏与 4K30 伪色不能混为一谈；不要因为后续颜色正常，就认为本分支 HPD 假设已经验证成功。

只在独立测试 EFI 中使用，保留可启动的恢复 EFI，不合并到 `main`。