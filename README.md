# WhateverXe A7A0 — E1.0 多输出实验分支（2026-11-05）

> **实验状态：E1.0 未经 Yoga 实机验证。** 当前分支以已封存的 D1.1 为起点，但运行时采用 Issue #38 作者的 `acer/current` 多屏源码，仅保留 D1.1 的 `CTL2 bit 3` eDP 判断修改。D1.1 以及 `archive/D1.1-2026-11-05` 没有改动。

详细设计、测试顺序、风险与故障回退：**[E1.0_README.md](e/E1.0_README.md)**。

## 一键源码构建（只构建，不安装）

```bash
git clone --branch E1.0 --single-branch https://github.com/Lanye-z/WhateverXe-yogapro13900.git
cd WhateverXe-yogapro13900
bash build_E_on_macos.command
```

只有 macOS + Apple 开发工具可编译 Kext。GitHub Actions 的 `E1.0 A7A0 multi-output experimental Kext` 工作流可在 macOS Intel Runner 编译，成功后上传 ZIP。

**首次测试必须使用单独的 USB 测试 EFI、删除 D 专属 `-wex-a7a0-panel-only` 参数，不得覆盖现有稳定 EFI 或更改 Graphics 0.4.0。**

历史 D1.1 研究与视频诊断材料仍保留在本分支，**不参与 E 版编译**；原始封存状态请见 [archive/D1.1-2026-11-05](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/archive/D1.1-2026-11-05)。
