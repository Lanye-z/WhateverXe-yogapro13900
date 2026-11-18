#!/usr/bin/env python3
"""Build TWO isolated Yoga 120Hz trials on pinned upstream 0.8.3.

V1: A7A0 eDP-only getOnlineInfo 720->800MHz admission experiment.
V2: V1 plus independent opt-in two-pixels-per-CDCLK WM bound.
Both changes default OFF. No EDID overrides or automatic mode switching.
"""
from __future__ import annotations
import argparse
import json
import re
import struct
import subprocess
from pathlib import Path

UPSTREAM="f26a36880c49ea1063393d943527808c0f38feca"
DONOR_SHA="115a4616e862228a8c82df6e52ba41ac02b9750f116352ff3575aadcc950888e"
DONOR="payloads/Tahoe/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer"
SITE=0x2E583
FIND=bytes.fromhex("48 8D 83 E4 01 00 00 E9 F6 00 00 00 48 C7 83 68 43 00 00 00 54 EA 2A 4C 89 F6 E8 2A 2D 02 00")
REPLACE=FIND[:19]+bytes.fromhex("00 08 AF 2F")+FIND[23:]
assert len(FIND)==len(REPLACE)==31 and [i for i,(x,y) in enumerate(zip(FIND,REPLACE)) if x!=y]==[20,21,22]

def replace_once(src:str, original:str, modified:str, what:str)->str:
    n=src.count(original)
    if n!=1:raise RuntimeError(f"Refused: {what} anchor count={n}, expected 1")
    return src.replace(original,modified,1)

