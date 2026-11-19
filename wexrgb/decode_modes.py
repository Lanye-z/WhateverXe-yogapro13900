#!/usr/bin/env python3
"""Decode the opt-in WEXYogaHDMIColorModeLive lazy IORegistry ring buffer."""
import argparse,json,re,struct
from pathlib import Path

N=24
RECORD_WORDS=12
WORDS=3+N*RECORD_WORDS
OUTCOME={0:"observe",1:"not-qualified",2:"conflicting-test-flags",
         3:"unknown-depth-no-change",4:"already-8bit",5:"native-arguments-adjusted"}
def decode(text:str):
    matches=re.findall(r'"WEXYogaHDMIColorModeLive"\s*=\s*<([0-9a-fA-F]+)>',text)
    if not matches:
        raise ValueError("WEXYogaHDMIColorModeLive absent: check mode-audit flag and WEXYogaHDMIColorModeHookReady")
    raw=bytes.fromhex(matches[-1])
    if len(raw)!=WORDS*4:
        raise ValueError(f"Unexpected color-mode payload {len(raw)} bytes, expected {WORDS*4}")
    w=struct.unpack(f"<{WORDS}I",raw)
    if w[0]!=1 or w[2]!=N:
        raise ValueError(f"Unknown version/capacity: {w[0]}, {w[2]}")
    records=[]
    for i in range(N):
        r=w[3+i*RECORD_WORDS:3+(i+1)*RECORD_WORDS]
        if not r[0]:continue
        records.append({
          "sequence":r[0],
          "qualified":bool(r[1]),
          "physical_ddi":r[2] if r[2]<7 else None,
          "pipe":r[3] if r[3]<3 else None,
          "original_mode":r[4],"original_depth":r[5],
          "native_flag":bool(r[6]),
          "forwarded_mode":r[7],"forwarded_depth":r[8],
          "outcome":OUTCOME.get(r[9],f"unknown({r[9]})"),
          "sink_match_u27p10":bool(r[10]),
          "physical_path_qualified":bool(r[11])
        })
    records.sort(key=lambda x:x["sequence"])
    return {"schema":w[0],"calls_total":w[1],"last_records":records,
            "u27p10_records":[x for x in records if x["qualified"]]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("ioreg_txt",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    payload=json.dumps(decode(a.ioreg_txt.read_text(errors="replace")),
                       ensure_ascii=False,indent=2)
    print(payload)
    if a.output:a.output.write_text(payload+"\n",encoding="utf8")
if __name__=="__main__":main()
