#!/usr/bin/env python3
"""Build the opt-in Yoga A7A0 Video B overlay on the exact pinned E/main donor.

Default OFF: identical AppleGVA behaviour to E/main.
Opt-in: preserve IOVARendererID=0x1080080 on Intel 8086:A7A0 only.
IOGVAScaler remains hidden, avoiding an unrelated known-dangerous change.
No edits to Graphics, EFI, system bundles, or existing main integration scripts.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
START = "bool XE::wrapTGLAcceleratorStart(IOService *that, IOService *provider) {"
END = "\nbool XE::startAlderLakeNParentBoundary("
REGISTRY_ANCHOR = '  "-wex-yoga-rgb8": [],\n'
NEW_ARGUMENT = '  "-wex-yoga-video-b": [],\n'
REMOVAL = re.compile(
    r'(?P<indent>^[ \t]*)if \(callbackXE->adlpDisplaySelected\) \{\n'
    r'[ \t]*that->removeProperty\("IOVARendererID"\);\n'
    r'[ \t]*SYSLOG\("igfx", "OBS021 va: IOVARendererID not advertised '
    r'\(pixel transfer stays off the VA driver\)"\);\n'
    r'[ \t]*\}',
    flags=re.MULTILINE,
)


def inject(source: Path) -> None:
    cpp = source / "WhateverXe" / "kern_xe.cpp"
    code = cpp.read_text()
    if code.count(START) != 1:
        raise ValueError("Refused: unexpected accelerator start signature")
    start = code.index(START)
    end = code.find(END, start)
    if end == -1:
        raise ValueError("Refused: accelerator end anchor not found")
    prefix, section, suffix = code[:start], code[start:end], code[end:]

    if (section.count('that->setProperty("IOVARendererID", 0x1080080, 32)') != 1
            or section.count('that->setProperty("IOGVAHEVCDecode", "2")') != 1
            or section.count('that->removeProperty("IOGVAScaler")') != 1
            or section.count('that->removeProperty("IOVARendererID")') != 1):
        raise ValueError("Refused: unexpected VA codec property layout")
    if "WEXYogaVideoB" in code or 'checkKernelArgument("-wex-yoga-video-b")' in code:
        raise ValueError("Refused: overlay already present")

    matches = list(REMOVAL.finditer(section))
    if len(matches) != 1:
        raise ValueError(f"Refused: expected one renderer removal block, got {len(matches)}")
    original = matches[0].group(0)
    indent = matches[0].group("indent")
    # This is the only changed runtime behaviour. E's original block is
    # retained byte-for-byte and is still reached unless the opt-in and all
    # strict A7A0/renderer checks pass. The scaler removal is untouched.
    inserted = """// Yoga Video B (experimental): retain the known 0x1080080 renderer ID
// ONLY for actual Intel 8086:A7A0 when explicitly requested.
// This may re-enable native VA paths and may reproduce the D BGRA crash.
const bool videoBRequested=checkKernelArgument("-wex-yoga-video-b");
auto videoBPci=videoBRequested ? OSDynamicCast(IOPCIDevice,provider) : nullptr;
const bool videoBMatched=videoBRequested && callbackXE->adlpDisplaySelected &&
    videoBPci && videoBPci->configRead16(0x00)==0x8086 &&
    videoBPci->configRead16(0x02)==0xA7A0;
auto videoBRenderer=videoBMatched ?
    OSDynamicCast(OSNumber,that->getProperty("IOVARendererID")) : nullptr;
const bool videoBPreserve=videoBRenderer &&
    videoBRenderer->unsigned32BitValue()==0x1080080;
auto videoBRoot=IORegistryEntry::getRegistryRoot();
videoBRoot->setProperty("WEXYogaVideoBRequested",videoBRequested);
videoBRoot->setProperty("WEXYogaVideoBMatched",videoBMatched);
videoBRoot->setProperty("WEXYogaVideoBRendererPreserved",videoBPreserve);
"""
    new_block = "".join(indent + s + "\n" for s in inserted.splitlines())
    # Extend exactly the original guard; leave original log and removal
    # sequence unchanged for no-flag or non-A7A0 machines.
    replaced = original.replace(
        "if (callbackXE->adlpDisplaySelected) {",
        "if (callbackXE->adlpDisplaySelected && !videoBPreserve) {",
        1,
    )
    section = section[:matches[0].start()] + new_block + replaced + section[matches[0].end():]
    merged = prefix + section + suffix
    if merged.count('that->removeProperty("IOGVAScaler")') != code.count('that->removeProperty("IOGVAScaler")'):
        raise ValueError("Refused: scaler code was unexpectedly changed")
    if merged.count('checkKernelArgument("-wex-yoga-video-b")') != 1:
        raise ValueError("Refused: wrong opt-in gate count")

    fixture = source / "tests" / "fixtures" / "boot_argument_names.json"
    registry = fixture.read_text()
    if registry.count(REGISTRY_ANCHOR) != 1 or NEW_ARGUMENT in registry:
        raise ValueError("Refused: boot-argument fixture differs from pinned E/main")
    cpp.write_text(merged)
    fixture.write_text(registry.replace(REGISTRY_ANCHOR, NEW_ARGUMENT + REGISTRY_ANCHOR, 1))

    subprocess.run(["git", "-C", str(source), "diff", "--check"], check=True)
    changed = set(subprocess.check_output(
        ["git", "-C", str(source), "diff", "--name-only"], text=True).splitlines())
    expected = {"WhateverXe/kern_alderlake_n.hpp",
                "WhateverXe/kern_xe.cpp", "tests/fixtures/boot_argument_names.json"}
    if changed != expected:
        raise ValueError("Refused: unexpected donor changes " + repr(changed))
    print("Video B prepared: renderer preserved ONLY with -wex-yoga-video-b on 8086:A7A0")
    print("No flag: original E renderer removal preserved. IOGVAScaler remains removed.")
    print("CAUTION: Re-enabling VA renderer may trigger native pixel-transfer crashes.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Clean pinned acer/current checkout")
    args = parser.parse_args()
    source = args.source.resolve()
    subprocess.run([
        "python3", str(ROOT / "e13/tools/prepare_rgb8.py"), str(source)
    ], check=True)
    inject(source)


if __name__ == "__main__":
    main()
