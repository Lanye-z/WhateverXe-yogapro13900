#!/usr/bin/env python3
"""Prepare opt-in, native WhateverXe Display13 HDMI EDID injection.

Runs *after* E1.1's pinned donor preparation. The exact-byte gate prevents
accidentally patching an unknown monitor or a different framebuffer ABI.
No system /Library, EFI, or Graphics binaries are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = '#include "kern_yoga_hdmi600.hpp"\n'
SIGNATURE = 'uint32_t XE::wrapAlderLakeNPortDDC(OSObject *port,uint32_t block,uint8_t *data,bool force) {'
ANCHOR = '    cachePanelDepth(port,block,data,result);\n'
ARG_KEY = '  "-wex-yoga-hdmi600": [],\n'
INSERT = r'''    // Yoga A7A0 HDMI: return the proven monitor-specific RGB8_STRICT
    // EDID from the *existing native DDC path*. Default OFF.
    // Never touch an eDP/DP/TC path or an unrelated EDID.
    const bool rgb8Requested=checkKernelArgument("-wex-yoga-rgb8");
    root->setProperty("WEXYogaRGB8Requested",rgb8Requested);
    if(!result && selected && data && config && rgb8Requested &&
       callbackXE->adlpDisplaySelected &&
       callbackXE->adlnOutputWiring.transport(config[0])==Display13OutputWiring::Transport::TMDS) {
        const auto outcome=YogaRGB8::rewrite(block,data);
        static uint32_t baseCount {},extensionCount {};
        if(outcome==YogaRGB8::Result::Applied) {
            if(block==1)__sync_add_and_fetch(&baseCount,1);
            else if(block==2)__sync_add_and_fetch(&extensionCount,1);
        }
        uint32_t resultInfo[] {config[0],block,static_cast<uint32_t>(outcome),
            __sync_add_and_fetch(&baseCount,0),
            __sync_add_and_fetch(&extensionCount,0)};
        root->setProperty("WEXYogaRGB8Last",resultInfo,sizeof(resultInfo));
        root->setProperty("WEXYogaRGB8Status",
            outcome==YogaRGB8::Result::Applied ? 4U :
            outcome==YogaRGB8::Result::Already ? 5U : 2U,32);
    }
'''


def check_edid(data: bytes) -> None:
    if len(data) != 256 or data[:8] != bytes.fromhex("00ffffffffffff00"):
        raise ValueError("Expected 256-byte EDID")
    if data[126] != 1:
        raise ValueError("Unexpected EDID extension count")
    if data[8:10] != bytes.fromhex("05e3") or data[10:12] != bytes.fromhex("1027"):
        raise ValueError("Not AOC 05E3:2710")
    if data[128] != 2:
        raise ValueError("CTA extension missing")
    for off in (0, 128):
        if sum(data[off:off + 128]) % 256:
            raise ValueError("EDID checksum failure")


def cpp_array(name: str, data: bytes) -> str:
    lines = [", ".join(f"0x{x:02x}" for x in data[i:i + 16])
             for i in range(0, len(data), 16)]
    return f"constexpr uint8_t {name}[128] {{\n    " + ",\n    ".join(lines) + "\n};\n"


def prepare_fixture() -> tuple[str, dict]:
    fixture = json.loads((ROOT / "e13/fixtures/u27p10.json").read_text())
    orig = bytes.fromhex(fixture["original_hex"])
    strict = bytes.fromhex(fixture["rgb8_strict_hex"])
    check_edid(orig)
    check_edid(strict)
    if orig == strict or orig[8:18] != strict[8:18]:
        raise ValueError("Wrong EDID variant or display identity")
    if orig[54:126] != strict[54:126]:
        raise ValueError("Base detailed timings were altered")
    if orig[128:132] != strict[128:132]:
        raise ValueError("CTA mode header changed")
    # The 4K60 advertised VICs and HDMI Forum max-TMDS (600MHz) stay present.
    must_preserve = (bytes.fromhex("5d5e5f6061"), bytes.fromhex("d85dc40178"))
    for marker in must_preserve:
        if marker not in orig or marker not in strict:
            raise ValueError("4K60/600MHz CTA capability was removed")
    header = '''// Generated from a real U27P10 RGB8_STRICT EDID. Exact-match only.
// Source monitor serial is in this *private* fixture: do not print EDID bytes.
// Opt-in at boot with -wex-yoga-rgb8. Disable flag to restore native reads.
#ifndef KERN_YOGA_RGB8_HPP
#define KERN_YOGA_RGB8_HPP
#include <stdint.h>
#include <string.h>
namespace YogaRGB8 {
enum class Result : uint32_t { Skipped=0, Applied=1, Already=2 };
'''
    for name, raw in (("OriginalBase", orig[:128]),
                      ("OriginalCTA", orig[128:]),
                      ("StrictBase", strict[:128]),
                      ("StrictCTA", strict[128:])):
        header += cpp_array(name, raw)
    header += '''inline Result rewrite(uint32_t block, uint8_t *bytes) {
    if(!bytes || (block!=1 && block!=2))return Result::Skipped;
    const auto original=block==1 ? OriginalBase : OriginalCTA;
    const auto replacement=block==1 ? StrictBase : StrictCTA;
    if(!memcmp(bytes,replacement,128))return Result::Already;
    if(memcmp(bytes,original,128))return Result::Skipped;
    memcpy(bytes,replacement,128);
    return Result::Applied;
}
}
#endif
'''
    return header, {"source_sha256": hashlib.sha256(orig).hexdigest(),
                    "strict_sha256": hashlib.sha256(strict).hexdigest()}


def inject(source: Path) -> dict:
    src = source / "WhateverXe/kern_xe.cpp"
    header, meta = prepare_fixture()
    code = src.read_text()
    if code.count(INCLUDE) != 1 or code.count(SIGNATURE) != 1:
        raise ValueError("Pinned E1.1 source include/hook mismatch")
    start = code.index(SIGNATURE)
    end = code.find("\n}", start)
    if end < 0:
        raise ValueError("DDC hook closing brace not found")
    body = code[start:end + 2]
    if body.count(ANCHOR) != 1 or "WEXYogaRGB8" in code:
        raise ValueError("Cannot uniquely patch target hook")
    body = body.replace(ANCHOR, INSERT + ANCHOR, 1)
    code = code[:start] + body + code[end + 2:]
    code = code.replace(INCLUDE, INCLUDE + '#include "kern_yoga_rgb8.hpp"\n', 1)
    if code.count('checkKernelArgument("-wex-yoga-rgb8")') != 1:
        raise ValueError("Wrong number of RGB8 boot-argument gates")
    src.write_text(code)
    (source / "WhateverXe/kern_yoga_rgb8.hpp").write_text(header)
    registry_file = source / "tests/fixtures/boot_argument_names.json"
    registry = registry_file.read_text()
    if registry.count(ARG_KEY) != 1:
        raise ValueError("Boot argument registry changed")
    registry_file.write_text(registry.replace(ARG_KEY,
        '  "-wex-yoga-rgb8": [],\n' + ARG_KEY, 1))
    subprocess.run(["git", "-C", str(source), "diff", "--check"], check=True)
    changed = set(subprocess.check_output(
        ["git", "-C", str(source), "diff", "--name-only"], text=True).splitlines())
    expected = {"WhateverXe/kern_alderlake_n.hpp",
                "WhateverXe/kern_xe.cpp", "tests/fixtures/boot_argument_names.json"}
    if changed != expected:
        raise ValueError("Unexpected donor changes: " + repr(changed))
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    subprocess.run(["python3", str(ROOT / "e11/tools/prepare_hdmi600.py"),
                    str(source)], check=True)
    meta = inject(source)
    print("RGB8 native Display13 DDC hook prepared; strict opt-in and exact EDID match.")
    print("Only the pin-qualified native HDMI path is eligible; test EFI only.")
    print("Original/strict SHA256:", meta["source_sha256"], meta["strict_sha256"])


if __name__ == "__main__":
    main()
