#!/usr/bin/env python3
"""Create E1.0 by overlaying D1.1's one-line eDP fix on pinned acer/current.

No local EFI, installed Graphics binary, or other driver is modified.
"""
from __future__ import annotations

import argparse
import difflib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACER_REV = "f7b9bf2229d323e37e8b1dfb87182f005eb7a277"
ACER_HEADER_BLOB = "11c68039074139aa25855e19ec1cfd550df0c748"
D_HEADER_BLOB = "c6fa4c05799e326e91cce659435fbc56a5068e96"
ACER_CPP_BLOB = "64aaccc418ddd0f479bf0d5f2a71e647595f3967"
HEADER = "WhateverXe/kern_alderlake_n.hpp"
BEFORE = "        !(trans&((1U<<15)|(1U<<9))) && !ctl2 &&"
AFTER = "        !(trans&((1U<<15)|(1U<<9))) && !(ctl2&~(panel?(1U<<3):0U)) &&"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True
    ).strip()


def blob(file: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(file)], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path, help="pinned clean acer/current checkout")
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    target = upstream / HEADER
    archived = ROOT / "src" / HEADER
    cpp = upstream / "WhateverXe/kern_xe.cpp"

    if git(upstream, "rev-parse", "HEAD") != ACER_REV:
        raise SystemExit("REFUSED: acer/current revision mismatch")
    if git(upstream, "status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("REFUSED: upstream source is not clean")
    if blob(target) != ACER_HEADER_BLOB or blob(cpp) != ACER_CPP_BLOB:
        raise SystemExit("REFUSED: upstream display source hashes changed")
    if blob(archived) != D_HEADER_BLOB:
        raise SystemExit("REFUSED: archived D1.1 header no longer matches reviewed SHA")
    if b"-wex-a7a0-panel-only" in cpp.read_bytes():
        raise SystemExit("REFUSED: upstream unexpectedly has D-only panel masking")

    a = target.read_text().splitlines(keepends=True)
    b = archived.read_text().splitlines(keepends=True)
    if len(a) != len(b):
        raise SystemExit("REFUSED: different header line counts")
    edits = [(i+1, x.rstrip("\r\n"), y.rstrip("\r\n"))
             for i, (x, y) in enumerate(zip(a, b)) if x != y]
    if edits != [(243, BEFORE, AFTER)]:
        d = "".join(difflib.unified_diff(a, b, fromfile="acer", tofile="D1.1"))
        raise SystemExit("REFUSED: unexpected display changes:\n" + d[:3000])

    target.write_bytes(archived.read_bytes())
    if blob(target) != D_HEADER_BLOB:
        raise SystemExit("REFUSED: resulting header is not D1.1 reviewed blob")
    git(upstream, "diff", "--check")
    changed = git(upstream, "diff", "--name-only")
    if changed != HEADER:
        raise SystemExit("REFUSED: more than the reviewed header changed: " + changed)
    print("E1.0 source verified: acer/current baseline + D1.1 CTL2 bit-3 line.")
    print("Unchanged: upstream kern_xe.cpp, multi-output, USB-C, hotplug, clock and eDP mode logic.")
    print("Not added: panel-only boot arg, forced mode=1, VBT output masking.")
    print("Kext is experimental; passing these checks is NOT hardware validation.")


if __name__ == "__main__":
    main()
