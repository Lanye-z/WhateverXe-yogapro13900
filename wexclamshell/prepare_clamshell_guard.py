#!/usr/bin/env python3
"""R5-Clamshell: opt-in lid-epoch guard for cached HDMI-B wake transactions.

Apply *after* R5-A. The default branch, native power callback semantics,
full SCDC readback, startup 4K60 and 2-external-display steady clamshell
behavior are unchanged without -wex-yoga-hdmi2-clamshell-guard.

The guard only denies one already-optional cached CTA wake restore when the
physical lid changed state *during* the HDMI framebuffer's Doze interval.
Native LightUpTMDS, DP/SST, eDP, HPD, PHY, PLL, DBUF, WM and modeset remain
unchanged. Does not force any display awake or synthesize connection events.
"""
import argparse
from pathlib import Path
import json
import shutil
import subprocess

HERE=Path(__file__).resolve().parent

def once(s,old,new,why):
    n=s.count(old)
    if n!=1:
        raise RuntimeError(f"R5-Clamshell {why}: wanted 1 exact anchor; found {n}")
    return s.replace(old,new,1)

CANDIDATE_STATE=r'''
// Read the documented IOPMrootDomain lid property only inside the existing
// native framebuffer power callback, never under tglAUXLock or during SCDC I2C.
// 0=open, 1=closed, 2=unknown. Unknown fails closed for cached 110 only.
static bool yogaHDMI2ClamshellGuard {};
static volatile uint32_t yogaHDMI2ClamshellDozeLid {2U};
static volatile uint32_t yogaHDMI2ClamshellWakeLid {2U};
static volatile uint32_t yogaHDMI2ClamshellTraceSeq {};
static inline uint32_t yogaHDMI2ClamshellReadLid() {
    // IOPMrootDomain is a single-inheritance IOService subclass in XNU.\n    // The pinned SDK exposes its accessor but not its private class header.\n    auto *root=reinterpret_cast<IOService *>(IOService::getPMRootDomain());
    if(!root)return 2U;
    auto *state=OSDynamicCast(OSBoolean,root->getProperty("AppleClamshellState"));
    return state?(state->getValue()?1U:0U):2U;
}
'''

def patch_header(s):
    s=once(s,
        '#include "kern_yoga_hdmi2_dynamic_policy.hpp"',
        '#include "kern_yoga_hdmi2_dynamic_policy.hpp"\n'
        '#include "kern_yoga_hdmi2_clamshell_guard.hpp"\n'
        '#include <IOKit/IOService.h>\n'
        '#include <libkern/c++/OSBoolean.h>',
        'isolated clamshell header')
    s=once(s,
        'static volatile uintptr_t yogaHDMI2WakeActiveWakeFB {};',
        'static volatile uintptr_t yogaHDMI2WakeActiveWakeFB {};\n'+CANDIDATE_STATE,
        'lid capture state after R5 dynamic framebuffer')
    # When the original verified HDMI EDID changes, never inherit the old
    # lid epoch alongside the already-invalidated R5 identity.
    s=once(s,
        '''            yogaHDMI2WakeProven.valid=false;
            __atomic_store_n(&yogaHDMI2WakeDozeFB,static_cast<uintptr_t>(0),__ATOMIC_RELEASE);''',
        '''            yogaHDMI2WakeProven.valid=false;
            __atomic_store_n(&yogaHDMI2ClamshellDozeLid,2U,__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2ClamshellWakeLid,2U,__ATOMIC_RELEASE);
            __atomic_store_n(&yogaHDMI2WakeDozeFB,static_cast<uintptr_t>(0),__ATOMIC_RELEASE);''',
        'invalidate lid epoch along with changed EDID')
    s=once(s,
        '''                // A new genuine native SCDC/CTA session rebases future Doze''',
        '''                // A new genuine native SCDC/CTA session rebases future Doze''',
        'keep new session anchor')
    # Ensure new genuine CTA session does not leave a previous clamshell token.
    s=once(s,
        '''                __atomic_store_n(&yogaHDMI2WakeDozeFB,static_cast<uintptr_t>(0),__ATOMIC_RELEASE);''',
        '''                __atomic_store_n(&yogaHDMI2ClamshellDozeLid,2U,__ATOMIC_RELEASE);
                __atomic_store_n(&yogaHDMI2ClamshellWakeLid,2U,__ATOMIC_RELEASE);
                __atomic_store_n(&yogaHDMI2WakeDozeFB,static_cast<uintptr_t>(0),__ATOMIC_RELEASE);''',
        'rebase lid epoch on genuine HDMI high mode')
    return s

