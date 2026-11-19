# A7A0 HDMI-B U27P10: read-only color format register snapshot

**EXPERIMENTAL TEST KEXT, not a color fix. No physical-machine validation yet.**
Only build from a separate test EFI; preserve your existing bootable WM_ONLY/HPD configuration.

## What this adds

Starting from the **same pinned WhateverXe 0.8.3 / Graphics 0.4.4** build as
the existing **first-HDMI-hotplug** experimental branch, reuses its exact
WM_ONLY/V2 eDP120 source and HPD instrumentation. The one-shot HPD event
rewrite is still OFF by default and MUST stay OFF in this test.

Adds one opt-in **-wex-yoga-hdmi-colortrace**. After a successful native DDC
read on the physical Lenovo A7A0, selected native HDMI DDI B, the driver
publishes \`WEXYogaHDMIColorLive\` as a lazy OSData serializer.

When \`ioreg -p IOService -l -w0\` requests the property, the callback:

1. Checks the existing Display13 owner/map and locks its existing display
   state mutex; does not install another display hook.
2. Reads display power-well status 0x45404 first. Reads registers only for
   pipes whose native power well is on.
3. Checks each active TRANS_DDI_FUNC_CTL for native HDMI DDI B
   (enable bit, physical port selector 2, TMDS mode 0 or 1).
4. Only on a proven HDMI B pipe, reads VIDEO_DIP_CTL, plus GCP if enabled
   and AVI data if AVI enabled.
5. Rechecks display power status; marks the snapshot invalid if it changed.
6. Unlocks the mutex and serializes a 248-byte record.

Never writes a hardware register; never edits EDID/CSC/gamma, HPD, HDR,
display timings, link modes, source pixel format, or macOS display settings.
In contrast to a purely passive write observer, this is a live **readback**,
but it is still experimental: on-demand MMIO reads might be incompatible with
unverified platform/power states. Only run the query after display is stable.
Do not spam repeated queries or run the dump during hotplug/unplug/sleep.

## Schema: \`WEXYogaHDMIColorLive\`

62 little-endian uint32 words:

- Header [0..7]: version=1, status (0 not ready, 1 valid, 2 power changed),
  PW_CTL before, PW_CTL after, EISA vendor, product ID, native HDMI-B pipe
  mask, powered pipe mask.
- Three pipe records, 17 words each:
  pipe index, powered, TRANS_DDI_FUNC_CTL, PIPE_MISC, PLANE_CTL, PIPECONF,
  TRANS_DDI_FUNC_CTL2, VIDEO_DIP_CTL, GCP, 7 AVI InfoFrame DWORDs,
  TRANS_MSA_MISC.
- Unread registers are UINT32_MAX, **never** hardware zero.
- A **valid** record is one with status 1, the expected HDMI-B pipe identified,
  stable power, and the requested register values populated.
- AVI/GCP payload only indicates register contents; it is **not** packet-level
  proof of what a signal analyzer sees on the cable.
- The macOS "Framebuffer Depth" line represents the framebuffer format, not
  this physical link state.

## Build and installation

The GitHub Actions workflow \`.github/workflows/yoga-hdmi-colortrace.yml\`
pins WhateverXe 0.8.3 f26a368, its Graphics 0.4.4 donor, MacKernelSDK and
Lilu. It runs the HPD unit assertions, upstream tests, RELEASE compile and
compatibility checking. Passing CI is **not** proof that reading registers
is safe or that this fixes corruption.

Do not overwrite daily EFI. Duplicate independently bootable EFI to a test
EFI and replace **only** \`EFI/OC/Kexts/WhateverXe.kext\`. Keep Graphics 0.4.4
unchanged and keep a recovery path. Do not enable \`-wex-yoga-hdmi-first-hpd\`,
\`-wex-yoga-rgb8\` or \`-wex-yoga-hdmi600\` here.

Append \`-wex-yoga-hdmi-colortrace\` to the existing:
\`-wex-yoga-edp120-admit -wex-yoga-edp120-wm -wex-yoga-hdmi-hpdtrace\`.

Connect the U27P10 to **native HDMI before boot** (avoids the known
late-first-insertion issue). Boot and verify Metal/inner display,
the U27P10 is attached, and the old RGB8_STRICT system override is absent.

After login **with the picture already stable (even if falsely colored)**,
run \`bash collect_color.sh\` from the extracted CI artifact. Upload
the generated \`~/Desktop/Yoga_HDMI_Color_*.zip\`.

If the test crashes or cannot boot, return to the untouched original EFI.
No reset of NVRAM, disabling graphics acceleration or modifying system Kexts
is necessary.

## Interpretation

- TRANS_DDI_FUNC_CTL bits22:20 report transcoder port depth.
- Display13 PIPE_MISC bits7:5 report port output bpc and bit11 is YUV.
- VIDEO_DIP_CTL AVI and GCP enable bits must be checked before interpreting
  any packet words; the decoder prints raw fields for manual inspection.
- If color corruption persists while these values agree on RGB 8bpc and
  AVI/GCP, investigate CSC/transmitter/pixel packing next instead of
  forcing EDID limitations.

Only the new branch is changed. The old \`main\`, proven WM_ONLY and
first-hotplug branches and the installed EFI are not modified.
