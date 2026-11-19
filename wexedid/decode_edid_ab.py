#!/usr/bin/env python3
"""Read EDID A/B status and only non-private CTA flags/checksum from ioreg."""
import argparse,json,re,struct
from pathlib import Path

STATUSES={
    0:"skipped-or-no-op",1:"invalid-CTA-header",2:"invalid-CTA-checksum",
    3:"unsupported-420-only-video",4:"duplicate-or-missing-data-block",
    5:"unrecognized-CTA-capabilities",6:"applied",7:"already-modified"
}
def decode(text):
    m=re.findall(r'"WEXYogaHDMIEDIDABLast"\s*=\s*<([0-9a-fA-F]+)>',text)
    if not m:
        return {"status":"not-published","note":"Check current Kext and exactly one EDID test flag"}
    b=bytes.fromhex(m[-1])
    if len(b)!=60:
        return {"status":"invalid-record","bytes":len(b)}
    r=struct.unpack("<15I",b)
    result={
        "schema":r[0],"deep8_requested":bool(r[1]),
        "rgb8_requested":bool(r[2]),
        "u27p10_base_identified":bool(r[3]),
        "ddc_block":r[4],"status":STATUSES.get(r[5],f"unknown-{r[5]}"),
        "feature_before":f"0x{r[6]:02X}","feature_after":f"0x{r[7]:02X}",
        "hdmi_deep_color_before":f"0x{r[8]:02X}",
        "hdmi_deep_color_after":f"0x{r[9]:02X}",
        "forum_deep_color_before":f"0x{r[10]:02X}",
        "forum_deep_color_after":f"0x{r[11]:02X}",
        "y420_map_before":f"0x{r[12]:02X}",
        "y420_map_after":f"0x{r[13]:02X}",
        "conflicting_flags":bool(r[14]),
        "applied_property":bool(re.search(r'"WEXYogaHDMIEDIDABApplied"\s*=\s*Yes',text))
    }
    ext=re.findall(r'"N97FBEDIDExtension"\s*=\s*<([0-9a-fA-F]{256})>',text)
    if ext:
        edid=bytes.fromhex(ext[-1])
        result["effective_cta_checksum_valid"]=sum(edid)%256==0
        result["effective_cta_header"]=edid[:4].hex().upper()
        result["effective_cta_dtd_offset"]=edid[2]
        result["effective_cta_vsdb_deep_flag_at_31"]=f"0x{edid[31]:02X}"
        result["effective_cta_forum_deep_flag_at_46"]=f"0x{edid[46]:02X}"
        result["effective_cta_y420_map_at_63"]=f"0x{edid[63]:02X}"
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("ioreg",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    obj=decode(a.ioreg.read_text(errors="replace"))
    raw=json.dumps(obj,indent=2,ensure_ascii=False)
    print(raw)
    if a.output:a.output.write_text(raw+"\n",encoding="utf8")
if __name__=="__main__":main()