TRACE=r'''
        if(yogaHDMI2WakeDiag && yogaHDMI2ClamshellGuard &&
           ((state==1U && yogaPowerPrior==2U) ||
            (state==2U && yogaPowerPrior==1U))) {
            const auto seq=__sync_add_and_fetch(&yogaHDMI2ClamshellTraceSeq,1U);
            uint64_t lidRecord[] {
                1U,seq,mach_absolute_time(),
                yogaPowerIndex,yogaPowerPrior,state,result,
                __atomic_load_n(&yogaHDMI2ClamshellDozeLid,__ATOMIC_ACQUIRE),
                __atomic_load_n(&yogaHDMI2ClamshellWakeLid,__ATOMIC_ACQUIRE),
                yogaClamshellSame?1ULL:0ULL,
                yogaPowerWindow?1ULL:0ULL
            };
            auto *root=IORegistryEntry::getRegistryRoot();
            root->setProperty("WEXYogaHDMI2ClamshellLast",
                              lidRecord,sizeof(lidRecord));
            char key[52];
            snprintf(key,sizeof(key),"WEXYogaHDMI2ClamshellHist%02u",
                     static_cast<unsigned>((seq-1U)%32U+1U));
            root->setProperty(key,lidRecord,sizeof(lidRecord));
        }
'''

def patch_power(s):
    s=once(s,
        '''    const bool yogaPowerWasDoze=yogaPowerTarget && state==2U &&''',
        '''    // At a genuine native HDMI Doze->Wake, compare the physical lid
    // with its state at the matching HDMI Wake->Doze. The observation is
    // outside the GMBUS/CTA lock and before the donor power callback.
    const uint32_t yogaClamshellNow =
        (yogaHDMI2ClamshellGuard && yogaPowerTarget &&
         state==2U && yogaPowerPrior==1U) ?
        yogaHDMI2ClamshellReadLid() : 2U;
    const bool yogaClamshellSame =
        YogaHDMI2Clamshell::cachedWakePermitted(
            yogaHDMI2ClamshellGuard,
            __atomic_load_n(&yogaHDMI2ClamshellDozeLid,__ATOMIC_ACQUIRE),
            yogaClamshellNow);
    if(yogaHDMI2ClamshellGuard && yogaPowerTarget &&
       state==2U && yogaPowerPrior==1U)
        __atomic_store_n(&yogaHDMI2ClamshellWakeLid,
                         yogaClamshellNow,__ATOMIC_RELEASE);
    const bool yogaPowerWasDoze=yogaPowerTarget && state==2U &&
        yogaClamshellSame &&''',
        'exclude cached 110 when the lid layout changed')
    s=once(s,
        '''            __atomic_store_n(&yogaHDMI2WakeDozeFB,
                confirmed?reinterpret_cast<uintptr_t>(fb):static_cast<uintptr_t>(0),
                __ATOMIC_RELEASE);''',
        '''            if(yogaHDMI2ClamshellGuard) {
                const uint32_t lid=confirmed?yogaHDMI2ClamshellReadLid():2U;
                __atomic_store_n(&yogaHDMI2ClamshellDozeLid,
                                 lid,__ATOMIC_RELEASE);
                __atomic_store_n(&yogaHDMI2ClamshellWakeLid,
                                 2U,__ATOMIC_RELEASE);
            }
            __atomic_store_n(&yogaHDMI2WakeDozeFB,
                confirmed?reinterpret_cast<uintptr_t>(fb):static_cast<uintptr_t>(0),
                __ATOMIC_RELEASE);''',
        'capture lid on genuine confirmed native Doze')
    s=once(s,
        '''                YogaHDMI2R5::samePowerObject(
                    __atomic_load_n(&yogaHDMI2WakeDozeFB,__ATOMIC_ACQUIRE),
                    reinterpret_cast<uintptr_t>(fb));''',
        '''                YogaHDMI2R5::samePowerObject(
                    __atomic_load_n(&yogaHDMI2WakeDozeFB,__ATOMIC_ACQUIRE),
                    reinterpret_cast<uintptr_t>(fb)) &&
                yogaClamshellSame;''',
        'do not authorize later low-mode reconcile on changed lid epoch')
    s=once(s,
        '''        if(yogaHDMI2WakeDiag && ((state==1U && yogaPowerPrior==2U) ||
                                 (state==2U && yogaPowerPrior==1U))) {''',
        TRACE+'''        if(yogaHDMI2WakeDiag && ((state==1U && yogaPowerPrior==2U) ||
                                 (state==2U && yogaPowerPrior==1U))) {''',
        'read-only 32-entry clamshell trace')
    return s

