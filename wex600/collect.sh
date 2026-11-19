#!/bin/bash
# Passive HDMI600/Display13 collection; no writes, mode switches or sudo.
set -uo pipefail
if [ "$#" -eq 0 ]; then LABEL=baseline; else LABEL="$1"; fi
case "$LABEL" in baseline|admit|black60|recovered|fallback) ;; *) echo "usage: bash collect.sh baseline|admit|black60|recovered|fallback" >&2; exit 2;; esac
SELF="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
DIR="$HOME/Desktop/Yoga_HDMI600_$LABEL_$STAMP"
mkdir -p "$DIR"
printf 'Stage: %s\nCaptured: %s\n' "$LABEL" "$(date)" > "$DIR/ABOUT.txt"
{
  sw_vers
  uname -a
  nvram boot-args
} > "$DIR/system_and_bootargs.txt" 2>&1 || true
system_profiler SPDisplaysDataType > "$DIR/displays.txt" 2>&1 || true
system_profiler SPDisplaysDataType -json > "$DIR/displays.json" 2>&1 || true
kmutil showloaded > "$DIR/kexts.txt" 2>&1 || true
ioreg -p IOService -l -w0 > "$DIR/ioreg.txt" 2>&1 || true
ioreg -r -l -w0 -c AppleDisplay > "$DIR/apple_displays.txt" 2>&1 || true
grep -Ei 'WEXYogaHDMI600|WEXYogaHDMIEDIDAB|WEXYogaEDP120|WEXYogaHDMIColor|N97FBClock|N97FBDBUF|N97FBPipe|N97FBWatermark|N97FBHDMI|IOFBTimingRange|IOFBCurrentPixelClock|IODisplayEDID' "$DIR/ioreg.txt" > "$DIR/hdmi_diagnostics.txt" || true
python3 "$SELF/diagnose.py" "$DIR" > "$DIR/summary.txt" 2>&1 || true
ditto -c -k --keepParent "$DIR" "$DIR.zip"
printf 'Saved: %s\n' "$DIR.zip"
printf 'Compare only after testing the same physical HDMI monitor and cable.\n'
