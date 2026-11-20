# Yoga A7A0 HDMI2 V1：4K60 黑屏后回切 4K30 外屏失联（01:24:36，2026-11-21）

## 证据来源及保密范围

用户上传 `Yoga_HDMI2_after_4k60_fallback_missing_20261121_012436.zip`。独立对照用户先前采集 `Yoga_HDMI2_V1_black_20261120_225512.zip` 和 `Yoga_HDMI4K60_hdmi30_20261120_201932.zip`。本文不包含序列号、完整 EDID、boot-args 或用户私人信息。本次仍为**已发生故障后的只读取证**，不要求重现。

**用户实际描述：**从 4K60 切回 4K30，AOC 不再显示于系统设置，另两屏没有随切换直接黑屏。采集文本的 `USER_OBSERVATION.txt` 仍是空白模板，不能凭它确认 AOC 的 OSD 是 No Signal 还是有信号黑屏，也不能确定另一外屏在 01:24:36 是否仍持续实时刷新。

## 1. macOS 原生显示器枚举

- `system_profiler SPDisplaysDataType` 只剩 **Lenovo 内屏 3072×1920 @ 120Hz**；Metal 2 / 1536 MB 显存仍在，说明加速未整体消失。该工具连 **另一外接 27B2** 也没有枚举，不能说只丢了 AOC。
- `IODisplayConnect.txt` 中只有 `display0/AppleBacklightDisplay`，无 4K AOC 或另一块外屏的 IODisplayConnect。
- `AppleDisplay.txt` 是空输出，符合当前没有该类额外外屏的观察。
- `AppleIntelFramebuffer@0/@1/@2` 三对象仍存在，但 @1/@2 下没有外部显示器连接子对象；各自的 `IOFBCurrentPixelClock` 为 **775690000 / 297000000 / 174500000 Hz**。这些数值是属性，不能推断外屏仍被启用。
- 对比成功基线：`IOFBConfig` 含 `IOFB0Hz=Yes` 的外接 framebuffer 数由 **1 个增加到 2 个**；现在 @1、@2 均标 `IOFB0Hz=Yes`，二者均 `IOFBNeedsRefresh=Yes`，`IOFBProbeOptions=1025`。这强烈支持两个外接 FB 已处于没有活动模式/等待刷新状态，不能单凭仍有 pixelClock 字段视为在线。

## 2. 只读 GPU 寄存器对照（不是持久缓存）

`WEXYogaHDMIColorLive` 来自 `wexcolor/prepare_colortrace.py` 生成的 **lazy OSSerializer**。只有用户读取 IORegistry 时，且受控访问获得 power lock，才读取 `0x60400 + pipe*0x1000`。本次 `schema=1,valid=1,poweredMask=0x7`，说明这次实际读取有效；但其物理状态仅对应采样瞬间。

| 采集 | HDMI B Pipe | `TRANS_DDI_FUNC_CTL` | enable | hiTMDS(bit4) | scrambling(bit0) | HDMI mask |
|---|---|---|---:|---:|---:|---|
| 20:19 正常 4K30 | Pipe2 | `0x90030200` | 1 | 0 | 0 | `0x4` |
| 22:55 4K60 黑屏 | Pipe1 | `0x90010200` | 1 | 0 | 0 | `0x2` |
| 01:24 回切后消失 | **无有效 HDMI-B Pipe** | P0=`0x02100106`, P1=`0x00030200`, P2=`0x02010002` | **三条均为 0** | 无有效 HDMI | 无有效 HDMI | **`0x0`** |

重要：三条 Pipe 的 enable=0 并不证明用户内屏实物也灭了；当前只针对这些采样位置解释，显示链路可能有另一路状态/使用阶段。结合内屏仍由 macOS 枚举，不能扩展为整个显示硬件停止工作。

## 3. WindowServer 真实显示器下线事件

20 分钟谓词查询最终执行 `tail -n 2000`，最早保留 **2026-11-21 01:20:19**，因此其余更早的事件缺失，不能还原 4K60 到 4K30 的全程。

日志明确：
- `01:20:20.727`：`Received display connect changed for display 0x78c9cb3a`
- `01:20:20.728`：`Display 0x78c9cb3a changed state to offline`
- `01:20:20.733`：ColorSync `NULL device` for that display
- `01:20:21.780`：`CGXDisplaysDidReconfigure: Display removed`

