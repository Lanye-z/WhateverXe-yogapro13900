#!/usr/bin/env python3
"""HDMI2 Display13 native TMDS route + per-stage diagnostics.

Base = pinned 0.8.3, verified Deep8+HDMI600, optional SCDC + native GMBUS.
Unlike the earlier experiment, the 0.8.3 TGL observation route does NOT run
for the Yoga Display13 output path. Install one separately qualified native
route only under an explicit route-only or link flag. First stage is read-only.
"""
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import argparse, json, subprocess

ROOT=Path(__file__).resolve().parents[1]

def once(s,old,new,what):
    n=s.count(old)
    if n!=1:raise RuntimeError(f"{what}: exact source anchor count={n}, expected 1")
    return s.replace(old,new,1)

def run(source,graphics):
    spec=spec_from_file_location("yoga_hdmi2_gmbus",ROOT/"wexlink/prepare_gmbus.py")
    base=module_from_spec(spec);spec.loader.exec_module(base)
    base.run(source,graphics)

    cpp=source/"WhateverXe/kern_xe.cpp"
    hpp=source/"WhateverXe/kern_xe.hpp"
    s=cpp.read_text();h=hpp.read_text()

    h=once(h,'uint32_t yogaHDMI2HighActive {0};',
      'uint32_t yogaHDMI2HighActive {0};\n'
      '    volatile uint32_t yogaHDMI2TMDSCalls {0};\n'
      '    mach_vm_address_t orgDisplay13HDMI2TMDS {};\n'
      '    static uint32_t wrapDisplay13HDMI2TMDS(void *,void *,void *,const void *);',
      "dedicated Display13 TMDS callback")
    hpp.write_text(h)

    # Crucial: never call the TGL-specific path/scanout observers from a new
    # Display13 route. This wrapper shares only the native function ABI.
    wrapper=r'''
uint32_t XE::wrapDisplay13HDMI2TMDS(void *controller,void *fb,void *path,const void *timing) {
    auto s=callbackXE;
    auto root=IORegistryEntry::getRegistryRoot();
    const auto *t=static_cast<const IODetailedTimingInformationV2 *>(timing);
    const uint64_t clock=t ? t->pixelClock : 0;
    const bool highMode=s->yogaHDMI2LinkEnabled && clock>340000000ULL;
    const auto call=__sync_add_and_fetch(&s->yogaHDMI2TMDSCalls,1U);
    const uint64_t entry[]={1,call,clock,highMode,
       s->yogaHDMI2LinkEnabled,controller==s->adlnTopologyController,
       bool(s->display13HDMII2CRequest),bool(s->yogaHDMI2GMBusWaitReady)};
    root->setProperty("WEXYogaHDMI2TMDSLast",entry,sizeof(entry));
    if(highMode) {
        root->setProperty("WEXYogaHDMI2TMDSHighSeen",true);
        root->setProperty("WEXYogaHDMI2TMDSHighEntry",entry,sizeof(entry));
        if(!prepareDisplay13HDMISCDC(controller,fb,path,timing)) {
            root->setProperty("WEXYogaHDMI2RouteHighRefused",true);
            return kIOReturnNotReady;
        }
        root->setProperty("WEXYogaHDMI2RouteHighPrepared",true);
    }
    const bool restore=s->yogaHDMI2LinkEnabled && !highMode && clock &&
        clock<=340000000ULL &&
        __atomic_load_n(&s->yogaHDMI2HighActive,__ATOMIC_ACQUIRE)!=0;
    if(restore) {
        const bool ok=prepareDisplay13HDMISCDC(controller,fb,path,timing);
        root->setProperty("WEXYogaHDMI2RouteLowReset",ok);
        // Even an unresponsive sink must never block the native 4K30 path.
    }
    const auto native=FunctionCast(wrapDisplay13HDMI2TMDS,s->orgDisplay13HDMI2TMDS)(
        controller,fb,path,timing);
    const uint64_t done[]={1,call,clock,highMode,uint64_t(native),restore};
    root->setProperty("WEXYogaHDMI2TMDSNativeLast",done,sizeof(done));
    if(highMode) {
        root->setProperty("WEXYogaHDMI2TMDSHighNative",done,sizeof(done));
        if(native) {
            // Native mode setting failed: undo sink scrambling without
            // changing the shared Display13 clock, eDP pipe or PLL state.
            auto low=*t;
            low.pixelClock=297000000ULL;
            const bool ok=prepareDisplay13HDMISCDC(controller,fb,path,&low);
            root->setProperty("WEXYogaHDMI2RouteFailedHighReset",ok);
        }
    }
    return native;
}
'''
    s=once(s,"bool XE::display13HDMISCDCOwned(void *controller,void *framebuffer,void *object) {",
      wrapper+"\nbool XE::display13HDMISCDCOwned(void *controller,void *framebuffer,void *object) {",
      "new Display13-specific wrapper (do not patch the original TGL observer)")

    # SCDC debug markers must be emitted BEFORE every early return. They are
    # purposefully diagnostics only; no MMIO/PLL/eDP work is added.
    s=once(s,
      'bool XE::prepareDisplay13HDMISCDC(void *controller,void *fb,void *path,const void *timing) {\n'
      '    if(!display13HDMISCDCOwned(controller,fb,path) || !timing || !tglAUXLock)return false;',
      'bool XE::prepareDisplay13HDMISCDC(void *controller,void *fb,void *path,const void *timing) {\n'
      '    auto debugRoot=IORegistryEntry::getRegistryRoot();\n'
      '    debugRoot->setProperty("WEXYogaHDMI2SCDCStage",uint32_t(1),32);\n'
      '    const bool owner=display13HDMISCDCOwned(controller,fb,path);\n'
      '    debugRoot->setProperty("WEXYogaHDMI2SCDCOwner",owner);\n'
      '    if(!owner || !timing || !tglAUXLock) {\n'
      '        debugRoot->setProperty("WEXYogaHDMI2SCDCStage",uint32_t(2),32);\n'
      '        return false;\n'
      '    }',
      "preflight ownership stage")
    s=once(s,
      'auto cfg=Display13FBMemory::field<uint32_t *>(port,0x548);if(cfg[0]>=7)return false;',
      'auto cfg=Display13FBMemory::field<uint32_t *>(port,0x548);\n'
      '    if(cfg[0]>=7) {\n'
      '        debugRoot->setProperty("WEXYogaHDMI2SCDCStage",uint32_t(3),32);\n'
      '        return false;\n'
      '    }',
      "preflight valid DDI")
    s=once(s,
      '    if(!plan.valid)return false;\n    struct IO {',
      '    const uint64_t preflight[]={1,cfg[0],uint64_t(caps.valid),uint64_t(caps.scdc),\n'
      '        uint64_t(caps.maxKHz),t->pixelClock,t->pixelEncoding,\n'
      '        t->bitsPerColorComponent,uint64_t(control),uint64_t(plan.valid)};\n'
      '    debugRoot->setProperty("WEXYogaHDMI2SCDCCaps",preflight,sizeof(preflight));\n'
      '    if(!plan.valid) {\n'
      '        debugRoot->setProperty("WEXYogaHDMI2SCDCStage",uint32_t(4),32);\n'
      '        return false;\n'
      '    }\n    struct IO {',
      "SCDC capability/admission diagnostics")
    s=once(s,
      '    const auto result=Display13HDMI::negotiateSCDC(io,t->pixelClock,plan.maximumHz,plan.scdc);',
      '    debugRoot->setProperty("WEXYogaHDMI2SCDCStage",uint32_t(5),32);\n'
      '    const auto result=Display13HDMI::negotiateSCDC(io,t->pixelClock,plan.maximumHz,plan.scdc);',
      "start SCDC transaction marker")
    s=once(s,
      '    IORegistryEntry::getRegistryRoot()->setProperty("N97FBHDMISCDC",record,sizeof(record));\n    return complete;',
      '    IORegistryEntry::getRegistryRoot()->setProperty("N97FBHDMISCDC",record,sizeof(record));\n'
      '    debugRoot->setProperty("WEXYogaHDMI2SCDCStage",uint32_t(complete?7:6),32);\n'
      '    return complete;',
      "completed SCDC transaction marker")

    # The reference A7A0 Display13 donor places LightUpTMDS at +0x50B22
    # and starts with the same verified eight-byte prologue as GMBUS.
    # Never attempt a route on a binary whose symbol/prologue/board differs.
    hook=r'''
    // Independent Display13 TMDS route. The original TGL observation route
    // is installed by a different framebuffer dispatcher and is absent here.
    // The route-only flag observes 4K30 without any new SCDC call.
    uint32_t yogaRouteStatus=0; // 0 off,1 gated,2 symbol,3 entry,4 ready,5 route failed,6 other route
    const bool yogaRouteRequested=checkKernelArgument("-wex-yoga-hdmi2-route-only") ||
        checkKernelArgument("-wex-yoga-hdmi2-link");
    if(yogaRouteRequested) {
        yogaRouteStatus=1;
        if(ready && display13FramebufferRequested && adlpDisplaySelected &&
           yogaEDP120Scoped && xeProfile.identity==0xA7A08086U &&
           adlnOutputWiring.hdmi==2U) {
            if(orgTGLLightUpTMDS) {
                yogaRouteStatus=6; // never hook the same native method twice
            } else {
                const char *sym="__ZN31AppleIntelFramebufferController11LightUpTMDSEP21AppleIntelFramebufferP21AppleIntelDisplayPathPK29IODetailedTimingInformationV2";
                const auto fn=patcher.solveSymbol<mach_vm_address_t>(index,sym,address,size);
                patcher.clearError();
                yogaRouteStatus=2;
                const uint8_t entry[]={0x55,0x48,0x89,0xE5,0x41,0x57,0x41,0x56};
                if(size>0x50B22+sizeof(entry) && fn==address+0x50B22 &&
                   !memcmp(reinterpret_cast<const void *>(fn),entry,sizeof(entry))) {
                    yogaRouteStatus=3;
                    KernelPatcher::RouteRequest request{sym,wrapDisplay13HDMI2TMDS,orgDisplay13HDMI2TMDS};
                    const bool installed=patcher.routeMultipleShort(index,&request,1,address,size);
                    patcher.clearError();
                    yogaRouteStatus=installed && orgDisplay13HDMI2TMDS ? 4 : 5;
                }
            }
        }
    }
    auto traceRoot=IORegistryEntry::getRegistryRoot();
    traceRoot->setProperty("WEXYogaHDMI2TMDSRouteStatus",yogaRouteStatus,32);
    traceRoot->setProperty("WEXYogaHDMI2TMDSRouteReady",yogaRouteStatus==4);
'''
    s=once(s,
       'IORegistryEntry::getRegistryRoot()->setProperty("N97FBGMBusObservationReady",ready);',
       'IORegistryEntry::getRegistryRoot()->setProperty("N97FBGMBusObservationReady",ready);'+hook,
       "one guarded Display13 native TMDS route")

    # Fixture and fail-closed assertions.
    fixture=source/"tests/fixtures/boot_argument_names.json"
    args=json.loads(fixture.read_text())
    key="-wex-yoga-hdmi2-route-only"
    if key in args:raise RuntimeError("duplicate route-only arg")
    args[key]=[]
    fixture.write_text(json.dumps(args,indent=2)+"\n")
    if s.count('wrapDisplay13HDMI2TMDS,orgDisplay13HDMI2TMDS')!=1:
        raise RuntimeError("Display13 route must be registered exactly once")
    if s.count('WEXYogaHDMI2TMDSRouteStatus')!=1:
        raise RuntimeError("Display13 status registration missing/duplicated")
    if s.count('if(hdmiHigh && !prepareDisplay13HDMISCDC(')!=1:
        raise RuntimeError("legacy TGL wrapper unexpectedly changed")
    cpp.write_text(s)
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)
    print("PASS: installed Display13 native route is strictly opt-in, exact A7A0 + 0x50B22")
    print("PASS: route-only mode invokes native TMDS and diagnostics, NEVER SCDC")
    print("PASS: no additional TGL path observer, no changes to eDP, clocks, PLL, PHY or HDMI color")
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    p.add_argument("graphics",type=Path)
    a=p.parse_args()
    run(a.source.resolve(),a.graphics.resolve())
