# D1.1.1 — video VA / HEVC encode discovery and isolation

**Strict scope:** A pair of *user-space diagnostic probes*, not a binary patch or complete system-wide fix. The D (`-wex-a7a0-panel-only`) Kext and the known-good Graphics install stay unchanged. No sudo or SIP/EFI changes required.

## What the machine already proves

- `H264/HW` encoding: 180 NV12 samples successful; `H264/HW` from BGRA through an **application-level CPU BGRA->NV12 conversion**: 180 successful, zero errors. Both on A7A0/Tahoe 25G241. This is not an operating-system-wide conversion fix.
- H.264 **BGRA-direct** encoding: native `AppleIntelTGLGraphicsVADriver` crashes in `AVFPixelProcess_PrepareToTransferImages` / `VTPixelTransferSessionTransferImage` with `EXC_BAD_ACCESS` at address `0x8`.
- HEVC HW session create with hardware required: `-12908`; installed VideoToolbox inventory shows *only* `Apple HEVC (SW)`. **Crucially, IORegistry already has `IOGVAHEVCEncodeCapabilities`**, so merely publishing the same capability cannot resolve observed registration.
- HEVC software fallback: 1 sample compressed; explicitly *not* proof of hardware.

## New diagnostics

From `macos/video-encode/` run:

```bash
# 1. Read-only encoder inventory (safe)
bash run_d11_probe.command inventory

# 2. Process-local professional-workflow registration and re-enumeration.
#    This is a DIFFERENTIAL test: no system-wide registration/configuration.
#    This Apple API loads professional workflow plug-ins, NOT necessarily a GPU VA encoder.
bash run_d11_probe.command professional

# 3. Encoder property negotiation, without creating a compression session.
#    This can load VideoToolbox provider code. Check statuses and selected ID.
bash run_d11_probe.command properties

# 4. Static installed VA bundle fingerprint: only reads files and metadata.
bash inspect_va_driver.command
```

For **isolating the native VPHAL crash**, only after you save your work and explicitly agree to the risk:

```bash
# Isolate the transfer path from the encoder. Start with a tiny frame.
bash run_d11_probe.command pixel 64 64 bgra-nv12 --i-accept-native-crash
# Compare with the same-format NV12 path:
bash run_d11_probe.command pixel 64 64 nv12-nv12 --i-accept-native-crash
# A native driver crash or even GPU instability is possible at 1080p!
# Only if the 64x64 tests work and you want to compare to the earlier crash:
bash run_d11_probe.command pixel 1920 1080 bgra-nv12 --i-accept-native-crash
bash run_d11_probe.command pixel 1920 1080 nv12-nv12 --i-accept-native-crash
```

Each subcommand compiles a local Objective-C program from source and saves a timestamped log to `macos/video-encode/output/`. `pixel` calls **only** `VTPixelTransferSession`; unlike the previous H.264 tests, it never creates a compression session. `nv12-nv12` can still invoke native VA code; it is not guaranteed crash-free. A successful isolated transfer does *not* rule out a failure when AppleGVA invokes its internal `AVFPixelProcess` path from the encoder.

## How to interpret results

| Finding | Interpretation | Next justified work |
| --- | --- | --- |
| New `HEVC HARDWARE=YES` after `professional` | Encoder was available through a process-specific registration route | Probe HW-required HEVC session, then 1/180 frame encode + decode; not proof yet |
| No HEVC HW after `professional`; `properties` fails when required | Encoder provider/registration still missing | Compare Tahoe VA binary SHA/UUID and AppleGVA registration vs native TGL reference; do not fabricate IORegistry property |
| Pixel transfer crashes for BGRA→NV12 in same driver | Crash exists outside codec session and supports independent VPHAL/pixel-transfer bug | Capture LLDB thread backtrace + VA image load base, compare exact binary and patch signature |
| Pixel transfer succeeds; BGRA compression still crashes | Native encoder-specific AppleGVA conversion/preparation path | Trace compression-stage pixel-transfer invocation and encoder input buffer attributes |
| All tests pass | No generalization to other apps, 4K, sleep, or HEVC hardware encode | Test video sample playback and screen-recording workflow separately |

## Key caution from reference project