def prepare(src:Path,graphics:Path,variant:str)->None:
    import hashlib
    revision=subprocess.check_output(["git","-C",str(src),"rev-parse","HEAD"],text=True).strip()
    if revision!=UPSTREAM:raise RuntimeError(f"un-pinned upstream {revision}")
    binpath=graphics/DONOR
    b=binpath.read_bytes()
    digest=hashlib.sha256(b).hexdigest()
    if digest!=DONOR_SHA:raise RuntimeError(f"unexpected donor sha256 {digest}")
    if b[SITE:SITE+len(FIND)]!=FIND:raise RuntimeError("eDP branch byte fingerprint mismatch")
    if b.count(FIND)!=1:raise RuntimeError("eDP branch fingerprint not unique")
    if b[0x2E780:0x2E784]!=struct.pack("<I",300000000):raise RuntimeError("HDMI donor anchor drift")
    if b[0x2E914:0x2E918]!=struct.pack("<I",720000000):raise RuntimeError("separate DP branch anchor drift")
    if b[0x2A12A:0x2A12E]!=struct.pack("<I",720000000):raise RuntimeError("default framebuffer anchor drift")

    cpppath=src/"WhateverXe/kern_xe.cpp"
    hppath=src/"WhateverXe/kern_xe.hpp"
    wmpath=src/"WhateverXe/kern_display13_wm.hpp"
    fixture=src/"tests/fixtures/boot_argument_names.json"
    cpp=cpppath.read_text()
    hdr=hppath.read_text()
    wm=wmpath.read_text()

    # Existing 0.8.3 Yoga accelerated baseline: ONLY panel CTL2 bit 3.
    ctl=src/"WhateverXe/kern_alderlake_n.hpp"
    ctr=ctl.read_text()
    orig="!(trans&((1U<<15)|(1U<<9))) && !ctl2 &&"
    modified="!(trans&((1U<<15)|(1U<<9))) && !(ctl2&~(panel?(1U<<3):0U)) &&"
    ctr=replace_once(ctr,orig,modified,"CTL2")
    ctl.write_text(ctr)

    header_anchor="\t__attribute__((noinline)) bool processDisplay13Framebuffer(KernelPatcher &patcher, size_t index, mach_vm_address_t address, size_t size);"
    newheader=header_anchor+"""
    // Yoga A7A0 eDP120 experiments. Both optional: no flags = upstream behavior.
    bool yogaEDP120Scoped {false};
    void processYogaEDP120Admission(KernelPatcher &,size_t,mach_vm_address_t,size_t);"""
    hdr=replace_once(hdr,header_anchor,newheader,"XE declaration")

    bootstrap_anchor="const auto board=display13BoardWiring(pci);adlnOutputWiring=board;"
    bootstrap=bootstrap_anchor+"""
    // Only physical A7A0 with VBT single internal eDP on DDI A.
    // The panel must be qualified before any 120Hz opt-in is enabled.
    yogaEDP120Scoped=displayRequested && pci->configRead16(0x02)==0xA7A0 &&
        board.described() && board.panel==1U && !board.dsi;
    pci->setProperty("WEXYogaEDP120Scoped",yogaEDP120Scoped);"""
    if variant=="V2":
        bootstrap+="""
    Display13WM::yogaEDP120PipeMask()=
        (yogaEDP120Scoped && checkKernelArgument("-wex-yoga-edp120-wm")) ? 1U : 0U;
    pci->setProperty("WEXYogaEDP120WMEnabled",Display13WM::yogaEDP120PipeMask()!=0);"""
    cpp=replace_once(cpp,bootstrap_anchor,bootstrap,"bootstrap panel/physical ID")

    method_anchor="bool XE::processDisplay13Framebuffer(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size) {"
    method="""// Exact Tahoe 16.0.0 donor: only the eDP getOnlineInfo fallback at 0x2E58F.
// The OTHER 720 MHz sites (global 0x2A123 and external capability 0x2E90D)
// are intentionally unchanged. The 800 MHz value only extends mode admission.
void XE::processYogaEDP120Admission(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size) {
    auto root=IORegistryEntry::getRegistryRoot();
    const bool requested=checkKernelArgument("-wex-yoga-edp120-admit");
    root->setProperty("WEXYogaEDP120AdmissionRequested",requested);
    uint32_t status=0; // 0 off, 1 not scoped, 2 donor check failed, 3 write failed, 4 installed.
    bool ready=false;
    if(requested) {
        status=1;
        if(yogaEDP120Scoped && display13FramebufferRequested &&
           currentFramebuffer && currentFramebuffer->loadIndex==index) {
            status=2;
            const char *symbol="__ZN21AppleIntelFramebuffer13getOnlineInfoEP21AppleIntelDisplayPathPhS2_";
            const auto fn=patcher.solveSymbol<mach_vm_address_t>(index,symbol,address,size);
            patcher.clearError();
            static const uint8_t find[]={
                0x48,0x8D,0x83,0xE4,0x01,0x00,0x00,0xE9,0xF6,0x00,0x00,0x00,
                0x48,0xC7,0x83,0x68,0x43,0x00,0x00,0x00,0x54,0xEA,0x2A,
                0x4C,0x89,0xF6,0xE8,0x2A,0x2D,0x02,0x00
            };
            static const uint8_t replace[]={
                0x48,0x8D,0x83,0xE4,0x01,0x00,0x00,0xE9,0xF6,0x00,0x00,0x00,
                0x48,0xC7,0x83,0x68,0x43,0x00,0x00,0x00,0x08,0xAF,0x2F,
                0x4C,0x89,0xF6,0xE8,0x2A,0x2D,0x02,0x00
            };
            constexpr size_t site=0x2E583;
            if(fn==address+0x2E232 && size>site+sizeof(find) &&
               !memcmp(reinterpret_cast<const void *>(address+site),find,sizeof(find))) {
                KernelPatcher::LookupPatch patch{currentFramebuffer,find,replace,sizeof(find),1};
                auto target=reinterpret_cast<uint8_t *>(address+site);
                patcher.applyLookupPatch(&patch,target,sizeof(find)+1);
                ready=!memcmp(target,replace,sizeof(replace));
                status=ready?4:3;
                patcher.clearError();
            }
        }
    }
    root->setProperty("WEXYogaEDP120AdmissionReady",ready);
    root->setProperty("WEXYogaEDP120AdmissionStatus",status,32);
}

""";
    cpp=replace_once(cpp,method_anchor,method+method_anchor,"FrameBuffer method entry")
    # Only the qualified Display13 path may patch; failures are non-fatal.
    call_anchor="if(!calcReady)return false;"
    cpp=replace_once(cpp,call_anchor,call_anchor+"\n  processYogaEDP120Admission(patcher,index,address,size);","FB qualified install site")

    if variant=="V2":
        check='''// These linear RGB/cursor WM and PIPE_WM_LINETIME equations do not consume
// CDCLK. An unchanged hardware-verified plan is valid at another clock when
// every consumer still fits its bandwidth. A clock request alone is no proof.
inline bool clockFits(const Snapshot &s,uint64_t nativeHz) {
    return s.primary && s.primary->status==Status::Complete && nativeHz &&
        s.primary->pixelHz && s.primary->pixelHz<=nativeHz/2 && s.pipePixelHz &&
        s.pipePixelHz<=nativeHz/2 && s.pipeLineTime==pipeLineTime(s.primary->htotal,s.pipePixelHz) &&
        (!s.cursorActive || (s.cursor && s.cursor->status==Status::Complete &&
            s.cursor->pixelHz && s.cursor->pixelHz<=nativeHz/2));
}'''
        patch='''// These linear RGB/cursor WM and PIPE_WM_LINETIME equations do not consume
// CDCLK. An unchanged hardware-verified plan is valid at another clock when
// every consumer still fits its bandwidth. A clock request alone is no proof.
// Yoga 120Hz opt-in: ADL/RPL Display13 processes two pixels per CDCLK.
// nativeHz is already 2*CDCLK; limit only eDP boot pipe A on scoped A7A0.
inline uint32_t &yogaEDP120PipeMask() {static uint32_t enabled=0;return enabled;}
inline bool clockFits(const Snapshot &s,uint64_t nativeHz) {
    const bool twoPixels=s.pipeIndex<3 && (yogaEDP120PipeMask()&(1U<<s.pipeIndex));
    const uint64_t limit=twoPixels?nativeHz:nativeHz/2;
    return s.primary && s.primary->status==Status::Complete && nativeHz &&
        s.primary->pixelHz && s.primary->pixelHz<=limit && s.pipePixelHz &&
        s.pipePixelHz<=limit && s.pipeLineTime==pipeLineTime(s.primary->htotal,s.pipePixelHz) &&
        (!s.cursorActive || (s.cursor && s.cursor->status==Status::Complete &&
            s.cursor->pixelHz && s.cursor->pixelHz<=limit));
}'''
        wm=replace_once(wm,check,patch,"WM two pixels")
        wmpath.write_text(wm)

    cpppath.write_text(cpp)
    hppath.write_text(hdr)

    args=json.loads(fixture.read_text())
    if "-wex-yoga-edp120-admit" in args or "-wex-yoga-edp120-wm" in args:
        raise RuntimeError("expected pristine boot argument fixture")
    args["-wex-yoga-edp120-admit"]=[]
    if variant=="V2":args["-wex-yoga-edp120-wm"]=[]
    fixture.write_text(json.dumps(args,indent=2)+"\n")

    # Cross-check exact in-memory patch bytes, without editing a binary on disk.
    assert FIND!=REPLACE and int.from_bytes(REPLACE[19:23],"little")==800000000
    assert b[0x2E780:0x2E784]==struct.pack("<I",300000000)
    assert b[0x2E914:0x2E918]==struct.pack("<I",720000000)
    changed=set(subprocess.check_output(["git","-C",str(src),"diff","--name-only"],text=True).splitlines())
    expected={"WhateverXe/kern_alderlake_n.hpp","WhateverXe/kern_xe.cpp","WhateverXe/kern_xe.hpp","tests/fixtures/boot_argument_names.json"}
    if variant=="V2":expected.add("WhateverXe/kern_display13_wm.hpp")
    if changed!=expected:raise RuntimeError(f"unexpected changes {changed} != {expected}")
    subprocess.run(["git","-C",str(src),"diff","--check"],check=True)
    print(f"VERIFIED {variant}: pinned 0.8.3 + CTL2; scoped eDP mode admission; WM variant opt-in = {variant=='V2'}")
    print("NO VBT/HDMI/DP/Graphics package/EDID/DSC/auto mode switches")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    p.add_argument("graphics",type=Path)
    p.add_argument("--variant",choices=("V1","V2"),required=True)
    a=p.parse_args()
    prepare(a.source.resolve(),a.graphics.resolve(),a.variant)
