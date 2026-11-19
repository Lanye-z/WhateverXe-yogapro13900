#!/bin/bash
# Yoga 82Y7 / WhateverXe 0.8.3 external display: non-mutating A/B capture.
# Usage: bash wexexternal/collect.sh before
#        [physically insert native HDMI B, then:]
#        bash wexexternal/collect.sh after
# Or use labels hdmi_before, hdmi_after, typec_before, typec_after.
set -u
label="${1:-snapshot}"
case "$label" in
  *[!A-Za-z0-9_-]*|'') echo "Use a safe label: A-Z a-z 0-9 _ -" >&2; exit 2 ;;
esac
out="$HOME/Desktop/Yoga_External_${label}_$(date +%Y%m%d_%H%M%S).txt"
{
  echo "===== STAGE / TIME / UPTIME ====="
  echo "$label"; date; uptime
  echo "===== BOOT FLAGS ====="
  nvram boot-args 2>&1
  echo "===== DISPLAY / POWER POLICY ====="
  pmset -g custom 2>&1
  pmset -g log 2>&1 | grep -E 'Sleep|Wake|DarkWake|Display' | tail -45
  echo "===== LOADED KEXTS ====="
  kmutil showloaded 2>&1 | grep -Ei 'WhateverXe|Lilu|NootedGreen|AppleIntel'
  echo "===== IOREG DISPLAY13 / IRQ / PORT / TC ====="
  ioreg -lw0 -p IOService 2>&1 | grep -E 'WEXYogaHDMIHPDTrace|WEXYogaMulti|WEXYogaEDP120|N97FBIRQ|N97FBPortProbe|N97FBConnectorPolicy|N97NativeBootConnector|N97FBTopologyHooksReady|N97FBOutputHooksReady|WEXDisplay13TC|N97FBTC|N97FBPower|N97FBPipe|N97FBClock|N97FBDBUF|N97FBAUX|N97FBSST|WEXDisplay13'
  echo "===== DISPLAY DEVICES ====="
  system_profiler SPDisplaysDataType 2>&1
  echo "===== USB / TB (TYPE-C DIAGNOSTICS ONLY) ====="
  system_profiler SPUSBDataType SPThunderboltDataType 2>&1
} > "$out" 2>&1
echo "$out"
