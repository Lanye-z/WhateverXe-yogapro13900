#!/usr/bin/env python3
"""Read-only AppleIntelTGLGraphicsFramebuffer x86_64 Mach-O audit.

Use the *installed* native Tahoe framebuffer Mach-O. This program does NOT
load a kext, patch memory, touch registers, use sudo, or change video modes.

Usage:
  python3 wex4k60/native_macho_audit.py
  python3 wex4k60/native_macho_audit.py /path/to/AppleIntelTGLGraphicsFramebuffer
  python3 wex4k60/native_macho_audit.py --out ~/Desktop/Yoga_HDMI_NativeAudit.json
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import uuid

EXPECTED_UUID = "B6078743-F795-3202-A55E-EA690FA40949"
# Function starts are hypotheses from same-GPU third-party source, NOT a
# substitute for checking the actual installed Apple Mach-O.
TARGETS = (
    ("getOnlineInfo", 0x2E232, "554889e541574156"),
    ("setColorMode", 0x491F2, "554889e541574156"),
    ("LightUpTMDS", 0x50B22, "554889e541574156"),
    ("hwDoI2CRequest", 0x53A20, "554889e54883ec20"),
    ("hwDoGMBusRequest", 0x53A7C, "554889e541574156"),
)
CALLSITE_RETURN = 0x4FFBB
DEFAULTS = (
    "/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/"
    "Contents/MacOS/AppleIntelTGLGraphicsFramebuffer",
    "/System/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/"
    "Contents/MacOS/AppleIntelTGLGraphicsFramebuffer",
)

class MachOError(ValueError):
    pass

def choose_arch(data):
    # Return (slice_offset, slice_size). Support thin x86_64 or fat images.
    if data[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"):
        return 0, len(data)
    if data[:4] not in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
                        b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"):
        raise MachOError("not a thin or fat Mach-O")
    big = data[:4] in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf")
    endian = ">" if big else "<"
    fat64 = data[:4] in (b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")
    if len(data) < 8:
        raise MachOError("truncated universal header")
    n = struct.unpack_from(endian+"I", data, 4)[0]
    entry_size = 32 if fat64 else 20
    if n > 64 or 8+n*entry_size > len(data):
        raise MachOError("invalid universal architecture count")
    for i in range(n):
        off = 8+i*entry_size
        cpu = struct.unpack_from(endian+"I", data, off)[0]
        if cpu != 0x01000007:
            continue
        if fat64:
            start, size = struct.unpack_from(endian+"QQ", data, off+8)
        else:
            start, size = struct.unpack_from(endian+"II", data, off+8)
        if start+size > len(data):
            raise MachOError("universal x86_64 slice exceeds file")
        return start, size
    raise MachOError("universal binary has no x86_64 slice")

def parse_macho(data):
    slice_start, slice_size = choose_arch(data)
    if data[slice_start:slice_start+4] != b"\xcf\xfa\xed\xfe":
        raise MachOError("expected little-endian x86_64 MH_MAGIC_64")
    if slice_start + 32 > len(data):
        raise MachOError("truncated Mach-O header")
    magic, cpu, subcpu, filetype, ncmds, sizeofcmds, flags, reserved = \
        struct.unpack_from("<IiiIIIII", data, slice_start)
    if cpu != 0x01000007 or ncmds > 4096:
        raise MachOError("not a valid x86_64 Mach-O")
    limit = slice_start+slice_size
    pos = slice_start+32
    if pos+sizeofcmds > limit:
        raise MachOError("load commands exceed architecture slice")
    segments=[]
    sections=[]
    symbols=None
    code_uuid=None
    for _ in range(ncmds):
        if pos+8 > limit:
            raise MachOError("truncated load command")
        cmd, size=struct.unpack_from("<II",data,pos)
        if size < 8 or pos+size>limit:
            raise MachOError("bad load command size")
        if cmd == 0x1B and size >= 24:
            code_uuid=str(uuid.UUID(bytes=data[pos+8:pos+24])).upper()
        elif cmd == 0x19 and size>=72:
            name,vmaddr,vmsize,fileoff,filesize,maxprot,initprot,nsects,sflags = \
                struct.unpack_from("<16sQQQQiiII",data,pos+8)
            name=name.split(b"\0",1)[0].decode("ascii","replace")
            segments.append({"name":name,"vmaddr":vmaddr,"vmsize":vmsize,
                             "fileoff":fileoff,"filesize":filesize})
            if nsects > 4096 or 72+nsects*80 > size:
                raise MachOError("malformed section array")
            for j in range(nsects):
                soff=pos+72+j*80
                sect,seg,addr,ssize,offset=struct.unpack_from("<16s16sQQI",data,soff)
                sections.append({
                    "name":sect.split(b"\0",1)[0].decode("ascii","replace"),
                    "segment":seg.split(b"\0",1)[0].decode("ascii","replace"),
                    "vmaddr":addr,"vmsize":ssize,"fileoff":offset})
        elif cmd==0x2 and size>=24:
            symbols=dict(zip(("symoff","nsyms","stroff","strsize"),
                             struct.unpack_from("<IIII",data,pos+8)))
        pos+=size
    if not segments:
        raise MachOError("no LC_SEGMENT_64")
    text=next((seg for seg in segments if seg["name"]=="__TEXT"),None)
    if text is None:
        raise MachOError("missing __TEXT")
    return {
        "slice_start":slice_start,"slice_size":slice_size,"uuid":code_uuid,
        "text_base":text["vmaddr"],"segments":segments,"sections":sections,
        "symtab":symbols,
    }

def image_bytes(data, m, relative, n):
    absolute=m["text_base"]+relative
    for seg in m["segments"]:
        if seg["vmaddr"] <= absolute and absolute+n <= seg["vmaddr"]+seg["filesize"]:
            pos=m["slice_start"]+seg["fileoff"]+(absolute-seg["vmaddr"])
            if pos+n <= m["slice_start"]+m["slice_size"]:
                return data[pos:pos+n]
    raise MachOError("VM offset 0x%X is not backed by file bytes" % relative)

def lookup_symbols(data, m):
    s=m["symtab"]
    if s is None or s["nsyms"]>500000:
        return {}
    start=m["slice_start"]
    if (s["symoff"]+s["nsyms"]*16>m["slice_size"]
            or s["stroff"]+s["strsize"]>m["slice_size"]):
        return {}
    names=(
        "getOnlineInfo","setColorMode","LightUpTMDS",
        "hwDoI2CRequest","hwDoGMBusRequest",
    )
    table=data[start+s["stroff"]:start+s["stroff"]+s["strsize"]]
    hits={}
    for i in range(s["nsyms"]):
        index,typ,sect,desc,va=struct.unpack_from(
            "<IBBHQ",data,start+s["symoff"]+i*16)
        if index>=len(table) or va==0:
            continue
        end=table.find(b"\0",index)
        if end<0:
            continue
        name=table[index:end].decode("ascii","replace")
        if any(token in name for token in names):
            hits[name]=("0x%X"%(va-m["text_base"]))
    return hits

def audit_bytes(data):
    m=parse_macho(data)
    result={
        "schema":1,
        "object":"AppleIntelTGLGraphicsFramebuffer",
        "file_size_bytes":len(data),
        "sha256":hashlib.sha256(data).hexdigest(),
        "expected_loaded_uuid":EXPECTED_UUID,
        "macho_uuid":m["uuid"],
        "uuid_matches_loaded_baseline":m["uuid"]==EXPECTED_UUID,
        "x86_64_slice_offset":m["slice_start"],
        "x86_64_slice_size":m["slice_size"],
        "text_vmaddr":"0x%X"%m["text_base"],
        "symtab_target_names":lookup_symbols(data,m),
        "targets":[],
    }
    for name,offset,expected in TARGETS:
        rec={"name":name,"image_offset":"0x%X"%offset,
             "expected_first8":expected}
        try:
            raw=image_bytes(data,m,offset,64)
            rec["actual_first8"]=raw[:8].hex()
            rec["first8_match"]=rec["actual_first8"]==expected
            rec["first64"]=raw.hex()
            rec["file_backed"]=True
        except MachOError as exc:
            rec["file_backed"]=False
            rec["error"]=str(exc)
        result["targets"].append(rec)
    # Reference disassembly uses image+0x4FFBB as return address.
    # x86 direct CALL rel32 is five bytes ending there.
    cr={"image_offset":"0x%X"%CALLSITE_RETURN}
    try:
        previous=image_bytes(data,m,CALLSITE_RETURN-5,5)
        cr["preceding_five_bytes"]=previous.hex()
        cr["direct_relative_call"]=previous[0]==0xE8
        if previous[0]==0xE8:
            displacement=struct.unpack_from("<i",previous,1)[0]
            target=CALLSITE_RETURN+displacement
            cr["direct_call_target"]="0x%X"%target
            cr["direct_call_targets_LightUpTMDS"]=(target==0x50B22)
        cr["neighbor_code_image_offset"]="0x%X"%(CALLSITE_RETURN-64)
        cr["neighbor_128_bytes"] = image_bytes(
            data,m,CALLSITE_RETURN-64,128).hex()
    except MachOError as exc:
        cr["error"]=str(exc)
    result["reference_callsite"]=cr
    result["interpretation"]=(
        "A matching UUID and first8 prologues are positive identity and entry "
        "evidence, NOT proof of the calling ABI, field offsets, source-side "
        "scrambling behavior, SCDC transactions, or safe live hooking.")
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("path",nargs="?",help="installed native Mach-O (not WhateverXe.kext)")
    p.add_argument("--out",type=Path,help="optional local JSON report path")
    args=p.parse_args(argv)
    candidates=[Path(args.path).expanduser()] if args.path else [Path(x) for x in DEFAULTS]
    path=next((candidate for candidate in candidates if candidate.is_file()),None)
    if path is None:
        p.error("native framebuffer executable not found at standard paths; "
                "pass its full path explicitly (do not use WhateverXe.kext)")
    report=audit_bytes(path.read_bytes())
    rendered=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.out:
        dest=args.out.expanduser()
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(rendered)
        print("Saved read-only Mach-O audit:",dest)
    else:
        print(rendered)
    print("UUID match:",report["uuid_matches_loaded_baseline"],file=sys.stderr)
    print("Function entry matches:",
          sum(bool(x.get("first8_match")) for x in report["targets"]),
          "/",len(report["targets"]),file=sys.stderr)
    print("No system files or display settings were modified.",file=sys.stderr)

if __name__=="__main__":
    main()
