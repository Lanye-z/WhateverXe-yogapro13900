#!/usr/bin/env python3
"""A7A0 HDMI2 V2: protected native LightUpTMDS *single CALL site* experiment.

V1 WM callback has no native controller owner lock (observed status=5).
The WM branch is made OBSERVATION ONLY in this overlay.  Instead of
routing/replacing the LightUpTMDS function (previously broke Metal),
replace precisely one verified native x86 CALL instruction in the exact
macOS 25G241 donor.  Default: absolutely no additional branch installed.

Experimental flags are mutually exclusive:
 -wex-yoga-hdmi2-callsite-observe: call-site ownership/timing only; zero new I2C/MMIO
 -wex-yoga-hdmi2-callsite-safe: negotiate SCDC only if owner-lock, DDC and
  caps are valid before LightUpTMDS; update path shadow bit0/bit4 only
  after matching SCDC readback; pass all other native behavior through.
Do NOT deploy to daily EFI or try 4K60 without independent recovery.
"""
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec
import argparse, subprocess, json

ROOT=Path(__file__).resolve().parents[1]

def once(s,old,new,name):
    n=s.count(old)
    if n!=1:raise RuntimeError(f"{name}: exactly one anchor required, found {n}")
    return s.replace(old,new,1)

def main(source,graphics):
    spec=spec_from_file_location("v1",ROOT/"wexhdmi2/prepare.py")
    m=module_from_spec(spec);spec.loader.exec_module(m)
    m.main(source,graphics)
    cpp=source/"WhateverXe/kern_xe.cpp"
    cand=source/"WhateverXe/kern_yoga_hdmi2_candidate.hpp"
    c=cand.read_text()
    # Original V1 callback has no controller owner lock. Never wait for
    # c.lock within native graphics modeset; a busy owner must fail closed.
    c=once(c,"    IOLockLock(state.lock);\n    const bool ready=",
            "    if(!IOLockTryLock(state.lock))return 54;\n    const bool ready=",
            "nonblocking GPU power lock")
    c=once(c,"__atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)!=pipe)return 52;",
          "__atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)>=3U)return 52;",
          "same-sink low-speed SCDC restoration across pipe changes")
    cand.write_text(c)
    s=cpp.read_text()
    s=once(s,'yogaHDMI2SafeRequested=checkKernelArgument("-wex-yoga-hdmi2-safe");',
           'yogaHDMI2SafeRequested=checkKernelArgument("-wex-yoga-hdmi2-callsite-safe");',
           "V2 exclusive active flag")
    s=once(s,'yogaHDMI2ObserveRequested=checkKernelArgument("-wex-yoga-hdmi2-observe");',
           'yogaHDMI2ObserveRequested=checkKernelArgument("-wex-yoga-hdmi2-callsite-observe");',
           "V2 exclusive observe flag")
    # Native WM is NOT the owner lock. Its HDMI2 fragment now does NO
    # SCDC, no active flag setting, not even under -callsite-safe.
    s=once(s,
          '''        const auto status=yogaHDMI2TryPrepare(controller,fb,path,pixelHz,
             callbackXE->yogaHDMI2SafeRequested,tglAUXLock);''',
          '''        const uint32_t status=55; // WM never owns native HDMI2 SCDC; OBSERVATION ONLY''',
          "remove V1 invalid SCDC timing path")
    flag='static Display13FBPowerContext display13FBPower;\n#include "kern_yoga_hdmi2_candidate.hpp"'
    globals=r'''
static mach_vm_address_t yogaHDMI2OriginalLightUp {};
static bool yogaHDMI2CallsiteSafe {}, yogaHDMI2CallsiteObserve {};
static volatile uint32_t yogaHDMI2CallsiteCalls {};
'''
    s=once(s,flag,flag+globals,"V2 globals")
    hpp=source/"WhateverXe/kern_xe.hpp"
    h=hpp.read_text()
    h=once(h,
      '    bool yogaHDMI2ObserveRequested {false};\n};',
      '    bool yogaHDMI2ObserveRequested {false};\n'
      '    static uint32_t yogaHDMI2Callsite(void *,void *,void *,const void *);\n};',
      "single CALL shim declaration inside XE")
    hpp.write_text(h)
    callsite=r'''
// Native 25G241: hwSetMode +0x4FFB6 calls LightUpTMDS +0x50B22.
// Unlike a global function hook, we patch precisely that one caller
// instruction and invoke the still-unaltered original function directly.
// Do not call C++ virtual methods or install a second TMDS route.
uint32_t XE::yogaHDMI2Callsite(void *controller,void *rawFB,void *rawPath,const void *rawTiming) {
    using Native=uint32_t (*)(void *,void *,void *,const void *);
    const auto original=reinterpret_cast<Native>(yogaHDMI2OriginalLightUp);
    if(!original)return kIOReturnNotReady; // never pretend success
    auto s=callbackXE;
    auto fb=static_cast<IOService *>(rawFB);
    auto path=static_cast<OSObject *>(rawPath);
    const auto count=__sync_add_and_fetch(&yogaHDMI2CallsiteCalls,1U);
    uint64_t record[12] {2,count};
    bool qualified=s && fb && path && rawTiming && tglAUXLock &&
        fb->getMetaClass()->getClassSize()>=0x4B90 &&
        path->getMetaClass()->getClassSize()>=0x3650 &&
        Display13FBMemory::field<void *>(fb,0x1D0)==controller &&
        Display13FBMemory::field<void *>(path,0x32B0)==fb;
    OSObject *port=qualified ? Display13FBMemory::field<OSObject *>(path,0x3648):nullptr;
    qualified=qualified && s->display13HDMIPort(port);
    const auto clock=qualified ? static_cast<const IODetailedTimingInformationV2 *>(rawTiming)->pixelClock : 0;
    const auto pipe=qualified ? Display13FBMemory::field<uint32_t>(path,0x3640):3;
    const auto owner=qualified ? Display13FBMemory::field<IORecursiveLock *>(controller,0x9B8):nullptr;
    const bool owns=owner && IORecursiveLockHaveLock(owner);
    record[2]=qualified;record[3]=pipe;record[4]=clock;record[5]=owns;
    record[6]=__atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE);
    uint32_t status=1; // 1 no path,2 no controller owner,50 observer,100 SCDC ready, etc
    uint32_t shadowBefore=0,shadowAfter=0;
    if(qualified && pipe<3) {
        shadowBefore=Display13FBMemory::field<uint32_t>(path,0x12C);
        shadowAfter=shadowBefore;
        if(!owns) status=2;
        else if(yogaHDMI2CallsiteObserve)status=50;
        else if(yogaHDMI2CallsiteSafe) {
            // Existing V1 policy verifies HDMI B, SCDC capability/generation,
            // current source mode, native owner, power, and full I2C readback.
            // On 4K30 we only touch SCDC to undo a *previously armed* high link.
            status=yogaHDMI2TryPrepare(static_cast<IOService *>(controller),fb,path,
                                       clock,true,tglAUXLock);
            if(status==100 &&
               __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)==pipe) {
                shadowAfter=shadowBefore|YogaHDMI2::SourceFlags;
                *reinterpret_cast<uint32_t *>(static_cast<uint8_t *>(rawPath)+0x12C)=shadowAfter;
            } else if(status==101) {
                shadowAfter=shadowBefore&~YogaHDMI2::SourceFlags;
                *reinterpret_cast<uint32_t *>(static_cast<uint8_t *>(rawPath)+0x12C)=shadowAfter;
            }
        }
    }
    record[7]=status;record[8]=shadowBefore;record[9]=shadowAfter;
    // Always execute original native function with the original ABI,
    // arguments and status. Never manufacture a successful modeset.
    const auto result=original(controller,rawFB,rawPath,rawTiming);
    record[10]=result;record[11]=__atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE);
    if(count<=16 || status==100 || status==101) {
        auto root=IORegistryEntry::getRegistryRoot();
        root->setProperty("WEXYogaHDMI2CallsiteLast",record,sizeof(record));
        if(count<=8) {
            char key[48];snprintf(key,sizeof(key),"WEXYogaHDMI2CallsiteFirst%u",count);
            root->setProperty(key,record,sizeof(record));
        }
    }
    return result;
}
'''
    anchor='bool XE::processDisplay13FramebufferOutput(KernelPatcher &patcher,size_t index,mach_vm_address_t address,size_t size) {'
    s=once(s,anchor,callsite+'\n'+anchor,"single native call-site shim")
    install=r'''
    // Only enabled for this one pinned x86_64 Apple framebuffer donor.
    // WEX route-only TMDS global-hook failure is NOT reused.
    {
        yogaHDMI2CallsiteSafe=yogaHDMI2SafeRequested;
        yogaHDMI2CallsiteObserve=yogaHDMI2ObserveRequested;
        uint32_t state=0; // 0 off,1 unready,2 opcode mismatch,3 unreachable,4 patch fail,5 installed
        if(yogaHDMI2CallsiteSafe || yogaHDMI2CallsiteObserve) {
            state=1;
            const uint8_t originalCall[] {0xE8,0x67,0x0B,0x00,0x00};
            constexpr uintptr_t callOffset=0x4FFB6;
            constexpr uintptr_t targetOffset=0x50B22;
            if(yogaHDMI2NativeI2C && ready && size>targetOffset+16 &&
               !memcmp(reinterpret_cast<const void *>(address+callOffset),
                       originalCall,sizeof(originalCall))) {
                state=3;
                // Never emit an out-of-range x86 rel32 displacement.
                const int64_t relative=static_cast<int64_t>(reinterpret_cast<uintptr_t>(yogaHDMI2Callsite))-
                                       static_cast<int64_t>(address+callOffset+5);
                if(relative>=INT32_MIN && relative<=INT32_MAX) {
                    uint8_t patchedCall[5] {0xE8};
                    const auto displacement=static_cast<int32_t>(relative);
                    memcpy(patchedCall+1,&displacement,sizeof(displacement));
                    yogaHDMI2OriginalLightUp=address+targetOffset;
                    patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));
                    state=patcher.getError()==KernelPatcher::Error::NoError &&
                        !memcmp(reinterpret_cast<const void *>(address+callOffset),
                                patchedCall,sizeof(patchedCall)) ? 5:4;
                    patcher.clearError();
                    if(state!=5)yogaHDMI2OriginalLightUp=0;
                }
            } else state=2;
            if(state!=5) {
                yogaHDMI2CallsiteSafe=false;yogaHDMI2CallsiteObserve=false;
                yogaHDMI2SafeRequested=false;yogaHDMI2ObserveRequested=false;
            }
            auto root=IORegistryEntry::getRegistryRoot();
            root->setProperty("WEXYogaHDMI2CallsiteStatus",state,32);
            root->setProperty("WEXYogaHDMI2CallsiteReady",state==5);
            root->setProperty("WEXYogaHDMI2CallsiteWriteEnabled",yogaHDMI2CallsiteSafe);
        }
    }
'''
    # V1 injection: this string is unique and nested inside the existing output processing.
    endpart='''            root->setProperty("WEXYogaHDMI2SafeWriteRequested",yogaHDMI2SafeRequested);
        }
    }
'''
    s=once(s,endpart,endpart+install,"V2 single CALL site installer")
    cpp.write_text(s)
    fixtures=source/"tests/fixtures/boot_argument_names.json"
    j=json.loads(fixtures.read_text())
    # Retire the V1 WM flags from the fixture namespace as well as the
    # production flag readers. The upstream test requires exact parity.
    for obsolete in ("-wex-yoga-hdmi2-safe","-wex-yoga-hdmi2-observe"):
        if obsolete not in j:raise RuntimeError("V1 fixture missing: "+obsolete)
        del j[obsolete]
    for x in ("-wex-yoga-hdmi2-callsite-safe","-wex-yoga-hdmi2-callsite-observe"):
        if x in j:raise RuntimeError("duplicate boot arg: "+x)
        j[x]=[]
    fixtures.write_text(json.dumps(j,indent=2)+"\n")
    assert '-wex-yoga-hdmi2-callsite-safe' in s
    assert 'WEXYogaHDMI2CallsiteLast' in s
    assert 'const uint32_t status=55' in s
    assert s.count('yogaHDMI2TryPrepare(')==1
    assert s.count('XE::yogaHDMI2Callsite(')==1
    assert 'orgDisplay13HDMI2TMDS' not in s
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)
    print("PASS V2: V1 unsafe WM SCDC path retired")
    print("PASS V2: one exact Apple 25G241 CALL site, original LightUpTMDS untouched")
    print("PASS V2: default OFF, observe mode never performs SCDC/MMIO")
    print("PASS V2: native recursive lock + nonblocking owner + sink readback required")
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path);parser.add_argument("graphics",type=Path)
    o=parser.parse_args();main(o.source.resolve(),o.graphics.resolve())
