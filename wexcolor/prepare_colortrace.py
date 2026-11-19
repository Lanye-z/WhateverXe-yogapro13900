#!/usr/bin/env python3
"""Optional, read-only HDMI-B colour register snapshot on pinned WEX 0.8.3.

Inherits the exact WM_ONLY/V2 + HDMI HPD trace source; leaves all existing
behaviour intact. No MMIO writes or color-mode/EDID/HPD event modifications.
Only a qualified physical A7A0 native HDMI-B DDC read publishes a lazy
OSSerializer. It reads hardware only when users request IORegistry.
"""
import argparse
import json
import subprocess
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: required exactly one anchor; got {source.count(old)}")
    return source.replace(old, new, 1)

# 8 header words followed by three fixed records of 17 u32 values.
# Records: pipe, powered, TRANS_DDI_FUNC_CTL, PIPE_MISC, PLANE_CTL,
# PIPECONF, TRANS_DDI_FUNC_CTL2, VIDEO_DIP_CTL, GCP,
# 7 AVI infoframe words, TRANS_MSA_MISC.
CODE = r'''
// Yoga A7A0 HDMI-B colour observation, default OFF.
// This serializer runs only when IORegistry is explicitly read. No
// periodic polling, timer, register write, EDID edit or IRQ work.
static volatile uint32_t wexYogaHDMIColorPublished {};
static volatile uint32_t wexYogaHDMIColorVendor {};
static volatile uint32_t wexYogaHDMIColorProduct {};
static bool wexYogaHDMIColorSerialize(void *,void *,OSSerialize *serializer) {
    if(!serializer)return false;
    uint32_t words[8+3*17] {};
    words[0]=1; // schema
    words[4]=__atomic_load_n(&wexYogaHDMIColorVendor,__ATOMIC_ACQUIRE);
    words[5]=__atomic_load_n(&wexYogaHDMIColorProduct,__ATOMIC_ACQUIRE);
    for(unsigned pipe=0;pipe<3;++pipe) {
        auto row=words+8+17*pipe;
        for(unsigned i=0;i<17;++i)row[i]=UINT32_MAX;
        row[0]=pipe;row[1]=0;
    }
    auto &c=display13FBPower;
    // No powered mapping or native driver owner => return an explicit
    // unavailable snapshot, never guess zeros are valid register contents.
    if(c.lock && c.map && c.engineEnabled && IOLockTryLock(c.lock)) {
        // Nonblocking: a concurrent modeset makes this read unavailable
        // instead of creating a potential IORegistry/display-lock cycle.
        if(c.map && c.engineEnabled) {
            Display13FBPowerIO io {c.map};
            const uint32_t before=io.read(0x45404);
            words[2]=before;words[1]=1;
            for(unsigned pipe=0;pipe<3;++pipe) {
                const uint32_t bank=0x1000U*pipe;
                const bool powered=(before&(1U<<(2U*(5U+pipe))))!=0;
                auto row=words+8+17*pipe;
                row[1]=powered?1U:0U;
                if(!powered)continue;
                const uint32_t func=io.read(0x60400+bank);
                row[2]=func;
                row[3]=io.read(0x70030+bank);
                row[4]=io.read(0x70180+bank);
                row[5]=io.read(0x70008+bank);
                row[6]=io.read(0x60404+bank);
                words[7]|=1U<<pipe;
                // DDI-B native TMDS selection must be proven by live
                // TRANS_DDI_FUNC_CTL: enabled, port selector 2, mode 0 or 1.
                const bool hdmiB=(func&0x80000000U) &&
                    ((func>>27)&15U)==2U && ((func>>24)&7U)<=1U;
                if(!hdmiB)continue;
                words[6]|=1U<<pipe;
                const uint32_t ctl=io.read(0x60200+bank);
                row[7]=ctl;
                // GCP is meaningful only when explicitly enabled.
                if(ctl&(1U<<16))row[8]=io.read(0x60210+bank);
                // AVI data is meaningful only when explicitly enabled.
                if(ctl&(1U<<12))
                    for(unsigned i=0;i<7;++i)
                        row[9+i]=io.read(0x60220+bank+4U*i);
                row[16]=io.read(0x60410+bank);
            }
            words[3]=io.read(0x45404);
            if(words[3]!=before)words[1]=2; // power changed mid-snapshot
        }
        IOLockUnlock(c.lock);
    }
    auto data=OSData::withBytes(words,sizeof(words));
    if(!data)return false;
    const bool ok=data->serialize(serializer);
    data->release();return ok;
}
'''

