#!/bin/bash
# Yoga A7A0 HDMI 4K60->4K30 display absent; passive-only capture.
# Does not switch modes, disconnect or re-probe, patch Kexts, or write I2C/MMIO.
set -uo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Only supported on macOS." >&2; exit 2
fi
STAMP="$(date +%Y%m%d_%H%M%S)"
DIR="$HOME/Desktop/Yoga_HDMI2_after_4k60_fallback_missing_$STAMP"
mkdir -p "$DIR" || exit 1
cat > "$DIR/ABOUT.txt" <<'TXT'
Passive recovery-state capture after HDMI 4K60 black -> 4K30 mode
-> AOC display absent, while other two screens still function.
No hardware state changes. The IORegistry may preserve stale properties
after the AOC disappears: an old property value is not live HPD proof.
Review boot args, EDID, log details and device identifiers before sharing.
TXT
date '+time=%Y-%m-%d %H:%M:%S %z' > "$DIR/time.txt"
{ sw_vers; uname -a; } > "$DIR/system.txt" 2>&1 || true
{ nvram boot-args; } > "$DIR/bootargs.txt" 2>&1 || true
{ kmutil showloaded; } > "$DIR/loaded_kexts.txt" 2>&1 || true
{ system_profiler SPDisplaysDataType; } > "$DIR/displays.txt" 2>&1 || true
{ system_profiler SPDisplaysDataType -json; } > "$DIR/displays.json" 2>&1 || true
{ ioreg -p IOService -l -w0; } > "$DIR/ioreg.txt" 2>&1 || true
{ ioreg -p IOService -r -l -w0 -c AppleDisplay; } > "$DIR/AppleDisplay.txt" 2>&1 || true
{ ioreg -p IOService -r -l -w0 -c IODisplayConnect; } > "$DIR/IODisplayConnect.txt" 2>&1 || true
{ ioreg -p IOService -r -l -w0 -c IOFramebuffer; } > "$DIR/IOFramebuffer.txt" 2>&1 || true
grep -Ei 'WEXYoga|N97FB|IOFBCurrentPixelClock|IOFBTimingRange|IOFBOnline|IODisplayEDID|IODisplayConnect|AppleDisplay|IOFramebuffer|IOPowerManagement|IOServiceBusyState|HPD|Hotplug|Transcoder|Pipe|DisplayPort' "$DIR/ioreg.txt" > "$DIR/display_registry_focus.txt" || true
if command -v log >/dev/null 2>&1; then
  log show --last 20m --style compact --info --predicate     '(eventMessage CONTAINS[c] "hotplug" OR eventMessage CONTAINS[c] "HPD" OR eventMessage CONTAINS[c] "HDMI" OR eventMessage CONTAINS[c] "SCDC" OR eventMessage CONTAINS[c] "EDID" OR eventMessage CONTAINS[c] "framebuffer" OR eventMessage CONTAINS[c] "display pipe" OR process == "WindowServer")'     2>/dev/null | tail -n 2000 > "$DIR/recent_display_log.txt" || true
fi
cat > "$DIR/USER_OBSERVATION.txt" <<'TXT'
HDMI cable physically still attached (yes/no):
AOC OSD status (No Signal / black with signal / other):
AOC absent from macOS Displays (yes/no):
Internal panel still works (yes/no):
Other external display still works (yes/no):
Restarted after black-screen event (yes/no):
TXT
find "$DIR" -maxdepth 1 -type f -exec wc -c {} + > "$DIR/CAPTURE_MANIFEST.txt" 2>/dev/null || true
ditto -c -k --keepParent "$DIR" "$DIR.zip" || exit 1
echo "Saved: $DIR.zip"
echo "No modeset, HPD trigger, I2C write, Kext/EFI modification, or sudo was used."
echo "Please review serials, EDID, bootargs and system logs before upload."
