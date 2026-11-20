#!/usr/bin/env python3
"""Static guard for the generated production DDI5 SST compatibility overlay.

Production compilation and the complete upstream regression suite run
separately in the workflow. This is not a hardware/DP-link simulator.
"""
from pathlib import Path
import json
import sys

source=Path(sys.argv[1]) if len(sys.argv)>1 else Path("Source")
cpp=(source/"WhateverXe/kern_xe.cpp").read_text()
hpp=(source/"WhateverXe/kern_xe.hpp").read_text()
flags=json.loads((source/"tests/fixtures/boot_argument_names.json").read_text())
block=cpp.split("uint64_t XE::wrapDisplay13DPCDInfo(void *raw)",1)[1]
block=block.split("\nbool XE::processDisplay13FramebufferTC(",1)[0]
tc=cpp.split("bool XE::processDisplay13FramebufferTC(",1)[1]
tc=tc.split("\nbool XE::",1)[0]

checks={
    "unique original-call DPCD wrapper":cpp.count("uint64_t XE::wrapDisplay13DPCDInfo(void *raw)")==1,
    "exactly one new short route":cpp.count("KernelPatcher::RouteRequest route(sym,wrapDisplay13DPCDInfo,orgDisplay13DPCDInfo);")==1,
    "native DPCD read first":block.index("const auto result=FunctionCast(")<block.index("const uint32_t original=bytes[0x1E]"),
    "DPCD native result unchanged":block.count("return result;")==2,
    "no fabricated training success": "kIOReturnSuccess" not in block and "kIOReturnSuccess" not in tc,
    "A7A0-only gate": "xeProfile.identity==0xA7A08086U" in tc,
    "physical DDI5-only gate": "config[0]!=5" in block and "adlnOutputWiring.typeC&(1U<<5)" in tc,
    "exact symbol/prologue/offset": all(s in tc for s in (
        "__ZN14AppleIntelPort11getDPCDInfoEv",
        "fn==address+0x1DE0E",
        "const uint8_t prologue[]={0x55,0x48,0x89,0xE5,0x41,0x57,0x41,0x56}")),
    "mask gated by opt-in": "const bool masked=s->yogaSSTMaskRequested && original!=0;" in block,
    "MST cache only and no forced mode": block.count("bytes[0x1E]=0;")==1 and "bytes[0x117]=" not in block,
    "no additional MMIO or AUX": not any(s in block for s in ("WriteRegister32","WriteRegister64","writeAUX","writeMMIO","tglPrepareTrainingLease")),
    "bounded observations": "if(sequence<=8)" in block,
    "explicit observe/mask boot args": "-wex-yoga-tc5-sst" in flags and "-wex-yoga-tc5-sst-observe" in flags,
    "function pointer declaration": "orgDisplay13DPCDInfo {};" in hpp,
    "hook status exposed": all(s in tc for s in ("WEXYogaSSTHookReady","WEXYogaSSTHookStatus")),
    "original DDI5 diagnostics preserved": all(s in cpp for s in ("WEXYogaUSBCDPTrainingLast","WEXYogaUSBCDPStopDetail")),
    "original display features preserved": all(s in cpp for s in ("WEXYogaHDMI600Status","WEXYogaEDP120WMEnabled","WEXYogaHDMIEDIDABApplied")),
    "old dangerous HDMI2 experiments absent": "orgDisplay13HDMI2TMDS" not in cpp,
}
for name,ok in checks.items():
    print(("PASS" if ok else "FAIL")+": "+name)
if not all(checks.values()):
    raise SystemExit("SST source guard failed")
print(f"PASS: {len(checks)} targeted checks. Hardware behavior NOT established.")
