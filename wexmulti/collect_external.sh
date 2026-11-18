#!/bin/zsh
# Read-only hotplug comparator. Does NOT edit display state or mount EFI.
set -u
STAMP=$(/bin/date +%Y%m%d_%H%M%S)
OUT="$HOME/Desktop/Yoga_MultiDisplay_$STAMP"
/bin/mkdir -p "$OUT"
/usr/sbin/system_profiler SPDisplaysDataType > "$OUT/displays.txt" 2>&1
/usr/sbin/ioreg -lw0 -p IOService > "$OUT/ioreg_full.txt" 2>&1
/usr/bin/grep -E 'WEXYogaMulti|N97FBPortProbe|N97FBConnectorPolicy|WEXDisplay13TC|XELPSharedProbe|N97FBIRQ|N97FBTopology|N97FBOutput|WEXYogaEDP120' "$OUT/ioreg_full.txt" > "$OUT/display13_marks.txt" || true
/usr/sbin/nvram boot-args > "$OUT/bootargs.txt" 2>&1 || true
/usr/bin/log show --last 15m --style compact \
 --predicate 'process == "WindowServer" OR (process == "kernel" AND (eventMessage CONTAINS[c] "hotplug" OR eventMessage CONTAINS[c] "AUX" OR eventMessage CONTAINS[c] "link training" OR eventMessage CONTAINS[c] "Display13"))' \
 > "$OUT/graphics_log_last15m.txt" 2>&1 || true
/bin/echo 'May contain device serial, local paths, monitor EDID and user names; review before sharing.' > "$OUT/README_PRIVACY.txt"
/usr/bin/ditto -c -k --keepParent "$OUT" "$OUT.zip"
if [[ -s "$OUT.zip" ]]; then
  /bin/echo "CREATED: $OUT.zip"
else
  /bin/echo "Zip not created; raw files remain at $OUT"
fi
