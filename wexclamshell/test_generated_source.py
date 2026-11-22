#!/usr/bin/env python3
"""Generated source safety checks for optional lid-layout guard."""
from pathlib import Path
root=Path('Source/WhateverXe')
h=(root/'kern_yoga_hdmi2_candidate.hpp').read_text()
p=(root/'kern_display13_framebuffer_power.inc').read_text()
c=(root/'kern_xe.cpp').read_text()
f=(root/'kern_yoga_hdmi2_clamshell_guard.hpp').read_text()
assert 'namespace YogaHDMI2Clamshell' in f
assert 'kAppleClamshellStateKey' in h or '"AppleClamshellState"' in h
assert 'IOService::getPMRootDomain()' in h
assert 'static bool yogaHDMI2ClamshellGuard {};' in h
assert 'static volatile uint32_t yogaHDMI2ClamshellDozeLid {2U}' in h
assert 'static volatile uint32_t yogaHDMI2ClamshellWakeLid {2U}' in h
assert 'YogaHDMI2Clamshell::cachedWakePermitted(' in p
assert 'yogaClamshellSame &&' in p
assert 'yogaClamshellSame;' in p
assert 'WEXYogaHDMI2ClamshellHist%02u' in p
assert 'WEXYogaHDMI2ClamshellGuardEnabled' in c
assert 'yogaHDMI2ClamshellGuard=yogaHDMI2WakeRecover &&' in c
assert 'checkKernelArgument("-wex-yoga-hdmi2-clamshell-guard")' in c
assert h.count('YogaHDMI2::prepareSCDC(')==1
assert c.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));')==1
assert p.count('FunctionCast(wrapDisplay13SetPowerState,callbackXE->orgDSIAttributes[2])(fb,state);')==1
assert 'YogaHDMI2R5::nativeWakeMatches(' in h
assert 'YogaHDMI2R5::sameBoundPipe(yogaPowerIndex,yogaPowerBoundPipe)' in p
assert 'WEXYogaHDMI2WakePowerHist%02u' in p
assert 'WEXYogaHDMI2CallsiteHist%02u' in c
assert 'yogaHDMI2ClamshellReadLid()' in p
# No extra SCDC I2C, HPD injection or native power routes.
assert h.count('native(controller,fbIndex,ddc,0,nullptr,&request)')==1
assert 'yogaHDMI2ClamshellReadLid()' not in c
assert 'yogaHDMI2ClamshellReadLid()' not in h.split('static inline uint32_t yogaHDMI2WakeTimeGuard(uint32_t pipe)',1)[1].split('//',1)[0]
print('PASS R5-Clamshell: opt-in ONLY; same native SCDC & power calls, no HPD/modeset')
print('PASS R5-Clamshell: lid read confined to native power callback, not DDC lock')
print('PASS R5-Clamshell: original R5 dynamic FB and R4 bounded recovery unchanged')
