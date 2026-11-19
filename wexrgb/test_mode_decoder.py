#!/usr/bin/env python3
import struct
from decode_modes import decode,WORDS,N
def main():
    w=[0]*WORDS;w[:3]=[1,2,N]
    w[3:3+12]=[1,0,0,0,1,10,0,1,10,1,0,0]
    w[3+12:3+24]=[2,1,1,1,2,30,1,2,24,5,1,1]
    raw='"WEXYogaHDMIColorModeLive" = <'+struct.pack(f"<{WORDS}I",*w).hex()+'>'
    result=decode(raw)
    assert result["calls_total"]==2
    assert len(result["last_records"])==2
    assert len(result["u27p10_records"])==1
    assert result["u27p10_records"][0]["original_depth"]==30
    assert result["u27p10_records"][0]["forwarded_depth"]==24
    assert result["u27p10_records"][0]["outcome"]=="native-arguments-adjusted"
    print("PASS: color-mode trace schema and recorder decoding")
if __name__=="__main__":main()
