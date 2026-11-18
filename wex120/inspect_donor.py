#!/usr/bin/env python3
"""Read-only analysis of the exact, pinned Tahoe Graphics 0.4.4 framebuffer.

This script NEVER patches an Apple driver or alters its signature. Its output
is diagnostic evidence for a guarded runtime WhateverXe opt-in patch.
"""
from __future__ import annotations
import hashlib
import re
import struct
import subprocess
from pathlib import Path

p = Path("Graphics/payloads/Tahoe/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer")
assert p.is_file(), p
data = p.read_bytes()
out = Path("dist")
out.mkdir(exist_ok=True)
sha = hashlib.sha256(data).hexdigest()
print(f"DONOR={p}\nBYTES={len(data)}\nSHA256={sha}")
assert data[:4] in (bytes.fromhex("cffaedfe"), bytes.fromhex("feedfacf")), "Unexpected Mach-O magic"
words = [300000000, 387840000, 533120000, 600000000, 652800000, 720000000, 775680000, 800000000]
report = [f"Byte-exact released Tahoe framebuffer\nsize={len(data)}\nsha256={sha}\n"]
for clock in words:
    for bits, fmt in [(32, "<I"), (64, "<Q")]:
        needle = struct.pack(fmt, clock)
        starts = [m.start() for m in re.finditer(re.escape(needle), data)]
        report.append(f"{clock} Hz / {bits}-bit little-endian / {len(starts)} hits / {[hex(k) for k in starts[:80]]}")
        for off in starts[:32]:
            lo=max(0, off-32); hi=min(len(data),off+len(needle)+32)
            report.append(f"  offset=0x{off:x} bytes[{lo:x}:{hi:x}]={data[lo:hi].hex(' ')}")
(out/"native_clock_hits.txt").write_text("\n".join(report)+"\n")
print("\n".join(report[:30]))
def cmd(args):
    z=subprocess.run(args, capture_output=True, text=True)
    print("command:", " ".join(args), "rc", z.returncode, "stdout_len", len(z.stdout), "stderr",z.stderr[:250])
    return z.stdout if z.returncode==0 else ""
for tool,args in [
    ("dwarfdump",["xcrun","dwarfdump","--uuid",str(p)]),
    ("nm",["nm","-an",str(p)]),
    ("otool",["otool","-tvV",str(p)])]:
    value=cmd(args)
    if tool=="dwarfdump":(out/"donor_uuid.txt").write_text(value)
    elif tool=="nm":
        (out/"donor_relevant_symbols.txt").write_text("\n".join(s for s in value.splitlines() if re.search("getOnlineInfo|Timing|EDP|mode|Mode|Clock|Range",s,re.I))+"\n")
        print("symbols", (out/"donor_relevant_symbols.txt").read_text()[:6000])
    elif tool=="otool":
        lines=value.splitlines()
        selected=set()
        patterns=("2aea5400","0x2aea5400","720000000","getOnlineInfo","2faf0800")
        for i,s in enumerate(lines):
            if any(x in s for x in patterns):
                for k in range(max(0,i-12),min(len(lines),i+15)):selected.add(k)
        matches=[f"{i+1}: {lines[i]}" for i in sorted(selected)]
        (out/"donor_relevant_disassembly.txt").write_text("\n".join(matches)+"\n")
        print("disasm snippets", "\n".join(matches[:100])[:10000])
