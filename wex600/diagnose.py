#!/usr/bin/env python3
"""Read-only summary of Yoga HDMI600 A+B captures; no hardware access."""
import sys,re
from pathlib import Path

root=Path(sys.argv[1])
text=(root/"ioreg.txt").read_text(errors="replace")
display=(root/"displays.txt").read_text(errors="replace")
boot=(root/"system_and_bootargs.txt").read_text(errors="replace")

def find(name):
    items=[]
    for m in re.finditer(re.escape('"'+name+'"')+r'\s*=\s*([^\n]+)',text):
        v=m.group(1).strip()
        if v not in items:items.append(v)
    return items

print("Yoga HDMI600 AB — read-only comparison report")
for key in ("WEXYogaHDMI600Requested","WEXYogaHDMI600Ready","WEXYogaHDMI600Status",
            "WEXYogaHDMIEDIDABApplied","WEXYogaHDMIEDIDABLast",
            "WEXYogaEDP120Scoped","WEXYogaHDMIColorModeHookReady"):
    print(f"{key}: {', '.join(find(key)) or 'not published'}")
print("Boot argument has Deep8:", "-wex-yoga-hdmi-edid-deep8" in boot)
print("Boot argument has HDMI600:", "-wex-yoga-hdmi600" in boot)
print("Boot argument has unsafe old HDMI4K60:", "-wex-yoga-hdmi4k60" in boot)
# IOFBTimingRange is often binary. A 600MHz literal anywhere in the
# full registry is not proof that HDMI B actually chose that limit.
range_lines=[line.strip() for line in text.splitlines() if '"IOFBTimingRange"' in line]
print("IOFBTimingRange records:",len(range_lines))
print("IMPORTANT: status=4 proves only admission patch installation, not live HDMI60")
print("IMPORTANT: verify HDMI60 with monitor OSD and actual framebuffer status")
for l in display.splitlines():
    if any(k in l for k in ("Resolution:","Refresh Rate:","UI Looks like:","Framebuffer Depth:","Metal Support:","Chipset Model:","Vendor:","Connection Type:")):
        print(l.strip())
