#!/usr/bin/env python3
"""Generate optional native setColorMode audit / two guarded policy trials.

Source base: exact pinned WhateverXe 0.8.3 + WM_ONLY(V2) + HPD + ColorTrace.
No EDID changes; no explicit MMIO writes; does not touch EFI or main.
All experiments default OFF, instrumentation is opt-in.
"""
import argparse
import json
import subprocess
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec

SYMBOL="__ZN31AppleIntelFramebufferController12setColorModeEP21AppleIntelFramebufferP21AppleIntelDisplayPathjjbPK29IODetailedTimingInformationV2"

GLOBALS=r'''
// Passive numeric callsite tracing; default OFF, no IORegistry write in modeset.
static volatile uint32_t yogaColorModeSinkU27 {};
static volatile uint32_t yogaColorModeCount {};
static volatile uint32_t yogaColorModeSlots[24][12] {};
static bool yogaColorModeSerialize(void *,void *,OSSerialize *serializer) {
    if(!serializer)return false;
    uint32_t words[3+24*12] {};
    words[0]=1;words[1]=__atomic_load_n(&yogaColorModeCount,__ATOMIC_ACQUIRE);words[2]=24;
    for(unsigned j=0;j<24;++j)
        for(unsigned k=0;k<12;++k)
            words[3+j*12+k]=__atomic_load_n(&yogaColorModeSlots[j][k],__ATOMIC_ACQUIRE);
    auto data=OSData::withBytes(words,sizeof(words));
    if(!data)return false;
    const bool ok=data->serialize(serializer);
    data->release();return ok;
}
void XE::wrapDisplay13YogaColorMode(void *controller,void *fb,void *path,
                                      uint32_t mode,uint32_t depth,bool flag,const void *timing) {
    auto self=callbackXE;
    auto p=static_cast<OSObject *>(path);
    uint32_t pipe=UINT32_MAX,ddi=UINT32_MAX;
    bool portMatch=false;
    // The same native Display13 association offsets are already used by
    // WM, scanout and gamma observers in pinned 0.8.3.
    if(p && p->getMetaClass()->getClassSize()>=0x3730) {
        pipe=Display13FBMemory::field<uint32_t>(p,0x3640);
        auto port=Display13FBMemory::field<OSObject *>(p,0x3648);
        if(port && port->getMetaClass()->getClassSize()>=0x580) {
            auto conf=Display13FBMemory::field<uint32_t *>(port,0x548);
            if(conf)ddi=conf[0];
            portMatch=conf && conf[0]==1 && pipe<3 &&
                Display13FBMemory::field<void *>(p,0x32B0)==fb &&
                Display13FBTopology::selected(self->adlnPlatform,conf,self->adlnOutputWiring);
        }
    }
    const bool board=self->adlpDisplaySelected && self->yogaEDP120Scoped &&
        self->adlnOutputWiring.hdmi==2U &&
        self->display13FramebufferRequested &&
        controller==display13FBPower.controller;
    const bool sink=__atomic_load_n(&yogaColorModeSinkU27,__ATOMIC_ACQUIRE)!=0;
    const bool matched=board && portMatch && sink;
    const bool test8=checkKernelArgument("-wex-yoga-hdmi-bpc8-test");
    const bool testRGB=checkKernelArgument("-wex-yoga-hdmi-rgb8-test");
    const bool audit=checkKernelArgument("-wex-yoga-hdmi-mode-audit") || test8 || testRGB;
    const bool conflict=test8 && testRGB;
    const auto variant=testRGB ? YogaHDMIColorPolicy::Variant::Rgb8 :
        test8 ? YogaHDMIColorPolicy::Variant::Bpc8 :
        YogaHDMIColorPolicy::Variant::Audit;
    const auto result=YogaHDMIColorPolicy::decide(mode,depth,variant,matched,conflict);
    if(audit) {
        const uint32_t seq=__atomic_fetch_add(&yogaColorModeCount,1U,__ATOMIC_ACQ_REL)+1U;
        const unsigned slot=(seq-1U)%24U;
        auto row=yogaColorModeSlots[slot];
        // Set sequence last, so observers can identify a complete sample.
        __atomic_store_n(&row[0],0U,__ATOMIC_RELAXED);
        __atomic_store_n(&row[1],matched?1U:0U,__ATOMIC_RELAXED);
        __atomic_store_n(&row[2],ddi,__ATOMIC_RELAXED);
        __atomic_store_n(&row[3],pipe,__ATOMIC_RELAXED);
        __atomic_store_n(&row[4],mode,__ATOMIC_RELAXED);
        __atomic_store_n(&row[5],depth,__ATOMIC_RELAXED);
        __atomic_store_n(&row[6],flag?1U:0U,__ATOMIC_RELAXED);
        __atomic_store_n(&row[7],result.mode,__ATOMIC_RELAXED);
        __atomic_store_n(&row[8],result.depth,__ATOMIC_RELAXED);
        __atomic_store_n(&row[9],static_cast<uint32_t>(result.outcome),__ATOMIC_RELAXED);
        __atomic_store_n(&row[10],sink?1U:0U,__ATOMIC_RELAXED);
        __atomic_store_n(&row[11],board && portMatch?1U:0U,__ATOMIC_RELAXED);
        __atomic_store_n(&row[0],seq,__ATOMIC_RELEASE);
    }
    FunctionCast(wrapDisplay13YogaColorMode,self->orgDisplay13YogaColorMode)(
        controller,fb,path,result.mode,result.depth,flag,timing);
}
'''
DDC_ADD=r'''    // Exact AOC U27P10 identity only; keep native EDID bytes unchanged.
    // Overwrite cached identity for EVERY successful HDMI-B base read,
    // including a normal 1080p monitor replacing the U27P10.
    if(!result && selected && config && config[0]==1 && data && block==1 &&
       callbackXE->adlpDisplaySelected && callbackXE->yogaEDP120Scoped &&
       callbackXE->adlnOutputWiring.hdmi==2U &&
       !memcmp(data,"\x00\xff\xff\xff\xff\xff\xff\x00",8)) {
        const bool exact=data[8]==0x05 && data[9]==0xE3 &&
            data[10]==0x10 && data[11]==0x27;
        __atomic_store_n(&yogaColorModeSinkU27,exact?1U:0U,__ATOMIC_RELEASE);
    }
'''
ROUTE_ADD=r'''    // This hook is independently optional; failure never disables native
    // Display13, gamma, eDP120, HDMI HPD or ColorTrace.
    if(checkKernelArgument("-wex-yoga-hdmi-mode-audit") ||
       checkKernelArgument("-wex-yoga-hdmi-bpc8-test") ||
       checkKernelArgument("-wex-yoga-hdmi-rgb8-test")) {
        const char *symbol="__ZN31AppleIntelFramebufferController12setColorModeEP21AppleIntelFramebufferP21AppleIntelDisplayPathjjbPK29IODetailedTimingInformationV2";
        const auto fn=patcher.solveSymbol<mach_vm_address_t>(index,symbol,address,size);
        patcher.clearError();
        const uint8_t prologue[]={0x55,0x48,0x89,0xE5};
        bool modeReady=fn>=address && fn+sizeof(prologue)<=address+size &&
            !memcmp(reinterpret_cast<void *>(fn),prologue,sizeof(prologue));
        if(modeReady) {
            KernelPatcher::RouteRequest route(symbol,wrapDisplay13YogaColorMode,orgDisplay13YogaColorMode);
            modeReady=patcher.routeMultipleShort(index,&route,1,address,size);
            patcher.clearError();
        }
        auto root=IORegistryEntry::getRegistryRoot();
        root->setProperty("WEXYogaHDMIColorModeHookReady",modeReady);
        if(modeReady)if(auto audit=OSSerializer::forTarget(nullptr,yogaColorModeSerialize)) {
            root->setProperty("WEXYogaHDMIColorModeLive",audit);
            audit->release();
        }
    }
'''

