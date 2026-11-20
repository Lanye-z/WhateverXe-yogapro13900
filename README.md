# 当前分支状态（2026-11-20）：Yoga 0.8.3 SST 三屏实机成功

**此分支已由用户实机验证**：在 HP Thunderbolt G4 拓展坞的 USB-C DP Alt Mode 兼容模式下，加上 `-wex-yoga-tc5-sst` 可以恢复拓展坞外屏；内屏、机身 HDMI、拓展坞形成三个独立画面，拓展坞热拔插也正常。**这是 SST 单流输出，不是拓展坞多路独立 MST。**

**冻结目前成功的 0.8.3 + eDP 120Hz WM_ONLY + HDMI Deep8/HDMI600 + DDI5 SST 配置。** 4K 屏接拓展坞 DP 仅显示 4K30 选项；同一 4K 屏接机身 HDMI 有 60Hz 选项但黑屏。二者分别研究：前者先核实 2-lane HBR2、EDID 和模式枚举；后者先研究 HDMI600 之后缺失的 SCDC/高速 TMDS/源端控制及失败恢复。不能为了 4K60 重新启用曾造成 22MB/核显加速丢失的 HDMI2 Route 实验。

- **当前可用修复与回退详情**：[wexsst/README.md](wexsst/README.md)
- **旧 HDMI600 模式准入与安全采集工具**：[wex600/README.md](wex600/README.md)
- **此前 HDMI 深色修复的历史技术说明**：见下文（是旧阶段记录，不代表本分支最终全部功能）

---

# Lenovo Yoga Pro 14s IRH8（82Y7）— HDMI 伪色修复实机验证分支

**状态：AOC U27P10 经机身 HDMI 连接时，4K 30Hz 伪色已在本机实测修复（2026-11-19）。**

本分支基于 WhateverXe 0.8.3，保留内屏 3072×1920 @ 120Hz 的 WM_ONLY/V2 补丁、HDMI HPD 诊断、ColorTrace 寄存器采集及原生 `setColorMode` 审计。**没有合并到 `main`，也不会自动修改你的 EFI。**

## 一、故障与实测结论

| 项目 | 修复前：伪色 | 修复后：正常 |
| --- | --- | --- |
| 外接显示器 | AOC U27P10（05E3:2710） | 相同设备 |
| 连接 | 机身 HDMI，DDI B / Pipe 1 | 相同路径 |
| 已对照的显示模式 | 3840×2160 @ 30Hz | 3840×2160 @ 30Hz |
| 输出编码 | YCbCr 4:4:4 | **仍为 YCbCr 4:4:4** |
| 输出色深 | **10 bpc** | **8 bpc** |
| `TRANS_DDI_FUNC_CTL` | `0x90130200` | `0x90030200` |
| `PIPE_MISC` | `0x01800830` | `0x01800810` |
| AVI InfoFrame | YCbCr 4:4:4 | YCbCr 4:4:4 |
| GCP 使能 | 关闭 | 关闭 |
| 实际画面 | 紫色、伪色 | **颜色正常** |

已记录的实验 A 启动参数包含 `-wex-yoga-hdmi-edid-deep8`，并且：
```text
WEXYogaHDMIEDIDABApplied = Yes
CTA YCbCr 能力：0xF1 → 0xF1（保留）
HDMI VSDB Deep Color：0x38 → 0x00
HDMI Forum Deep Color：0x03 → 0x00
YCbCr 4:2:0 能力映射：0x0C → 0x0C（保留）
```

**结论：** 在这台 Yoga 与 U27P10 的组合上，只限制 Deep Color 声明，macOS 原生显示驱动即可选用 8 bpc 并恢复正常色彩，**无须关闭 YCbCr 或安装 macOS 系统级 EDID 覆盖**。这支持 10-bit 颜色传输/配套信令路径存在兼容性问题；尚不能仅凭寄存器快照区分像素打包错误和 GCP 等信令缺陷。

## 二、可用方案

- **方案 A（实机成功）：** `-wex-yoga-hdmi-edid-deep8`。仅关闭目标显示器 HDMI VSDB 与 HDMI Forum VSDB 的 Deep Color 能力；保留分辨率时序、HDMI 物理地址、600MHz 声明以及 YCbCr 能力。
- **方案 B（备选，非必要且未实机验证）：** `-wex-yoga-hdmi-edid-rgb8`。在 A 基础上进一步限制 YCbCr 声明；**当前颜色已恢复正常，不建议启用**。
- 两个参数**互斥**，默认均关闭；均只作用于匹配的 A7A0 / 机身 HDMI DDI B / U27P10。原始 EDID 基本块（含序列号）未被改写，未知 CTA 结构或校验不合法时不修改。
- 旧 `-wex-yoga-hdmi-bpc8-test` / `-wex-yoga-hdmi-rgb8-test` 不适合本机：实测原生 `setColorMode` 为 `mode=0x100, depth=0`，旧测试假定的 `depth=8/10/24/30` 不成立。

### 已验证的实验 A 启动参数

```text
-v keepsyms=1 -vi2c-force-polling -ibtcompatbeta -allow3d -disablegfxfirmware -igfxdvmt -wex-yoga-edp120-admit -wex-yoga-edp120-wm -wex-yoga-hdmi-colortrace -wex-yoga-hdmi-mode-audit -wex-yoga-hdmi-edid-deep8
```

安装时只替换**独立测试 EFI** 中的 `EFI/OC/Kexts/WhateverXe.kext`，继续使用原来的 WhateverXe Graphics 0.4.4，保留能独立启动的恢复 EFI。显示器最好在开机前接在机身 HDMI，勿将首次测试与雷电扩展坞混在一起。

## 三、验证与资料

```bash
nvram boot-args
ioreg -p IOService -l -w0 | grep 'WEXYogaHDMIEDIDAB'
bash collect_edid_ab.sh
```

采集工具生成 `~/Desktop/Yoga_HDMI_EDID_AB_*.zip`；重点检查 `edid_decoded.json`、`color_decoded.json`、`mode_decoded.json` 和显示器实际画面。

- [本分支详细技术说明](wexedid/README.md)
- [前置颜色模式审计](wexrgb/README.md)
- [只读 HDMI 颜色寄存器诊断](wexcolor/README.md)
- [仍在研究的 HDMI 首次热插拔问题](wexhdmi/README.md)
- [Intel 原生回归测试与 RELEASE 构建（成功）](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44494354268)

## 四、已解决与尚未解决的范围

**已实机确认：** U27P10 的 HDMI 4K30 颜色正常；物理管线从 YCbCr 10 bpc 切换到 YCbCr 8 bpc；内屏 120Hz 与外屏正常色彩可以共存。

**不应混同为已解决：** 4K60 黑屏（涉及 HDMI TMDS/SCDC）、4K 显示器开机首次点亮、eDP-only 启动后的首次 HDMI 热插拔以及长期稳定性。它们需要独立测试。本次修复是本机的明确有效方案，但不应宣称通用于所有机器或显示器。

本分支只进行能力声明的最小化修改，不强制写入已启用显示管线的硬件颜色寄存器。