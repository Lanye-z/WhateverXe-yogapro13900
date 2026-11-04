#!/usr/bin/env python3
"""D1.1.4: audit the exact VPHAL null-subrenderer crash and optionally
create an UNSIGNED, OFFLINE candidate in a separate output file.

NO installation, signing, Mach-O injection into processes, SIP/EFI changes,
or modifications to the installed source file. Never install this output.
Technical reference: JulioNectar's encode-experimental/patch_vpnull2.py.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import struct
import sys

WEX_SHA = "a972cdb7ddd56bcf38c3ab71e874b73efc34bc683d30e49f0a1a1919625a726d"
WEX_SIZE = 8454464
STOCK_SHA = "d265f2038135c2c5c3649b621d9aea48cf1cb74a1fb36069bb1b3562b3750129"
STOCK_SIZE = 8450544
BEGIN, END, CAVE = 0x1336D2, 0x1336F7, 0xAC0
# This is the exact 37-byte text span that contains the observed NULL write
# at 0x1336F3. It also contains the earlier 0x920 write at 0x1336DD.
EXPECTED = bytes.fromhex(
    "488b55d8" "488bba20090000" "48894f08" "4881c2b02c0000"
    "488b4dd8" "488bb910090000" "48895708"
)
assert len(EXPECTED) == END - BEGIN


def rel32(src_next: int, dst: int) -> bytes:
    return struct.pack("<i", dst - src_next)


def candidate_patch_bytes() -> tuple[bytes, bytes]:
    # Critical behavioral change: guard both subrenderer pointers BEFORE
    # writing their member at +8. This mirrors the specific approach
    # explored by JulioNectar; it does not initialize the missing objects.
    code = bytearray(bytes.fromhex(
        "488b55d8"               # mov rdx,[rbp-0x28]
        "488bba20090000"         # mov rdi,[rdx+0x920]
        "4885ff"                 # test rdi,rdi
        "7404"                   # je skip the following 4-byte store
        "48894f08"               # mov [rdi+8],rcx
        "4881c2b02c0000"         # add rdx,0x2cb0
        "488b4dd8"               # mov rcx,[rbp-0x28]
        "488bb910090000"         # mov rdi,[rcx+0x910]
        "4885ff"                 # test rdi,rdi
        "7404"                   # je skip the following 4-byte store
        "48895708"               # mov [rdi+8],rdx
    ))
    code += b"\xE9" + rel32(CAVE + len(code) + 5, END)
    hook = (b"\xE9" + rel32(BEGIN + 5, CAVE)).ljust(END - BEGIN, b"\x90")
    return bytes(hook), bytes(code)


def get_fingerprint(payload: bytes) -> tuple[str, int]:
    return hashlib.sha256(payload).hexdigest(), len(payload)


def preflight(payload: bytes, *, accept_stock: bool = False) -> dict:
    digest, size = get_fingerprint(payload)
    if digest == WEX_SHA and size == WEX_SIZE:
        flavor = "WhateverXe Graphics v0.4.0 Tahoe (verified installed build)"
    elif digest == STOCK_SHA and size == STOCK_SIZE and accept_stock:
        flavor = "stock Apple Tiger Lake 16.0.32 (TESTING ONLY)"
    else:
        raise ValueError("REFUSED: unrecognized VA binary SHA256/size; do NOT apply to an unknown build")
    if payload[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("REFUSED: not a little-endian 64-bit Mach-O")
    # Parse Mach-O load commands: confirm exact __TEXT VM/file mapping, not a
    # heuristic string occurrence. For this build VM RVA equals disk offset.
    if len(payload) < 32:
        raise ValueError("REFUSED: truncated Mach-O header")
    ncmds, cmds_size = struct.unpack_from("<II", payload, 16)
    cursor, end_commands, ok_text = 32, 32 + cmds_size, False
    if not 1 <= ncmds <= 256 or end_commands >= len(payload):
        raise ValueError("REFUSED: malformed Mach-O load command table")
    for _ in range(ncmds):
        if cursor + 8 > end_commands:
            raise ValueError("REFUSED: truncated Mach-O load command")
        cmd, cmdsize = struct.unpack_from("<II", payload, cursor)
        if cmdsize < 8 or cursor + cmdsize > end_commands:
            raise ValueError("REFUSED: invalid Mach-O load command size")
        if cmd == 0x19 and cmdsize >= 72:  # LC_SEGMENT_64
            segname = payload[cursor + 8:cursor + 24].rstrip(b"\x00")
            if segname == b"__TEXT":
                vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<QQQQ", payload, cursor + 24)
                ok_text = vmaddr == 0 and fileoff == 0 and filesize > END and vmsize > END
        cursor += cmdsize
    if not ok_text:
        raise ValueError("REFUSED: unexpected __TEXT vmaddr/fileoff mapping")
    if payload[BEGIN:END] != EXPECTED:
        raise ValueError("REFUSED: binary has DIFFERENT instructions at VPHAL crash site")
    hook, cave = candidate_patch_bytes()
    if any(payload[CAVE:CAVE + len(cave) + 8]):
        raise ValueError("REFUSED: code cave at 0xAC0 is OCCUPIED in this build")
    return {
        "build": flavor, "sha256": digest, "size": size,
        "crash_rva": "0x1336f3", "source_slot": "+0x910",
        "second_store_rva": "0x1336dd", "second_slot": "+0x920",
        "hook_offset": hex(BEGIN), "cave_offset": hex(CAVE),
        "hook_bytes": hook.hex(), "guard_bytes": cave.hex(),
        "result": "PRECHECK_PASS (no files modified)",
    }


def patch_in_memory(payload: bytes) -> bytes:
    # Only ever call after strict preflight of the source bytes and cave.
    b = bytearray(payload)
    hook, cave = candidate_patch_bytes()
    b[CAVE:CAVE + len(cave)] = cave
    b[BEGIN:END] = hook
    assert len(b) == len(payload)
    assert b[CAVE:CAVE + len(cave)] == cave
    assert b[BEGIN:END] == hook
    assert b[0x1336F7:0x133700] == payload[0x1336F7:0x133700]
    return bytes(b)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("binary", type=Path, help="read an existing VA executable; never modified")
    p.add_argument("--emit-unsigned-candidate", type=Path, metavar="OUTPUT",
                   help="write an untrusted, UNSIGNED candidate to NEW output file, NEVER install")
    p.add_argument("--acknowledge-uninstallable", action="store_true",
                   help="required with --emit-unsigned-candidate")
    p.add_argument("--accept-stock-for-unit-test", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()
    try:
        if not args.binary.is_file():
            raise ValueError("Input file not found")
        payload = args.binary.read_bytes()
        data = preflight(payload, accept_stock=args.accept_stock_for_unit_test)
        for key, val in data.items():
            print(f"{key.upper()}={val}")
        if args.emit_unsigned_candidate is None:
            print("MODE=READ_ONLY_AUDIT; NO_BINARY_WRITTEN")
            return 0
        if not args.acknowledge_uninstallable:
            raise ValueError("Output needs --acknowledge-uninstallable; never install this unsigned candidate")
        out = args.emit_unsigned_candidate.expanduser().resolve()
        source = args.binary.resolve()
        if out == source or out.is_relative_to(Path("/Library")) or out.is_relative_to(Path("/System")) or out.is_relative_to(Path("/Volumes/EFI")):
            raise ValueError("REFUSED: output cannot overwrite source or target a system/EFI directory")
        if out.exists():
            raise ValueError("REFUSED: output exists; will not overwrite")
        # Deliberately fails if output parent does not exist, to avoid accidental writes.
        patched = patch_in_memory(payload)
        with out.open("xb") as handle:
            handle.write(patched)
        print("MODE=OFFLINE_UNSIGNED_CANDIDATE_ONLY")
        print(f"OUTPUT={out}")
        print(f"OUTPUT_SHA256={hashlib.sha256(patched).hexdigest()}")
        print("NOT_INSTALLABLE=Apple/OCLP signed payload modified; binary signature invalidated")
        print("FIX_NOT_PROVEN=This only guards two stores; downstream VPHAL init can still fail")
        return 0
    except (OSError, ValueError) as exc:
        print(f"AUDIT_ERROR={exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
