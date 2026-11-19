#!/usr/bin/env python3
"""A+B: stable WM_ONLY + validated EDID Deep8, opt-in HDMI 300->600 and passive collection.

Based ONLY on wexedid/prepare_edid_ab.py. No SCDC writes, no LightUpTMDS hook,
no PHY/PLL programming, no modification to color, HPD, WM or 120Hz handlers.
"""
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import argparse
import json
import subprocess
import shutil

ROOT=Path(__file__).resolve().parents[1]
FLAG="-wex-yoga-hdmi600"
SYMBOL="__ZN21AppleIntelFramebuffer13getOnlineInfoEP21AppleIntelDisplayPathPhS2_"
ANCHOR='\tIORegistryEntry::getRegistryRoot()->setProperty("N97FBClockSetHookReady",display13FBClockSetHookReady);\n'

# The same exact-match source instruction test used by historical E1.1,
# but installed on top of the successfully validated EDID Deep8 build.
PATCH=r'''
    // Yoga A7A0 native Combo HDMI B: ONLY the max-pixel-clock admission.
    // Never install a new LightUpTMDS/getOnlineInfo runtime hook or write
    // any SCDC, PLL, PHY, color, HDMI packet or Watermark register.
    {
        auto root=IORegistryEntry::getRegistryRoot();
        const bool requested=checkKernelArgument("-wex-yoga-hdmi600");
        bool success=false;
        uint32_t status=0; // 0=off 1=gate 2=donor mismatch 3=patch failed 4=installed
        if(requested) {
            status=1;
            if(xeProfile.identity==0xA7A08086U &&
               adlpDisplaySelected && yogaEDP120Scoped &&
               adlnOutputWiring.hdmi==2U &&
               display13FramebufferRequested &&
               display13FBClockReadoutHooksReady && display13FBClockSetHookReady &&
               currentFramebuffer && currentFramebuffer->loadIndex==index) {
                const auto fn=patcher.solveSymbol<mach_vm_address_t>(
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
        root->setProperty("WEXYogaHDMI600Requested",requested);
        root->setProperty("WEXYogaHDMI600Ready",success);
        root->setProperty("WEXYogaHDMI600Status",status,32);
    }
'''

def replace_once(text,old,new,name):
    count=text.count(old)
    if count!=1:
        raise RuntimeError(f"{name}: expected exactly one source anchor, got {count}")
    return text.replace(old,new,1)

def prepare(source:Path, graphics:Path):
    spec=spec_from_file_location("yoga_verified_deep8",ROOT/"wexedid/prepare_edid_ab.py")
    mod=module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main(source,graphics)

    cpp=source/"WhateverXe/kern_xe.cpp"
    old=cpp.read_text()
    # Assert this is still the real validated color-fix source, not older HPD-only.
    for term in ('WEXYogaHDMIEDIDABApplied','WEXYogaHDMIColorLive',
                 'WEXYogaHDMIColorModeLive',
                 'checkKernelArgument("-wex-yoga-hdmi-edid-deep8")'):
        if old.count(term)!=1:
            raise RuntimeError(f"stable Deep8 baseline missing/duplicated: {term}")
    if 'checkKernelArgument("-wex-yoga-hdmi4k60")' in old:
        raise RuntimeError("unsafe previous 4K60 experiment is present")
    old_include='#include "kern_display13_color.hpp"\n'
    new_include=old_include+'#include "kern_yoga_hdmi600.hpp"\n'
    updated=replace_once(old,old_include,new_include,"header include")
    start=updated.find("bool XE::processDisplay13Framebuffer(")
    end=updated.find("\nbool XE::",start+5)
    if start<0 or end<0:raise RuntimeError("Display13 framebuffer installer method boundaries missing")
    method=updated[start:end]
    method2=replace_once(method,ANCHOR,ANCHOR+PATCH,"Display13 exact native-clock hook anchor")
    updated=updated[:start]+method2+updated[end:]
    if updated.count('checkKernelArgument("-wex-yoga-hdmi600")')!=1:
        raise RuntimeError("HDMI600 not unique")
    # Guard the implementation against accidentally mutating other functions.
    original_body=old[old.index("bool XE::processDisplay13Framebuffer("):
                      old.find("\nbool XE::",old.index("bool XE::processDisplay13Framebuffer(")+5)]
    if method2.replace(ANCHOR+PATCH,ANCHOR)!=original_body:
        raise RuntimeError("Display13 method beyond the opt-in HDMI600 block changed")
    if updated.replace(new_include,old_include).replace(ANCHOR+PATCH,ANCHOR)!=old:
        raise RuntimeError("unrelated code changed outside opt-in gate")
    cpp.write_text(updated)
    header=source/"WhateverXe/kern_yoga_hdmi600.hpp"
    if header.exists():raise RuntimeError("HDMI600 header collision")
    shutil.copyfile(ROOT/"e11/kern_yoga_hdmi600.hpp",header)
    args=source/"tests/fixtures/boot_argument_names.json"
    values=json.loads(args.read_text())
    if FLAG in values:raise RuntimeError("HDMI600 startup argument already exists")
    values[FLAG]=[]
    args.write_text(json.dumps(values,indent=2)+"\n")

    allowed={
        "WhateverXe/kern_alderlake_n.hpp","WhateverXe/kern_xe.cpp",
        "WhateverXe/kern_xe.hpp","WhateverXe/kern_display13_wm.hpp",
        "tests/fixtures/boot_argument_names.json","tests/display13_offline.py",
        "tests/dsi_port_adapter.py"
    }
    modified=set(subprocess.check_output(
        ["git","-C",str(source),"diff","--name-only"],text=True).splitlines())
    if modified!=allowed:raise RuntimeError(f"Unexpected source changes: {modified ^ allowed}")
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)

    print("PASS: generated from the original proven WM_ONLY + U27P10 Deep8 baseline.")
    print("PASS: exactly one guarded HDMI600 immediate-only patch; default OFF.")
    print("PASS: no LightUpTMDS/getOnlineInfo hook, no SCDC, PHY/PLL, WM, color or EDID changes.")
    print("PASS: original ColorTrace/ModeAudit/HPD instrumentation preserved.")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path);p.add_argument("graphics",type=Path)
    a=p.parse_args()
    prepare(a.source.resolve(),a.graphics.resolve())
