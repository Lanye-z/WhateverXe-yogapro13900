#!/usr/bin/env python3
"""A7A0 Display13 multi-output AUDIT build from the exactly pinned V2/WM_ONLY.

The E1.0 'multi-output repair' is already present in official 0.8.3:
VBT board wiring, display13 multiOutputWiring, TC / DP-alt, IRQ, hotplug.
Do not overwrite a newer implementation with older 0.7.0 sources.
This adds only A7A0-gated, opt-in read-only registry snapshots. No
port policy, HDMI clock, link training, WM, EDID or display register writes.
"""
import argparse
import json
import subprocess
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

def exact(s,original,replacement,context):
    n=s.count(original)
    if n!=1:raise RuntimeError('%s: expected one exact anchor, got %d'%(context,n))
    return s.replace(original,replacement,1)

def run(src,graphics):
    root=Path(__file__).resolve().parents[1]
    spec=spec_from_file_location("yoga_120",root/"wex120/prepare_120.py")
    v2=module_from_spec(spec)
    spec.loader.exec_module(v2)
    v2.prepare(src,graphics,"V2")
    cppfile=src/"WhateverXe/kern_xe.cpp"
    cpp=cppfile.read_text()
    gate='''const auto board=display13BoardWiring(pci);adlnOutputWiring=board;'''
    telemetry='''const auto board=display13BoardWiring(pci);adlnOutputWiring=board;
    // E1.0/acer/current multi-output framework is already included
    // upstream; publish the actual selected VBT ports without changing them.
    if(pci->configRead16(0x02)==0xA7A0 &&
       checkKernelArgument("-wex-yoga-multi-audit")) {
        uint32_t wexYogaMultiWiring[] {
            1U, uint32_t(board.valid), uint32_t(board.described()),
            board.selected(),board.panel,board.hdmi,board.dp,board.typeC,
            board.hotplug(),board.links()
        };
        pci->setProperty("WEXYogaMultiWiring",wexYogaMultiWiring,sizeof(wexYogaMultiWiring));
        IORegistryEntry::getRegistryRoot()->setProperty(
            "WEXYogaMultiWiring",wexYogaMultiWiring,sizeof(wexYogaMultiWiring));
    }'''
    cpp=exact(cpp,gate,telemetry,"VBT board selection")
    ready='''IORegistryEntry::getRegistryRoot()->setProperty("N97FBTopologyHooksReady",display13FBTopologyHooksReady);'''
    publish='''IORegistryEntry::getRegistryRoot()->setProperty("N97FBTopologyHooksReady",display13FBTopologyHooksReady);
    if(yogaEDP120Scoped && checkKernelArgument("-wex-yoga-multi-audit")) {
        // 1=record format. These are already-computed states; do not
        // override any plugin readiness, hotplug bits or output topology.
        uint32_t wexYogaMultiHooks[] {
            1U, uint32_t(display13FBTopologyHooksReady),
            uint32_t(display13FBOutputHooksReady),
            uint32_t(display13FBTCHooksReady),
            uint32_t(display13TCProbeReady),
            uint32_t(display13DPAltProbeReady),
            uint32_t(display13FBAUXHooksReady),
            uint32_t(display13FBSSTHooksReady),
            uint32_t(display13FBIRQReady),
            uint32_t(display13FBClockSetHookReady),
            uint32_t(display13FBWatermarkHooksReady),
            uint32_t(display13FBDBUFHooksReady)
        };
        IORegistryEntry::getRegistryRoot()->setProperty(
            "WEXYogaMultiHooks",wexYogaMultiHooks,sizeof(wexYogaMultiHooks));
    }'''
    cpp=exact(cpp,ready,publish,"Display13 hook readiness")
    cppfile.write_text(cpp)
    argsfile=src/"tests/fixtures/boot_argument_names.json"
    args=json.loads(argsfile.read_text())
    if "-wex-yoga-multi-audit" in args:raise RuntimeError("flag already exists")
    args["-wex-yoga-multi-audit"]=[]
    argsfile.write_text(json.dumps(args,indent=2)+"\n")
    changed=set(subprocess.check_output(["git","-C",str(src),"diff","--name-only"],text=True).splitlines())
    expected={
        "WhateverXe/kern_alderlake_n.hpp",
        "WhateverXe/kern_xe.cpp",
        "WhateverXe/kern_xe.hpp",
        "WhateverXe/kern_display13_wm.hpp",
        "tests/fixtures/boot_argument_names.json"
    }
    if changed!=expected:raise RuntimeError("unexpected source modifications %r"%changed)
    subprocess.run(["git","-C",str(src),"diff","--check"],check=True)
    if cpp.count('checkKernelArgument("-wex-yoga-multi-audit")')!=2:
        raise RuntimeError("audit must be enabled in exactly two read-only paths")
    assert '-wex-yoga-edp120-admit' in cpp and '-wex-yoga-edp120-wm' in cpp
    assert 'WEXYogaMultiWiring' in cpp and 'WEXYogaMultiHooks' in cpp
    assert '-wex-yoga-hdmi600' not in cpp and '-wex-yoga-rgb8' not in cpp
    print("PASS: exact V2 WM_ONLY + read-only A7A0 Display13 multi-output audit")
    print("NO port routing, TC/DP-alt, hotplug, clock, DSC or Graphics behavior changed")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("src",type=Path)
    ap.add_argument("graphics",type=Path)
    a=ap.parse_args()
    run(a.src.resolve(),a.graphics.resolve())
