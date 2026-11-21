# HDMI2 V2：实机启动后 Metal 丢失的源码级故障隔离（2026-11-21）

## 结论等级

**实机确认：**此前的 SST/Deep8/HDMI600 原 EFI 已经正常工作。用户将新编译的 HDMI2 V2 Kext 与 `-wex-yoga-hdmi2-callsite-safe` 加入测试 EFI 后，在尚未手动切换 4K60 时即出现 **GPU Metal 硬件加速丢失、仅内屏点亮、两路外屏均不可用**。同机的旧 `LightUpTMDS` 全函数 route-only 也曾引发类似回归，故不得继续试验 V2 observe 或 safe。

用户该次 IORegistry：
```
WEXYogaHDMI2CallsiteWriteEnabled = Yes
WEXYogaHDMI2CallsiteReady = Yes
WEXYogaHDMI2CallsiteStatus = 5
WEXYogaHDMI2SafeStatus = 3
```
`WEXYogaHDMI2CallsiteLast` 和 `WEXYogaHDMI2CallsiteFirst*` **均未出现在 grep 输出中**。

这是**已安装补丁但没有发布完成记录**的状态，不应声称原生函数已完成调用，更不应声称已经尝试或成功执行 0xA8/0x20 SCDC 写入。

## 1. 确认的源码差异与风险

### 1.1 V2 改写原生 CALL，不是“只观察”

V2 `wexhdmi2v2/prepare.py` 在同一个安装分支（observe/safe 均进入）中检查 `image+0x4FFB6` 原本为 `E8 67 0B 00 00`（CALL 到 `image+0x50B22`），之后生成 5 字节 `E8 rel32`、调用：

```cpp
patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));
state=... && !memcmp(address+callOffset,patchedCall,5) ? 5:4;
```

用户 `status=5` 说明**这 5 个字节读回与 patch 后 bytes 一致**。该状态并未证明目标 helper 已运行。

核查 Lilu 真正的 `KernelPatcher::routeBlock` 实现（`acidanthera/Lilu/Lilu/Sources/kern_patcher.cpp`）：在默认 `buildWrapper=false` 下，直接调用 `lilu_os_memcpy(from,opcodes,opnum)` 覆写原生代码，**不创建原函数包装/trampoline，也不保存原始指令**。因此所谓 observe 模式并非无侵入；存在二进制代码改写/并发执行窗口方面的风险。但**尚不能证明正是并发 patch 导致这次 Metal 丢失**。

### 1.2 已证实的诊断盲区

`XE::yogaHDMI2Callsite` 在调用 `original(controller,rawFB,rawPath,rawTiming)` **之后**才通过 IORegistry 发布 `CallsiteLast` / `First*`。所以完整 grep 中缺少属性，至少有四种可能：未进入 helper、进入后被阻断/异常、原生调用未返回、属性发布失败。**不能仅凭缺少 Last 判断 CALL 没执行**。

对于安全回滚，后续如果重构，只能先记录调用进入且避免锁/IORegistry 死锁；但这不授权继续在现有坏 V2 上增设侵入 Hook。

### 1.3 这不是 V1 的重复故障

V1 4K60 黑屏时 Metal 正常，有 `WEXYogaHDMI2HighLast=[1,22,1,533250000,5,3]`，其 SCDC 在 WM 处因为原生 owner lock 未持有而在写前中止。V2 在手动选 4K60 前已 Metal 失效，`CallsiteLast` 缺失，因此**没有任何证据能断言这次问题是接收端 SCDC 0xA8 未响应造成的**。

源代码上 V2 low-mode 条件为 `pixelHz<=340MHz && armedPipe>=3` 时直接返回52、不会调用新增 SCDC；但由于**本次启动过程中实际尝试的 HDMI 时序没有采集**，不能断言启动时一定走的是低频路径。

### 1.4 软件 CI 的覆盖空白

成功运行 SHA `3ab20204c384dd3b45902c0c4bd0c2b136e7db1d`、Actions `44869605258`：RELEASE、Compat、221/221 通过，上传了实验 Kext。测试验证了静态机器码/符号与纯逻辑；**没有重演 Apple 的真实同步锁所有权、硬件启用顺序、其他显卡加速 Hook 与多屏路径的相互作用**。绝不能把 CI 绿色解释为实机安全。

## 2. 已核实的 V2/V1 编译产物

当前研究容器中可重新读取 ZIP：
- V1 `WhateverXe_0.8.3_HDMI2_SAFE_CANDIDATE.zip`：Mach-O 可执行文件 **1,869,816 bytes**，SHA256 `d1569f95ab46e601baa4b38bbacb31a4c57e681868a28b93989294280d9b592e`。
- V2 `WhateverXe_0.8.3_HDMI2_CALLSITE_V2_EXPERIMENT.zip`：Mach-O **1,870,272 bytes**，SHA256 `7e598d7bdf7153bc3b69653efdf1732f31d93913159e43324bef7cfd567b6931`。
- V2 Mach-O 实际符号表含 `XE::yogaHDMI2Callsite(void*,void*,void*,void const*)`，位置 `__TEXT,__text +0x584A0`（Kext 镜像内地址，并非 Apple framebuffer 中 CALL 的地址）；证明本次打包包含了编译后的 helper，而不只是源码。

**仍不具备：**V2 实机启动时的完整 IORegistry、kernel/WindowServer 日志和原生调用入口状态；因此无法区分是否触发了 live Call 路径，也无法确认导致 Metal 失效的**第一条异常**。

## 3. 非破坏性下一步

**不再要求重启 stable EFI 作 A/B；以前 EFI 正常是已确认事实。**

如果用户仍处于本次坏 V2 启动环境且内屏可操作，仅运行本次单独提供的 `Yoga_V2_MetalLoss_ReadOnly_Audit.sh`，会读取（不写硬件）：`system_profiler SPDisplaysDataType`、`kmutil showloaded`、`ioreg` Framebuffer/Accelerator、已保留的 HDMI2/Display13/SST 状态、近25分钟内核/WindowServer图形错误。上传前检查私有标识；无需再切换4K60或拔插任何连接。

记录收齐后，对照 `CallsiteStatus`、`N97FBOutputHooksReady`、Graphics activation、当前 framebuffer 模式、是否出现原生 LightUp 调用 / IOAccelerator fallback。根据数据再判断是否优先为 **安装期 code-patch**、**原生 wrapper 执行期**还是 **其他已有 USB4/雷电实验配置**进行定因。

**目前确定的可行动工程处置：冻结并禁用 V2（observe 和 safe 都禁止），不要重新设计一个更激进的 TMDS CALL/route hook；以成功的 SST 原始分支作为可靠研究基线，静态查找无代码重定向的下一步方案。**
