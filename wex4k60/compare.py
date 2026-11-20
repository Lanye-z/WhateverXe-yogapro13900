#!/usr/bin/env python3
"""Offline, read-only comparison of Yoga chassis-HDMI 4K30 vs 4K60 captures.

Usage:
  python3 wex4k60/compare.py hdmi30.zip
  python3 wex4k60/compare.py hdmi30.zip hdmi60black.zip [hdmi_recovered.zip]
or pass the unzipped capture directories.

Does not access hardware, change display settings or infer physical output
from macOS logical resolution. Unknown/missing properties are not assumed false.
"""
import hashlib
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
    if not p.exists():
        candidates=[]
        for folder in (Path.home()/"Desktop",Path.home()/"Downloads"):
            if folder.is_dir():
                candidates.extend(str(x) for x in folder.glob("*hdmi30*.zip"))
                candidates.extend(str(x) for x in folder.glob("*HDMI30*.zip"))
        hints="; ".join(dict.fromkeys(candidates[:8]))
        raise FileNotFoundError(
            "Capture path does not exist: "+str(p)+
            ("\\nFound possible local capture(s): "+hints if hints else
             "\\nFind the actual file using: find ~/Desktop ~/Downloads -maxdepth 4 -iname '*hdmi30*.zip' -print"+
             "\\nOr capture a new normal 4K30 baseline: bash wex4k60/collect.sh hdmi30")
        )
    raise ValueError("Capture exists but is not a directory or a readable ZIP: "+str(p))

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


def decode_colorlive(raw):
    """Decode the existing passive 236-byte WEXYogaHDMIColorLive IORegistry snapshot.

    This is a GPU register snapshot only: it cannot prove sink SCDC, TMDS
    link training, or physical video output. Never infer missing flags as zero.
    """
    m=re.fullmatch(r"<([0-9a-fA-F]+)>",raw.strip())
    if not m:
        return "colortrace-unparseable (not a raw OSData hex payload)"
    try:
        b=bytes.fromhex(m.group(1))
    except ValueError:
        return "colortrace-invalid-hex"
    if len(b)!=59*4:
        return "colortrace-unexpected-length=%d (expected 236)"%len(b)
    w=[int.from_bytes(b[i:i+4],"little") for i in range(0,len(b),4)]
    schema,valid=w[0],w[1]
    if schema!=1:
        return "colortrace-unrecognized-schema=%d"%schema
    if valid!=1:
        return "colortrace-not-valid (status=%d; no register inference)"%valid
    mask,powered=w[6],w[7]
    matches=[]
    for i in range(3):
        p=w[8+17*i:8+17*(i+1)]
        idx=p[0]
        if idx>2 or not (mask & (1<<idx)):
            continue
        func=p[2]
        if func==0xffffffff:
            matches.append("Pipe%d FUNC_CTL=unavailable"%idx)
            continue
        matches.append(
            "Pipe%d FUNC_CTL=0x%08X enable=%d highTMDS=%d scrambling=%d "
            "HDCPselect=%d HDCPsignal=%d BPCfield=%d"%(
                idx,func,(func>>31)&1,(func>>4)&1,func&1,
                (func>>5)&1,(func>>9)&1,(func>>20)&7
            )
        )
    if not matches:
        return ("colortrace-valid HDMI-mask=0x%X powered-mask=0x%X "
                "no readable HDMI-B pipe")%(mask,powered)
    return "colortrace-valid "+"; ".join(matches)

def format_registry(key, raw):
    if key=="WEXYogaHDMIColorLive":
        return decode_colorlive(raw)
    # The already-existing Display13 hook records a uint64_t[21] GMBUS
    # request/result at "N97FBGMBusLast". Decode it without reading DDC again.
    if key.startswith(("N97FBGMBusLast","N97FBGMBusFirst")):
        match=re.fullmatch(r"<([0-9a-fA-F]+)>", raw)
        if match:
            payload=bytes.fromhex(match.group(1))
            if len(payload)==21*8:
                v=[int.from_bytes(payload[i:i+8],"little") for i in range(0,len(payload),8)]
                return ("schema=%u seq=%u bus=%u speed=%u req@0x28=%u "
                        "req@0x38=%u native=0x%08X request=0x%08X "
                        "samples=%u error=%u")%(
                            v[0],v[1],v[2],v[3],v[6],v[7],
                            v[8]&0xffffffff,v[9]&0xffffffff,v[15],v[16])
    if len(raw)>120:
        digest=hashlib.sha256(raw.encode()).hexdigest()[:12]
        return raw[:90]+"... [sha256:"+digest+"]"
    return raw

def registry_values(txt):
    result={}
    for line in txt.splitlines():
        m=re.search(r'"([^"]+)"\s*=\s*(.*)',line)
        if not m:
            continue
        key,value=m.groups()
        if key not in KEYS and not any(key.startswith(p) for p in PREFIXES):
            continue
        val=format_registry(key,value.strip())
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
    if len(sys.argv) not in (2,3,4):
        raise SystemExit("usage: python3 wex4k60/compare.py <hdmi30.zip> [hdmi60black.zip] [recovered.zip]")
    snaps=[snapshot(name) for name in sys.argv[1:]]
    print("Yoga A7A0 native HDMI passive comparison")
    for x in snaps:
        print("\nCAPTURE:",x["capture"])
        print("Published HDMI600 status:",x["registry"].get("WEXYogaHDMI600Status","not recorded"))
        print("HDMI-B source register:",x["registry"].get("WEXYogaHDMIColorLive","not recorded"))
        print("Physical OSD observation must be entered manually in USER_OBSERVATION.txt")
    if len(snaps)==1:
        print("Single capture only: decoded source snapshot, no A/B comparison.")
    else:
        compare(snaps[0],snaps[1])
    if len(snaps)==3:
        compare(snaps[1],snaps[2])
    print("\nCAUTION: no live SCDC read/write confirmation is present in this capture method.")
    print("A 60Hz option with black physical output is not proof that SCDC alone is the root cause.")
    print("If Pipe/Clock/DBUF states differ, investigate rollback before attempting another 60Hz mode.")

if __name__=="__main__":
    main()
