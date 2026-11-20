#!/usr/bin/env python3
"""Add an opt-in TC5 MST-capability -> SST compatibility hook to the
already-tested Yoga 0.8.3 Deep8/HDMI600/WM_ONLY/DP diagnostic build.

This generator intentionally edits only generated upstream Source, never EFI.
Do not import Thunderbolt/USB4 patches or the old acer/current driver wholesale.
"""
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import argparse
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MASK_FLAG = "-wex-yoga-tc5-sst"
OBSERVE_FLAG = "-wex-yoga-tc5-sst-observe"

def replace_once(s, before, after, label):
    count = s.count(before)
    if count != 1:
        raise RuntimeError(f"{label}: require one exact anchor, got {count}")
    return s.replace(before, after, 1)

WRAPPER = r'''
// 0.8.3 Yoga A7A0 / DDI5 only: retain the acer/current SST compatibility
// technique without replacing the donor's DP link training, PHY or MST logic.
// The native getDPCDInfo result is always preserved.
uint64_t XE::wrapDisplay13DPCDInfo(void *raw) {
    auto s=callbackXE;
    const auto result=FunctionCast(wrapDisplay13DPCDInfo,s->orgDisplay13DPCDInfo)(raw);
    auto port=static_cast<OSObject *>(raw);
    auto config=port && port->getMetaClass()->getClassSize()>=0x580
        ? Display13FBMemory::field<uint32_t *>(port,0x548) : nullptr;
    if(!s->yogaSSTHookReady || !config || config[0]!=5 ||
       !(s->adlnOutputWiring.typeC&(1U<<5)))return result;
    auto bytes=static_cast<uint8_t *>(raw);
    const uint32_t original=bytes[0x1E];
    const uint32_t mstMode=bytes[0x117];
    const bool masked=s->yogaSSTMaskRequested && original!=0;
    if(masked)bytes[0x1E]=0;

    static uint32_t count,hidden;
    const auto sequence=__atomic_add_fetch(&count,1,__ATOMIC_RELAXED);
    const auto masks=masked?__atomic_add_fetch(&hidden,1,__ATOMIC_RELAXED)
                           :__atomic_load_n(&hidden,__ATOMIC_RELAXED);
    // Bound registry logging: do not spam training/reconnect hot paths.
    if(sequence<=8) {
        uint32_t state[]={1,sequence,5,original,bytes[0x1E],mstMode,
                          static_cast<uint32_t>(result),masked?1U:0U,masks};
        auto root=IORegistryEntry::getRegistryRoot();
        if(sequence==1)root->setProperty("WEXYogaSSTFirstDPCD",state,sizeof(state));
        root->setProperty("WEXYogaSSTLastDPCD",state,sizeof(state));
        if(masked && masks==1)root->setProperty("WEXYogaSSTCapabilityMasked",true);
    }
    return result;
}
'''

INSTALL = r'''
    // Separate from Thunderbolt/USB4 and all HDMI/eDP hooks. Install no
    // new route and publish no extra IORegistry data without user opt-in.
    {
        const bool requested=checkKernelArgument("-wex-yoga-tc5-sst");
        const bool observe=checkKernelArgument("-wex-yoga-tc5-sst-observe");
        const bool conflict=requested && observe;
        const bool eligible=xeProfile.identity==0xA7A08086U &&
            adlpDisplaySelected && display13FramebufferRequested &&
            (adlnOutputWiring.typeC&(1U<<5)) &&
            (adlnOutputWiring.links()&(1U<<5)) &&
            currentFramebuffer && currentFramebuffer->loadIndex==index;
        yogaSSTMaskRequested=requested && !observe && eligible;
        yogaSSTHookReady=false;
        if(requested || observe) {
            uint32_t status=conflict?5:1; // gated=1,mismatch=2,route=3,ready=4,conflict=5
            if(!conflict && eligible) {
                const char *sym="__ZN14AppleIntelPort11getDPCDInfoEv";
                const uint8_t prologue[]={0x55,0x48,0x89,0xE5,0x41,0x57,0x41,0x56};
                const auto fn=patcher.solveSymbol<mach_vm_address_t>(index,sym,address,size);
                patcher.clearError();
                status=2;
                if(fn==address+0x1DE0E &&
                   !memcmp(reinterpret_cast<void *>(fn),prologue,sizeof(prologue))) {
                    KernelPatcher::RouteRequest route(sym,wrapDisplay13DPCDInfo,orgDisplay13DPCDInfo);
                    yogaSSTHookReady=patcher.routeMultipleShort(index,&route,1,address,size);
                    patcher.clearError();
                    status=yogaSSTHookReady?4:3;
                }
            }
            auto root=IORegistryEntry::getRegistryRoot();
            root->setProperty("WEXYogaSSTRequested",requested);
            root->setProperty("WEXYogaSSTObserveRequested",observe);
            root->setProperty("WEXYogaSSTHookReady",yogaSSTHookReady);
            root->setProperty("WEXYogaSSTHookStatus",status,32);
        }
    }
'''

