#!/usr/bin/env python3
"""Read-only source inspection for exact WhateverXe 0.8.3 display hook points."""
from pathlib import Path
import re
s=Path("Source/WhateverXe/kern_xe.cpp").read_text()
lines=s.splitlines()
tests=[
("adlnBootstrap",r"^void XE::adlnBootstrap\("),
("processKextFull",r"^bool XE::processKextFull\("),
("processDisplay13Framebuffer",r"^bool XE::processDisplay13Framebuffer\("),
("display13 FB watermark",r"Display13WM::clockFits\("),
("Framebuffer kernel image",r"framebufferClockImage"),
("ADL-N branch selected",r"adlnDisplaySelected"),
("native loaded kext",r"currentFramebuffer->loadIndex"),
("firmware panel",r"adlnOutputWiring\.panel"),
]
out=[]
for title,pattern in tests:
    hits=[i for i,l in enumerate(lines) if re.search(pattern,l)]
    out.append(f"## {title}: matches={len(hits)}")
    for i in hits[:8]:
        a=max(0,i-(15 if title in ("display13 FB watermark","native loaded kext","firmware panel") else 8))
        b=min(len(lines),i+(55 if title in ("adlnBootstrap","processKextFull","processDisplay13Framebuffer") else 13))
        out.append("\n".join(f"{j+1}: {lines[j]}" for j in range(a,b)))
data="\n\n".join(out)
Path("dist").mkdir(exist_ok=True)
Path("dist/wex083_target_hooks.txt").write_text(data)
print(data[:66000])
