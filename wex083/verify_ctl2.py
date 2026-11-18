#!/usr/bin/env python3
"""Guarded source check for the single Yoga A7A0 CTL2 exception."""
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-original", action="store_true")
    modes.add_argument("--check-patched", action="store_true")
    args = parser.parse_args()
    src = (args.source / "WhateverXe" / "kern_alderlake_n.hpp").read_text()
    start = src.index("inline bool dpSource(")
    stop = src.index("enum class GOPProtocol", start)
    func = src[start:stop]
    original = "!(trans&((1U<<15)|(1U<<9))) && !ctl2 &&"
    patched = "!(trans&((1U<<15)|(1U<<9))) && !(ctl2&~(panel?(1U<<3):0U)) &&"
    assert func.count(original) + func.count(patched) == 1, "CTL2 anchor changed: review upstream manually"
    assert "return (trans&0xFF000000U)" in func, "upstream dpSource policy changed"
    if args.check_original:
        assert original in func and patched not in func, "not the pinned unmodified 0.8.3 source"
    else:
        assert patched in func and original not in func, "patched expression missing"
        # This exception must never approve CTL2 bits other than bit 3,
        # and it must never apply to HDMI / external DP (panel=False).
        for is_panel in (False, True):
            for bits in range(256):
                allowed = (bits & ~((1 << 3) if is_panel else 0)) == 0
                assert allowed == (bits == 0 or (is_panel and bits == 8))
    print("PASS: 0.8.3 CTL2 source guard; only internal eDP bit 3 admitted")

if __name__ == "__main__":
    main()
