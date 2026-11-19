# Lenovo Yoga Pro 14s IRH8（82Y7）— HDMI ColorTrace 只读诊断分支

**状态：寄存器诊断功能已在 A7A0 实机验证有效；本分支本身不是颜色修复补丁。**

继承 WhateverXe 0.8.3、内屏 120Hz WM_ONLY/V2 以及 HDMI HPD 诊断。新增 `-wex-yoga-hdmi-colortrace`，当原生机身 HDMI DDI B 满足条件时，允许按需读取 `WEXYogaHDMIColorLive`，分析 Pipe 色深、RGB/YCbCr、AVI 和 GCP。

## 关键实机发现

| 场景 | 4K30 伪色 | 后续 Deep8 修复后 |
| --- | --- | --- |
| `TRANS_DDI_FUNC_CTL` | `0x90130200` | `0x90030200` |
| `PIPE_MISC` | `0x01800830` | `0x01800810` |
| 输出 | YCbCr 4:4:4、10 bpc | YCbCr 4:4:4、8 bpc |
| 画面 | 伪色 | 正常 |

这证实问题与 U27P10 的 10-bit Deep Color 输出路径密切相关；**不需要简单地把所有 YCbCr 都视为错误**。

- [ColorTrace 完整中文说明](wexcolor/README.md)
- [继承的 HDMI 热插拔诊断说明](wexhdmi/README.md)
- [ColorTrace 构建通过记录](https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44470795471)
- [后续实机成功的 Deep8 修复分支](https://github.com/Lanye-z/WhateverXe-yogapro13900/tree/experiment/wex-0.8.3-yoga-edid-ab)

## 使用

仅在独立测试 EFI 中安装该分支的 `WhateverXe.kext`，并保留 Graphics 0.4.4、恢复 EFI。启动参数加入：

```text
-wex-yoga-edp120-admit -wex-yoga-edp120-wm -wex-yoga-hdmi-colortrace
```

显示器稳定后运行 `bash collect_color.sh`，使用 `decode_color.py` 解析桌面生成的 `Yoga_HDMI_Color_*.zip`。诊断器是只读采集，不更改 EDID 或 HDMI 寄存器；**只有后续 EDID A/B 分支包含真正的 `-wex-yoga-hdmi-edid-deep8` 修复参数**。

4K60 的 TMDS/SCDC、首次点亮与热插拔另行研究。