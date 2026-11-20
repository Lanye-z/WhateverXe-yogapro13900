# Display13 HDMI HelperTrace 第三轮：DDI_FUNC_CTL 写入定位（2026-11-20）

## 身份与证据范围
用户上传 `Yoga_Display13_HDMI_HelperTrace.json` 的 5 段原生代码窗口与基线匹配：
UUID `B6078743-F795-3202-A55E-EA690FA40949`；SHA256 `115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e`。
已用 GNU objdump 反汇编。没有动态测量实际寄存器或做 4K60 切换。

## 已确认的直接写入
- `LightUpTMDS +0x50B98` 调用 `0x48BB6`。
- `0x48C10`: 调用 `setColorMode(0x491F2)`。
- `0x48F9E–0x48FB0`: `[path+0x134]` 写 `0x60410+transOffset`（MSA_MISC）。
- `0x4902B–0x4903D`: `[path+0x130]` 写 `0x60404+transOffset`（FUNC_CTL2）。
- **`0x4904A–0x4905C`: `[path+0x12C]` 写 `0x60400+transOffset`（FUNC_CTL）。**
- `0x4908C–0x490B1`: 特定分支用 `OR 0x100` 更新 `[path+0x12C]` 并第二次写 FUNC_CTL；存在跳过首次写入的条件分支。
- `0x4D8EA–0x4D90D`: 另一控制路径用掩码 `0xFFFFFEFF` 清 bit8 后写 FUNC_CTL。
- `0x4D937` 从寄存器读值并清 bit27..31；后续最终调用在上一采集窗口 `0x4D94B` 处截断，不应推断已完成写回。

**重要更正：`0x100` = `TRANS_DDI_DP_VC_PAYLOAD_ALLOC` (bit8)，不是 DDI 输出使能！** Intel 定义中 bit31 为 FUNC_ENABLE、bit4 为 HIGH_TMDS_CHAR_RATE、bit0 为 HDMI_SCRAMBLING。当前窗口尚未定位 bit31/4/0 的真实赋值来源。路径索引来自 `[path+0x3640]`，不得硬编码 Pipe2。

Linux 参考：[寄存器定义](https://codebrowser.dev/linux/linux/drivers/gpu/drm/i915/display/intel_display_regs.h.html)、[DDI 配置](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_ddi.c)。

## 未解决问题
1. `DisplayPath+0x12C` 最初由谁构造，4K60 时 bit0/4 是否置位？
2. 原生 I²C 是否按正确时序设置显示器 SCDC `0x20` 的 bit0/bit1？与 GPU 寄存器位不要混淆。
3. DPLL、PHY、TMDS 594MHz 是否实际稳定？本次静态代码无法判断黑屏根因。

## 下一轮只读收集
实验分支新加 `wex4k60/native_macho_ddi_xref.py`，对精确 UUID/SHA 的原生 Mach-O，仅扫描 `__text` 中 `2C 01 00 00` 候选位移并导出有限上下文；另外补抓 `0x4D920+0x100` 的截断尾部。字节匹配不等于已解码的有效引用，必须检查寄存器溯源。

```bash
cd ~/Downloads/Yoga_HDMI4K60_Audit
git pull --ff-only
python3 wex4k60/native_macho_ddi_xref.py \
  --out ~/Desktop/Yoga_Display13_DDI_Xrefs.json
```

此轮只读；**不更改 EFI、Kext、NVRAM、HDMI 模式、SST 三屏、内屏 120Hz，也不启用旧 TMDS Hook。**
