#!/bin/bash
set -euo pipefail
OUT="$HOME/Desktop/Yoga_HDMI_Color_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"

sw_vers > "$OUT/sw_vers.txt"
nvram boot-args > "$OUT/boot_args.txt" 2>&1 || true
kmutil showloaded > "$OUT/kexts_full.txt" 2>&1 || true
grep -Ei 'WhateverXe|Lilu' "$OUT/kexts_full.txt" > "$OUT/kexts.txt" || true
system_profiler SPDisplaysDataType > "$OUT/displays.txt" 2>&1 || true
ioreg -p IOService -l -w0 > "$OUT/ioreg.txt" 2>&1 || true

{
  echo "===== boot arguments ====="
  cat "$OUT/boot_args.txt"
  echo "===== actual loaded kexts ====="
  cat "$OUT/kexts.txt"
  echo "===== key IORegistry evidence ====="
  grep -Ei 'WEXYogaHDMIColorLive|WEXYogaHDMIHPDTrace|N97FBPortDDCLast|N97FBPortProbeLast|WEXYogaEDP120WMEnabled|N97FBEDID' "$OUT/ioreg.txt" | cut -c 1-600 || true
} > "$OUT/audit_summary.txt"

if grep -q '"WEXYogaHDMIColorLive"' "$OUT/ioreg.txt"; then
  if python3 "$(dirname "$0")/decode_color.py" "$OUT/ioreg.txt" \
        --output "$OUT/color_decoded.json" \
        > "$OUT/decode_stdout.txt" 2> "$OUT/decode_stderr.txt"; then
    echo "color_live: decoded" > "$OUT/color_status.txt"
  else
    echo "color_live: present but decoder failed" > "$OUT/color_status.txt"
  fi
else
  echo "color_live: absent (raw logs retained; not a Python failure)" > "$OUT/color_status.txt"
fi

(cd "$(dirname "$OUT")" && zip -qr "$(basename "$OUT").zip" "$(basename "$OUT")")
echo "Complete: $OUT.zip"
cat "$OUT/color_status.txt"
