#!/usr/bin/env python3
"""Offline, read-only comparison of Yoga chassis-HDMI 4K30 vs 4K60 captures.

Usage:
  python3 wex4k60/compare.py hdmi30.zip hdmi60black.zip [hdmi_recovered.zip]
or pass the unzipped capture directories.

Does not access hardware, change display settings or infer physical output
from macOS logical resolution. Unknown/missing properties are not assumed false.
"""
import re
import sys
import zipfile
from pathlib import Path

def read(capture, filename):
    p=Path(capture)
    if p.is_dir():
        f=p / filename
        return f.read_text(errors="replace") if f.is_file() else ""
    if p.is_file() and zipfile.is_zipfile(p):
        with zipfile.ZipFile(p) as z:
            # ditto --keepParent wraps files in exactly one parent folder.
            names=[n for n in z.namelist() if n == filename or n.endswith("/"+filename)]
            names=[n for n in names if not n.startswith("__MACOSX/")]
            if len(names)==1:
                return z.read(names[0]).decode("utf-8",errors="replace")
        return ""
    raise ValueError("Capture must be a folder or ZIP: "+str(p))

KEYS=(
  "WEXYogaHDMI600Status","WEXYogaHDMI600Ready",
  "WEXYogaHDMIEDIDABApplied","WEXYogaHDMIEDIDABLast",
  "WEXYogaHDMIColorModeHookReady","WEXYogaHDMIColorModeLive",
  "WEXYogaHDMIColorLive","WEXYogaSSTHookStatus",
  "N97FBClockSetHookReady","N97FBOutputHooksReady",
  "IOFBCurrentPixelClock","IOFBTimingRange",
)
PREFIXES=("N97FBClock", "N97FBDBUF", "N97FBPipe",
          "N97FBHDMI", "N97FBGMBus", "N97FBWatermark")
DISPLAY_FIELDS=("Resolution:", "Refresh Rate:", "UI Looks like:",
                "Framebuffer Depth:", "Metal Support:", "Connection Type:")

def registry_values(txt):
    result={}
    for line in txt.splitlines():
        m=re.search(r'"([^"]+)"\s*=\s*(.*)',line)
        if not m:
            continue
        key,value=m.groups()
        if key not in KEYS and not any(key.startswith(p) for p in PREFIXES):
            continue
        val=value.strip()
        # IORegistry embeds bytes for some properties; keep the report bounded.
        if len(val)>120:
            val=val[:117]+"..."
        result.setdefault(key,[])
        if val not in result[key]:
            result[key].append(val)
    return {key:" | ".join(v[:3])+(" | ...more" if len(v)>3 else "")
            for key,v in result.items()}

def selected_display_lines(txt):
    return [line.strip() for line in txt.splitlines()
            if any(x in line for x in DISPLAY_FIELDS)][:50]

def snapshot(path):
    io=read(path,"ioreg.txt")
    if not io:
        raise ValueError("Missing ioreg.txt in "+str(path))
    return {
        "capture": str(path),
        "registry":registry_values(io),
        "display":selected_display_lines(read(path,"displays.txt")),
        "boot":read(path,"system_and_bootargs.txt"),
        "notes":read(path,"USER_OBSERVATION.txt"),
    }

def compare(left,right):
    print("\nCOMPARE:",left["capture"],"vs",right["capture"])
    keys=sorted(set(left["registry"])|set(right["registry"]))
    change_count=0
    for key in keys:
        a=left["registry"].get(key,"<not recorded>")
        b=right["registry"].get(key,"<not recorded>")
        if a!=b:
            change_count+=1
            print("  CHANGED",key)
            print("    30/reference:",a)
            print("    comparison :",b)
    print("Differing published property keys:",change_count)
    if left["display"]!=right["display"]:
        print("Display profiler changed (logical state, NOT proof of physical light-up):")
        print("  reference:",left["display"])
        print("  compared :",right["display"])
    else:
        print("Display profiler fields unchanged or not available")
    for arg in ("-wex-yoga-tc5-sst","-wex-yoga-hdmi600",
                "-wex-yoga-hdmi-edid-deep8"):
        a=arg in left["boot"];b=arg in right["boot"]
        if a!=b:
            print("WARNING: boot-argument mismatch:",arg,a,b)

def main():
    if len(sys.argv) not in (3,4):
        raise SystemExit("usage: python3 wex4k60/compare.py <hdmi30.zip> <hdmi60black.zip> [recovered.zip]")
    snaps=[snapshot(name) for name in sys.argv[1:]]
    print("Yoga A7A0 native HDMI passive comparison")
    for x in snaps:
        print("\nCAPTURE:",x["capture"])
        print("Published HDMI600 status:",x["registry"].get("WEXYogaHDMI600Status","not recorded"))
        print("Physical OSD observation must be entered manually in USER_OBSERVATION.txt")
    compare(snaps[0],snaps[1])
    if len(snaps)==3:
        compare(snaps[1],snaps[2])
    print("\nCAUTION: no live SCDC read/write confirmation is present in this capture method.")
    print("A 60Hz option with black physical output is not proof that SCDC alone is the root cause.")
    print("If Pipe/Clock/DBUF states differ, investigate rollback before attempting another 60Hz mode.")

if __name__=="__main__":
    main()
