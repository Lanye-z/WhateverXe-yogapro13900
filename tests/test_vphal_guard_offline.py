#!/usr/bin/env python3
"""Runs with Python stdlib; verifies correct jump destinations and no unknown modifications."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("d114", ROOT / "macos/video-encode/vphal_guard_offline.py")
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


class VPHALGuardTest(unittest.TestCase):
    def test_jump_geometry_and_guards(self):
        hook, cave = v.candidate_patch_bytes()
        self.assertEqual(len(hook), v.END - v.BEGIN)
        self.assertEqual(hook[0], 0xE9)
        self.assertEqual(v.BEGIN + 5 + struct.unpack("<i", hook[1:5])[0], v.CAVE)
        self.assertEqual(cave[-5], 0xE9)
        self.assertEqual(v.CAVE + len(cave) + struct.unpack("<i", cave[-4:])[0], v.END)
        self.assertEqual(cave.count(b"\x48\x85\xff\x74\x04"), 2)  # test rdi,rdi; je +4
        self.assertEqual(cave.count(b"\x48\x89\x4f\x08"), 1)
        self.assertEqual(cave.count(b"\x48\x89\x57\x08"), 1)

    def test_only_two_regions_changed(self):
        p = bytearray(v.WEX_SIZE)
        p[v.BEGIN:v.END] = v.EXPECTED
        patched = v.patch_in_memory(bytes(p))
        self.assertEqual(len(patched), len(p))
        cave_end = v.CAVE + len(v.candidate_patch_bytes()[1])
        self.assertEqual(patched[:v.CAVE], p[:v.CAVE])
        self.assertEqual(patched[cave_end:v.BEGIN], p[cave_end:v.BEGIN])
        self.assertEqual(patched[v.END:], p[v.END:])

    def test_unknown_sha_refused(self):
        p = bytearray(v.WEX_SIZE)
        p[:4] = b"\xcf\xfa\xed\xfe"
        p[v.BEGIN:v.END] = v.EXPECTED
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            v.preflight(bytes(p))


if __name__ == "__main__":
    unittest.main()
