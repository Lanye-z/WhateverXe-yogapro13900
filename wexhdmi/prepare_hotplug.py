#!/usr/bin/env python3
"""Pinned WM_ONLY/V2 + A7A0-only HDMI cold-first-hotplug trial.

Two opt-in arguments: -wex-yoga-hdmi-hpdtrace (read-only ISR counters);
-wex-yoga-hdmi-first-hpd (same trace + one-shot native short->long mapping
only if HDMI B was absent on the FIRST real probe).
This is a guarded hypothesis, NOT a verified cause or repair.
"""
import argparse,json,subprocess
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec

def replace(s,before,after,label):
    count=s.count(before)
    if count!=1:
        raise RuntimeError(f"{label}: expected 1 exact anchor, observed {count}")
    return s.replace(before,after,1)

def run(src:Path,graphics:Path):
    root=Path(__file__).resolve().parents[1]
    spec=spec_from_file_location("yoga_wm_only",root/"wex120/prepare_120.py")
    mod=module_from_spec(spec);spec.loader.exec_module(mod)
    mod.prepare(src,graphics,"V2")
    cppfile=src/"WhateverXe/kern_xe.cpp"
    s=cppfile.read_text()
    s=replace(s,'#include "kern_display13_fb_irq.hpp"',
        '#include "kern_display13_fb_irq.hpp"\n#include "kern_yoga_hdmi_first_hpd.hpp"',
        "HDMI unit-tested pure helper")
    globals=r'''// A7A0 HDMI-B first hotplug experiment. ISR writes ONLY preallocated atomics.
// The IORegistry serializer runs on the caller's thread, never in the ISR.
// Array schema: version,firstB,lastB,probesB,ProcessIRQ,ProcessDE,
// PCHMaster,BLONG,BSHORT,promoted,lastPCH,lastDDI,rawEvents,
// forwardedEvents,status,enabled,faulted,active,admittedPipes,traceSamples.
static volatile uint32_t wexYogaHDMITrace[20] {1U,UINT32_MAX};
static volatile uint32_t wexYogaHDMITraceActive {};
static volatile uint32_t wexYogaHDMIPromoteActive {};
static volatile uint32_t wexYogaHDMIPromoted {};
static volatile uint32_t wexYogaHDMITracePublished {};
static bool wexYogaHDMITraceSerializer(void *,void *,OSSerialize *serializer) {
    if(!serializer)return false;
    uint32_t words[20] {};
    for(unsigned i=0;i<20;++i)words[i]=__atomic_load_n(&wexYogaHDMITrace[i],__ATOMIC_ACQUIRE);
    auto data=OSData::withBytes(words,sizeof(words));
    if(!data)return false;
    const bool ok=data->serialize(serializer);data->release();return ok;
}
'''
    s=replace(s,"bool XE::wrapDisplay13FBProcessIRQ(IOService *controller) {",
        globals+"\nbool XE::wrapDisplay13FBProcessIRQ(IOService *controller) {",
        "non-IRQ read-only telemetry registration")
    s=replace(s,"bool XE::wrapDisplay13FBProcessIRQ(IOService *controller) {\n\tif(!adlnIRQOwner(controller))return false;",
        "bool XE::wrapDisplay13FBProcessIRQ(IOService *controller) {\n"
        "    if(__atomic_load_n(&wexYogaHDMITraceActive,__ATOMIC_RELAXED))"
        "__atomic_fetch_add(&wexYogaHDMITrace[4],1U,__ATOMIC_RELAXED);\n"
        "\tif(!adlnIRQOwner(controller))return false;",
        "native IRQ entry counter")
    old='''	const auto e=Display13FBIRQ::collect(io,c.state);c.status=e.status;
	*pipe=e.pipe;*aux=e.aux;*hotplug=e.hotplug;'''
    new=r'''	const auto e=Display13FBIRQ::collect(io,c.state);c.status=e.status;
	*pipe=e.pipe;*aux=e.aux;*hotplug=e.hotplug;
    if(__atomic_load_n(&wexYogaHDMITraceActive,__ATOMIC_RELAXED)) {
        __atomic_fetch_add(&wexYogaHDMITrace[5],1U,__ATOMIC_RELAXED);
        if(c.state.lastMaster&(1U<<23))
            __atomic_fetch_add(&wexYogaHDMITrace[6],1U,__ATOMIC_RELAXED);
        if(e.hotplug&YogaHDMIFirstHPD::BLong)
            __atomic_fetch_add(&wexYogaHDMITrace[7],1U,__ATOMIC_RELAXED);
        if(e.hotplug&YogaHDMIFirstHPD::BShort)
            __atomic_fetch_add(&wexYogaHDMITrace[8],1U,__ATOMIC_RELAXED);
        const auto firstB=__atomic_load_n(&wexYogaHDMITrace[1],__ATOMIC_ACQUIRE);
        const bool fix=__atomic_load_n(&wexYogaHDMIPromoteActive,__ATOMIC_RELAXED);
        if(YogaHDMIFirstHPD::shouldPromote(e.hotplug,firstB,fix,
              __atomic_load_n(&wexYogaHDMIPromoted,__ATOMIC_ACQUIRE)!=0)) {
            uint32_t unused=0;
            if(__atomic_compare_exchange_n(&wexYogaHDMIPromoted,&unused,1U,false,
                    __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) {
                // Native handler still owns connector probing/EDID and may
                // reject any disconnected sink. Do not fabricate HPD in MMIO.
                *hotplug=YogaHDMIFirstHPD::asLong(e.hotplug);
                __atomic_fetch_add(&wexYogaHDMITrace[9],1U,__ATOMIC_RELAXED);
            }
        }
        __atomic_store_n(&wexYogaHDMITrace[10],c.state.lastPCH,__ATOMIC_RELAXED);
        __atomic_store_n(&wexYogaHDMITrace[11],c.state.lastDDI,__ATOMIC_RELAXED);
        __atomic_store_n(&wexYogaHDMITrace[12],e.hotplug,__ATOMIC_RELAXED);
        __atomic_store_n(&wexYogaHDMITrace[13],*hotplug,__ATOMIC_RELAXED);
        __atomic_store_n(&wexYogaHDMITrace[14],uint32_t(e.status),__ATOMIC_RELAXED);
        __atomic_store_n(&wexYogaHDMITrace[15],uint32_t(c.state.enabled),__ATOMIC_RELAXED);
        __atomic_store_n(&wexYogaHDMITrace[16],uint32_t(c.state.faulted),__ATOMIC_RELAXED);
        __atomic_store_n(&wexYogaHDMITrace[17],c.state.active,__ATOMIC_RELAXED);
        __atomic_store_n(&wexYogaHDMITrace[18],c.admittedPipes,__ATOMIC_RELAXED);
        __atomic_fetch_add(&wexYogaHDMITrace[19],1U,__ATOMIC_RELAXED);
    }'''
    # The string uses escaped tab literals to avoid tool-generated whitespace drift.
    new=new.replace("\\t","\t")
    s=replace(s,old,new,"native ProcessDE hotplug forwarding")
    marker='''        const result=FunctionCast(wrapAlderLakeNPortState,s->orgAlderLakeNPortState)(port); // Real selected HPD/EDID path.'''
    # Source actually uses "const auto result".
    marker='''        const auto result=FunctionCast(wrapAlderLakeNPortState,s->orgAlderLakeNPortState)(port); // Real selected HPD/EDID path.'''
    addition=r'''
        // This callback is not an IRQ handler; record HDMI B's first physical
        // native probe and install lazy read-only evidence on the registry.
        if(config[0]==1 && s->adlpDisplaySelected && s->yogaEDP120Scoped &&
           s->adlnOutputWiring.hdmi==2U) {
            const bool promote=checkKernelArgument("-wex-yoga-hdmi-first-hpd");
            if(promote || checkKernelArgument("-wex-yoga-hdmi-hpdtrace")) {
                uint32_t notSeen=UINT32_MAX;
                __atomic_compare_exchange_n(&wexYogaHDMITrace[1],&notSeen,result,false,
                    __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
                __atomic_store_n(&wexYogaHDMITrace[2],result,__ATOMIC_RELEASE);
                __atomic_fetch_add(&wexYogaHDMITrace[3],1U,__ATOMIC_RELAXED);
                __atomic_store_n(&wexYogaHDMIPromoteActive,promote?1U:0U,__ATOMIC_RELEASE);
                __atomic_store_n(&wexYogaHDMITraceActive,1U,__ATOMIC_RELEASE);
                uint32_t notPublished=0;
                if(__atomic_compare_exchange_n(&wexYogaHDMITracePublished,&notPublished,1U,false,
                     __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) {
                    if(auto serializer=OSSerializer::forTarget(nullptr,wexYogaHDMITraceSerializer)) {
                        IORegistryEntry::getRegistryRoot()->setProperty(
                            "WEXYogaHDMIHPDTrace",serializer);
                        serializer->release();
                    }
                }
            }
        }'''
    # The two upstream synthetic port fixtures extract this single method
    # without the actual IORegistry/boot-arg environment. They test the native
    # original port-state path; a separate pure C++ fixture tests this opt-in.
    addition="\n#ifndef WEX_YOGA_HPD_PORT_FIXTURE" + addition + "\n#endif"
    s=replace(s,marker,marker+addition,"first native HDMI B port probe")
    cppfile.write_text(s)
    for testpath,anchor in (
        ("tests/display13_offline.py","['clang++','-std=c++17'"),
        ("tests/dsi_port_adapter.py","['clang++','-std=c++17'")
    ):
        p=src/testpath
        t=p.read_text()
        t=replace(t,anchor,"['clang++','-DWEX_YOGA_HPD_PORT_FIXTURE=1','-std=c++17'",
                  "isolated upstream port fixture")
        p.write_text(t)
    h=src/"WhateverXe/kern_yoga_hdmi_first_hpd.hpp"
    h.write_text((root/"wexhdmi/kern_yoga_hdmi_first_hpd.hpp").read_text())
    argsfile=src/"tests/fixtures/boot_argument_names.json"
    args=json.loads(argsfile.read_text())
    for key in ("-wex-yoga-hdmi-hpdtrace","-wex-yoga-hdmi-first-hpd"):
        if key in args: raise RuntimeError("boot arg already exists "+key)
        args[key]=[]
    argsfile.write_text(json.dumps(args,indent=2)+"\n")
    changed=set(subprocess.check_output(["git","-C",str(src),"diff","--name-only"],text=True).splitlines())
    expected={"WhateverXe/kern_alderlake_n.hpp","WhateverXe/kern_xe.cpp",
      "WhateverXe/kern_xe.hpp","WhateverXe/kern_display13_wm.hpp",
      "tests/fixtures/boot_argument_names.json",
      "tests/display13_offline.py","tests/dsi_port_adapter.py"}
    if changed!=expected:raise RuntimeError("unexpected source diff "+str(changed))
    assert h.is_file() and s.count('"WEXYogaHDMIHPDTrace"')==1
    subprocess.run(["git","-C",str(src),"diff","--check"],check=True)
    subprocess.run(["clang++","-std=c++17","-Wall","-Wextra","-Werror",
      "-I",str(src/"WhateverXe"),str(root/"wexhdmi/test_first_hpd.cpp"),
      "-o",str(src/"wex_yoga_hdmi_hpd_test")],check=True)
    subprocess.run([str(src/"wex_yoga_hdmi_hpd_test")],check=True)
    print("PASS: EXACT pinned WM_ONLY/V2 + A7A0/HDMI-B opt-in one-shot trial")
    print("No display register writes, no HDMI600/RGB8/DP changes")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("src",type=Path);p.add_argument("graphics",type=Path)
    a=p.parse_args();run(a.src.resolve(),a.graphics.resolve())
