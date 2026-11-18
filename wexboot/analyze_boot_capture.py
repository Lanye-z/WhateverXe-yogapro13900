#!/usr/bin/env python3
"""Decode EXISTING WhateverXe N97Display13Boot IORegistry boot snapshot.

This needs NO kernel patch and NO register writes. Accept either the existing
Yoga_EDP120_V1.zip or a text file produced by 'ioreg -lw0 -p IOService'.
Never upload a complete ioreg capture to a public repo.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import struct
from zipfile import ZipFile

def get_text(filename: Path) -> str:
    if filename.suffix.lower() != ".zip":
        return filename.read_text(errors="replace")
    with ZipFile(filename) as f:
        names=[x for x in f.namelist() if x.endswith("/ioreg.txt") or x=="ioreg.txt"]
        if len(names)!=1:raise ValueError(f"Expected one ioreg.txt, found {names}")
        return f.read(names[0]).decode("utf8","replace")

def boot_snapshot(text: str) -> dict:
    pat=r'"N97Display13Boot"\s*=\s*<([a-fA-F0-9]+)>'
    m=re.search(pat,text)
    if not m:raise ValueError("N97Display13Boot was not found; confirm the actual WEX build and ioreg options")
    b=bytes.fromhex(m.group(1))
    if len(b)<24:raise ValueError("Too short")
    version,status,count,powered,active,hdmi=struct.unpack_from("<6I",b)
    if version!=2 or count>160 or len(b)<24+8*count:
        raise ValueError(f"Invalid record header: {version}, {count}, {len(b)}")
    regs={}
    for k in range(count):
        offset,value=struct.unpack_from("<II",b,24+8*k)
        regs[offset]=value
    def require(address: int) -> int:
        if address not in regs:raise ValueError(f"Missing boot register 0x{address:x}")
        return regs[address]
    ctl=require(0x70180)
    stride=require(0x70188)
    surface=require(0x7019c)
    size=require(0x70190)
    source=require(0x6001c)
    pixels_w=(source>>16)+1
    pixels_h=(source&0xffff)+1
    plane_w=(size&0xffff)+1
    plane_h=(size>>16)+1
    # Display13 plane stride is in 64-byte units, not pixels.
    line_bytes=stride*64
    # ((ctl>>10)&7)==0 is linear GOP in the sample, and 4 indicates the
    # alternative tiled layout seen in issue 131; interpretation must be
    # confirmed against this target's hardware driver.
    mode=(ctl>>10)&7
    result={
        "record_version":version,
        "snapshot_status":status,
        "register_count":count,
        "powered_pipe_mask":hex(powered),
        "active_pipe_mask":hex(active),
        "pipe0_source_pixels":[pixels_w,pixels_h],
        "boot_plane0_pixels":[plane_w,plane_h],
        "boot_plane_ctl":f"0x{ctl:08x}",
        "boot_plane_tiling_bits":mode,
        "boot_plane_stride":f"0x{stride:08x}",
        "boot_plane_stride_bytes":line_bytes,
        "boot_plane_surface":f"0x{surface:08x}",
        "boot_trans_ctl2":f"0x{require(0x60404):08x}",
        "looks_like_3072x1920_linear_GOP":bool(
          status==1 and active&1 and pixels_w==3072 and pixels_h==1920 and
          plane_w==3072 and plane_h==1920 and mode==0 and
          line_bytes==3072*4 and surface==0
        ),
        "diagnostic_boundary":"Early firmware/GOP snapshot only; does NOT establish the later WindowServer resource's tiling.",
    }
    return result

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("file",type=Path)
    a=p.parse_args()
    print(json.dumps(boot_snapshot(get_text(a.file)),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
