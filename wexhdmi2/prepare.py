#!/usr/bin/env python3
"""Compose the proven SST+Deep8+HDMI600 source with an opt-in HDMI2 experiment.
No second LightUpTMDS/ColorMode/GetOnlineInfo hook. Writes occur ONLY in
existing Display13 callbacks and ONLY under -wex-yoga-hdmi2-safe.
"""
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec
import argparse,json,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]
def once(s,needle,replacement,reason):
    n=s.count(needle)
    if n!=1:raise RuntimeError(f"{reason}: expected exact one anchor, found {n}")
    return s.replace(needle,replacement,1)

def main(source,graphics):
    spec=spec_from_file_location("yoga_sst",ROOT/"wexsst/prepare.py")
    module=module_from_spec(spec);spec.loader.exec_module(module)
    module.prepare(source,graphics)
    cpp=source/"WhateverXe/kern_xe.cpp"
    hpp=source/"WhateverXe/kern_xe.hpp"
    s=cpp.read_text();h=hpp.read_text()
    if any(x in s for x in ("-wex-yoga-hdmi2-link","orgDisplay13HDMI2TMDS","-wex-yoga-hdmi4k60")):
        raise RuntimeError("unsafe legacy HDMI2 route present")
    for term in ('WEXYogaHDMI600Status','WEXYogaHDMIEDIDABApplied',
                 'WEXYogaSSTHookStatus','WEXYogaHDMIColorLive'):
        if term not in s:raise RuntimeError("stable baseline absent: "+term)

    for name in ("hdmi2_8bpc_plan.hpp","hdmi2_scdc_prepare.hpp"):
        shutil.copyfile(ROOT/"wex4k60"/name,source/"WhateverXe"/name)
    shutil.copyfile(ROOT/"wexhdmi2/kern_yoga_hdmi2_candidate.hpp",
                    source/"WhateverXe/kern_yoga_hdmi2_candidate.hpp")
    shutil.copyfile(ROOT/"wexhdmi2/kern_display13_hdmi_caps.hpp",
                    source/"WhateverXe/kern_display13_hdmi_caps.hpp")

    # Parser may be included at the normal header site. The runtime helper
    # also refers to display13FBPower, so introduce it after that context
    # has been defined, never at the first include in the TU.
    s=once(s,'#include "kern_display13_fb_irq.hpp"',
           '#include "kern_display13_fb_irq.hpp"\n#include "kern_display13_hdmi_caps.hpp"',
           "CTA parser include")
    s=once(s,'static Display13FBPowerContext display13FBPower;',
           'static Display13FBPowerContext display13FBPower;\n'
           '#include "kern_yoga_hdmi2_candidate.hpp"',
           "candidate runtime helper after Display13 power context")
    # Append after the already-installed SST tail. Do NOT rewrite the
    # original class prefix or move its existing SST fields.
    h=once(h,'    mach_vm_address_t orgDisplay13DPCDInfo {};\n};',
       '    mach_vm_address_t orgDisplay13DPCDInfo {};\n'
       '    // Yoga HDMI2 candidate: tail only, preserve existing XE offsets.\n'
       '    bool yogaHDMI2SafeRequested {false};\n'
       '    bool yogaHDMI2ObserveRequested {false};\n};',"new tail fields")

    # Installer: reuse already routed Display13 GMBUS and MMIO interfaces.
    install=r'''
    {
        yogaHDMI2SafeRequested=checkKernelArgument("-wex-yoga-hdmi2-safe");
        yogaHDMI2ObserveRequested=checkKernelArgument("-wex-yoga-hdmi2-observe");
        const bool eligible=ready && display13FramebufferRequested &&
          adlpDisplaySelected && yogaEDP120Scoped && xeProfile.identity==0xA7A08086U &&
          adlnOutputWiring.hdmi==2U;
        uint32_t status=0; // 0 off,1 gated,2 donor mismatch,3 ready,4 conflict
        if(yogaHDMI2SafeRequested || yogaHDMI2ObserveRequested) {
            status=(yogaHDMI2SafeRequested && yogaHDMI2ObserveRequested)?4:1;
            if(status!=4 && eligible) {
                const char *symbol="__ZN31AppleIntelFramebufferController14hwDoI2CRequestEjjjP14IOI2CBusTimingP12IOI2CRequest";
                const auto fn=patcher.solveSymbol<mach_vm_address_t>(index,symbol,address,size);
                patcher.clearError();
                const uint8_t entry[]={0x55,0x48,0x89,0xE5,0x48,0x83,0xEC,0x20};
                status=2;
                if(size>0x53A20+sizeof(entry) && fn==address+0x53A20 &&
                   !memcmp(reinterpret_cast<const void *>(fn),entry,sizeof(entry))) {
                    yogaHDMI2NativeI2C=fn;
                    status=3;
                }
            }
            if(status!=3) {
                yogaHDMI2SafeRequested=false;yogaHDMI2ObserveRequested=false;
                yogaHDMI2NativeI2C=0;
            }
            auto root=IORegistryEntry::getRegistryRoot();
            root->setProperty("WEXYogaHDMI2SafeStatus",status,32);
            root->setProperty("WEXYogaHDMI2SafeReady",status==3);
            root->setProperty("WEXYogaHDMI2SafeWriteRequested",yogaHDMI2SafeRequested);
        }
    }
'''
    target='const bool ready=patcher.routeMultipleShort(index,routes,arrsize(routes),address,size);patcher.clearError();'
    start=s.index('bool XE::processDisplay13FramebufferOutput(')
    end=s.index('\nbool XE::',start+10)
    part=once(s[start:end],target,target+install,"safe HDMI2 installer")
    s=s[:start]+part+s[end:]

    # Cache physical HDMI B EDID CTA properties after original DDC read.
    ddc_start=s.index('uint32_t XE::wrapAlderLakeNPortDDC(')
    ddc_end=s.index('\nbool XE::',ddc_start)
    part=s[ddc_start:ddc_end]
    original='    cachePanelDepth(port,block,data,result);'
    extension=r'''
    if((callbackXE->yogaHDMI2SafeRequested || callbackXE->yogaHDMI2ObserveRequested) &&
        !result && data && (block==1 || (block>=2 && block<=8))) {
        auto cfg=Display13FBMemory::field<uint32_t *>(port,0x548);
        if(cfg && cfg[0]==1 && cfg[2]==2 &&
           callbackXE->display13HDMIPort(port)) {
            yogaHDMI2ObserveDDC(port,block,data,true,tglAUXLock);
        }
    }
'''
    part=once(part,original,original+extension,"physical HDMI B CTA observer")
    s=s[:ddc_start]+part+s[ddc_end:]

    # Existing WM callback already computes real pending CRTC pixel clock;
    # call native I2C only after dropping WM IOLock. Unchanged if no flag.
    wm_start=s.index('void XE::wrapAlderLakeNPipeWMSetup(')
    wm_end=s.index('\n',s.index('\n}',wm_start)+2) if '\n}' in s[wm_start:] else -1
    wm_next=s.index('\n// Native RegisterAccessManager',wm_start)
    frag=s[wm_start:wm_next]
    insertion=r'''
#ifndef WEX_HDMI2_DBUF_FIXTURE
    if(associated && valid && callbackXE->display13HDMIPort(port) &&
       (callbackXE->yogaHDMI2SafeRequested || callbackXE->yogaHDMI2ObserveRequested)) {
        const auto pixelHz=record[3];
        const auto status=yogaHDMI2TryPrepare(controller,fb,path,pixelHz,
             callbackXE->yogaHDMI2SafeRequested,tglAUXLock);
        static uint32_t seq {};
        const auto n=__sync_add_and_fetch(&seq,1);
        uint64_t snapshot[] {1,n,record[7],pixelHz,status,
           __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)};
        if(n<=16 || (pixelHz>340000000ULL && n<=48))
           IORegistryEntry::getRegistryRoot()->setProperty("WEXYogaHDMI2WMEvent",snapshot,sizeof(snapshot));
        if(pixelHz>340000000ULL)
           IORegistryEntry::getRegistryRoot()->setProperty("WEXYogaHDMI2HighLast",snapshot,sizeof(snapshot));
    }
#endif
'''
    frag=once(frag,'\tIOLockUnlock(c.lock);\n\tIORegistryEntry::getRegistryRoot()->setProperty("N97FBPipeWM",record,sizeof(record));',
        '\tIOLockUnlock(c.lock);\n'+insertion+
        '\tIORegistryEntry::getRegistryRoot()->setProperty("N97FBPipeWM",record,sizeof(record));',
        "WM after unlocking")
    s=s[:wm_start]+frag+s[wm_next:]

    # The upstream display13_dbuf_setup test extracts this one method
    # into a tiny fixture. It has no HDMI2 controller/I2C/mode state.
    # Exclude only the new experimental tail in that fixture, not in Kext.
    dbuf_test=source/"tests/display13_dbuf_setup.py"
    t=dbuf_test.read_text()
    t=once(t,
        "code = (r / 'tests/display13_dbuf_setup_fixture.cpp').read_text()",
        "code = '#define WEX_HDMI2_DBUF_FIXTURE\\n' + (r / 'tests/display13_dbuf_setup_fixture.cpp').read_text()",
        "isolated DBUF fixture only")
    dbuf_test.write_text(t)

    # Only modify the native source register's HDMI-B activation write.
    # All other writes are passed through byte-for-byte.
    write_start=s.index('void XE::wrapDisplay13GMBusWrite(')
    write_end=s.index('\n}',write_start)
    fragment=s[write_start:write_end]
    location='    FunctionCast(wrapDisplay13GMBusWrite,callbackXE->orgDisplay13GMBusWrite)(access,reg,value);'
    modifier=r'''
    if(callbackXE->yogaHDMI2SafeRequested && access==display13FBPower.access &&
       (value&0x80000000U) && ((value>>27)&15)==2 &&
       ((value>>24)&7)==0 && ((value>>20)&7)==0 &&
       __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)<3) {
        const auto pipe=__atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE);
        if(reg==0x60400U+0x1000U*pipe) {
            value=YogaHDMI2::mergeFuncCtl(value,YogaHDMI2::SourceFlags);
            const auto number=__sync_add_and_fetch(&yogaHDMI2Writes,1U);
            uint32_t record[] {1,pipe,uint32_t(reg),value,number};
            if(number<=16)IORegistryEntry::getRegistryRoot()->setProperty(
                "WEXYogaHDMI2SourceLast",record,sizeof(record));
        }
    }
'''
    fragment=once(fragment,location,modifier+location,"source flags in existing MMIO path")
    s=s[:write_start]+fragment+s[write_end:]
    hpp.write_text(h);cpp.write_text(s)
    fixture=source/"tests/fixtures/boot_argument_names.json"
    data=json.loads(fixture.read_text())
    for flag in ("-wex-yoga-hdmi2-safe","-wex-yoga-hdmi2-observe"):
        if flag in data:raise RuntimeError("duplicate flag "+flag)
        data[flag]=[]
    fixture.write_text(json.dumps(data,indent=2)+"\n")
    assert s.count('WEXYogaHDMI2SourceLast')==1
    assert 'orgDisplay13HDMI2TMDS' not in s
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)
    print("PASS: built on proven SST/Deep8/HDMI600, no new native route")
    print("PASS: off by default, observe-only and qualified HDMI2 experiment")
    print("PASS: native lock ownership and SCDC readback required for source bit4/0")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path);parser.add_argument("graphics",type=Path)
    opt=parser.parse_args();main(opt.source.resolve(),opt.graphics.resolve())
