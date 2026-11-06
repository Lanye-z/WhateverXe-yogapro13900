#!/usr/bin/env python3
"""Prepare E1.1 experimental Display13 HDMI600 patch from pinned E1.0."""
from pathlib import Path
import argparse
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
ACER_CPP="64aaccc418ddd0f479bf0d5f2a71e647595f3967"
INCLUDE='#include "kern_display13_color.hpp"\n'
ANCHOR='\tIORegistryEntry::getRegistryRoot()->setProperty("N97FBClockSetHookReady",display13FBClockSetHookReady);\n'
PATCH=r'''
    // Issue #41 adapted for the MOBILE Display13 backend; opt-in only.
    // Mode admission only. Never mutate the system Graphics or Apple binary.
    {
        auto yoga600Root=IORegistryEntry::getRegistryRoot();
        const bool requested=checkKernelArgument("-wex-yoga-hdmi600");
        bool success=false;
        uint32_t status=0; // 0=off;1=guard;2=donor mismatch;3=write failed;4=patched
        if(requested) {
            status=1;
            if(adlpDisplaySelected && display13FramebufferRequested &&
               display13FBClockReadoutHooksReady && display13FBClockSetHookReady &&
               currentFramebuffer && currentFramebuffer->loadIndex==index) {
                auto fn=patcher.solveSymbol<mach_vm_address_t>(
                    index,YogaHDMI600::Symbol,address,size);
                patcher.clearError();
                status=2;
                if(fn==address+YogaHDMI600::Function &&
                   YogaHDMI600::matches(reinterpret_cast<const uint8_t *>(address),size,fn-address)) {
                    KernelPatcher::LookupPatch patch {
                        currentFramebuffer,YogaHDMI600::Find,YogaHDMI600::Replace,
                        sizeof(YogaHDMI600::Find),1
                    };
                    auto site=reinterpret_cast<uint8_t *>(address+YogaHDMI600::Site);
                    patcher.applyLookupPatch(&patch,site,sizeof(YogaHDMI600::Find)+1);
                    success=patcher.getError()==KernelPatcher::Error::NoError &&
                        !memcmp(site,YogaHDMI600::Replace,sizeof(YogaHDMI600::Replace));
                    patcher.clearError();
                    status=success?4:3;
                }
            }
        }
        yoga600Root->setProperty("WEXYogaHDMI600Requested",requested);
        yoga600Root->setProperty("WEXYogaHDMI600Ready",success);
        yoga600Root->setProperty("WEXYogaHDMI600Status",status,32);
    }
'''

def shell(*args):
    return subprocess.check_output(args,text=True).strip()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source",type=Path)
    source=ap.parse_args().source.resolve()
    subprocess.run(["python3",str(ROOT/"e/tools/prepare_e.py"),str(source)],check=True)
    cpp=source/"WhateverXe/kern_xe.cpp"
    if shell("git","hash-object",str(cpp))!=ACER_CPP:
        raise SystemExit("REFUSED: source hash changed")
    original=cpp.read_text()
    start=original.find("bool XE::processDisplay13Framebuffer(")
    end=original.find("\nbool XE::",start+5)
    if start<0 or end<0:
        raise SystemExit("REFUSED: Display13 function not found")
    section=original[start:end]
    if original.count(INCLUDE)!=1 or section.count(ANCHOR)!=1:
        raise SystemExit("REFUSED: anchors not uniquely matched")
    patched=original.replace(INCLUDE,INCLUDE+'#include "kern_yoga_hdmi600.hpp"\n',1)
    a=patched.find("bool XE::processDisplay13Framebuffer(")
    b=patched.find("\nbool XE::",a+5)
    changed=patched[a:b].replace(ANCHOR,ANCHOR+PATCH,1)
    patched=patched[:a]+changed+patched[b:]
    if patched.count('checkKernelArgument("-wex-yoga-hdmi600")')!=1:
        raise SystemExit("REFUSED: unexpected patch count")
    cpp.write_text(patched)
    shutil.copyfile(ROOT/"e11/kern_yoga_hdmi600.hpp",source/"WhateverXe/kern_yoga_hdmi600.hpp")
    fixture=source/"tests/fixtures/boot_argument_names.json"
    registry=fixture.read_text()
    first='  "-wex-dsi-audit": [],\n'
    if registry.count(first)!=1:
        raise SystemExit("REFUSED: boot argument registry changed")
    fixture.write_text(registry.replace(first,'  "-wex-yoga-hdmi600": [],\n'+first,1))
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)
    changed=set(shell("git","-C",str(source),"diff","--name-only").splitlines())
    if changed!={"WhateverXe/kern_alderlake_n.hpp","WhateverXe/kern_xe.cpp","tests/fixtures/boot_argument_names.json"}:
        raise SystemExit("REFUSED: unexpected edits "+repr(changed))
    print("E1.1-HDMI600 prepared; E1.0 display and GVA behavior unchanged by default.")
    print("IMPORTANT: 4K60 hardware stability and HDMI colors are NOT validated.")

if __name__=="__main__":
    main()
