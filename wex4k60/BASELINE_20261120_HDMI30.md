# 2026-11-20 17:26:54｜Yoga HDMI 4K30 成功基线解码（脱敏）

来源：用户提供的 `Yoga_HDMI4K60_hdmi30_20261120_172654.zip`，其中包含系统显示模式、IORegistry、现有 WhateverXe 原生观察记录以及 EDID。**只记录技术状态，不公开主机名、显示器序列号、设备唯一标识或完整原始 ZIP。**

## A. 三屏当前状态

| 逻辑输出 | system_profiler | 实际 IOFBCurrentPixelClock |
| --- | --- | ---: |
| AppleIntelFramebuffer@0，内屏 | 3072×1920 @ **60Hz**（当次状态，不是 120Hz） | 387.84MHz |
| AppleIntelFramebuffer@1，AOC 27B2 | 1920×1080 @ 75Hz | 174.50MHz |
| AppleIntelFramebuffer@2，AOC U27P10 | **3840×2160 @ 30Hz**，非镜像、Online | **297.00MHz** |

核显 Intel `8086:A7A0`，macOS 26.7.1，`VRAM Dynamic Max=1536MB`，`Metal 2`。内屏 `WEXYogaEDP120AdmissionReady=Yes`、`AdmissionStatus=4` 表示准入补丁就绪，**但不是当次屏幕实际输出 120Hz 的证据**。

`IOFBTimingRange.maxPixelClock`（每个 FB 对应 312-byte 数据的 little-endian uint64 at byte offset 40）：
- @0: 800MHz
- @1: 720MHz
- **@2: 600MHz**

机身 HDMI600 准入：`WEXYogaHDMI600Requested=Yes`、`Ready=Yes`、`Status=4`。这只证明允许超过 300MHz 的候选模式进入后续阶段，不证明 HDMI 4K60 完整连通。

## B. HDMI Deep8 和物理 4K 管线

- `WEXYogaHDMIEDIDABApplied=Yes`
- `WEXYogaHDMIEDIDABLast` 显示 HDMI VSDB Deep Color `0x38 -> 0x00`，HDMI Forum Deep Color `0x03 -> 0x00`；CTA 色彩声明和 YCbCr420 位图保留。
- `WEXYogaHDMIColorLive` schema 1、有效标志 1、HDMI 管线掩码 0x4、已上电管线掩码 0x7。
- **当前 4K HDMI U27P10 位于 Pipe 2（不是旧双屏实验的 Pipe 1）**：
  - `TRANS_DDI_FUNC_CTL=0x90030200`
  - `PIPE_MISC=0x01800810`
  - `VIDEO_DIP_CTL=0x00001100`
  - `PIPE_MISC[11]=1`（YUV），位深字段为 8bpc，延续之前已确认的 **YCbCr 4:4:4 / 8bpc** 修复结果。
- Pipe 0、Pipe 1 分别对应内屏及另一台外屏；**不要把 HDMI Pipe 2 固定写死到新驱动**，管线会随显示连接拓扑变化。

## C. U27P10 有效 EDID 关键能力

直接解析本次 `IODisplayEDID` 中 AOC 产品 `0x2710`，共 256 字节，基础/CTA 块校验和均为 0。CTA Video Data Block 包含如下 VIC：
- `0x5D` = VIC 93 = 3840×2160@24Hz
- `0x5E` = VIC 94 = 3840×2160@25Hz
- `0x5F` = VIC 95 = 3840×2160@30Hz
- `0x60` = VIC 96 = 3840×2160@50Hz
- `0x61` = VIC 97 = 3840×2160@60Hz

HDMI Forum VSDB 有效数据：`D8 5D C4 01 78 80 00`。
- HDMI Forum OUI：`C4-5D-D8`
- 版本：1
- Max TMDS Character Rate：`0x78 × 5MHz = 600MHz`
- `0x80` 表示 `SCDC_Present=1`

**含义**：显示器在本次经机身 HDMI 读取的有效 EDID 中确实声明了 4K60、600MHz 高速 TMDS 和 SCDC；不支持将当前黑屏归因为“显示器未声明 4K60 或 SCDC”。不过 EDID 声明**不是** SCDC 命令已实际成功、GPU/source 已启用高比率时钟或屏幕物理亮起的证据。

## D. 当前 GMBUS/DDC 观察

`N97FBGMBusObservationReady=Yes`，本次可完整拼接 GMBUS 请求序列 1–17，bus=2。native `IOI2CRequest.sendAddress` 偏移 `+0x0C`：

- #1、#2、#5、#6 的 `sendAddress=0xA0`，`replyBytes=128`，原生返回和 I2C 结果均为 **0**。这些是成功的 EDID/DDC 读取。
- #3、#4、#7–#13 的地址主要为 `0x74`，返回 `0xE00002ED`（`kIOReturnNotResponding`），与普通 DDC/CI 访问更相符；不能当作 SCDC 报错。
- #14–#17 原生返回 `0xE00002C2`（`kIOReturnBadArgument`），相关请求的地址字段为 0，不可解释为 SCDC 失败。
- **没有记录到 `sendAddress=0xA8` 的 GMBUS 请求。** 这符合当次 HDMI 297MHz/4K30 不需要高于 340MHz 的 SCDC 高速协商的情形，但不能断言 4K60 时也没有此操作，或者其他 I²C 路径不存在。

参考：
- https://leopard-adc.pepas.com/documentation/Darwin/Reference/IOKit/IOReturn_h/index.html
- https://jia.je/kb/en/hardware/cta_vic.html
- https://github.com/b00t0x/WhateverXe/blob/f26a36880c49ea1063393d943527808c0f38feca/WhateverXe/kern_xe.cpp#L7793-L7829

## E. SST 补丁运行证据（本轮首次获得）

`WEXYogaSSTHookReady=Yes`、`HookStatus=4`、`CapabilityMasked=Yes`。

- `WEXYogaSSTFirstDPCD`：sequence 1、DDI=5、缓存 `port+0x1E: 1→0`、`port+0x117=0`、原生读取返回 0、`masked=1`。
- `WEXYogaSSTLastDPCD`：sequence 8，累计已屏蔽 **4 次**，本次最后读取缓存值 0。
- `WEXYogaUSBCDPTrainingFirst1..4` 和 `Last`：DDI5 SST 端口有效，`port+0x117=0`，原生训练返回 **0x0**，Lease reason 0。与修复前首次 `0xE00002D8` / 之后 Busy 的诊断形成对照。

这已直接证明 MST 缓存屏蔽代码确实执行并允许至少四次成功训练。结合用户实机确认三屏/热插拔，SST 修复已得到充分支持。

## F. 尚缺证据和下一步

- 上传的 `USER_OBSERVATION.txt` 仍是未经填写的模板；软件记录说明设备 Online、30Hz，但**屏幕 OSD 的物理输入时序需用户确认**，不能从 ZIP 推断。
- 本次 `system_profiler` 内屏是 **60Hz**；不能宣称同一时间实际在 120Hz。
- **还没有任何 HDMI 4K60 黑屏状态的同条件对照数据**；本次正常 30Hz GMBUS 报错不能解释 60Hz 黑屏根因。
- 下一步优先从已有失败日志对比原生时钟、GMBUS 序号、颜色、Pipe 绑定、模式回滚；避免为采集强制重现之前的双屏黑屏。

**本文件为用户日志解码分析；未更改当前 SST 成功驱动或 EFI。**
