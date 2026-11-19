#!/usr/bin/env python3
"""Yoga A7A0 HDMI-B 4K60 opt-in overlay, preserving pinned 0.8.3 WM_ONLY + HDMI trace.

This is a hardware EXPERIMENT, not a claim that the sink or PHY is working.
Every injected hook is scoped and source anchors must match exactly.
No persistent EFI, EDID, graphics driver or main-branch changes.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import shutil
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/"wex4k60/reference"
BASE=ROOT/"wexhdmi/prepare_hotplug.py"

def once(s:str, old:str, new:str, label:str)->str:
    count=s.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: exact anchor count={count}, expected 1")
    return s.replace(old,new,1)

def method(s:str,name:str):
    start=s.find(name)
    if start<0 or s.find(name,start+1)>=0:
        raise RuntimeError(f"method not unique: {name}")
    opened=s.find("{",start)
    if opened<0:raise RuntimeError(f"method opening missing: {name}")
    depth=0
    # Braces in comments may confuse a blind parser, but each known source
    # method is checked by its unique declaration AND validated after edit.
    for i in range(opened,len(s)):
        if s[i]=="{":depth+=1
        elif s[i]=="}":
            depth-=1
            if depth==0:return start,i+1
    raise RuntimeError(f"method close missing: {name}")

def replace_in_method(s,name,old,new,label):
    a,b=method(s,name)
    part=once(s[a:b],old,new,label)
    return s[:a]+part+s[b:]

def run(source:Path,graphics:Path):
    spec=spec_from_file_location("yoga_first_hpd",BASE)
    mod=module_from_spec(spec);spec.loader.exec_module(mod)
    mod.run(source,graphics)
    cpp=source/"WhateverXe/kern_xe.cpp"
    hpp=source/"WhateverXe/kern_xe.hpp"
    orig=cpp.read_text();hdr=hpp.read_text()

    # Use read-only capability parsing and an SCDC state machine from a tested
    # A7A0 notebook, not its power-control or port-selection patches.
    for filename in ("kern_display13_hdmi_caps.hpp","kern_display13_hdmi_scdc.hpp"):
        target=source/"WhateverXe"/filename
        if target.exists():raise RuntimeError(f"header collision: {filename}")
        shutil.copyfile(REF/filename,target)

    orig=once(orig,'#include "kern_display13_fb_irq.hpp"',
      '#include "kern_display13_fb_irq.hpp"\n'
      '#include "kern_display13_hdmi_caps.hpp"\n'
      '#include "kern_display13_hdmi_scdc.hpp"\n'
      '#include <IOKit/i2c/IOI2CInterface.h>\n'
      '#include <IOKit/graphics/IOGraphicsTypes.h>',
      "HDMI capabilities and native I2C includes")

    hdr=once(hdr,'bool yogaEDP120Scoped {false};',
      'bool yogaEDP120Scoped {false};\n'
      '    // HDMI 2.0 high-rate path remains default OFF, only physical A7A0 Combo B.\n'
      '    bool yogaHDMI4K60Enabled {false};',
      "eDP feature gate")
    hdr=once(hdr,'static uint32_t wrapAlderLakeNPortDDC(OSObject *port,uint32_t block,uint8_t *data,bool force);',
      'static uint32_t wrapAlderLakeNPortDDC(OSObject *port,uint32_t block,uint8_t *data,bool force);\n'
      '    mach_vm_address_t orgDisplay13HDMIOnline {},display13HDMII2CRequest {};\n'
      '    static uint32_t wrapDisplay13HDMIOnline(IOService *,OSObject *,uint8_t *,uint8_t *);\n'
      '    static bool prepareDisplay13HDMISCDC(void *,void *,void *,const void *);\n'
      '    static bool display13HDMISCDCTransfer(void *,void *,void *,bool,uint8_t,uint8_t &);\n'
      '    static bool display13HDMISCDCOwned(void *,void *,void *);\n'
      '    static void configureDisplay13HDMISDR(void *,void *);',
      "HDMI optional methods")
    (hpp).write_text(hdr)

    scope='pci->setProperty("WEXYogaEDP120Scoped",yogaEDP120Scoped);'
    scoped=scope+'''
    // Keep RGB8/EDID overrides, eDP admission/WM and HPD trace untouched.
    // The machine's qualified Combo B HDMI must be present in its firmware VBT.
    yogaHDMI4K60Enabled=yogaEDP120Scoped && adlpDisplaySelected &&
        board.hdmi==2U && checkKernelArgument("-wex-yoga-hdmi4k60");
    pci->setProperty("WEXYogaHDMI4K60Enabled",yogaHDMI4K60Enabled);'''
    orig=once(orig,scope,scoped,"scoped A7A0/HDMI-B enable")

    methods=(REF/"hdmi_runtime_methods.inc").read_text()
    if any(methods.count(sig)!=1 for sig in (
      "bool XE::display13HDMISCDCOwned(",
      "bool XE::display13HDMISCDCTransfer(",
      "bool XE::prepareDisplay13HDMISCDC(",
      "uint32_t XE::wrapDisplay13HDMIOnline(")):
        raise RuntimeError("reference native runtime methods incomplete")
    # The Air14 adapter already checks native port binding, controller ownership,
    # a live IORecursiveLock and cache generation during every SCDC transaction.
    methods=once(methods,
       'if(!s->display13FramebufferRequested || !s->display13BootReady || !s->display13HDMII2CRequest ||',
       'if(!s->yogaHDMI4K60Enabled || !s->display13FramebufferRequested || !s->display13BootReady || !s->display13HDMII2CRequest ||',
       "SCDC opt-in ownership")
    methods=once(methods,'if(result || !online || !*online || !fb || !path || !tglAUXLock ||',
       'if(!s->yogaHDMI4K60Enabled || result || !online || !*online || !fb || !path || !tglAUXLock ||',
       "HDMI online opt-in")
    orig=once(orig,'uint32_t XE::wrapAlderLakeNPortDDC(OSObject *port,uint32_t block,uint8_t *data,bool force) {',
       methods+'\nuint32_t XE::wrapAlderLakeNPortDDC(OSObject *port,uint32_t block,uint8_t *data,bool force) {',
       "runtime methods before DDC")
    # Explicitly tie cached capabilities to connection generation, never a
    # monitor name/serial. Disconnect/replacement invalidates the old cache.
    cache='''    if(selected && config && config[0]<7 && tglAUXLock &&
       callbackXE->yogaHDMI4K60Enabled && callbackXE->display13HDMIPort(port)) {
        IOSimpleLockLock(tglAUXLock);
        auto &cached=display13HDMICache[config[0]];
        if(block==1 || result || cached.port!=port) {
            ++cached.generation;
            cached.port=result ? nullptr : port;
            cached.caps={};
            cached.edid.reset();
        }
        if(cached.port==port && cached.edid.observe(block,data,!result)) {
            if(block!=1)++cached.generation;
            cached.caps=cached.edid.caps();
        }
        IOSimpleLockUnlock(tglAUXLock);
    }'''
    orig=replace_in_method(orig,
      'uint32_t XE::wrapAlderLakeNPortDDC(OSObject *port,uint32_t block,uint8_t *data,bool force) {',
      'cachePanelDepth(port,block,data,result);',
      'cachePanelDepth(port,block,data,result);\n'+cache,
      "generation-safe EDID caching")

    # Colour depth: for SDR RGB, the stock donor calculates TMDS at pixel
    # clock and only reliably supports 8bpc. This is NOT a new color profile.
    sdr=(REF/"hdmi_sdr_gcp_methods.inc").read_text()
    sdr=sdr[:sdr.index('void XE::configureDisplay13HDMIGCP(')]
    sdr=once(sdr,'if(!s->display13FramebufferRequested || !s->display13BootReady || !fb || !timing ||',
      'if(!s->yogaHDMI4K60Enabled || !s->display13FramebufferRequested || !s->display13BootReady || !fb || !timing ||',
      "SDR gate")
    orig=once(orig,'void XE::wrapTGLModeTiming(void *controller,void *fb,void *timing) {',
      sdr+'\nvoid XE::wrapTGLModeTiming(void *controller,void *fb,void *timing) {',
      "native mode copy helper")
    orig=replace_in_method(orig,
      'void XE::wrapTGLModeTiming(void *controller,void *fb,void *timing) {',
      'FunctionCast(wrapTGLModeTiming,callbackXE->orgTGLModeTiming)(controller,fb,timing);',
      'FunctionCast(wrapTGLModeTiming,callbackXE->orgTGLModeTiming)(controller,fb,timing);\n'
      '    if(callbackXE->yogaHDMI4K60Enabled)configureDisplay13HDMISDR(fb,timing);',
      "RGB8 SDR mode mapping")

    # The SCDC sink handshake is performed BEFORE the donor enables TMDS.
    # If the sink fails to acknowledge the required high-rate settings, do
    # not assert high-rate source flags or run a mismatched HDMI link.
    light='uint32_t XE::wrapTGLLightUpTMDS(void *controller, void *fb, void *path, const void *timing) {'
    a,b=method(orig,light)
    frag=orig[a:b]
    needle='const auto r = FunctionCast(wrapTGLLightUpTMDS, callbackXE->orgTGLLightUpTMDS)(controller, fb, path, timing);'
    frag=once(frag,needle,
      'if(callbackXE->yogaHDMI4K60Enabled && !prepareDisplay13HDMISCDC(controller,fb,path,timing))\n'
      '        return kIOReturnNotReady;\n\t'+needle,
      "SCDC before native TMDS lightup")
    orig=orig[:a]+frag+orig[b:]

    # The upstream 0.8.3 output frontend must remain independently functional.
    # Add a separately guarded route; its failure must not turn off Metal/eDP.
    route='''    if(yogaHDMI4K60Enabled) {
        bool ok=false;
        const char *online="__ZN21AppleIntelFramebuffer13getOnlineInfoEP21AppleIntelDisplayPathPhS2_";
        const char *light="__ZN31AppleIntelFramebufferController11LightUpTMDSEP21AppleIntelFramebufferP21AppleIntelDisplayPathPK29IODetailedTimingInformationV2";
        auto a=patcher.solveSymbol<mach_vm_address_t>(index,online,address,size);
        patcher.clearError();
        auto b=patcher.solveSymbol<mach_vm_address_t>(index,light,address,size);
        patcher.clearError();
        const uint8_t entry[]={0x55,0x48,0x89,0xE5};
        if(ready && size>0x53A30 &&
           a==address+0x2E232 && b==address+0x50B22 &&
           !memcmp(reinterpret_cast<void *>(a),entry,sizeof(entry)) &&
           !memcmp(reinterpret_cast<void *>(b),entry,sizeof(entry))) {
            KernelPatcher::RouteRequest hooks[] {
                {online,wrapDisplay13HDMIOnline,orgDisplay13HDMIOnline},
                {light,wrapTGLLightUpTMDS,orgTGLLightUpTMDS}
            };
            ok=patcher.routeMultipleShort(index,hooks,arrsize(hooks),address,size);
            patcher.clearError();
        }
        IORegistryEntry::getRegistryRoot()->setProperty("WEXYogaHDMI4K60HooksReady",ok);
    }'''
    orig=replace_in_method(orig,
      'bool XE::processDisplay13FramebufferOutput(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size) {',
      'const bool ready=patcher.routeMultipleShort(index,routes,arrsize(routes),address,size);patcher.clearError();',
      'const bool ready=patcher.routeMultipleShort(index,routes,arrsize(routes),address,size);patcher.clearError();\n'+route,
      "optional HDMI native route")

    # Do not block the normal Display13 output hooks if the optional native
    # I2C symbol isn't present. The opt-in high-rate path then refuses.
    i2c='''    if(yogaHDMI4K60Enabled) {
        const char *name="__ZN31AppleIntelFramebufferController14hwDoI2CRequestEjjjP14IOI2CBusTimingP12IOI2CRequest";
        auto fn=patcher.solveSymbol<mach_vm_address_t>(index,name,address,size);
        patcher.clearError();
        const uint8_t entry[]={0x55,0x48,0x89,0xE5,0x48,0x83,0xEC,0x20};
        if(fn==address+0x53A20 && size>0x53A20+sizeof(entry) &&
            !memcmp(reinterpret_cast<void *>(fn),entry,sizeof(entry)))
            display13HDMII2CRequest=fn;
        IORegistryEntry::getRegistryRoot()->setProperty("WEXYogaHDMI4K60I2CReady",bool(display13HDMII2CRequest));
    }'''
    orig=replace_in_method(orig,
      'bool XE::processDisplay13FramebufferOutput(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size) {',
      'const bool ready=patcher.routeMultipleShort(index,routes,arrsize(routes),address,size);patcher.clearError();',
      i2c+'\n    const bool ready=patcher.routeMultipleShort(index,routes,arrsize(routes),address,size);patcher.clearError();',
      "native I2C symbol exact qualification")

    cpp.write_text(orig)
    # Keep the upstream panel-depth fixture active. Its minimal synthetic XE
    # does not include the new opt-in HDMI member, so add a no-op mock only
    # to this test fixture; panel behaviour and assertions stay unchanged.
    panel_test=source/"tests/tgl_panel_depth_route.py"
    panel=panel_test.read_text()
    panel=once(panel," bool display13FramebufferRequested=false;",
      " bool display13FramebufferRequested=false; bool yogaHDMI4K60Enabled=false;\\n"
      " static void configureDisplay13HDMISDR(void*,void*){};",
      "synthetic panel fixture's no-op HDMI gate")
    panel_test.write_text(panel)
    fixture=source/"tests/fixtures/boot_argument_names.json"
    args=json.loads(fixture.read_text())
    flag="-wex-yoga-hdmi4k60"
    if flag in args:raise RuntimeError("4K60 flag already registered")
    args[flag]=[]
    fixture.write_text(json.dumps(args,indent=2)+"\n")

    # The inherited first-hotplug HPD gate stays default OFF. Source output
    # is a new opt-in Kext with no disk binary patch and no HDMI color override.
    changed=set(subprocess.check_output(
      ["git","-C",str(source),"diff","--name-only"],text=True).splitlines())
    expected={"WhateverXe/kern_alderlake_n.hpp",
      "WhateverXe/kern_xe.cpp","WhateverXe/kern_xe.hpp",
      "WhateverXe/kern_display13_wm.hpp",
      "tests/fixtures/boot_argument_names.json",
      "tests/display13_offline.py","tests/dsi_port_adapter.py",
      "tests/tgl_panel_depth_route.py"}
    if changed!=expected:raise RuntimeError(f"unexpected modified tracked paths: {changed ^ expected}")
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)
    print("PREPARED Yoga A7A0 HDMI 4K60 opt-in over 0.8.3 WM_ONLY + existing HPD trace.")
    print("No EFI, EDID override, Graphics package, IRQ, TC DP, Thunderbolt or default mode changes.")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path);p.add_argument("graphics",type=Path)
    a=p.parse_args()
    run(a.source.resolve(),a.graphics.resolve())
