#!/usr/bin/env python3
"""Non-invasive DDI5 failure telemetry on proven Deep8+HDMI600.
No new native route, no changed returns, MMIO writes, PLL/PHY or HPD patches.
"""
from pathlib import Path
from importlib.util import module_from_spec,spec_from_file_location
import argparse,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
def once(s,old,new,label):
    n=s.count(old)
    if n!=1:raise RuntimeError(f"{label}: need 1 exact anchor, found {n}")
    return s.replace(old,new,1)
def method(s,a,b,fn):
    i=s.index(a);j=s.index(b,i+len(a))
    return s[:i]+fn(s[i:j])+s[j:]
def run(source,graphics):
    sp=spec_from_file_location("yoga_stable_hdmi600",ROOT/"wex600/prepare_hdmi600_observe.py")
    m=module_from_spec(sp);sp.loader.exec_module(m);m.prepare(source,graphics)
    hpp=source/"WhateverXe/kern_xe.hpp";cpp=source/"WhateverXe/kern_xe.cpp"
    h=hpp.read_text();s=cpp.read_text()
    h=once(h,"bool display13FBSSTHooksReady {};",
      "bool display13FBSSTHooksReady {};\n bool yogaUSBCDPDiagEnabled {false};\n void yogaUSBCDPDiagSnapshot(void *,uint32_t *);",
      "safe fields / non-virtual helper")
    hpp.write_text(h)
    init='''        root->setProperty("WEXYogaHDMI600Status",status,32);
    }
'''
    s=once(s,init,init+'''    yogaUSBCDPDiagEnabled=checkKernelArgument("-wex-yoga-usbc-dpdiag") &&
        xeProfile.identity==0xA7A08086U && adlpDisplaySelected &&
        display13FramebufferRequested && (adlnOutputWiring.typeC&(1U<<5));
    IORegistryEntry::getRegistryRoot()->setProperty(
        "WEXYogaUSBCDPDiagEnabled",yogaUSBCDPDiagEnabled);
''',"A7A0 TC5-only opt in")
    diagnostic=r'''
void XE::yogaUSBCDPDiagSnapshot(void *controller,uint32_t *rec) {
    if(!rec)return;
    auto s=callbackXE;auto &c=display13FBPower;
    rec[0]=1;rec[1]=5;
    if(!s->yogaUSBCDPDiagEnabled || !c.lock || !s->tglPortByDDI)return;
    // Preserve the original port lookup -> Display13 lock order; do NOT
    // invoke the native port lookup while holding the Display13 IOLock.
    auto p=static_cast<OSObject *>(reinterpret_cast<void *(*)(uint32_t)>(s->tglPortByDDI)(5));
    IOLockLock(c.lock);
    const bool valid=p && p->getMetaClass()->getClassSize()>=0x624;
    auto cfg=valid ? Display13FBMemory::field<uint32_t *>(p,0x548) : nullptr;
    rec[2]=controller==c.controller;
    rec[3]=c.clockFaulted;rec[4]=c.clockStopped;
    rec[5]=c.memoryFaulted;rec[6]=c.watermarkFaulted;
    rec[7]=c.panelFaulted;rec[8]=c.bridge.state.faulted;rec[9]=c.bridge.state.suspended;
    rec[10]=valid;rec[11]=bool(display13SSTPort(p));
    rec[12]=cfg?cfg[0]:UINT32_MAX;
    rec[13]=valid?Display13FBMemory::field<uint32_t>(p,0x550):UINT32_MAX;
    rec[14]=valid?Display13FBMemory::field<uint32_t>(p,0x120):UINT32_MAX;
    rec[15]=valid?reinterpret_cast<const uint8_t *>(p)[0x117]:UINT32_MAX;
    rec[16]=cfg && Display13FBTopology::selected(s->adlnPlatform,cfg,s->adlnOutputWiring);
    rec[17]=bool(s->adlnOutputWiring.links()&(1U<<5));
    rec[18]=valid && Display13FBMemory::field<void *>(p,0x578)==c.access;
    rec[19]=controller==s->adlnTopologyController;
    IOLockUnlock(c.lock);
}
'''
    s=once(s,"uint32_t XE::wrapTGLTraining(void *controller, void *request, void *output) {",
       "#ifndef WEX_DPDIAG_TEST_MOCK\n"+diagnostic+"\n#endif\nuint32_t XE::wrapTGLTraining(void *controller, void *request, void *output) {",
       "snapshot helper: no new hook")
    def training(x):
        return once(x,"\trecord[2] = r;",'''\trecord[2] = r;
    // Outside power/pool locks: publish conditions responsible for the
    // first NotReady vs later preflight Busy. No influence on the result.
#ifndef WEX_DPDIAG_TEST_MOCK
    if(callbackXE->yogaUSBCDPDiagEnabled && id==6) {
        uint32_t diag[24] {};
        callbackXE->yogaUSBCDPDiagSnapshot(controller,diag);
        diag[20]=record[0];diag[21]=r;
        diag[22]=selected!=nullptr;diag[23]=leaseError;
        auto root=IORegistryEntry::getRegistryRoot();
        root->setProperty("WEXYogaUSBCDPTrainingLast",diag,sizeof(diag));
        if(record[0]<=8) {
            char key[48];snprintf(key,sizeof(key),"WEXYogaUSBCDPTrainingFirst%u",record[0]);
            root->setProperty(key,diag,sizeof(diag));
        }
    }
#endif''',"post-training diagnostics")
    s=method(s,"uint32_t XE::wrapTGLTraining(","\nuint32_t XE::wrapTGLTrainingEnd(",training)
    def stop(x):
        x=once(x," IOLockLock(c.lock);auto p=display13SSTPort(port);Display13FBPowerIO power{c.map};bool ok=false;",
          '''#ifndef WEX_DPDIAG_TEST_MOCK
 uint32_t stop[16] {};stop[0]=1;
#endif
 IOLockLock(c.lock);auto p=display13SSTPort(port);Display13FBPowerIO power{c.map};bool ok=false;
#ifndef WEX_DPDIAG_TEST_MOCK
 stop[1]=p!=nullptr;stop[3]=pipe;
#endif''',"stop setup")
        x=once(x," if(p && c.bridge.pipeHeld(power,pipe)) {",
          ''' if(p && c.bridge.pipeHeld(power,pipe)) {
#ifndef WEX_DPDIAG_TEST_MOCK
  if(s->yogaUSBCDPDiagEnabled)stop[2]=1;
#endif''',
          "note power held without second power query")
        x=once(x,"  auto &deferred=display13DeferredClocks[pipe];",
          '''  auto &deferred=display13DeferredClocks[pipe];
#ifndef WEX_DPDIAG_TEST_MOCK
  if(s->yogaUSBCDPDiagEnabled && ddi==5) {
   stop[4]=buffer;stop[5]=conf;stop[6]=func;stop[7]=tp;stop[8]=clock;
   stop[9]=deferred.pending;stop[10]=deferred.port==port;
   stop[11]=c.bridge.nativeDDIRefs(ddi);stop[12]=c.clockFaulted;
  }
#endif''',"stop register values already read by native code")
        return once(x," IOLockUnlock(c.lock);return ok;",
          ''' IOLockUnlock(c.lock);
#ifndef WEX_DPDIAG_TEST_MOCK
 if(!ok && s->yogaUSBCDPDiagEnabled && stop[1] && stop[3]<3)
  IORegistryEntry::getRegistryRoot()->setProperty("WEXYogaUSBCDPStopDetail",stop,sizeof(stop));
#endif
 return ok;''',"nonblocking publish after lock")
    s=method(s,"bool XE::display13StopTranscoder(","\nbool XE::processDisplay13FramebufferSST(",stop)
    cpp.write_text(s)
    # Production telemetry uses IOKit; native mock fixtures lack IOKit and
    # must omit only this observational code via a test-only preprocessor flag.
    mock=source/"tests/tgl_training_leases.py"
    t=mock.read_text()
    t=once(t,
        'code = (repo / "tests/tgl_training_leases_fixture.cpp").read_text()',
        'code = "#define WEX_DPDIAG_TEST_MOCK\\n" + (repo / "tests/tgl_training_leases_fixture.cpp").read_text()',
        "TGL training fixture guard")
    mock.write_text(t)
    mock=source/"tests/display13_training_frontend.py"
    t=mock.read_text()
    t=once(t,
        "prefix='''#include <mutex>",
        "prefix='''#define WEX_DPDIAG_TEST_MOCK\n#include <mutex>",
        "Display13 production binding fixture guard")
    mock.write_text(t)
    flags=source/"tests/fixtures/boot_argument_names.json"
    args=json.loads(flags.read_text());flag="-wex-yoga-usbc-dpdiag"
    if flag in args:raise RuntimeError("duplicate boot flag")
    args[flag]=[];flags.write_text(json.dumps(args,indent=2)+"\n")
    assert s.count('WEXYogaUSBCDPTrainingLast')==1
    assert s.count('WEXYogaUSBCDPStopDetail')==1
    assert s.count('yogaUSBCDPDiagSnapshot(void *controller')==1
    assert "orgDisplay13HDMI2TMDS" not in s
    subprocess.run(["git","-C",str(source),"diff","--check"],check=True)
    print("PASS: no new routes or display registration hooks")
    print("PASS: read-only A7A0 TC5 opt-in; original training/stop returns retained")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("source",type=Path);p.add_argument("graphics",type=Path)
    a=p.parse_args();run(a.source.resolve(),a.graphics.resolve())
