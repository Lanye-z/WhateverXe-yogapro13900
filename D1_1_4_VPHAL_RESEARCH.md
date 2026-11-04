# D1.1.4 — VPHAL null-subrenderer binary analysis / HEVC static hints

**Status: OFFLINE RESEARCH ONLY. No installed driver has been patched.** The stable D EFI, NootedGreen recovery EFI, Graphics 0.4.0 installation and code-signing chain must stay intact. None of these tools requires sudo, SIP changes, or boot flags.

## 1. Two independent crashes meet at the same VA instruction

On the Yoga A7A0 / Tahoe 25G241, both direct-BGRA H.264 compression and stand-alone 64×64 `VTPixelTransferSessionTransferImage(BGRA,NV12)` crashed at the exact same unnamed symbol offset, in `AppleIntelTGLGraphicsVADriver`. The latter does not use an encoder session, establishing a separate pixel-transfer fault. LLDB recorded:

```text
EXC_BAD_ACCESS code=1 address=0x8
rdi=0x0000000000000000
rip=0x1015fb6f3  [ASLR-specific]
VA driver loaded base=0x1014c8000
binary-relative VM instruction offset=0x1336f3
movq %rdx,0x8(%rdi)
```

We extracted the **original Apple Tiger Lake 16.0.32** VA executable from the previously supplied `IrisXe_Tahoe_Latest_Drivers.zip` (SHA256 `d265f2038135c2c5c3649b621d9aea48cf1cb74a1fb36069bb1b3562b3750129`) and disassembled the actual Mach-O `__TEXT,__text` around `0x133690`:

```asm
0x1336d6  movq 0x920(%rdx), %rdi
0x1336dd  movq %rcx, 0x8(%rdi)  ; unguarded first store
...
0x1336ec  movq 0x910(%rcx), %rdi
0x1336f3  movq %rdx, 0x8(%rdi)  ; confirmed NULL rdi=0
```

The immediate bug at the second store is therefore **a NULL value read from renderer +0x910**. This does not prove why that sub-renderer was absent or that skipping the write would produce valid video output.

## 2. Exact existing reference found

JulioNectar's [`patch_vpnull2.py`](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/macos/vadriver/encode-experimental/patch_vpnull2.py) independently documents the same **`0x1336f3`** fault. Its code guards both `renderer+0x920` and `renderer+0x910` fields in function `0x133690` by redirecting a 37-byte instruction sequence through a short code cave. The **37 original bytes match exactly** in our locally extracted unmodified Tiger Lake 16.0.32 binary. Its older [`patch_vpnull.py`](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/macos/vadriver/encode-experimental/patch_vpnull.py) guards related sub-renderer `Initialize` calls.

**Critical caveat:** the reference project's [encode-experimental/README](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/macos/vadriver/encode-experimental/README.md) documents further VPHAL transfers failing in another function (`0x126520`) *after* NULL-guards. Thus a patch which avoids our current crash can merely move failure downstream. Its author deliberately excludes these changes from the normal installer.

## 3. Our implementation: strict audit + offline UNSIGNED patch candidate

`macos/video-encode/vphal_guard_offline.py` is a standalone Python stdlib-only implementation of the precisely scoped double-guard concept. It checks all of these **before doing anything**:

- Installed **WhateverXe Graphics v0.4.0 Tahoe** VA executable SHA256 is exactly `a972cdb7ddd56bcf38c3ab71e874b73efc34bc683d30e49f0a1a1919625a726d` and size **8,454,464** bytes. The stock original is accepted *only* for a hidden test flag, not as a user-target build.
- Mach-O is x86_64 64-bit and its `__TEXT` load-command has VM/file offset mapping equal to zero.
- The exact **37 original bytes** between `0x1336d2` and `0x1336f7` match expectations.
- The candidate code-cave region at file offset `0xac0` is **all zero**; a collision rejects the candidate.
- If building an optional candidate, only the 37-byte hook and the code-cave bytes are changed; no installed file, EFI, executable process, or signed bundle is modified.

It may return **`REFUSED`** for the currently installed WEX image. That is a useful, expected safety outcome: it means the code cave or instruction signature differs and should be investigated rather than bypassed.

### Safest user command (read-only)

On the Mac, with the latest **D1.1** checkout:

```bash
cd macos/video-encode
bash audit_vphal_installed.command
python3 hevc_va_static_audit.py
```

These commands **do not run pixel transfers or invoke hardware encoding**. Save and share their short output. They do not create a fixed driver.

### Advanced, NOT for installation

There is an opt-in `--emit-unsigned-candidate OUTPUT --acknowledge-uninstallable` mode for studying an offline *copy* after the strict checks succeed. **Do not move the generated binary to `/Library/GPUBundles`**. Its original OCLP Mod certificate signature no longer covers the changed bytes. Simply `codesign -s -` does not recreate the original trusted chain or prove the code is safe; an unsupported binary replacement could break hardware decode, render pipeline stability, or boot/login.

The Python unit tests verify jump destinations, both NULL guards, unknown-SHA rejection and unchanged non-patch regions. On the original stock VA file, the audit and patch-candidate build pass. **The installed signed WEX 0.4.0 file has NOT been made available to this analysis runtime**, so its byte-for-byte acceptance remains an open test. **No macOS live test of this patch has been performed.**

## 4. HEVC hardware encoding: not just an IORegistry property

The target already publishes `IOGVAHEVCEncodeCapabilities` but 
`VTCopyVideoEncoderList` reports **only** `com.apple.videotoolbox.videoencoder.hevc.vcp` (software). With hardware required, HEVC session creation and even supported-property discovery return `-12908`; professional workflow plug-in registration does not change that.

The original **Tiger Lake 16.0.32** VA binary has the following embedded path/name *hints* (we counted them directly):

| Embedded string pattern | Occurrences |
|---|---:|
| `/HEVC/Decode/` | 1 |
| `/HEVC/Encode/` | 0 |
| `GVAHEVCEncodingImpl` | 0 |
| `GVAAVCEncodingImpl` | 1 |
| `AVCVDENC` | 3 |
| `HEVCVDENC` | 0 |

This **suggests** HEVC encode may not be implemented/exposed in that specific older VA binary even though H.264 encode and HEVC decode are; strings are **not evidence of absence** of all executable code. `hevc_va_static_audit.py` scans the *actual installed WEX binary*, read-only, to compare these hints. If its results match stock, future work may require implementing or sourcing a real HEVC encode provider rather than altering `IOGVAHEVCEncodeCapabilities` or faking a VideoToolbox encoder-list entry.

Official WhateverXe upstream regression coverage lists H.264 **encode/decode** and HEVC **decode**, not HEVC encode: https://github.com/b00t0x/WhateverXe/blob/main/README.md

## 5. Next acceptance gate

- Read-only installed VA **audit succeeds** (exact hash, code region, cave) before considering any candidate patch.
- Any eventual signed, independently **rollback-able** VA candidate must first be validated on isolated user consented testing environment. A single null-write guard is not sufficient proof of pixel correctness or stability.
- If native BGRA→NV12 progresses past the known crash, independently verify output content, no GPU hangs, 180-frame H.264 HW encode, H.264/HEVC HW decode, normal desktop operation and sleep/wake.
- HEVC HW remains a separate problem until VideoToolbox lists and actually successfully runs a **hardware** HEVC encoder. Software `hevc.vcp` is not hardware.

**Summary:** D1.1.4 makes a concrete, testable finding and an offline candidate, not a proven system-level repair. Do **not** replace the stable D or signed Graphics installation on the strength of this analysis.
