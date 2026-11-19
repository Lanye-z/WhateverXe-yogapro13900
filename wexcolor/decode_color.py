#!/usr/bin/env python3
"""Decode WEXYogaHDMIColorLive from an ioreg -p IOService -l -w0 dump.

The source is a live powered-well-guarded register *snapshot*, not the
framebuffer bit-depth label. Never interpret UINT32_MAX as a hardware value.
"""
import argparse
import json
import re
import struct
from pathlib import Path

INVALID=0xffffffff
def hx(v):
    return "unavailable" if v == INVALID else f"0x{v:08X}"

def decode(raw: str):
    hits=re.findall(r'"WEXYogaHDMIColorLive"\s*=\s*<([0-9a-fA-F]+)>',raw)
    if not hits:
        raise ValueError("WEXYogaHDMIColorLive absent: confirm test kext and -wex-yoga-hdmi-colortrace")
    data=bytes.fromhex(hits[-1])
    if len(data)!=62*4:
        raise ValueError(f"Unexpected record size {len(data)} bytes (expected 248)")
    w=struct.unpack("<62I",data)
    if w[0]!=1:
        raise ValueError(f"Unknown schema {w[0]}")
    result={
        "schema":w[0],
        "status":{0:"not ready",1:"snapshot captured",2:"power changed DURING capture"}.get(w[1],f"unknown {w[1]}"),
        "power_before":hx(w[2]),
        "power_after":hx(w[3]),
        "vendor_eisa":f"0x{w[4]:04X}",
        "product_id":f"0x{w[5]:04X}",
        "hdmi_b_pipe_mask":f"0x{w[6]:X}",
        "powered_pipe_mask":f"0x{w[7]:X}",
        "pipes":[]
    }
    for i in range(3):
        r=w[8+17*i:8+17*(i+1)]
        fn=r[2]
        misc=r[3]
        ctl=r[7]
        is_hdmi=bool(w[6] & (1<<i))
        f_bpc={0:"8 bpc",1:"10 bpc",2:"6 bpc",3:"12 bpc"}.get((fn>>20)&7,"unknown") if fn!=INVALID else "unknown"
        # Display13 ADLP+ PIPE_MISC bits7:5 are PORT_OUTPUT_BPC.
        p_bpc={0:"8 bpc",1:"10 bpc",2:"6 bpc",4:"12 bpc"}.get((misc>>5)&7,"unknown") if misc!=INVALID else "unknown"
        result["pipes"].append({
          "pipe":i,
          "powered":r[1]==1,
          "hdmi_b_live":is_hdmi,
          "trans_ddi_func_ctl":hx(fn),
          "trans_ddi_func_ctl2":hx(r[6]),
          "trans_bpc":f_bpc,
          "trans_ddi_selector":((fn>>27)&15) if fn!=INVALID else None,
          "trans_mode_code":((fn>>24)&7) if fn!=INVALID else None,
          "pipe_misc":hx(misc),
          "pipe_bpc":p_bpc,
          "pipe_color":("YUV" if misc&(1<<11) else "RGB") if misc!=INVALID else "unknown",
          "plane_ctl":hx(r[4]),
          "pipeconf":hx(r[5]),
          "video_dip_ctl":hx(ctl),
          "avi_enabled":bool(ctl&(1<<12)) if ctl!=INVALID else None,
          "gcp_enabled":bool(ctl&(1<<16)) if ctl!=INVALID else None,
          "gcp":hx(r[8]),
          "avi_dwords":[hx(x) for x in r[9:16]],
          "trans_msa_misc":hx(r[16])
        })
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("ioreg_txt",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    result=decode(a.ioreg_txt.read_text(errors="replace"))
    formatted=json.dumps(result,indent=2,ensure_ascii=False)
    print(formatted)
    if a.output:
        a.output.write_text(formatted+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
