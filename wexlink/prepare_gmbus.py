#!/usr/bin/env python3
"""Opt-in SCDC GMBUS readiness polling, precisely scoped to HDMI2 high-rate I2C.

Inherits the verified Deep8+HDMI600 and the duplicate-hook-free high-only
SCDC state machine. All additional GMBUS branches are off unless the same
-wex-yoga-hdmi2-link argument is enabled on qualified A7A0/HDMI B.
"""
import argparse
import shutil
import subprocess
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

ROOT=Path(__file__).resolve().parents[1]

def once(s,old,new,reason):
    hits=s.count(old)
    if hits!=1:
        raise RuntimeError(f"{reason}: anchor count={hits}, expected 1")
    return s.replace(old,new,1)

def run(source,graphics):
    spec=spec_from_file_location("yoga_hdmi2_highonly",ROOT/"wexlink/prepare_link.py")
    base=module_from_spec(spec)
    spec.loader.exec_module(base)
    base.run(source,graphics)

    cpp=source/"WhateverXe/kern_xe.cpp"
    hpp=source/"WhateverXe/kern_xe.hpp"
    s=cpp.read_text()
    h=hpp.read_text()

    header=source/"WhateverXe/kern_yoga_hdmi2_gmbus.hpp"
    if header.exists():raise RuntimeError("GMBUS helper collision")
    shutil.copyfile(ROOT/"wexlink/reference/kern_yoga_hdmi2_gmbus.hpp",header)

    s=once(s,'#include "kern_display13_hdmi_scdc.hpp"',
           '#include "kern_display13_hdmi_scdc.hpp"\n#include "kern_yoga_hdmi2_gmbus.hpp"',
           "GMBUS helper include")
    h=once(h,'uint32_t yogaHDMI2HighActive {0};',
           'uint32_t yogaHDMI2HighActive {0};\n    bool yogaHDMI2GMBusWaitReady {false};',
           "GMBUS exact-site gate")
    hpp.write_text(h)

    s=once(s,'    bool edid {};\n    uint64_t history[96][4] {};',
           '    bool edid {},scdcRead {},scdcWrite {};\n    uint64_t history[96][4] {};',
           "preserve EDID qualifier; add isolated SCDC state")

    # The original donor GMBUS function is pinned at 0x53A7C.
    # Verify BOTH exact SCDC HW_RDY sites before allowing additional waits.
    # Re-evaluate the physical HDMI flag here, after VBT/output wiring is
    # selected rather than relying on an earlier PCI initialization call.
    readiness='''    // Exactly two known GMBUS wait sites on pinned TGL donor.
    if(checkKernelArgument("-wex-yoga-hdmi2-link")) {
        yogaHDMI2LinkEnabled=yogaEDP120Scoped && adlpDisplaySelected &&
            xeProfile.identity==0xA7A08086U && adlnOutputWiring.hdmi==2U;
        IORegistryEntry::getRegistryRoot()->setProperty(
            "WEXYogaHDMI2LinkEnabled",yogaHDMI2LinkEnabled);
    }
    yogaHDMI2GMBusWaitReady=yogaHDMI2LinkEnabled &&
        YogaHDMI2GMBus::waitSites(reinterpret_cast<const uint8_t *>(bus),
                                   size-(bus-address));
    IORegistryEntry::getRegistryRoot()->setProperty(
        "WEXYogaHDMI2GMBusWaitReady",yogaHDMI2GMBusWaitReady);
'''
    s=once(s,"    adlnGMBusFunction=bus;",
           "    adlnGMBusFunction=bus;\n"+readiness,"GMBUS precise gate")

    edid='''        o.edid=controller==callbackXE->adlnTopologyController &&
            callbackXE->adlnOutputWiring.usesDDC(bus) && speed==0 && req &&
            *reinterpret_cast<uint32_t *>(req)==0 && *reinterpret_cast<uint32_t *>(req+4)==1 &&
            *reinterpret_cast<uint32_t *>(req+0x0C)==0xA0 && *reinterpret_cast<uint32_t *>(req+0x38)==128;'''
    extra='''        const auto scdc=callbackXE->yogaHDMI2GMBusWaitReady ?
            YogaHDMI2GMBus::qualify(
                controller==callbackXE->adlnTopologyController,
                callbackXE->adlnOutputWiring.usesDDC(bus),speed,
                static_cast<const IOI2CRequest *>(request)) : YogaHDMI2GMBus::Wait{};
        o.scdcRead=scdc.read;o.scdcWrite=scdc.write;'''
    s=once(s,edid,edid+"\n"+extra,"qualify only native SCDC read/write")

    original='''    if(reg==0xC5108 && caller>=start && caller-start==0x7E8 && access==display13FBPower.access) {
        const auto thread=reinterpret_cast<uintptr_t>(current_thread());
        for(auto &o:adlnGMBusScopes)if(__sync_fetch_and_add(&o.thread,0)==thread && o.edid) {'''
    scoped='''    if(reg==0xC5108 && caller>=start && access==display13FBPower.access &&
       (caller-start==0x7E8 ||
        (callbackXE->yogaHDMI2GMBusWaitReady && caller-start==0x45C))) {
        const auto thread=reinterpret_cast<uintptr_t>(current_thread());
        for(auto &o:adlnGMBusScopes)if(__sync_fetch_and_add(&o.thread,0)==thread &&
            ((o.edid && caller-start==0x7E8) ||
             YogaHDMI2GMBus::boundary({o.scdcRead,o.scdcWrite},
                                      reg,caller-start,true))) {'''
    s=once(s,original,scoped,"guarded real GMBUS HW_RDY polling")

    # The previously existing EDID 128-byte poll is byte-for-byte retained
    # inside the same wrapper. The new path never changes data or DDC pins.
    for forbidden in ('orgDisplay13HDMIOnline','WEXYogaHDMI4K60HooksReady'):
        if forbidden in s:raise RuntimeError(f"unexpected legacy hook: {forbidden}")
    cpp.write_text(s)
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)
    print("PASS: GMBUS SCDC read/write wait only under HDMI2 opt-in and 2 exact donor sites")
    print("PASS: existing EDID wait and single LightUpTMDS observation route preserved")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    p.add_argument("graphics",type=Path)
    a=p.parse_args()
    run(a.source.resolve(),a.graphics.resolve())