DDC_OLD = '''    cachePanelDepth(port,block,data,result);
    if(selected) {'''
DDC_NEW = '''    cachePanelDepth(port,block,data,result);
    // Exact hardware-qualified *passive* sampler publication.
    // The native read and its EDID bytes have already been handled.
    if(!result && selected && config && config[0]==1 &&
       callbackXE->adlpDisplaySelected && callbackXE->yogaEDP120Scoped &&
       callbackXE->adlnOutputWiring.hdmi==2U &&
       checkKernelArgument("-wex-yoga-hdmi-colortrace")) {
        if(block==1 && data &&
           !memcmp(data,"\\x00\\xff\\xff\\xff\\xff\\xff\\xff\\x00",8)) {
            __atomic_store_n(&wexYogaHDMIColorVendor,
                (uint32_t(data[8])<<8)|uint32_t(data[9]),__ATOMIC_RELEASE);
            __atomic_store_n(&wexYogaHDMIColorProduct,
                uint32_t(data[10])|(uint32_t(data[11])<<8),__ATOMIC_RELEASE);
        }
        uint32_t expected=0;
        if(__atomic_compare_exchange_n(&wexYogaHDMIColorPublished,
            &expected,1U,false,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) {
            if(auto observer=OSSerializer::forTarget(nullptr,wexYogaHDMIColorSerialize)) {
                root->setProperty("WEXYogaHDMIColorLive",observer);
                observer->release();
            }
        }
    }
    if(selected) {'''

def main(src: Path, graphics: Path):
    root=Path(__file__).resolve().parents[1]
    spec=spec_from_file_location("wexhpd",root/"wexhdmi/prepare_hotplug.py")
    hpd=module_from_spec(spec);spec.loader.exec_module(hpd)
    hpd.run(src,graphics)
    target=src/"WhateverXe/kern_xe.cpp"
    s=target.read_text()
    anchor="uint32_t XE::wrapAlderLakeNPortDDC(OSObject *port,uint32_t block,uint8_t *data,bool force) {"
    s=replace_once(s,anchor,CODE+"\n"+anchor,"colour sampler global")
    s=replace_once(s,DDC_OLD,DDC_NEW,"qualified DDC observer publication")
    assert s.count("WEXYogaHDMIColorLive")==1
    assert s.count('checkKernelArgument("-wex-yoga-hdmi-colortrace")')==1
    assert s.count('"WEXYogaHDMIHPDTrace"')==1
    target.write_text(s)

    argsfile=src/"tests/fixtures/boot_argument_names.json"
    args=json.loads(argsfile.read_text())
    if "-wex-yoga-hdmi-colortrace" in args:
        raise RuntimeError("boot arg collision")
    args["-wex-yoga-hdmi-colortrace"]=[]
    argsfile.write_text(json.dumps(args,indent=2)+"\n")

    changed=set(subprocess.check_output(
        ["git","-C",str(src),"diff","--name-only"],text=True).splitlines())
    expected={"WhateverXe/kern_alderlake_n.hpp",
              "WhateverXe/kern_xe.cpp","WhateverXe/kern_xe.hpp",
              "WhateverXe/kern_display13_wm.hpp",
              "tests/fixtures/boot_argument_names.json",
              "tests/display13_offline.py","tests/dsi_port_adapter.py"}
    if changed!=expected:
        raise RuntimeError(f"unexpected diff {changed ^ expected}")
    subprocess.run(["git","-C",str(src),"diff","--check"],check=True)
    print("PASS: pinned WEX 0.8.3, WM_ONLY + existing HPD trace preserved")
    print("PASS: opt-in A7A0 HDMI B on-demand MMIO read, no register writes")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("src",type=Path)
    p.add_argument("graphics",type=Path)
    a=p.parse_args()
    main(a.src.resolve(),a.graphics.resolve())