def prepare(source: Path, graphics: Path):
    # The exact current-EFI implementation: WM_ONLY -> EDID Deep8 ->
    # HDMI600 admission -> noninvasive DDI5 diagnostics.
    upstream = spec_from_file_location("yoga_dpdiag_base", ROOT/"wexdpdiag/prepare.py")
    module = module_from_spec(upstream)
    upstream.loader.exec_module(module)
    module.run(source, graphics)

    hpp=source/"WhateverXe/kern_xe.hpp"
    cpp=source/"WhateverXe/kern_xe.cpp"
    h=hpp.read_text()
    s=cpp.read_text()

    if "wrapDisplay13DPCDInfo" in h or "wrapDisplay13DPCDInfo" in s:
        raise RuntimeError("DPCD SST wrapper already present")
    header_anchor=" bool display13FBSSTHooksReady {};"
    # Keep the original XE object layout as a prefix: append all new
    # instance fields at the end, adding only a static method near the TC API.
    header_fields="\n static uint64_t wrapDisplay13DPCDInfo(void *);"
    end_anchor="    DVMTCalcFix modDVMTCalcFix;\n};"
    tail_fields=(
        "\n    // Yoga DDI5 SST: new fields at tail, original member offsets unchanged."
        "\n    bool yogaSSTMaskRequested {false};"
        "\n    bool yogaSSTHookReady {false};"
        "\n    mach_vm_address_t orgDisplay13DPCDInfo {};"
    )
    h2=replace_once(h,header_anchor,header_anchor+header_fields,"static function declaration")
    h2=replace_once(h2,end_anchor,
        "    DVMTCalcFix modDVMTCalcFix;"+tail_fields+"\n};",
        "append fields at class tail")

    wrapper_anchor="bool XE::processDisplay13FramebufferTC("
    s2=replace_once(s,wrapper_anchor,WRAPPER+"\n"+wrapper_anchor,"TC wrapper insertion")
    installer_anchor=(
        "    display13FBDPHooksReady=true;display13FBPower.tcSupported=true;"
        "return processDisplay13Training(patcher,index,address,size);"
    )
    installer=INSTALL+"\n"
    s3=replace_once(s2,installer_anchor,installer+installer_anchor,"TC route registration")
    if s3.replace(installer+installer_anchor,installer_anchor).replace(
            WRAPPER+"\n"+wrapper_anchor,wrapper_anchor)!=s:
        raise RuntimeError("Unexpected mutations outside DPCD wrapper and TC registration")
    if h2.replace("    DVMTCalcFix modDVMTCalcFix;"+tail_fields+"\n};",
                  end_anchor).replace(header_anchor+header_fields,header_anchor)!=h:
        raise RuntimeError("Unexpected mutations outside additive XE tail and declaration")

    hpp.write_text(h2)
    cpp.write_text(s3)

    flags=source/"tests/fixtures/boot_argument_names.json"
    values=json.loads(flags.read_text())
    for flag in (MASK_FLAG,OBSERVE_FLAG):
        if flag in values:
            raise RuntimeError(f"Boot argument already exists: {flag}")
        values[flag]=[]
    flags.write_text(json.dumps(values,indent=2)+"\n")

    if s3.count("KernelPatcher::RouteRequest route(sym,wrapDisplay13DPCDInfo,orgDisplay13DPCDInfo);")!=1:
        raise RuntimeError("DPCD route must be unique")
    for forbidden in ("orgDisplay13HDMI2TMDS", "-wex-yoga-hdmi2-link",
                      "-wex-yoga-hdmi4k60"):
        if forbidden in s3:raise RuntimeError(f"Forbidden legacy experiment: {forbidden}")
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)
    print("PASS: 0.8.3 current-EFI source chain retained")
    print("PASS: native DPCD result preserved; scoped A7A0/DDI5 hook; default OFF")
    print("PASS: observe-only and MST-cache mask A/B; no Type4/USB4 changes")
    print("PASS: no MMIO, AUX, PHY, PLL, HPD, or link training override")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("graphics",type=Path)
    args=parser.parse_args()
    prepare(args.source.resolve(),args.graphics.resolve())
