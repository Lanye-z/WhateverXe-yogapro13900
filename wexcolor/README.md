# A7A0 HDMI-B 实际色彩寄存器采集（ColorTrace）

**状态：只读诊断功能已在 Lenovo Yoga Pro 14s IRH8（82Y7）实机验证有效。此模块本身不修复伪色。**

本模块基于 WhateverXe 0.8.3 + WhateverXe Graphics 0.4.4，继承内屏 120Hz 的 WM_ONLY/V2 和 HDMI HPD 诊断。仅在启用 `-wex-yoga-hdmi-colortrace` 且满足 A7A0 / 机身 HDMI DDI B 范围后，向 IORegistry 发布 `WEXYogaHDMIColorLive`。

## 一、这次排查实际证明了什么

| 条目 | 伪色（修复前） | 正常（后续 EDID Deep8 修复） |
| --- | --- | --- |
| 显示器 / 端口 | AOC U27P10、DDI B、Pipe 1 | 相同 |
| 实测对照模式 | 3840×2160 @ 30Hz | 3840×2160 @ 30Hz |
| `TRANS_DDI_FUNC_CTL` | `0x90130200` | `0x90030200` |
| `PIPE_MISC` | `0x01800830` | `0x01800810` |
| HDMI 输出色深 | 10 bpc | 8 bpc |
| 输出编码 | YCbCr 4:4:4 | YCbCr 4:4:4 |
| AVI InfoFrame | YCbCr 4:4:4 | YCbCr 4:4:4 |
| GCP 使能 | 关闭 | 关闭 |
| 实际画面 | 伪色 | 正常 |

**结论：** 这台机器与 U27P10 的问题更接近 HDMI 10-bit Deep Color 兼容性，而不是“只要 YCbCr 就伪色”。后续 [EDID A/B 实验](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab) 通过 `-wex-yoga-hdmi-edid-deep8` 限制能力声明，使原生驱动选择 YCbCr 8 bpc 并恢复正常颜色。本只读分支不包含该修复开关。

## 二、原理及数据结构

读取动作只有在 `ioreg` 查询属性时触发，不设周期采样任务：

1. 检查 Display13 驱动所有者、映射及电源锁，采用非阻塞锁，避免在模式切换期间强行读取。
2. 检查 power well 状态，只读取已上电管线。
3. 通过 `TRANS_DDI_FUNC_CTL` 区分真正使用 HDMI DDI B 的 Pipe。
4. 根据 AVI/GCP 使能情况读取 `VIDEO_DIP_CTL`、InfoFrame 和相关寄存器。
5. 再次检查电源状态是否变化，变化则标记快照失效。
6. 以 236 字节 OSData 序列化原始寄存器快照。

`WEXYogaHDMIColorLive` 包含 59 个小端序 `uint32`：

- 前 8 个字段：版本、数据有效性（0 未就绪、1 有效、2 读取期间电源变化）、前后电源状态、厂商 ID、产品 ID、HDMI B 管线掩码及已上电管线掩码。
- 后面有 3 组、每组 17 个字段：Pipe 索引、上电状态、`TRANS_DDI_FUNC_CTL`、`PIPE_MISC`、`PLANE_CTL`、`PIPECONF`、`TRANS_DDI_FUNC_CTL2`、`VIDEO_DIP_CTL`、GCP、7 个 AVI 数据字段与 `TRANS_MSA_MISC`。
- 无法读取的寄存器填 `UINT32_MAX`，**不等于硬件寄存器值为 0**。

`TRANS_DDI_FUNC_CTL[22:20]` 与 `PIPE_MISC[7:5]` 用于判读输出色深；`PIPE_MISC[11]` 标识 YUV 输出；AVI 需检查使能与原始字节，不可仅凭 macOS 显示的 ARGB8888 帧缓冲格式判定物理链路色深。

**限制：** 读取的是 GPU 寄存器，不是 HDMI 协议分析仪的线缆抓包。不能由 GCP 使能位单独证明全部线上信令正确与否。

## 三、如何复现诊断

使用独立测试 EFI，仅替换 `EFI/OC/Kexts/WhateverXe.kext`，保留 Graphics 0.4.4 及恢复方案。确认启动参数包括：

```text
-wex-yoga-edp120-admit -wex-yoga-edp120-wm -wex-yoga-hdmi-colortrace
```

建议在显示器已连接机身 HDMI、模式稳定后执行：

```bash
nvram boot-args
ioreg -p IOService -l -w0 | grep 'WEXYogaHDMIColorLive'
bash collect_color.sh
```

`collect_color.sh` 与 `decode_color.py` 放在同一目录；采集包输出到桌面，名称形如 `Yoga_HDMI_Color_*.zip`。不要在睡眠、插拔或刷新率切换过程中高频读取。

此模块**不写显示寄存器、不改 EDID、色彩转换矩阵、gamma、HPD 事件和时序**。实验性的 `-wex-yoga-hdmi-first-hpd`、`-wex-yoga-rgb8`、`-wex-yoga-hdmi600` 与本次只读诊断无关，不应混开。

## 四、构建与状态

[ColorTrace 构建成功记录](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44470795471)；之后实机已确认属性存在、快照有效。**只读诊断成功并不等于此旧分支具有 Deep8 伪色修复能力。**

4K60、首次点亮和热插拔是独立问题，不能以颜色寄存器验证结果代替这些项目的测试。