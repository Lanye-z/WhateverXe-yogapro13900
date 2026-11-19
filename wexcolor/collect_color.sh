#!/bin/bash
set -euo pipefail
OUT="$HOME/Desktop/Yoga_HDMI_Color_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
sw_vers > "$OUT/sw_vers.txt"
nvram boot-args > "$OUT/boot_args.txt" 2>&1 || true
kmutil showloaded | grep -Ei 'WhateverXe|Lilu' > "$OUT/kexts.txt" 2>&1 || true
system_profiler SPDisplaysDataType > "$OUT/displays.txt" 2>&1
ioreg -p IOService -l -w0 > "$OUT/ioreg.txt" 2>&1
python3 "$(dirname "$0")/decode_color.py" "$OUT/ioreg.txt" --output "$OUT/color_decoded.json"
(cd "$(dirname "$OUT")" && zip -qr "$(basename "$OUT").zip" "$(basename "$OUT")")
echo "Complete: $OUT.zip"