def patch_cpp(s):
    s=once(s,
        '''root->setProperty("WEXYogaHDMI2WakeRecoverEnabled",yogaHDMI2WakeRecover);''',
        '''root->setProperty("WEXYogaHDMI2WakeRecoverEnabled",yogaHDMI2WakeRecover);
            yogaHDMI2ClamshellGuard=yogaHDMI2WakeRecover &&
                checkKernelArgument("-wex-yoga-hdmi2-clamshell-guard");
            root->setProperty("WEXYogaHDMI2ClamshellGuardEnabled",
                              yogaHDMI2ClamshellGuard);''',
        'opt-in only with existing R5-B')
    return s

def main(source):
    h=source/'WhateverXe/kern_yoga_hdmi2_candidate.hpp'
    p=source/'WhateverXe/kern_display13_framebuffer_power.inc'
    c=source/'WhateverXe/kern_xe.cpp'
    f=source/'tests/fixtures/boot_argument_names.json'
    nh=patch_header(h.read_text())
    np=patch_power(p.read_text())
    nc=patch_cpp(c.read_text())
    args=json.loads(f.read_text())
    flag="-wex-yoga-hdmi2-clamshell-guard"
    if flag in args:raise RuntimeError('already added flag')
    args[flag]=[]
    target=source/'WhateverXe/kern_yoga_hdmi2_clamshell_guard.hpp'
    if target.exists():raise RuntimeError('guard header already installed')
    assert nh.count('YogaHDMI2::prepareSCDC(')==1
    assert np.count('FunctionCast(wrapDisplay13SetPowerState,callbackXE->orgDSIAttributes[2])(fb,state);')==1
    assert nc.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
    assert 'YogaHDMI2R5::nativeWakeMatches(' in nh
    assert 'YogaHDMI2R5::sameBoundPipe(yogaPowerIndex,yogaPowerBoundPipe)' in np
    h.write_text(nh)
    p.write_text(np)
    c.write_text(nc)
    f.write_text(json.dumps(args,indent=2)+'\n')
    shutil.copyfile(HERE/'kern_yoga_hdmi2_clamshell_guard.hpp',target)
    subprocess.run(['git','-C',str(source),'diff','--check'],check=True)
    print('PASS R5-Clamshell: opt-in only; unchanged native LightUpTMDS and power callback')
    print('PASS R5-Clamshell: lid mismatch denies cached SCDC wake and stale low reconcile')
    print('PASS R5-Clamshell: no new HPD/modeset/I2C, no eDP, SST, WM/DBUF/PHY/PLL edits')

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    main(parser.parse_args().source.resolve())
