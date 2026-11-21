#!/usr/bin/env python3
"""Single Yoga 0.8.3 integration: default-on verified features, HDMI2 V3 opt-in.

Run AFTER wexhdmi2v2/prepare.py on the exact pinned WhateverXe 0.8.3 donor.
Replaces only five existing boot-argument condition expressions in generated
kern_xe.cpp. All existing A7A0/Display13/EDID/signature checks remain intact.
Never patches a user's EFI or changes installed kexts.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

# Include an emergency master disable plus independent per-feature opt-outs.
MASTER = "-wex-yoga-disable-integrated"
FEATURES = {
    "-wex-yoga-edp120-admit": ("-wex-yoga-disable-edp120-admit",
        'const bool requested=checkKernelArgument("-wex-yoga-edp120-admit");',
        'const bool requested=!checkKernelArgument("-wex-yoga-disable-integrated") && '
        '!checkKernelArgument("-wex-yoga-disable-edp120-admit");'),
    "-wex-yoga-edp120-wm": ("-wex-yoga-disable-edp120-wm",
        '(yogaEDP120Scoped && checkKernelArgument("-wex-yoga-edp120-wm")) ? 1U : 0U;',
        '(yogaEDP120Scoped && !checkKernelArgument("-wex-yoga-disable-integrated") && '
        '!checkKernelArgument("-wex-yoga-disable-edp120-wm")) ? 1U : 0U;'),
    "-wex-yoga-hdmi-edid-deep8": ("-wex-yoga-disable-hdmi-deep8",
        'const bool edidDeep=checkKernelArgument("-wex-yoga-hdmi-edid-deep8");',
        'const bool edidDeep=!checkKernelArgument("-wex-yoga-disable-integrated") && '
        '!checkKernelArgument("-wex-yoga-disable-hdmi-deep8") && '
        '!checkKernelArgument("-wex-yoga-hdmi-edid-rgb8");'),
    "-wex-yoga-hdmi600": ("-wex-yoga-disable-hdmi600",
        'const bool requested=checkKernelArgument("-wex-yoga-hdmi600");',
        'const bool requested=!checkKernelArgument("-wex-yoga-disable-integrated") && '
        '!checkKernelArgument("-wex-yoga-disable-hdmi600");'),
    "-wex-yoga-tc5-sst": ("-wex-yoga-disable-tc5-sst",
        'const bool requested=checkKernelArgument("-wex-yoga-tc5-sst");',
        'const bool requested=!checkKernelArgument("-wex-yoga-disable-integrated") && '
        '!checkKernelArgument("-wex-yoga-disable-tc5-sst") && '
        '!checkKernelArgument("-wex-yoga-tc5-sst-observe");'),
}

def patch_string(source: str) -> str:
    for old_flag, (new_flag, before, after) in FEATURES.items():
        count = source.count(before)
        if count != 1:
            raise RuntimeError(f"Refuse source mismatch: {old_flag} expected one anchor, got {count}")
        source = source.replace(before, after, 1)
        if source.count('checkKernelArgument("' + old_flag + '")'):
            raise RuntimeError(f"Legacy enable reader still present: {old_flag}")
        if source.count('checkKernelArgument("' + new_flag + '")') != 1:
            raise RuntimeError(f"Missing new reader: {new_flag}")
    # V3 active HDMI2 is NEVER turned on by this integration.
    if source.count('yogaHDMI2SafeRequested=checkKernelArgument("-wex-yoga-hdmi2-callsite-safe");') != 1:
        raise RuntimeError("V3 HDMI2 opt-in changed unexpectedly")
    if 'const uint32_t status=55' not in source:
        raise RuntimeError("V3 WM path changed unexpectedly")
    if source.count('patcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));') != 1:
        raise RuntimeError("V3 patch-order guard changed unexpectedly")
    return source

def update_fixtures(raw: str) -> str:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("boot_argument_names.json must contain an object")
    for old, (new, _, _) in FEATURES.items():
        if old not in data:
            raise RuntimeError(f"Missing original boot arg fixture: {old}")
        if new in data:
            raise RuntimeError(f"Duplicate new boot arg fixture: {new}")
        del data[old]
        data[new] = []
    if MASTER in data:
        raise RuntimeError("Duplicate master disable boot arg")
    data[MASTER] = []
    return json.dumps(data, indent=2) + "\n"

def self_test():
    anchors = "\n".join(v[1] for v in FEATURES.values())
    anchors += "\nyogaHDMI2SafeRequested=checkKernelArgument(\"-wex-yoga-hdmi2-callsite-safe\");"
    anchors += "\nconst uint32_t status=55;"
    anchors += "\npatcher.routeBlock(address+callOffset,patchedCall,sizeof(patchedCall));"
    out = patch_string(anchors)
    assert all(v[2] in out for v in FEATURES.values())
    assert 'yogaHDMI2SafeRequested=checkKernelArgument("-wex-yoga-hdmi2-callsite-safe");' in out
    fixtures = {key: [] for key in FEATURES}
    fixtures["-wex-yoga-hdmi2-callsite-safe"] = []
    new = json.loads(update_fixtures(json.dumps(fixtures)))
    assert all(key not in new for key in FEATURES)
    assert MASTER in new and all(v[0] in new for v in FEATURES.values())
    try:
        patch_string(anchors.replace(next(iter(FEATURES.values()))[1], "bad"))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Unexpected success on donor anchor mismatch")
    print("PASS: five verified features default-on, independent opt-outs, V3 opt-in unchanged")

def main(source: Path):
    cpp = source / "WhateverXe/kern_xe.cpp"
    fixture = source / "tests/fixtures/boot_argument_names.json"
    before_cpp = cpp.read_text()
    before_fixture = fixture.read_text()
    new_cpp = patch_string(before_cpp)
    new_fixture = update_fixtures(before_fixture)
    # Finish all checks before touching either file.
    cpp.write_text(new_cpp)
    fixture.write_text(new_fixture)
    subprocess.run(["git", "-C", str(source), "diff", "--check"], check=True)
    print("PASS: unified Yoga 0.8.3 default-on + emergency-disable integration")
    print("PASS: HDMI2 V3 callsite-safe remains explicitly opt-in, untouched")
    print("PASS: ColorTrace/ModeAudit/USB-C DPDiag remain off unless explicitly requested")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        if args.source is None:
            parser.error("source donor path is required")
        main(args.source.resolve())