def once(s,a,b,label):
    n=s.count(a)
    if n!=1:raise RuntimeError(f"{label}: expected 1 anchor; got {n}")
    return s.replace(a,b,1)

def main(src:Path,graphics:Path):
    root=Path(__file__).resolve().parents[1]
    spec=spec_from_file_location("wexcolor",root/"wexcolor/prepare_colortrace.py")
    mod=module_from_spec(spec);spec.loader.exec_module(mod)
    mod.main(src,graphics)
    cpp=src/"WhateverXe/kern_xe.cpp"
    hpp=src/"WhateverXe/kern_xe.hpp"
    s=cpp.read_text()
    s=once(s,'#include "kern_display13_fb_irq.hpp"',
        '#include "kern_display13_fb_irq.hpp"\n#include "kern_yoga_hdmi_color_policy.hpp"',
        "include policy header")
    s=once(s,'bool XE::processDisplay13FramebufferColor(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size) {',
        GLOBALS+'\nbool XE::processDisplay13FramebufferColor(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size) {',
        "insert pre-mode observer and wrapper")
    start=s.index('bool XE::processDisplay13FramebufferColor(KernelPatcher &patcher')
    end=s.index('\nvoid XE::wrapAlderLakeNPreGamma(',start)
    body=s[start:end]
    body=once(body,'    return ready;\n}',ROUTE_ADD+'    return ready;\n}',"opt-in mode hook")
    s=s[:start]+body+s[end:]
    s=once(s,'    cachePanelDepth(port,block,data,result);\n    // Exact hardware-qualified',
        '    cachePanelDepth(port,block,data,result);\n'+DDC_ADD+'    // Exact hardware-qualified',
        "identify sink without EDID rewrite")
    cpp.write_text(s)
    h=hpp.read_text()
    h=once(h,'    bool processDisplay13FramebufferColor(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size);',
      '    mach_vm_address_t orgDisplay13YogaColorMode {};\n'
      '    static void wrapDisplay13YogaColorMode(void *,void *,void *,uint32_t,uint32_t,bool,const void *);\n'
      '    bool processDisplay13FramebufferColor(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size);',
      "insert method declaration")
    hpp.write_text(h)
    (src/"WhateverXe/kern_yoga_hdmi_color_policy.hpp").write_text(
       (root/"wexrgb/kern_yoga_hdmi_color_policy.hpp").read_text())
    args=src/"tests/fixtures/boot_argument_names.json"
    values=json.loads(args.read_text())
    for flag in ("-wex-yoga-hdmi-mode-audit",
                 "-wex-yoga-hdmi-bpc8-test","-wex-yoga-hdmi-rgb8-test"):
        if flag in values:raise RuntimeError(f"existing flag {flag}")
        values[flag]=[]
    args.write_text(json.dumps(values,indent=2)+"\n")
    changed=set(subprocess.check_output(["git","-C",str(src),"diff","--name-only"],
                                         text=True).splitlines())
    expected={"WhateverXe/kern_alderlake_n.hpp","WhateverXe/kern_xe.cpp",
              "WhateverXe/kern_xe.hpp","WhateverXe/kern_display13_wm.hpp",
              "tests/fixtures/boot_argument_names.json",
              "tests/display13_offline.py","tests/dsi_port_adapter.py"}
    if changed!=expected:raise RuntimeError(f"unexpected source diff: {changed ^ expected}")
    if s.count("WEXYogaHDMIColorModeLive")!=1:raise RuntimeError("missing output")
    subprocess.run(["git","-C",str(src),"diff","--check"],check=True)
    print("PASS: original HDMI/WM/HPD/ColorTrace source preserved")
    print("PASS: opt-in native colour mode route, strict A7A0+DDI B+U27P10 qualification")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("src",type=Path);p.add_argument("graphics",type=Path)
    args=p.parse_args()
    main(args.src.resolve(),args.graphics.resolve())
