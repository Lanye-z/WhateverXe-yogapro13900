#!/usr/bin/env python3
"""Prepare A7A0/U27P10 native HDMI EDID capability A/B tests.

Pinned upstream source + WM_ONLY(V2) + HPD + ColorTrace + prior ColorPolicy audit.
Only CTA block 2 on the validated native HDMI B path can be modified.
No whole-EDID substitution, serial exposure, clock hacks or direct MMIO writes.
"""
import argparse,json,subprocess
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec

EXPERIMENT=r'''    // Experimental sink *capability* inputs to the donor's native
    // modeset; not post-activation register edits. Default OFF.
    const bool edidDeep=checkKernelArgument("-wex-yoga-hdmi-edid-deep8");
    const bool edidRgb=checkKernelArgument("-wex-yoga-hdmi-edid-rgb8");
    if((edidDeep || edidRgb) && block==2 && selected && config &&
       config[0]==1 && !result && data &&
       callbackXE->adlpDisplaySelected && callbackXE->yogaEDP120Scoped &&
       callbackXE->adlnOutputWiring.hdmi==2U &&
       callbackXE->adlnOutputWiring.transport(config[0])==
           Display13OutputWiring::Transport::TMDS) {
        const bool knownSink=__atomic_load_n(&yogaColorModeSinkU27,__ATOMIC_ACQUIRE)!=0;
        YogaHDMIEDIDAB::Outcome outcome {};
        if(knownSink && !(edidDeep && edidRgb)) {
            outcome=YogaHDMIEDIDAB::apply(data,
                edidRgb?YogaHDMIEDIDAB::Variant::Rgb8:
                        YogaHDMIEDIDAB::Variant::DeepColor8);
        }
        uint32_t record[15] {
            1U,static_cast<uint32_t>(edidDeep),static_cast<uint32_t>(edidRgb),
            static_cast<uint32_t>(knownSink),block,
            static_cast<uint32_t>(outcome.result),
            outcome.featureBefore,outcome.featureAfter,
            outcome.classicBefore,outcome.classicAfter,
            outcome.forumBefore,outcome.forumAfter,
            outcome.y420Before,outcome.y420After,
            (edidDeep && edidRgb)?1U:0U
        };
        root->setProperty("WEXYogaHDMIEDIDABLast",record,sizeof(record));
        if(outcome.result==YogaHDMIEDIDAB::Result::Applied)
            root->setProperty("WEXYogaHDMIEDIDABApplied",true);
    }
'''

def replace_once(s,a,b,what):
    n=s.count(a)
    if n!=1:raise RuntimeError(f"{what}: expected 1 anchor but found {n}")
    return s.replace(a,b,1)

def main(src:Path,graphics:Path):
    root=Path(__file__).resolve().parents[1]
    spec=spec_from_file_location("yoga_colorpolicy",root/"wexrgb/prepare_policy.py")
    mod=module_from_spec(spec);spec.loader.exec_module(mod)
    mod.main(src,graphics)

    cpp=src/"WhateverXe/kern_xe.cpp"
    s=cpp.read_text()
    s=replace_once(s,
        '#include "kern_yoga_hdmi_color_policy.hpp"',
        '#include "kern_yoga_hdmi_color_policy.hpp"\n#include "kern_yoga_hdmi_edid_ab.hpp"',
        "include CTA experiment helper")
    s=replace_once(s,
        '    cachePanelDepth(port,block,data,result);\n    // Exact AOC U27P10 identity only; keep native EDID bytes unchanged.',
        EXPERIMENT+'    cachePanelDepth(port,block,data,result);\n'
        '    // Base-read AOC U27P10 identity only; the base block is never changed.',
        "CTA post-DDC/pre-cache interception")
    cpp.write_text(s)
    (src/"WhateverXe/kern_yoga_hdmi_edid_ab.hpp").write_text(
        (root/"wexedid/kern_yoga_hdmi_edid_ab.hpp").read_text())

    args=src/"tests/fixtures/boot_argument_names.json"
    value=json.loads(args.read_text())
    for flag in ("-wex-yoga-hdmi-edid-deep8","-wex-yoga-hdmi-edid-rgb8"):
        if flag in value:raise RuntimeError("Existing boot argument: "+flag)
        value[flag]=[]
    args.write_text(json.dumps(value,indent=2)+"\n")
    changed=set(subprocess.check_output(["git","-C",str(src),"diff","--name-only"],
                                        text=True).splitlines())
    allowed={
        "WhateverXe/kern_alderlake_n.hpp",
        "WhateverXe/kern_xe.cpp","WhateverXe/kern_xe.hpp",
        "WhateverXe/kern_display13_wm.hpp",
        "tests/fixtures/boot_argument_names.json",
        "tests/display13_offline.py","tests/dsi_port_adapter.py"
    }
    if changed!=allowed:
        raise RuntimeError(f"unexpected modifications: {sorted(changed^allowed)}")
    for needle in ['WEXYogaHDMIEDIDABLast',
                   'WEXYogaHDMIColorLive','WEXYogaHDMIColorModeLive',
                   'checkKernelArgument("-wex-yoga-hdmi-edid-deep8")',
                   'checkKernelArgument("-wex-yoga-hdmi-edid-rgb8")']:
        if s.count(needle)!=1:raise RuntimeError("unexpected count "+needle)
    subprocess.run(["git","-C",str(src),"diff","--check"],check=True)
    print("PASS: U27P10 A/B EDID input modification is qualified and optional")
    print("PASS: existing WM / HPD / ColorTrace / native mode audit remain intact")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("src",type=Path);p.add_argument("graphics",type=Path)
    a=p.parse_args();main(a.src.resolve(),a.graphics.resolve())
