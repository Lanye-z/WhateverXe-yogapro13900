# Yoga Pro 14s IRH8 · 0.8.3 Stable Deep8 + HDMI600 / 只读诊断（A+B）

## 2026-11-20 状态续报：SST 已修复，机身 HDMI4K60 尚未修复

在独立分支 `experiment/wex-0.8.3-yoga-usbc-sst-compat` 启用 `-wex-yoga-tc5-sst` 后，用户实机确认 USB-C 拓展坞恢复显示、三屏独立输出、热拔插正常。这是 **SST 成功**，与当前机身 HDMI 4K60 黑屏属于两条独立路径。本文件原先的 HDMI600 实验只提高 `getOnlineInfo` 的 300→600MHz 模式准入，**没有**完成 HDMI 2.0 SCDC、high TMDS clock ratio、源端 scrambling、PLL/PHY 或错误回滚的全链路验证。

2026-11-20 进一步实测：4K 屏在 HP G4 DP 上只有 4K30 选项，换回 **机身 HDMI** 可以选择 4K60 但外屏黑屏。暂不能将其直接归因为唯一的 SCDC 故障；需在保持现在 SST/eDP/Deep8 工作的前提下，分别验证 sink EDID/SCDC 能力、实际像素/TMDS 时钟、原生 HDMI LightUp 调用路径、GMBUS I2C 能力、源端 1:40 比率/扰码状态、Transcoder/Pipe/PLL 以及失败后回滚。4K60 采用 YCbCr 4:2:0 时所需 TMDS 速率与 4:4:4 不同，必须先获取实际模式参数。

**新的 HDMI4K60 工作只从已验证 SST 分支派生**，不要从本早期 HDMI600/旧 HDMI2 Route 构建替换日常 EFI。原 `-wex-yoga-hdmi2-route-only` 分支已发生核显加速丢失，标记为禁止实机重试。已有 `collect.sh`、`diagnose.py` 可以无需重编译先对照采集 4K30、黑屏4K60与恢复后的状态；采集结果不能冒充完整的物理 SCDC 抓包。

---


**这是模式准入 + 诊断合并实验，不是完整的 HDMI 2.0/4K60 修复。**
**基线为用户在 2026-11-19 重新上传并再次确认正常的 WhateverXe.kext，和原已验证的 experiment/wex-0.8.3-yoga-edid-ab。**
恢复版 x86_64 主可执行文件 SHA-256：8089a685790a3f19121ba8dcbdc0f8d6ca63cffccc4669a95256615b401d5791。

## 保留的已验证功能

- eDP 3072×1920 @120Hz，WM_ONLY；不修改 120Hz 启动参数、Watermark、DBUF 及 Pipe 准入。
- U27P10 HDMI 4K30 正常颜色：保留原有 -wex-yoga-hdmi-edid-deep8 和 ColorTrace、ModeAudit、HPD Trace。实测伪色修复后输出是 **YCbCr 4:4:4 / 8 bpc**，不是 RGB8 强制转换。
- 原 Graphics 0.4.4、原有 macOS 显示器覆盖、正常 HDMI 1080p 不动。
- 之前的 -wex-yoga-hdmi4k60 **不能加入**；旧实验启用时已经产生 22MB 显存、内屏缩放异常，已停用。

## A：精确模式准入

仅新增 -wex-yoga-hdmi600，默认关闭。

在原 WhateverXe Display13 framebuffer 安装函数已有的 ClockSet 初始化锚点上，只对 A7A0 + 移动 Display13 + 已核准 eDP/WM + 固定 Combo HDMI B + 正确 framebuffer loadIndex 生效。精确校验 AppleIntelFramebuffer::getOnlineInfo 在给定驱动版本的函数偏移和 28 个字节，成功时只把 HDMI 分支 300000000 改为 600000000（偏移 0x2E780 处四字节立即数）。符号、指令、平台不吻合时直接拒绝。

