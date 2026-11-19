#!/usr/bin/env python3
"""Fast pure-Python schema regression for the color snapshot decoder."""
import struct
from decode_color import decode

def main():
    words=[0xffffffff]*59
    words[0]=1
    words[1]=1
    words[2]=(1<<10)|(1<<12)
    words[3]=words[2]
    words[4]=0x05e3
    words[5]=0x2710
    words[6]=2
    words[7]=3
    for pipe in range(3):
        i=8+17*pipe
        words[i]=pipe
        words[i+1]=int(pipe<2)
    i=8+17
    words[i+2]=0x90010200
    words[i+3]=0
    words[i+4]=0x84000008
    words[i+5]=0x80000000
    words[i+6]=0
    words[i+7]=0x00001000
    words[i+8]=0xffffffff
    words[i+9]=0x01020304
    words[i+16]=0x00000020
    sample='"WEXYogaHDMIColorLive" = <'+struct.pack("<59I",*words).hex()+'>'
    obj=decode(sample)
    assert obj["status"]=="snapshot captured"
    assert obj["vendor_eisa"]=="0x05E3"
    assert obj["product_id"]=="0x2710"
    assert obj["pipes"][1]["hdmi_b_live"]
    assert obj["pipes"][1]["trans_ddi_selector"]==2
    assert obj["pipes"][1]["pipe_color"]=="RGB"
    assert obj["pipes"][1]["trans_bpc"]=="8 bpc"
    assert obj["pipes"][1]["avi_enabled"] is True
    assert obj["pipes"][1]["gcp_enabled"] is False
    assert obj["pipes"][1]["gcp"]=="unavailable"
    assert not obj["pipes"][2]["powered"]
    words[1]=2
    sample='"WEXYogaHDMIColorLive" = <'+struct.pack("<59I",*words).hex()+'>'
    assert "power changed" in decode(sample)["status"]
    print("PASS: HDMI color 59-u32 schema, validity, masks, RGB/depth decode")

if __name__=="__main__":
    main()
