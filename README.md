# Yoga Pro 14s IRH8（82Y7）— 历史 RGB8 集成实验分支

**状态：早期 E1.0/E1.1 多输出与 RGB8_STRICT EDID 集成候选，不是 2026-11-19 本机实测成功的最终伪色修复版。**

本分支曾基于 `Thatisjigen/WhateverXe` 的 `acer/current` 多输出 Display13 路径，集成：

- D1.1 内屏 eDP CTL2 bit 3 准入修正。
- `-wex-yoga-hdmi600`：将 HDMI 模式准入上限从 300MHz 放宽至 600MHz；**未实现完整 HDMI 2.0 SCDC/扰码，不能据此认定 4K60 黑屏已修复**。
- `-wex-yoga-rgb8`：按 U27P10 原始 EDID 严格匹配，在原生 DDC 路径替换为当时的 `RGB8_STRICT` EDID 块。
- 保留当时的 WhateverXe Graphics 0.4.0；不包含后续基于 0.8.3 的新 ColorTrace 与 Deep8 修复。

## 后续实机结论

**2026-11-19**：使用 WhateverXe 0.8.3 的独立 [EDID A/B 实验分支](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab)，仅启用 `-wex-yoga-hdmi-edid-deep8`，U27P10 经机身 HDMI 的 4K30 从 YCbCr 10 bpc 伪色恢复为 YCbCr 8 bpc 正常画面。该结果证明**无须整体强制 RGB8**，也无须依赖旧的系统级 RGB8_STRICT 覆盖。

**两套实现不同，不要混用启动参数或将早期集成分支当作已验证的修复版。**

- [本分支原有技术设计、代码路径与测试回退（中文）](e13/YOGA_MAIN_RGB8_README.md)
- [本分支构建工作流](.github/workflows/yoga-main.yml)
- [后续成功的 0.8.3 Deep8 方案](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab)

本分支保留为历史研究对照；不建议替换当前可以正常启动的 EFI，也不代表 4K60 或首次热插拔已获得修复。