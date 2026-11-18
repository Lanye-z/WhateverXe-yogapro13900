#!/usr/bin/env python3
"""Pinned 0.8.3 test patcher: WM only, or WM plus opt-in clock gate retry."""
import argparse, json, subprocess
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

def replace_once(s, old, new, label):
    if s.count(old) != 1:
        raise RuntimeError('%s: matched %d times (expected 1)' % (label, s.count(old)))
    return s.replace(old, new, 1)

def main():
    a = argparse.ArgumentParser()
    a.add_argument('src', type=Path)
    a.add_argument('graphics', type=Path)
    a.add_argument('--trial', choices=('WM_ONLY', 'WM_GATE'), required=True)
    args = a.parse_args()
    src, graphics = args.src.resolve(), args.graphics.resolve()
    root = Path(__file__).resolve().parents[1]
    spec = spec_from_file_location('v1', root/'wex120/prepare_120.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare(src, graphics, 'V2')
    cpp = src/'WhateverXe/kern_xe.cpp'
    body = cpp.read_text()
    old = '''                if(!evidence[7]) {
                    ready=reinterpret_cast<bool (*)(IOWorkLoop *)>(callbackXE->adlnWorkLoopTryClose)(loop);
                    if(ready) {acquired=loop;evidence[8]=1;}
                }'''
    if body.count(old) != 1: raise RuntimeError('exact upstream workloop gate anchor drift')
    if args.trial == 'WM_GATE':
        new = '''                if(!evidence[7]) {
                    // #102 gated recovery: no change without A7A0 panel and opt-in.
                    const bool retry=yogaEDP120Scoped &&
                        checkKernelArgument("-wex-yoga-edp120-gateretry");
                    unsigned tries=0;
                    for(;;) {
                        ready=reinterpret_cast<bool (*)(IOWorkLoop *)>(callbackXE->adlnWorkLoopTryClose)(loop);
                        if(ready || !retry || tries>=50)break;
                        ++tries;IOLockUnlock(c.lock);IOSleep(1);IOLockLock(c.lock);
                    }
                    evidence[27]=tries;
                    if(ready) {acquired=loop;evidence[8]=1;}
                }'''
        body=replace_once(body,old,new,'bounded gate retry')
        anchor='    pci->setProperty("WEXYogaEDP120WMEnabled",Display13WM::yogaEDP120PipeMask()!=0);'
        newprop='''    pci->setProperty("WEXYogaEDP120GateRetryEnabled",
        yogaEDP120Scoped && checkKernelArgument("-wex-yoga-edp120-gateretry"));'''
        body=replace_once(body,anchor,anchor+'\n'+newprop,'report gate flag')
        cpp.write_text(body)
        fixture=src/'tests/fixtures/boot_argument_names.json'
        payload=json.loads(fixture.read_text())
        if '-wex-yoga-edp120-gateretry' in payload: raise RuntimeError('argument already registered')
        payload['-wex-yoga-edp120-gateretry']=[]
        fixture.write_text(json.dumps(payload,indent=2)+'\n')
    else:
        assert '-wex-yoga-edp120-gateretry' not in body
    changed=set(subprocess.check_output(['git','-C',str(src),'diff','--name-only'],text=True).splitlines())
    expected={'WhateverXe/kern_alderlake_n.hpp','WhateverXe/kern_xe.cpp',
        'WhateverXe/kern_xe.hpp','WhateverXe/kern_display13_wm.hpp',
        'tests/fixtures/boot_argument_names.json'}
    if changed != expected: raise RuntimeError('unexpected source files '+repr(changed))
    subprocess.run(['git','-C',str(src),'diff','--check'],check=True)
    print('VERIFIED PINNED 0.8.3 bootfix trial',args.trial)

if __name__=='__main__':
    main()
