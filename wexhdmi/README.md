# Yoga Pro 14s IRH8 A7A0 — first HDMI after panel-only boot

**Status: EXPERIMENTAL one-shot *hypothesis*, not a verified HDMI hotplug repair.**

On the physical Yoga, HDMI DDI B works when attached **before boot** and subsequent removal/reinsertion works. When the Yoga boots with only eDP, first HDMI insertion does **not** attach. Existing WM_ONLY 0.8.3 telemetry shows both the PCH HDMI IRQ bits and DDI HPD detector enabled even in the failing boot; this rules out blindly enabling HPD masks again.

This code is **not** the E1.0 transplant (that multi-output implementation is already in official 0.8.3). It starts from the **same exact source patches as the successful WM_ONLY/V2** and does not add HDMI600, RGB8, USB-C, Thunderbolt/DP, DSC, GateRetry or eDP-keep.

## Diagnostic and limited candidate fix

The exact native Display13 `collect()` adapter translates a DDI B **long HPD** pulse into native hotplug bit **2**, and a **short HPD** into bit **3**. A short pulse after a panel-only boot might not cause the native stack to treat a previously absent monitor as a new sink. This is *unproven* until the actual IRQ is captured.

The optional flags are:
- `-wex-yoga-hdmi-hpdtrace`: **read-only**, publishes a live lazy `WEXYogaHDMIHPDTrace` OSData snapshot. Safe for first diagnostic run. No event rewriting.
- `-wex-yoga-hdmi-first-hpd`: **one-shot test workaround**. Only when this same A7A0 WM_ONLY device selects **HDMI DDI B**, the **very first native HDMI-B probe returned 0**, and a **short B HPD event actually reaches the Display13 IRQ handler with no B long pulse**, change that *one* forwarded native short B event into a long B event. No registers, EDID data, timing or external-link clocks are changed; native driver still tests and accepts/rejects the real sink. Only one attempt per boot. If no event arrives, the fix does **nothing**.

**Do not test the second flag until the first flag shows a B-short IRQ.** If the result is zero, the actual failure is earlier (physical HPD delivery/IRQ or power) or later (framebuffer admission), and this hypothesis must not be presented as a solution.

### IORegistry record schema (20 little-endian uint32)

`WEXYogaHDMIHPDTrace = [schema,firstB,lastB,probesB,irqCalls,deCalls,pchMasterHits,bLongHits,bShortHits,promotions,lastPCH,lastDDI,lastEvents,forwardedEvents,status,irqEnabled,irqFaulted,activePipes,admittedPipes,observations]`.

- `firstB=0`: initial HDMI B was disconnected. `firstB=2`: already connected.
- `bShortHits>0` and `bLongHits=0`: specifically tests the short-only pulse hypothesis.
- `pchMasterHits=0` after late cable insertion: no PCH IRQ observed.
- `bLongHits>0` but no screen: connection/FB path failure beyond pulse mapping.
- `promotions=1`: workaround forwarded once, *not* proof of physical success.

### Safe staged trial

Preserve your original successfully rebooting WM_ONLY EFI. **Never overwrite it.** Make an independently bootable clone and replace only `EFI/OC/Kexts/WhateverXe.kext` from the CI artifact; keep signed Graphics 0.4.4, all other Kexts and hardware configuration unchanged.

1. **First trial: read-only only.** Add `-wex-yoga-hdmi-hpdtrace` alongside the existing `-wex-yoga-edp120-admit -wex-yoga-edp120-wm`. Do NOT add `-wex-yoga-hdmi-first-hpd` yet.
2. Disconnect HDMI *before* cold boot, and do not connect the Thunderbolt dock. Boot with eDP only. Record the initial trace; then connect native HDMI at **1080p60**, without reboot. Record the second trace and `system_profiler SPDisplaysDataType`.
3. Only if `bShortHits>0, bLongHits=0`, test an independent clone with `-wex-yoga-hdmi-first-hpd` **instead of** the audit-only flag. Confirm `promotions=1` AND actual display listing. Without these both, do not call it fixed.
4. If the external monitor fails, goes black, system hangs or WindowServer stops responding, use untouched WM_ONLY recovery EFI.

**Important:** `WEXYogaHDMIHPDTrace` serializes the latest atomic counters on read. The callback performs no IORegistry writes in an interrupt and no live MMIO reads in its serializer. The fix does not poll, invent events or perform port reset. Expect no change if IRQ delivery is missing.

## Quick collection

After each stage run:

```bash
ioreg -lw0 -p IOService | grep -E 'WEXYogaHDMIHPDTrace|N97FBIRQEnableCheck|N97FBPortProbe(First2|Last)'
system_profiler SPDisplaysDataType
```

Record the first and second outputs separately. The byte array is a little-endian `uint32_t[20]`. The exact N97/HPD trace is sensitive to prior hotplug attempts in that same boot; compare counters as deltas.

CI runs the exact pinned WEX 0.8.3 + Graphics 0.4.4 V2 builder, pure C++ edge-case assertions, upstream regression tests and RELEASE compilation. **Compile success never proves the one-shot fix works on the machine.**
