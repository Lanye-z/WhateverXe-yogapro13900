# 2026-11-21 HDMI2 V2 22MB Metal 回归：已定位与软件验证

## 已定位的直接冲突
- 实机 ZIP：`Yoga_V2_MetalLoss_20261121_133318.zip`；显示仅 22 MB、`.Display_boot/IONDRVFramebuffer`，`WEXDisplay13TCHooksReady=No`、`N97FramebufferBackendReady=No`、`N97SharedRegisterPrerequisites=No`。
- 源码顺序：`processDisplay13FramebufferOutput()` 先执行 V2 的 `routeBlock(address+0x4FFB6,...5 bytes)`；之后 `processDisplay13FramebufferTC()` 读取同位置原始 7 字节 `E8 67 0B 00 00 EB 1C` 并 `memcmp`。签名不匹配使 TC 钩子失败，导致 Display13 后端不满足启动合同。
- V2 `CallsiteStatus=5` 仅表示重写机器码成功；没有 `CallsiteLast` 与已观察到的 TC 失败相符，不能证明执行过 SCDC。

## 已落实的工程更改
- `wexhdmi2v2/prepare.py` 把 **实验 CALL 写入**从 Output 安装阶段移至 TC 验证完成之后；只有 Output 和 TC 都成功才考虑安装，不能再提前破坏 TC 的签名字节。
- `-wex-yoga-hdmi2-callsite-observe` 现在**不调用 routeBlock**，仅进行软件门控和原字节校验，`status=6`、`WEXYogaHDMI2PassiveReady=Yes`。旧 V2 的观察模式并不是真观察，已被修正。
- `wexhdmi2v2/test_plan.py` 明确检测原生 7 字节签名、TC-先于-CALL 的依赖关系、以及 observe 模式不能改写原生 CALL。

## CI 结果
- 对应代码 commit：`df458fe496a1133105ff560f10951dd1eb3a5d41`
- GitHub Actions：`44871825686`
  https://github.com/Lanye-z/WhateverXe-yogapro13900/actions/runs/44871825686
- **RELEASE 编译通过、Compat 通过、221/221 回归测试通过、打包完成。**
- 此结果仅验证编译、源代码与既有测试，不包含对 Yoga 实机 Metal/HDMI/USB4/SCDC/4K60 的新测试。

## 禁止作为日常 EFI 使用
**不得将 active `-wex-yoga-hdmi2-callsite-safe` 当成已验证修复。** 即使错误安装顺序已经调整，原生调用栈/返回 PC 变化、SCDC 0xA8 非响应及失败回切仍未解决。此前用户已两次遇到原生 TMDS 路由导致的加速失效，且扩展坞 USB 枚举近期不稳。继续使用经过用户实机确认的 SST/Deep8/HDMI600 版本，避免盲测。

后续更稳妥的 4K60 研究入口是**复用现存的 Display13 模式设置和原生 GMBUS/DDC 观察钩子**、首先确认调用时序与锁归属，再单独研究 SCDC 和源端 bit0/4；不应为了高速视频重新安装覆盖 TC 已验证字节的 CALL 重定向。

详细代码对照见 `wexhdmi2v2/ORDERFIX_20261121.md`。