因此真实发生了**至少一个显示器对象下线/移除**，并非仅系统设置界面隐藏。**不要把 `0x78c9cb3a` 直接称为 AOC**：成功旧基线的 27B2 ID 是 `0x78c9cb39`，AOC ID 是 `0x78c9459a`，但 ID 跨重枚举可变化；没有当次 EDID 映射前不归属具体物理显示器。此 01:20 事件也可能是另一台外屏的掉线，AOC 更早的掉线日志被截断。

## 4. GMBUS/DDC 不是完全不可用

- 初始 16 条请求的 #1–4、#7–8 为 DDC bus2 / `sendAddress=0xA0` / EDID 长度128，结果成功；
- #5/6/9/10/12–15 为 bus2 / `0x74`，`0xE00002ED`（Not Responding）；#11 为 `0xA8` SCDC 读取，亦为 `0xE00002ED`；
- 上次 4K60 黑屏采集的 `N97FBGMBusLast` seq28 为失败；现在 seq36 是 bus2 `0xA0` 128 字节，**native=0、request=0**，说明两次采集之间有继续执行并成功的 EDID DDC 事务。但没有时间戳，**不能证明该成功发生在 01:20 下线之后**。
- `N97FBPortDDCLast=[1,3,0,0,0,0,0,0]` 是最近发布的 block3 成功返回，未能凭此把它归属物理 HDMI B；此属性也是会覆盖的观察值。
- 本次 `WEXYogaHDMI2HighLast=[1,22,1,533250000,5,3]` 与黑屏采集完全相同，`WEXYogaHDMI2SourceLast` 仍不存在。V1 实验 SCDC 在 `status=5` 原生递归锁前置条件失败时即中止，不能声称源端高速位曾写成功。
- **V1 日志盲区：**低于 340MHz 的模式回切不更新 `HighLast`；`WMEvent` 又仅发布前 16 次或部分高速事件。因此没有新增 `WMEvent` 并不证明回切没有运行 WM 回调。

## 5. 综合结论与优先级

**已证实：**一次 4K60 黑屏发生时（源 enable1、hi bit0/4=0）补丁未过锁；随后选择 4K30 后，系统至少有显示对象真实下线，最终外接连接节点为空、两个外接 FB 均 0Hz 标记且没有有效 HDMI-B transcoder enable。此过程**更符合输出关闭/失去连接对象后重枚举未恢复**，而非单纯 UI 显示问题。

**仍不能定因：**究竟是 HPD 电平消失、原生 HDMI disable/enable 状态无法回滚、EDID 读取/对象重建故障、主动停止外屏输出还是其他状态机原因。V1 无法执行新增 SCDC 写入，不能把回切下线直接归咎于那条未执行的写入；此前旧 HDMI600 模式下也曾出现类似回切黑屏。

**后续开发步骤：**
1. 先做**完全只读**的失败后路径仪表化：在原有 native `wrapDisplay13GMBus`、已安装 HPD/Online 回调、`wrapDisplay13GMBusWrite` / disable-port/lifecycle 回调上记录有界的模式切换时序、port、pipe、原生返回和失败状态。**不新增 SCDC 读写、MMIO、LightUpTMDS Hook。**
2. 对 `IOFB0Hz` 和 Display13 本机生命周期状态按真实 pipe/port 追踪，比较“成功 4K30 → 4K60 失败 → 4K30 回切”旧日志；在没有恢复证明前，不再主动切到 4K60。
3. 另外研究适当的 native DDC owner 锁/调用入口：WM callback 的 owner lock 未持有是已证实事实，**不得移除锁检查直接从 WM 发 SCDC**；将 4K60 修复与热插拔恢复分别单独验证。
4. 用户若要恢复生产用屏，保存工作后正常关机，在断开 HDMI 下从成功备份 EFI 启动，再尝试稳定 4K30。不在黑屏/消失状态下强制热重置显示控制器。

## 数据边界
- `USER_OBSERVATION.txt` 未填写：不能确定用户眼见的外屏在 01:24 时是否仍实时工作、OSD 显示什么。
- Unity log 最早 01:20:19：未捕获完整实际失败开始时刻的 kernel/HPD 信息。
- `WEXYogaHDMIColorLive` 的 HW 值是采样瞬间，不代表所有输出接口/时刻，更不能以没有 HDMI-B 推断 Intel 显卡彻底崩溃。
