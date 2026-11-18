#!/usr/bin/env python3
"""Read-only native donor and upstream C++ anchor audit for boot-logo investigation.
Never install or binary-patch the Apple driver.
"""
from pathlib import Path
import subprocess,hashlib,re
gfx=Path("Graphics/payloads/Tahoe/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/MacOS/AppleIntelTGLGraphics")
fb=Path("Graphics/payloads/Tahoe/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer")
source=Path("Source/WhateverXe/kern_xe.cpp")
out=Path("dist");out.mkdir(exist_ok=True)
def read_shell(argv):
    p=subprocess.run(argv,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(f"{argv} failed {p.returncode}: {p.stderr[:1000]}")
    return p.stdout
assert gfx.read_bytes()[:4]==bytes.fromhex("cffaedfe")
assert hashlib.sha256(fb.read_bytes()).hexdigest()=="115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e"
lines=[
 f"Graphic donor bytes {len(gfx.read_bytes())}",
 f"Graphic donor sha256 {hashlib.sha256(gfx.read_bytes()).hexdigest()}",
 f"Framebuffer donor sha256 {hashlib.sha256(fb.read_bytes()).hexdigest()}",
]
symbols=read_shell(["nm","-an",str(gfx)]).splitlines()
for tag in ["initFramebufferResource","initResourceInfo","setupPlane","enablePlane","programPipeScaler","IGAccelDisplayPipe"]:
    found=[l for l in symbols if tag.lower() in l.lower()]
    lines.append(f"SYMBOL {tag}: "+(" | ".join(found[:16]) if found else "NOT FOUND"))
disasm=read_shell(["otool","-tvV",str(gfx)]).splitlines()
for addr,tag in [(0x7f160,"initFramebufferResource"),(0x7ee9a,"initResourceInfo")]:
    matches=[i for i,s in enumerate(disasm) if s.startswith(f"{addr:016x}\t") or s.startswith(f"{addr:016x}:")]
    lines.append(f"TARGET {tag} 0x{addr:x} count={len(matches)}")
    for i in matches:
        lines+=disasm[max(0,i-8):min(len(disasm),i+20)]
body=source.read_text().splitlines()
for pat in ["bool XE::processTGLAccelerator(","void XE::adlnBootstrap(","N97Display13Boot","N97FBBootHandoffCheck","N97FBBootHandoff","processTGLAccelerator(patcher","void XE::processTGLAccelerator("]:
    hits=[i for i,l in enumerate(body) if pat in l]
    lines.append(f"CPP anchor {pat} count={len(hits)}")
    for i in hits[:5]:
        lines+=["%d: %s"%(k+1,body[k]) for k in range(max(i-12,0),min(len(body),i+55))]
text="\n".join(lines)
(out/"bootlogo_donor_source_audit.txt").write_text(text)
print(text[:55000])