不新增 getOnlineInfo/LightUpTMDS Hook；不写 SCDC、PLL、PHY、TMDS、HDMI InfoFrame；也不修改原 Deep8 色彩修复。独立实验 Kext 加入 IORegistry root 状态：

- WEXYogaHDMI600Requested：是否传了开关
- WEXYogaHDMI600Ready：精确位置补丁是否成功
- WEXYogaHDMI600Status：0=未启用、1=平台/路径门槛拒绝、2=原生代码不匹配、3=写入失败、4=已成功安装

**Status=4 并不代表外屏 4K60 视频链路正常。** 没有 SCDC 协商时，选中高于 340MHz 的 HDMI RGB/444 模式仍可能黑屏。

## B：复用已有诊断，不增加内核 Hook

本实验保持原版已提供的 -wex-yoga-hdmi-colortrace、-wex-yoga-hdmi-mode-audit 和原生 IORegistry 记录，只新增用户空间的 wex600/collect.sh + diagnose.py。

它采集 HDMI600 准入结果、IOFBTimingRange / IOFBCurrentPixelClock、EDID Deep8 状态、GPU Metal/显示模式、原有 N97FBClock / Pipe / WM / DBUF 状态。**只读取，不写寄存器，不发送 SCDC 命令，不切换刷新率。**
限于稳定驱动已有的日志字段，本阶段不能凭空声称读取了完整 HDMI PLL/PHY 或 SCDC 状态；缺失的数据应如实标注。

### 需要比较的三个状态

1. baseline：保留现有 EFI 的成功 120Hz + 4K30（用于二进制基线对照）
2. admit：独立测试 EFI 加入 -wex-yoga-hdmi600，但继续保持 4K30；先确认没有 22MB、伪色、缩放回归，并检查 Status=4
3. black60 / recovered：若安全地选择 4K60 但画面黑屏，**保持内屏可用**立即采集；切回 4K30 后再采集 recovered。若内屏也异常，立即用恢复 EFI 启动，不要冒险采集。

采集脚本与 diagnose.py 放在同一目录：

    bash collect.sh baseline
    bash collect.sh admit
    bash collect.sh black60
    bash collect.sh recovered

ZIP 输出在桌面。若不想上传包含完整 IORegistry 的信息，可先检查或删除机型序列号、硬件标识等不需要的部分。

## 安装顺序（独立测试 EFI）

- **先保存已成功的 EFI 和完整旧 Kext；测试版只换 WhateverXe.kext，其他所有配置原样。**
- 第一次启动测试版不添加新开关；确认 Metal、内屏 120Hz、HDMI 4K30 颜色正常，并确认 WEXYogaHDMIEDIDABApplied。不开 4K60。
- 第二次仅新增 -wex-yoga-hdmi600；继续保留 -wex-yoga-hdmi-edid-deep8 及原有全部参数。先验证 4K30 和 Status，再决定是否测试 4K60。
- 若 4K60 黑屏，但内屏正常，切回 4K30、保留对照日志；这是尚无 SCDC 的预期限制之一。
- 如出现 22MB、内屏缩放错误、颜色退化、崩溃，直接恢复旧 EFI。不能靠继续加旧 -wex-yoga-hdmi4k60 修复。
- 只有实际显示器 OSD + 系统模式 + 正常画面一致时，才能称 4K60 真正成功。

## 构建保障

GitHub Actions 使用固定 WhateverXe 0.8.3 源码提交、对应 Graphics 0.4.4、Lilu 1.7.2 和 MacKernelSDK。构建器首先执行成功基线的 wexedid/prepare_edid_ab.py，再在独立 Display13 入口加入旧 E1.1 已测试的 300→600MHz 指令补丁。检查注入前后只有一个 include、一段独立安装代码和启动参数注册发生变化。运行上游完整测试、E1.1 立即数测试、Deep8/颜色模式测试和 RELEASE 编译，通过后才提供测试 Kext。

参考：https://github.com/b00t0x/WhateverXe/issues/41 以及用户仓库的 e11/E1.1_HDMI600_README.md、wexedid/README.md。
