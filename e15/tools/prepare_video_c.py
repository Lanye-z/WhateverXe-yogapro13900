#!/usr/bin/env python3
"""Create independent opt-in Video C (restore both D-style VA registry keys).

Based on the EXACT pinned E/main overlay. Default OFF is unmodified E behavior.
With -wex-yoga-video-c, only Intel 8086:A7A0 + expected 0x1080080
preserves BOTH IOVARendererID and IOGVAScaler. No VA binary modifications.

IMPORTANT: This is an unsafe diagnostic experiment, NOT a VPHAL crash fix.
The D1.1 and Video B 0x1336f3 native VA driver crash can persist.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
START = "bool XE::wrapTGLAcceleratorStart(IOService *that, IOService *provider) {"
END = "\nbool XE::startAlderLakeNParentBoundary("
SCALER = 'if (callbackXE->adlpDisplaySelected && that->getProperty("IOGVAScaler")) {'
RENDERER = 'if (callbackXE->adlpDisplaySelected) {\n\t\tthat->removeProperty("IOVARendererID");'
REGISTRY_ANCHOR = '  "-wex-yoga-rgb8": [],\n'
NEW_ARGUMENT = '  "-wex-yoga-video-c": [],\n'

INSERT = """// Yoga Video C (EXPERIMENTAL): restore both of D's VA properties only on
// the physical A7A0 with an explicit boot flag. DOES NOT fix VPHAL NULL+8.
const bool videoCRequested=checkKernelArgument("-wex-yoga-video-c");
auto videoCPci=videoCRequested ? OSDynamicCast(IOPCIDevice,provider) : nullptr;
const bool videoCMatched=videoCRequested && callbackXE->adlpDisplaySelected &&
    videoCPci && videoCPci->configRead16(0x00)==0x8086 &&
    videoCPci->configRead16(0x02)==0xA7A0;
auto videoCRenderer=videoCMatched ?
    OSDynamicCast(OSNumber,that->getProperty("IOVARendererID")) : nullptr;
const bool videoCPreserve=videoCRenderer &&
    videoCRenderer->unsigned32BitValue()==0x1080080;
const bool videoCScalerPresent=that->getProperty("IOGVAScaler")!=nullptr;
auto videoCRoot=IORegistryEntry::getRegistryRoot();
videoCRoot->setProperty("WEXYogaVideoCRequested",videoCRequested);
videoCRoot->setProperty("WEXYogaVideoCMatched",videoCMatched);
videoCRoot->setProperty("WEXYogaVideoCPropertiesPreserved",videoCPreserve);
videoCRoot->setProperty("WEXYogaVideoCScalerPresent",videoCScalerPresent);
"""


def patch(source: Path) -> None:
    cpp = source / "WhateverXe/kern_xe.cpp"
    code = cpp.read_text()
    if code.count(START) != 1:
        raise ValueError("Refused: accelerator start signature changed")
    a = code.index(START)
    b = code.find(END, a)
    if b < 0:
        raise ValueError("Refused: accelerator end signature changed")
    section = code[a:b]
    if (section.count(SCALER) != 1 or
            section.count(RENDERER) != 1 or
            section.count('that->setProperty("IOVARendererID", 0x1080080, 32)') != 1 or
            section.count('that->setProperty("IOGVAHEVCDecode", "2")') != 1 or
            section.count('that->removeProperty("IOGVAScaler")') != 1 or
            section.count('that->removeProperty("IOVARendererID")') != 1 or
            'WEXYogaVideoC' in code):
        raise ValueError("Refused: pinned E VA sequence mismatch")
    # Preserve all existing E logic when opt-in is false, including logs and
    # Scaler/RendererID removal. Only the two conditional expressions change.
    section = section.replace(
        SCALER,
        'if (callbackXE->adlpDisplaySelected && !videoCPreserve && '
        'that->getProperty("IOGVAScaler")) {', 1
    )
    section = section.replace(
        RENDERER,
        'if (callbackXE->adlpDisplaySelected && !videoCPreserve) {\n'
        '\t\tthat->removeProperty("IOVARendererID");', 1
    )
    insertion = "".join("\t" + line + "\n" for line in INSERT.splitlines())
    section = section.replace(
        '// Acer ANV15-52, Raptor Lake-P: AppleGVA\'s pixel transfer',
        insertion + '\t// Acer ANV15-52, Raptor Lake-P: AppleGVA\'s pixel transfer',
        1
    )
    updated = code[:a] + section + code[b:]
    if (updated.count('checkKernelArgument("-wex-yoga-video-c")') != 1 or
            updated.count('that->removeProperty("IOGVAScaler")') !=
            code.count('that->removeProperty("IOGVAScaler")') or
            updated.count('that->removeProperty("IOVARendererID")') !=
            code.count('that->removeProperty("IOVARendererID")')):
        raise ValueError("Refused: invalid gate or property-removal counts")
    fixture = source / "tests/fixtures/boot_argument_names.json"
    names = fixture.read_text()
    if names.count(REGISTRY_ANCHOR) != 1 or NEW_ARGUMENT in names:
        raise ValueError("Refused: boot-argument fixture mismatch")
    cpp.write_text(updated)
    fixture.write_text(names.replace(REGISTRY_ANCHOR,
        NEW_ARGUMENT + REGISTRY_ANCHOR, 1))
    subprocess.run(["git", "-C", str(source), "diff", "--check"], check=True)
    changed = set(subprocess.check_output(
        ["git", "-C", str(source), "diff", "--name-only"], text=True).splitlines())
    allowed = {"WhateverXe/kern_xe.cpp", "WhateverXe/kern_alderlake_n.hpp",
               "tests/fixtures/boot_argument_names.json"}
    if changed != allowed:
        raise ValueError("Refused: unexpected modified donor files: " + repr(changed))
    print("Video C created: original E behavior unless -wex-yoga-video-c on 8086:A7A0")
    print("When enabled, both IOVARendererID and IOGVAScaler are retained.")
    print("WARNING: does not fix the known VA-driver 0x1336f3 / NULL+8 crash.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    source = parser.parse_args().source.resolve()
    subprocess.run(["python3", str(ROOT / "e13/tools/prepare_rgb8.py"),
                    str(source)], check=True)
    patch(source)


if __name__ == "__main__":
    main()
