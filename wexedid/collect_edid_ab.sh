#!/bin/bash
set -euo pipefail
OUT="$HOME/Desktop/Yoga_HDMI_EDID_AB_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
sw_vers > "$OUT/system.txt" 2>&1 || true
nvram boot-args > "$OUT/boot_args.txt" 2>&1 || true
kmutil showloaded > "$OUT/kexts.txt" 2>&1 || true
system_profiler SPDisplaysDataType > "$OUT/displays.txt" 2>&1 || true
ioreg -p IOService -l -w0 > "$OUT/ioreg.txt" 2>&1 || true
HERE="$(cd "$(dirname "$0")" && pwd)"
for ITEM in \
  "decode_edid_ab.py edid_decoded.json edid" \
  "decode_color.py color_decoded.json color" \
  "decode_modes.py mode_decoded.json mode"; do
  set -- $ITEM
  if [ -f "$HERE/$1" ] && python3 "$HERE/$1" "$OUT/ioreg.txt" --output "$OUT/$2" \
      > "$OUT/$3_stdout.txt" 2>"$OUT/$3_error.txt"; then
    echo "$3: decoded" >> "$OUT/decode_status.txt"
  else
    echo "$3: unavailable (raw logs kept)" >> "$OUT/decode_status.txt"
  fi
done
grep -Ei 'WEXYogaHDMIEDIDAB|WEXYogaHDMIColorModeHookReady|WEXYogaHDMIColorLive' "$OUT/ioreg.txt" |
    cut -c 1-500 > "$OUT/audit_summary.txt" || true
(cd "$(dirname "$OUT")" && zip -qr "$(basename "$OUT").zip" "$(basename "$OUT")")
echo "Captured: $OUT.zip"
cat "$OUT/decode_status.txt"
