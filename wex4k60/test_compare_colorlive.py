#!/usr/bin/env python3
"""Offline fixtures for the existing WEXYogaHDMIColorLive source bit decoder."""
import struct
import unittest

from compare import decode_colorlive, format_registry


def make_live(func=0x90030200, schema=1, valid=1, mask=0b100):
    fields=[0]*59
    fields[0]=schema
    fields[1]=valid
    fields[6]=mask
    fields[7]=0b111
    for i in range(3):
        fields[8+17*i]=i
        fields[8+17*i+1]=1
        fields[8+17*i+2]=0xffffffff
    fields[8+17*2+2]=func
    return "<"+struct.pack("<59I",*fields).hex()+">"


class ColorLiveTests(unittest.TestCase):
    def test_baseline_4k30(self):
        txt=decode_colorlive(make_live())
        assert "Pipe2 FUNC_CTL=0x90030200" in txt, txt
        assert "enable=1 highTMDS=0 scrambling=0" in txt, txt
        assert "HDCPsignal=1" in txt, txt
        assert "BPCfield=0" in txt, txt

    def test_4k60_hypothetical_flags(self):
        txt=format_registry("WEXYogaHDMIColorLive",make_live(0x90030211))
        assert "highTMDS=1 scrambling=1" in txt, txt

    def test_unreadable_register(self):
        txt=decode_colorlive(make_live(0xffffffff))
        assert "FUNC_CTL=unavailable" in txt,txt
        assert "scrambling=" not in txt,txt

    def test_invalid_snapshot_not_interpreted(self):
        txt=decode_colorlive(make_live(valid=2))
        assert "colortrace-not-valid" in txt,txt
        assert "FUNC_CTL" not in txt,txt

    def test_unrecognized_schema_not_interpreted(self):
        txt=decode_colorlive(make_live(schema=42))
        assert "unrecognized-schema=42" in txt,txt

    def test_absent_pipe_and_short_payload(self):
        assert "no readable HDMI-B pipe" in decode_colorlive(make_live(mask=0))
        assert "unexpected-length" in decode_colorlive("<010200>")

if __name__ == "__main__":
    unittest.main()
