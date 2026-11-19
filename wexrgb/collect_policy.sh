#!/bin/bash
set -euo pipefail
OUT="$HOME/Desktop/Yoga_HDMI_Mode_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
sw_vers > "$OUT/system.txt" 2>&1 || true
nvram boot-args > "$OUT/boot_args.txt" 2>&1 || true
kmutil showloaded > "$OUT/kexts.txt" 2>&1 || true
system_profiler SPDisplaysDataType > "$OUT/displays.txt" 2>&1 || true
ioreg -p IOService -l -w0 > "$OUT/ioreg.txt" 2>&1 || true

if python3 "$(dirname "$0")/decode_color.py" "$OUT/ioreg.txt" \
    --output "$OUT/color_decoded.json" > "$OUT/color_stdout.txt" 2> "$OUT/color_error.txt"; then
    echo "color_registers: decoded" > "$OUT/color_status.txt"
else
    echo "color_registers: absent or unavailable; raw ioreg preserved" > "$OUT/color_status.txt"
fi
if python3 "$(dirname "$0")/decode_modes.py" "$OUT/ioreg.txt" \
    --output "$OUT/mode_decoded.json" > "$OUT/mode_stdout.txt" 2> "$OUT/mode_error.txt"; then
    echo "native_modes: decoded" > "$OUT/mode_status.txt"
else
    echo "native_modes: absent or unavailable; raw ioreg preserved" > "$OUT/mode_status.txt"
fi

grep -E 'WEXYogaHDMIColorModeHookReady|WEXYogaHDMIColorLive|WEXYogaHDMIColorModeLive|WEXYogaHDMIColorMode' "$OUT/ioreg.txt" | cut -c 1-700 \
    > "$OUT/color_registry_summary.txt" || true
(cd "$(dirname "$OUT")" && zip -qr "$(basename "$OUT").zip" "$(basename "$OUT")")
echo "Captured: $OUT.zip"
cat "$OUT/color_status.txt" "$OUT/mode_status.txt"
