#!/usr/bin/env python3
"""R5.1: diagnostic-only capture of the FIRST SCDC sink-version I2C read.

Apply AFTER R5-A overlay. Does not alter native I2C request fields,
number of transactions, return codes, retry count, GMBUS polling, HPD,
modeset, power callbacks, or source flags. Does not touch Graphics 0.4.4.
"""
from pathlib import Path
import argparse
import subprocess

def once(s,old,new,label):
    n=s.count(old)
    if n!=1:
        raise RuntimeError(f"R5.1 {label}: expected one exact anchor, got {n}")
    return s.replace(old,new,1)

TRACE_TYPE=r'''
// Diagnostic facts for SCDC 0x01 only; never authorizes a recovery.
struct YogaHDMI2SCDCI2CTrace {
    uint32_t requested {};
    uint32_t nativeCalled {};
    uint32_t disconnectedBefore {};
    uint32_t nativeReturn {};
    uint32_t requestResult {};
    uint32_t connectedAfter {}; // 0=lost, 1=valid, 2=not checked (native error)
    uint32_t fbIndex {};
    uint32_t ddc {};
    uint32_t reg {};
    uint64_t startTicks {};
    uint64_t elapsedTicks {};
};
'''

TRACE_PUBLISH=r'''
    // Publish only after the native LightUpTMDS call. Never add IOKit work
    // inside the original I2C request/response or under tglAUXLock.
    // schema, original CALL count, pipe, SCDC outcome, reg, request/native
    // evidence, real native code, native request.result, surviving generation,
    // FB index, DDC bus, start and elapsed ticks.
    if(yogaHDMI2WakeDiag && yogaSCDCI2CTrace.requested) {
        uint64_t i2cRecord[] {
            1U,count,pipe,status,
            yogaSCDCI2CTrace.reg,yogaSCDCI2CTrace.nativeCalled,
            yogaSCDCI2CTrace.disconnectedBefore,
            yogaSCDCI2CTrace.nativeReturn,
            yogaSCDCI2CTrace.requestResult,
            yogaSCDCI2CTrace.connectedAfter,
            yogaSCDCI2CTrace.fbIndex,
            yogaSCDCI2CTrace.ddc,
            yogaSCDCI2CTrace.startTicks,
            yogaSCDCI2CTrace.elapsedTicks,
            __atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE)
        };
        auto root=IORegistryEntry::getRegistryRoot();
        root->setProperty("WEXYogaHDMI2SCDCI2CLast",
                          i2cRecord,sizeof(i2cRecord));
        char i2cKey[52];
        snprintf(i2cKey,sizeof(i2cKey),"WEXYogaHDMI2SCDCI2CHist%02u",
                 static_cast<unsigned>((count-1U)%32U+1U));
        root->setProperty(i2cKey,i2cRecord,sizeof(i2cRecord));
    }
'''

def candidate(s):
    s=once(s,'struct YogaHDMI2Bus {',
           TRACE_TYPE+'\nstruct YogaHDMI2Bus {',
           'read-only trace data type')
    s=once(s,'    Native native {};\n',
           '    Native native {};\n    YogaHDMI2SCDCI2CTrace *trace {};\n',
           'passive trace pointer in native bus')
    s=once(s,
        '''        if(!connected())return false;
        IOI2CRequest request {};''',
        '''        const bool traceVersion=trace && read && reg==0x01;
        if(traceVersion) {
            trace->requested=1U;
            trace->reg=reg;
            trace->fbIndex=fbIndex;
            trace->ddc=ddc;
        }
        if(!connected()) {
            if(traceVersion)trace->disconnectedBefore=1U;
            return false;
        }
        IOI2CRequest request {};''',
        'record matching SCDC request without extra I2C')
    s=once(s,
        '''        request.result=kIOReturnNotReady;
        const auto status=native(controller,fbIndex,ddc,0,nullptr,&request);
        return !status && !request.result && connected();''',
        '''        request.result=kIOReturnNotReady;
        const uint64_t traceStarted=traceVersion?mach_absolute_time():0ULL;
        const auto status=native(controller,fbIndex,ddc,0,nullptr,&request);
        // Preserve the original short-circuit: connected() is called only
        // when native status AND request.result report success.
        const bool okay=!status && !request.result && connected();
        if(traceVersion) {
            trace->nativeCalled=1U;
            trace->nativeReturn=static_cast<uint32_t>(status);
            trace->requestResult=static_cast<uint32_t>(request.result);
            trace->connectedAfter=(!status && !request.result)?
                                  (okay?1U:0U):2U;
            trace->startTicks=traceStarted;
            trace->elapsedTicks=mach_absolute_time()-traceStarted;
        }
        return okay;''',
        'native return and request-result capture')
    s=once(s,
        '''       OSObject *path,uint64_t pixelHz, bool allowWrite,IOSimpleLock *lock) {''',
        '''       OSObject *path,uint64_t pixelHz, bool allowWrite,IOSimpleLock *lock,
       YogaHDMI2SCDCI2CTrace *trace=nullptr) {''',
        'optional diagnostic parameter')
    s=once(s,
        'reinterpret_cast<YogaHDMI2Bus::Native>(yogaHDMI2NativeI2C)',
        'reinterpret_cast<YogaHDMI2Bus::Native>(yogaHDMI2NativeI2C),trace',
        'attach trace to same unmodified native bus')
    return s

def cpp(s):
    s=once(s,
        '''    uint64_t record[12] {2,count};
''',
        '''    uint64_t record[12] {2,count};
    YogaHDMI2SCDCI2CTrace yogaSCDCI2CTrace {};
''',
        'per-call diagnostic local')
    s=once(s,
        '''clock,true,tglAUXLock);''',
        '''clock,true,tglAUXLock,
                                        yogaHDMI2WakeDiag?&yogaSCDCI2CTrace:nullptr);''',
        'passively record original callsite')
    s=once(s,
        '''    record[10]=result;record[11]=__atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE);
''',
        '''    record[10]=result;record[11]=__atomic_load_n(&yogaHDMI2ArmedPipe,__ATOMIC_ACQUIRE);
'''+TRACE_PUBLISH,
        'publish only on return from original native modeset')
    return s

def main(root):
    h=root/"WhateverXe/kern_yoga_hdmi2_candidate.hpp"
    x=root/"WhateverXe/kern_xe.cpp"
    hs=candidate(h.read_text())
    xs=cpp(x.read_text())
    assert hs.count("YogaHDMI2::prepareSCDC(")==1
    assert xs.count("patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));")==1
    assert "yogaHDMI2WakeRecover=(state==5 && yogaHDMI2CallsiteSafe &&" in xs
    assert "YogaHDMI2R5::nativeWakeMatches(" in hs
    assert "YogaHDMI2R5::sameBoundPipe(" in hs
    # One native SCDC call, unchanged; no new native call sites.
    assert hs.count("native(controller,fbIndex,ddc,0,nullptr,&request)")==1
    assert xs.count("WEXYogaHDMI2SCDCI2CLast")==1
    h.write_text(hs)
    x.write_text(xs)
    subprocess.run(["git","-C",str(root),"diff","--check"],check=True)
    print("PASS R5.1: native return and request.result for SCDC register 0x01")
    print("PASS R5.1: capture occurs only in wake-diag, no extra I2C/MMIO/HPD/modeset")
    print("PASS R5.1: original short-circuit guards and SCDC failure behavior preserved")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("source",type=Path)
    main(ap.parse_args().source.resolve())
