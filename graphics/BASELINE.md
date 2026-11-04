# D1.1 Graphics integration — upstream signed release only

Pinned release: [WhateverXe Graphics 0.4.0](https://github.com/b00t0x/WhateverXe-Graphics/releases/tag/v0.4.0). Signed Tahoe VA binary SHA256 observed on A7A0: `a972cdb7ddd56bcf38c3ab71e874b73efc34bc683d30e49f0a1a1919625a726d`.

- Native `VTPixelTransferSession` 64×64 BGRA→NV12 crashes in the **userspace** `AppleIntelTGLGraphicsVADriver` at VA image-relative `0x1336f3`: `movq %rdx,0x8(%rdi)` with `rdi=0`. This is not repaired by the Kext's display-source changes.
- HEVC HW encoding is not registered in VideoToolbox (`-12908`); the `hevc.vcp` software encoder works. IORegistry HEVC capabilities are NOT evidence of functioning HEVC HW encoder.
- The attempted offline guard refused to proceed because the `0xAC0` code cave is occupied. The binary and its signatures must not be force-modified.
- Official Graphics repository holds **signed binaries and installer packaging**, not the complete public Apple VA driver source, patch/re-sign pipeline or private Mod signing keys. Our connected account cannot push upstream Graphics changes.

**Integration policy:** D1.1 pins the upstream Graphics release, builds only its own Kext source, and never creates detached binary patches or overwrites Graphics. A real VA fix must be delivered as an upstream-compatible, properly signed Graphics provider rebuild; this project has not produced one. Keep the working D EFI/Graphics as rollback baseline.
