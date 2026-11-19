# A7A0 HDMI 原生颜色模式审计（ColorPolicy）

**定位：用于查明 macOS 如何选择颜色模式的中间实验分支；它不是最终解决 U27P10 伪色的开关。**

本模块在已验证的 WhateverXe 0.8.3 / WhateverXe Graphics 0.4.4、WM_ONLY/V2 内屏 120Hz、HDMI HPD 诊断和 ColorTrace 基础上，增加对原生 `AppleIntelFramebufferController::setColorMode` 的审计。默认不修改调用参数，不修改 EDID 或 HDMI MMIO 寄存器。

## 一、实机采集结果（2026-11-19）

AOC U27P10 经 Lenovo Yoga Pro 14s IRH8（82Y7，Intel A7A0）机身 HDMI DDI B 连接：

| 观察项目 | 实机结果 |
| --- | --- |
| `WEXYogaHDMIColorModeHookReady` | `Yes`，钩子安装成功 |
| 物理端口与 Pipe | DDI B / Pipe 1 |
| 原生 `setColorMode` 的 `mode` | `0x100`（256） |
| 原生 `setColorMode` 的 `depth` | `0` |
| 当时的 HDMI 输出 | YCbCr 4:4:4 / 10 bpc，存在伪色 |
| 采集断面 | U27P10 的 2560×1440 与 3840×2160 输出 |

这说明旧实验假设的 `depth=8/10/24/30` 在本机不成立；不应把 `mode=0x100` 直接解释为某一种颜色格式，亦不应盲目改成 `mode=1`。

## 二、启动参数的实际用途

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| `-wex-yoga-hdmi-mode-audit` | 只读记录原生颜色模式函数的入参及匹配范围 | 可继续用于诊断 |
| `-wex-yoga-hdmi-bpc8-test` | 原先假设数字位深参数可按 10→8 或 30→24 调整 | **不适用于本机当前实测参数** |
| `-wex-yoga-hdmi-rgb8-test` | 原先假设数字位深可调整，且 `mode=1` 表示期望的颜色模式 | **未经证实，不建议使用** |

在 `depth=0` 的实测条件下，保护逻辑会跳过不认识的深度编码。即使 Kext 编译通过，也不代表这两个实验开关有效。

调用审计使用 `WEXYogaHDMIColorModeLive`，保存最近 24 条记录；解码器 `decode_modes.py` 会显示修改前后 `mode/depth`、物理匹配条件及跳过原因。回环缓冲区仅保留最近记录，切换分辨率会刷新其内容。

## 三、最终有效的修复在后续分支

经过 ColorTrace 与本审计定位，后续改为在 U27P10 的**原生 HDMI DDC/CTA 能力协商**中仅限制 Deep Color：

- 参数 `-wex-yoga-hdmi-edid-deep8`，仅在后续 [EDID A/B 分支](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab) 实现，**本 ColorPolicy 分支没有该功能**。
- 2026-11-19 实机结果：U27P10 4K30 从 YCbCr 10 bpc 伪色变成 YCbCr 8 bpc 正常显示，保持 YCbCr 4:4:4，GCP 仍未启用。
- 正常画面的出现及寄存器数据共同证明该机的 Deep Color 能力限制方案有效；并非证明本分支的旧 `bpc8-test` 或 `rgb8-test` 修好了问题。

相关代码包括 `prepare_policy.py`、`kern_yoga_hdmi_color_policy.hpp`、`collect_policy.sh`、`decode_modes.py` 与对应测试。更多寄存器数据参考 [ColorTrace 文档](../wexcolor/README.md)。

## 四、构建与安全边界

仅在独立测试 EFI 使用，保留能够启动的原始 EFI；WhateverXe Graphics 0.4.4 不变。

```bash
nvram boot-args
ioreg -p IOService -l -w0 | grep -E 'WEXYogaHDMIColorMode(HookReady|Live)'
bash collect_policy.sh
```

本分支只负责诊断与此前的未证实策略实验。4K60 的高速 TMDS/SCDC、首次点亮失败和热插拔问题需要分开排查，**不得因颜色问题已在后续分支解决，就宣称这些问题也已解决**。