[JulioNectar's encode-experimental README](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/macos/vadriver/encode-experimental/README.md) documents VPHAL kernel-table/sub-renderer patching, 1080p pixel-transfer crashes, and VDENC hangs on real P frames. Their **experimental** VA binary byte offsets target a different patched binary; they are **not** an installable or verified fix for the signed WhateverXe Graphics 0.4.0 Tahoe bundle. No automatic binary mutation in D1.1.1.

## CI, constraints and acceptance

The separate GitHub Action `video-encode-d11.yml` compiles these macOS Objective-C programs (but never runs the hardware probes), validates shell syntax and runs portable C conversion unit tests. This CI is not hardware validation. A system-level fix requires arbitrary applications using BGRA encode to stop crashing, HEVC HW to appear in encoder list, and successful HEVC compressed frames **with decode verification**. Confirm unchanged display/sleep stability and no GPU hangs before distributing an actual VA patch.

### Additional observation about apparent HEVC capability

`IOGVAHEVCEncodeCapabilities` is an accelerator property, not a VideoToolbox encoder implementation. The absence of an HW entry from `VTCopyVideoEncoderList()` despite the property is a **measured mismatch**; its cause is unproven (potentially discovery/registration or actual missing provider support). Apple documents `VTRegisterProfessionalVideoWorkflowVideoEncoders` as loading encoders from the client's `/Library/Video/Professional Video Workflow Plug-Ins/` directory. This is a bounded negative/control test, **not** an established route for registering the Tiger Lake GPU VA codec.

### Capturing a crashing native transfer with LLDB

If a pixel test exits with signal 11, keep the generated log and run **only if you explicitly want to reproduce**:

```bash
cd macos/video-encode
xcrun lldb ./output/wex_vphal_transfer_probe
# In LLDB (choose the same dimensions as the crashing probe):
run 64 64 bgra-nv12
thread backtrace all
image list -o -f
quit
```

The backtrace plus loaded VA image address and SHA256 from `inspect_va_driver.command` are necessary before considering a byte-level VPHAL patch. Do **not** use unverified binary offsets from a different distribution.

## 2026-11-05 Yoga D1.1.1 real-device results and D1.1.2 follow-up

- `inventory` in the previous Bash script hit `args[@]: unbound variable` on macOS's old Bash 3.2 when `set -u` and the array was empty. **This was a script bug**, unrelated to the GPU; D1.1.2 uses `"$@"` instead.
- HEVC workflow registration changes **nothing**: 0 HEVC HW entries before and after. HEVC HW-required property query returns **-12908**, and unrestricted property query selects `com.apple.videotoolbox.videoencoder.hevc.vcp`. The accelerator separately publishes `IOGVAHEVCEncodeCapabilities`, so adding the same property to EFI is not an established remedy.
- **Driver fingerprint**: `/Library/GPUBundles/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver` SHA256 `a972cdb7ddd56bcf38c3ab71e874b73efc34bc683d30e49f0a1a1919625a726d`, UUID `00204000-0263-4092-B483-CC2544D26350`. This matches the WhateverXe Graphics v0.4.0 **Tahoe** payload hash in upstream `docs/payload-provenance.json`. The bundle passes `codesign --verify` and contains `@loader_path/TGLVA`. No evidence that a corrupted or mismatched Tahoe payload caused this.
- **Crucial new isolation**: independent `VTPixelTransferSessionTransferImage` of **64×64 BGRA to NV12** crashed immediately after `STAGE=PIXEL_TRANSFER_BEGIN`, exit **139/SIGSEGV**, *without any VTCompressionSession or H.264 encoder*. This establishes a native pixel-transfer failure outside the encoder, but the precise instruction/NULL object requires LLDB. **Do not repeat the same crashing transfer without a diagnostic purpose**; no need to try 1080p.
- Added `macos/video-encode/collect_vphal_backtrace.command` with a required explicit crash opt-in. It runs only the already-broken 64×64 case under LLDB and captures `thread backtrace all`, `register read`, `disassemble`, and `image list -o -f` in one log. This intentionally reproduces a driver crash; do not run in a production session or without saving work. The analysis can distinguish the null-sub-renderer context from another VPHAL problem and identify a binary-relative disassembly offset.
- **No system-wide patch yet**. A safe driver-level binary fix must match this exact signed binary, avoid corrupting signatures, be delivered as an opt-in offline artifact with verified rollback, and be tested separately from the stable D EFI. HEVC hardware encode additionally needs a *real* provider; a fabricated list/capability property is not a fix.

Example, only if you are willing to reproduce the crash **once** to capture its machine-specific call site:

```bash
cd macos/video-encode
bash collect_vphal_backtrace.command --i-accept-native-crash
```

## 2026-11-05 LLDB crash confirmed — D1.1.3 output tightening

LLDB successfully captured the **64×64 BGRA→NV12** transfer crash. Its stack exactly matches the previously observed direct-BGRA H.264 encode crash through `AppleGVA::AVFPixelProcess_PrepareToTransferImages`:

```text
Process stopped: EXC_BAD_ACCESS (code=1, address=0x8)
rdi = 0x0
rip = 0x1015fb6f3 (run-specific ASLR address)
AppleIntelTGLGraphicsVADriver: movq %rdx, 0x8(%rdi)
AppleIntelTGLGraphicsVADriver loaded base = 0x1014c8000
Binary-relative instruction offset = 0x1336f3
LLDB's printed unnamed-symbol offset = 195379 (identical in both observed crashes)
```

This proves the immediate fault is a **NULL pointer write to address 0x8 in the VA driver** during native pixel transfer, independent of an encoder session. The allocation or initialization mistake that made the pointer NULL is **not proven**. These addresses are tied to the exact installed Tahoe VADriver SHA256 `a972cdb7ddd56bcf38c3ab71e874b73efc34bc683d30e49f0a1a1919625a726d`; do not transplant a patch from another binary.

The previous collection script printed the entire loaded-image table (377 entries) and appeared to hang at the last line. D1.1.3 filters the image lookup to the VA driver and TGLVA and explicitly kills the **crashed debuggee** after capturing diagnostic commands, allowing LLDB to exit. **The existing trace is sufficient; do not repeat the known-crashing test merely to try the shorter script.**

## D1.1.4 follow-up

The exact NULL slot is confirmed: `0x1336ec movq 0x910(%rcx),%rdi` -> `0x1336f3 movq %rdx,0x8(%rdi)`, with LLDB `rdi=0`. Reference [JulioNectar patch_vpnull2.py](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/macos/vadriver/encode-experimental/patch_vpnull2.py) covers this exact file offset and handles +0x920 too. See [D1.1.4 research report](D1_1_4_VPHAL_RESEARCH.md), including strict read-only preflight, cave checks, and HEVC binary strings; do not replace the installed signed VA driver.
