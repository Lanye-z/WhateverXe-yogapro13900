# 第四轮：Display13 DDI Xrefs 逐项归类与首版补丁决策门槛（2026-11-20）

## 输入与验证边界
用户 `Yoga_Display13_DDI_Xrefs.json`，UUID `B6078743-F795-3202-A55E-EA690FA40949`，完整 Mach-O SHA256 `115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`，`exact_baseline_match=true`，代码段 `__TEXT,__text` 617888B，位移字节串 `2c 01 00 00` 的 46 处命中，`truncated=false`。

GNU objdump 对每个命中的窗口做静态反汇编。**字节串不等于 DisplayPath xref**：其他对象碰巧包含相同偏移，跳转偏移、整型立即数、memcpy 长度也可能匹配。不能将 46 处全都当作 HDMI 字段使用。

## 1. 直接建立的 DDI 控制相关数据流

| 位置 | 机器码操作与意义 | 证据性质 |
|---|---|---|
| `0x4C67D–0x4C689` | 读取 `0x60400+transOffset`，写入 `[path+0x12C]` | 硬件 → 缓存 |
| `0x4904A–0x4905C` | `[path+0x12C]` → `0x60400+transOffset` | 缓存 → 硬件（原生 `0x48BB6`） |
| `0x4908C–0x490B1` | 条件 `[path+0x12C] |= 0x100` 后再次写 FUNC_CTL | bit8 为 DP VC Payload Allocation；非 HDMI2 |
| `0x6973A–0x6974A` | 缓存 → FUNC_CTL | 另一恢复/配置路径 |
| `0x4D8EA–0x4D90D` | `[path+0x12C] & ~0x100` → FUNC_CTL | bit8 清除 |
| `0x4D928–0x4D94B` | 从 FUNC_CTL 回读，`and eax,0x07ffffff`，**通过 [vtable+0x130] 写回** | 补齐上一轮截断；此路径清 bit27–31，不应认为只清 HDMI enable |

## 2. 更多写入地点：不是 Scrambling / High TMDS
以下窗口均含对实际 DDI 控制寄存器操作以及 `+0x12C` 缓存更新：
- `0x8734F–0x87379`、`0x8B831–0x8B864`：`and ebx,0xffffffdf`，清 bit5。
- `0x88855–0x88880`、`0x8E843–0x8E874`：`or ebx,0x20`，置 bit5。
- `0x87747–0x8776B`、`0x8837C–0x88399`、`0x8BC10–0x8BC2F`、`0x8E526–0x8E544`、`0x8E659–0x8E677`：前置代码出现 `or 0x200`，涉及 bit9，仍应逐条核对条件与实际寄存器。
- bit5 在 Linux i915 对应 `TRANS_DDI_HDCP_SELECT`，bit9 为 `TRANS_DDI_HDCP_SIGNALLING`；**不能当作 bit0/4 的构造者**。

此外，`0x37919` 从 +0x12C 读取并解码 bit20..22（BPC），`0x4A1F5` 读取 bit16/17（极性），进一步支持该字段是 DDI FUNC_CTL 的缓存，但并未展示 HDMI2 的 bit0/4 赋值。

### 当前不能下的结论
`0x48BB6` 中没有直接为 HDMI 2.0 设置 bit0/4，当前抽取的上述写入路径同样没有独立证明 bit0/4 是在此处生成。**这不等于原生驱动从未在其他函数、其他扩展或原有硬件状态中设置它们**。本次只读代码既没有 4K60 MMIO 值，也没有 SCDC 实际请求/应答。

本机已保存的 **4K30** 控制字是 `0x90030200`，其中 bit0/4 都为 0 是合理的低速状态；不能以它推断 4K60 也是 0。

## 3. 首版修复的确定性决策树
1. 先用**现有 Display13 RegisterAccessManager 写寄存器观察器**（若不引入新的原生路由）在将来受控实验中捕获 4K60 启用 `0x60400+transOffset` 的实际写入值，解码 enable(bit31)、high rate(bit4)、scrambling(bit0)，动态映射 Pipe/Transcoder；不要固定 Pipe 2。
2. 利用现有 GMBUS/DDC 记录核对 HDMI DDI B 是否出现 `0xA8` 地址上的 SCDC `TMDS_CONFIG=0x20` 事务及返回码；若原生经其它 I2C 路径，GMBUS 缺失**不能**证明完全没有 SCDC。
3. 如果 4K60 源端 0/4 没置位且 sink 没配置，首版独立实验补丁必须解决**两侧一致性**：在真实 HDMI/高速/已确认 SCDC 能力的模式下，于原生 TMDS 发送启用**之前**完成 sink 配置及读回，然后在既有原生 FUNC_CTL 写入前把 shadow 中源端两位设为 1，失败时恢复原值。务必保留所有无关位，且不能在寄存器访问回调的未知锁下进行阻塞 I2C。
4. 如果 source/sink 都正确而屏幕仍黑，优先检查 DPLL/PHY/时钟锁与板级转换器，避免无证据重复修改 bit0/4。
5. **不重新启用历史独立 `LightUpTMDS` route-only Hook**。旧实机已经反馈硬件加速丢失；一切实验默认关闭、用独立 EFI、必须有低速恢复路径。

## 4. 下一步实施建议
**不继续泛化搜索 +0x12C**。先写一个只读、现有 RegisterAccessManager/GMBUS 事件的紧凑对比视图（register offset、值、bit31/4/0、总线地址、结果、顺序号），确认 4K60 真实状态的最小缺失项；若没有安全的既有动态观察点，优先检查用户历史黑屏日志，而不是再装旧 TMDS Hook。

Linux 参考：
- https://codebrowser.dev/linux/linux/drivers/gpu/drm/i915/display/intel_display_regs.h.html
- https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_ddi.c

当前仅静态研究，未构建 Kext 或实机验证 4K60；原 SST / HDMI600 / Deep8 成功配置保持不变。
