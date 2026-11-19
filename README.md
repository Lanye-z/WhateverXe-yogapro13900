# WhateverXe A7A0 — E1.2 HDMI RGB8 历史实验（2026-11-05）

**状态：历史阶段的离线 EDID 颜色能力实验工具，不是当前推荐的修复版本。**

本分支从 `E1.1-HDMI600`（提交 `91629bd10c5d40f41a6df76e8daf96a87ab0ed07`）派生，仅新增离线生成 `RGB_ONLY` 和 `RGB8_STRICT` EDID 覆盖的脚本、测试与说明；**没有改动 E1.1 的驱动源代码，没有提供新的内核启动参数，也不自动安装覆盖文件**。旧 D1.1/E1.0/E1.1 的 EFI 应继续保留。

## 后续实机结论（2026-11-19）

在新的 WhateverXe **0.8.3** 实验链路中，已经找到比整体替换 EDID 更精确的解决办法：

- 问题：AOC U27P10 机身 HDMI 4K30 输出 **YCbCr 4:4:4 / 10 bpc** 时出现伪色。
- 修复：启动参数 **`-wex-yoga-hdmi-edid-deep8`**，只限制目标显示器的 Deep Color 能力。
- 结果：macOS 原生驱动选择 **YCbCr 4:4:4 / 8 bpc**，画面正常，且不需要屏蔽所有 YCbCr 能力。
- 实现于：[0.8.3 EDID A/B 实机验证分支](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab)，**本 E1.2 分支不含此修复参数**。

因此，E1.2 的 `RGB8_STRICT` 整体覆盖已经成为历史对照方案。它同时更改多个 EDID 能力字段，不适合当作本次 Deep Color 故障的最小因果实验。

## 资料

- [E1.2 离线 EDID 工具与测试说明（中文）](e12/E1.2_RGB8_README.md)
- [E1.1 HDMI600 实验](e11/E1.1_HDMI600_README.md)
- [E1.0 多输出集成](e/E1.0_README.md)
- [封存的 D1.1](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/archive/D1.1-2026-11-05)
- 上游参考：[Issue #40](https://github.com/b00t0x/WhateverXe/issues/40)、[Issue #41](https://github.com/b00t0x/WhateverXe/issues/41)

**颜色修复不等于 4K60 TMDS/SCDC、首次点亮和热插拔已解决。**