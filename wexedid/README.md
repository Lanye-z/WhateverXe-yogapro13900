# U27P10 HDMI 伪色修复：Deep Color 能力限制

## 实机结果（2026-11-19）

**本机修复成功。** Lenovo Yoga Pro 14s IRH8（82Y7，Intel A7A0）连接 AOC U27P10（05E3:2710）到机身 HDMI DDI B，原 4K30 伪色状态下开启 `-wex-yoga-hdmi-edid-deep8`，画面恢复正常。采集结果证明物理输出由 **YCbCr 4:4:4 / 10 bpc** 改为 **YCbCr 4:4:4 / 8 bpc**，并未切换 RGB。

| 关键字段 | 伪色状态 | 正常状态 |
| --- | --- | --- |
| `TRANS_DDI_FUNC_CTL` | `0x90130200` | `0x90030200` |
| `PIPE_MISC` | `0x01800830` | `0x01800810` |
| AVI | YCbCr 4:4:4 | YCbCr 4:4:4 |
| GCP | 未启用 | 未启用 |
| 用户目视结果 | 伪色 | 正常 |

实验日志显示 `WEXYogaHDMIEDIDABApplied = Yes`，CTA 能力变化符合预期，并且 EDID 校验和有效。此结果验证的是**本机 U27P10 的 4K30 颜色问题**，而非 4K60 或热插拔的完整修复。

## 实现机制

补丁在原生 Display13 HDMI DDC 返回路径对**扩展块**进行严格条件限定，只有设备、端口、EDID 结构和校验均满足时才按所选实验调整能力字节。保持 EDID 基本块、序列号、详细时序、HDMI 物理地址和最大 TMDS 能力不变。修改后重新计算 CTA 扩展块校验和，由 macOS 原生显示驱动重新选择实际颜色模式，而不是点亮后强写 MMIO 寄存器。

### 方案 A：限制 Deep Color（已实机成功）

启动参数：`-wex-yoga-hdmi-edid-deep8`

| CTA 数据 | 原始 | 修改后 |
| --- | --- | --- |
| CTA 色彩能力 | `0xF1` | `0xF1` |
| HDMI VSDB Deep Color 标志 | `0x38` | `0x00` |
| HDMI Forum 的 4:2:0 Deep Color 标志 | `0x03` | `0x00` |
| 4:2:0 能力映射 | `0x0C` | `0x0C` |

在已识别的 CTA 布局下，仅修改扩展块偏移 **31、46、127**（含校验和）；不缩减视频格式列表，不删除 4K 时序。

### 方案 B：进一步限制 YCbCr（备选，未实机验证）

启动参数：`-wex-yoga-hdmi-edid-rgb8`

在 A 的基础上将 CTA 头部 `0xF1` 改为 `0xC1`，并清除对应的 4:2:0 能力映射。已识别布局只改扩展块偏移 **3、31、46、63、127**（含校验和）。发现不支持的 4:2:0-only 数据块时会拒绝此操作。

**A 已修复现有伪色，因此没有必要启动 B。不能同时开启 A 和 B。**

## 编译及启用

- 源码生成器：`prepare_edid_ab.py`；校验代码：`kern_yoga_hdmi_edid_ab.hpp`；单元测试：`test_edid_ab.cpp`。
- 继承 WhateverXe 0.8.3 / WhateverXe Graphics 0.4.4 的 WM_ONLY/V2、HPD 追踪、ColorTrace 和原生颜色模式审计。
- [Intel 原生回归、RELEASE 编译及 ZIP 校验通过](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44494354268)。
- 保留原有可启动 EFI，在独立测试 EFI 替换 `WhateverXe.kext`。确认 `nvram boot-args` 包含 `-wex-yoga-hdmi-edid-deep8`，不要添加过时的 `bpc8-test` / `rgb8-test`。
- 建议开启原有 `-wex-yoga-hdmi-colortrace` 和 `-wex-yoga-hdmi-mode-audit` 以便核查。

```bash
nvram boot-args
ioreg -p IOService -l -w0 | grep -E 'WEXYogaHDMIEDIDAB(Last|Applied)'
bash collect_edid_ab.sh
```

采集脚本旁应有 `decode_edid_ab.py`、`decode_color.py`、`decode_modes.py`，输出为桌面的 `Yoga_HDMI_EDID_AB_*.zip`。

## 解释与边界

`WEXYogaHDMIEDIDABApplied=Yes` 仅代表能力字节已修改；本次修复成立是因为**同时**看到了用户确认画面正常以及 GPU 物理寄存器由 10 bpc 变为 8 bpc。

`setColorMode` 的实测参数为 `mode=0x100, depth=0`，旧的直接替换数值的方案并不适合本机。最可能的兼容问题落在 HDMI 10-bit Deep Color 传输或信令链路，但尚未通过 HDMI 协议分析仪确定具体硬件故障环节。

4K60 TMDS/SCDC、首次点亮、热插拔、长期稳定性仍须独立验证。本补丁不能作为所有 A7A0 显示器的通用修复保证。