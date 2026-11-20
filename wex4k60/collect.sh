#!/bin/bash
# Yoga A7A0 chassis-HDMI 4K60 research: read-only capture.
# Does NOT switch displays, modify NVRAM/EFI/kexts, write I2C/MMIO, or call sudo.
set -uo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: bash wex4k60/collect.sh hdmi30|hdmi60black|hdmi_recovered|dock30" >&2
  exit 2
fi
case "$1" in
  hdmi30|hdmi60black|hdmi_recovered|dock30) STAGE="$1" ;;
  *) echo "invalid stage: $1" >&2; exit 2 ;;
esac

STAMP="$(date +%Y%m%d_%H%M%S)"
DIR="$HOME/Desktop/Yoga_HDMI4K60_"$STAGE"_"$STAMP
mkdir -p "$DIR" || exit 1
{
  echo "stage=$STAGE"
  echo "time=$(date)"
  echo "source=current installed WhateverXe (no new Kext installed by this script)"
  echo "NOTE: HDMI observations are not a direct SCDC/PLL hardware capture."
  echo "NOTE: if internal display blacked out too, use remote/recovery EFI, no repeated mode switches."
} > "$DIR/ABOUT.txt"

{ sw_vers; uname -a; nvram boot-args; } > "$DIR/system_and_bootargs.txt" 2>&1 || true
system_profiler SPDisplaysDataType > "$DIR/displays.txt" 2>&1 || true
system_profiler SPDisplaysDataType -json > "$DIR/displays.json" 2>&1 || true
kmutil showloaded > "$DIR/kexts.txt" 2>&1 || true
ioreg -p IOService -l -w0 > "$DIR/ioreg.txt" 2>&1 || true
ioreg -r -l -w0 -c AppleDisplay > "$DIR/apple_displays.txt" 2>&1 || true

# Short bounded retrospective of HDMI/Framebuffer/WindowServer errors.
# Reading system logs performs no changes to the display state.
if command -v log >/dev/null 2>&1; then
  log show --last 3m --style compact --info --predicate \
    '(eventMessage CONTAINS[c] "HDMI" OR eventMessage CONTAINS[c] "TMDS" OR eventMessage CONTAINS[c] "SCDC" OR eventMessage CONTAINS[c] "Display Pipe" OR eventMessage CONTAINS[c] "framebuffer")' \
    2>/dev/null | tail -n 800 > "$DIR/recent_display_log.txt" || true
fi

grep -Ei 'WEXYogaHDMI600|WEXYogaHDMIEDIDAB|WEXYogaHDMIColor|WEXYogaSST|N97FBClock|N97FBDBUF|N97FBPipe|N97FBHDMI|N97FBGMBus|N97FBWatermark|IOFBTimingRange|IOFBCurrentPixelClock|IODisplayEDID|TRANS_DDI_FUNC_CTL|PIPE_MISC' \
  "$DIR/ioreg.txt" > "$DIR/hdmi_diagnostics.txt" || true

# Manually observed physical output status. Do NOT infer panel visibility
# from system_profiler: macOS may report 60Hz while the panel is black.
cat > "$DIR/USER_OBSERVATION.txt" <<'EOF'
Monitor: AOC U27P10 or other (please write):
Cable and port: chassis HDMI / HP G4 DP (please write):
macOS selected resolution/refresh (please write):
Monitor OSD input timing (please write, if visible):
Actual picture: normal / black / colored noise / unknown
Internal eDP state: normal / black / unknown
Other external monitor state: normal / black / unknown
EOF

printf 'Source label: %s\n' "$STAGE" > "$DIR/CAPTURE_MANIFEST.txt"
for file in ioreg.txt displays.txt displays.json apple_displays.txt system_and_bootargs.txt; do
  if [ -f "$DIR/$file" ]; then
    wc -c "$DIR/$file" >> "$DIR/CAPTURE_MANIFEST.txt"
  fi
done
ditto -c -k --keepParent "$DIR" "$DIR.zip"
printf '\nSaved: %s\n' "$DIR.zip"
printf '%s\n' 'Before uploading, review IODisplayEDID, system serial numbers, hardware IDs and boot-args for sensitive data.'
printf '%s\n' 'This script NEVER selects 4K60 or changes display settings. Collect only if doing so is safe.'
