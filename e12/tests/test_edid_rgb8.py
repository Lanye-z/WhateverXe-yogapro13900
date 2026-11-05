import plistlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import edid_rgb8 as tool


def fixture(rgb=True, y420_only=False, with_dtd=False):
    base = bytearray(128)
    base[:8] = tool.HEADER
    base[8:10] = (0x05e3).to_bytes(2, "big")
    base[10:12] = (0x27b2).to_bytes(2, "little")
    base[20], base[126] = 0xb0, 1   # Digital 10bpc; one CTA extension
    if with_dtd:
        d = bytearray(18)
        d[:2] = (53325).to_bytes(2, "little")  # 533.25 MHz
        d[2], d[3], d[4] = 0, 160, 0xf0        # 3840 x total 4000
        d[5], d[6], d[7] = 0x70, 62, 0x80      # 2160 x total 2222
        base[54:72] = d
    tool.checksum(base)
    cta = bytearray(128)
    cta[0], cta[1], cta[3] = 2, 3, 0x70
    blocks = []
    def add(tag, payload):
        blocks.append(bytes([(tag << 5) + len(payload)]) + bytes(payload))
    add(1, [9, 7, 7])
    add(2, [97, 16] if rgb else [16])
    add(3, [3, 12, 0, 16, 0, 0x78, 0x78])
    add(3, [0xd8, 0x5d, 0xc4, 1, 120, 0x88, 7])
    add(7, [14, 97 if y420_only else 96])
    add(7, [15, 1])
    add(7, [6, 1, 0, 0])
    add(7, [7, 1])
    payload = b''.join(blocks)
    cta[2] = 4 + len(payload)
    cta[4:4+len(payload)] = payload
    tool.checksum(cta)
    return bytes(base + cta)


class EDIDTests(unittest.TestCase):
    def test_variants_preserve_mode_clock_and_scdc(self):
        src = fixture()
        for strict in (False, True):
            with self.subTest(strict=strict):
                edid, stats = tool.transform(src, strict)
                tool.validate(edid)
                self.assertTrue(tool.rgb_4k60(edid))
                self.assertEqual(edid[20], 0xa0 if strict else 0xb0)
                self.assertEqual(edid[131] & 0x30, 0)
                self.assertEqual(stats["removed_y420"], 2)
                blocks, _ = tool.cta(edid[128:256])
                self.assertIn((2, bytes([97, 16])), blocks)
                forum = next(v for tag, v in blocks if tag == 3 and v[:3] == b'\xd8\x5d\xc4')
                hdmi = next(v for tag, v in blocks if tag == 3 and v[:3] == b'\x03\x0c\x00')
                self.assertEqual(forum[4:6], bytes([120, 0x88]))
                self.assertEqual(forum[6], 0 if strict else 7)
                self.assertEqual(hdmi[6], 0x78)
                self.assertEqual(hdmi[5], 0 if strict else 0x78)
                hdr = [v for tag, v in blocks if tag == 7 and v and v[0] in (6, 7)]
                self.assertEqual(len(hdr), 0 if strict else 2)

    def test_420_only_4k60_refused(self):
        with self.assertRaisesRegex(tool.EDIDError, "420-only"):
            tool.transform(fixture(rgb=False, y420_only=True), True)

    def test_base_4k60_dtd_preserved(self):
        src = fixture(rgb=False, with_dtd=True)
        self.assertTrue(tool.rgb_4k60(src))
        result, _ = tool.transform(src, True)
        self.assertEqual(result[54:72], src[54:72])

    def test_bad_checksum_and_extension_count_refused(self):
        data = bytearray(fixture())
        data[140] ^= 1
        with self.assertRaises(tool.EDIDError):
            tool.validate(bytes(data))
        data = bytearray(fixture())
        data[126] = 0
        tool.checksum(data[:128])  # testing below resets base checksum explicitly
        base = bytearray(data[:128])
        tool.checksum(base)
        data[:128] = base
        with self.assertRaisesRegex(tool.EDIDError, "Extension count"):
            tool.validate(bytes(data))

    def test_cta_overrun_refused(self):
        data = bytearray(fixture()[128:256])
        data[2] = 6
        with self.assertRaises(tool.EDIDError):
            tool.cta(bytes(data))

    def test_plist_has_correct_identity_and_bytes(self):
        data, _ = tool.transform(fixture(), True)
        plist = plistlib.loads(tool.plist_override(data, tool.identity(data)))
        self.assertEqual(plist["IODisplayEDID"], data)
        self.assertEqual(plist["DisplayProductID"], 0x27b2)

    def test_non_cta_extension_unchanged(self):
        data = bytearray(fixture())
        data[126] = 2
        base = bytearray(data[:128])
        tool.checksum(base)
        data[:128] = base
        third = bytearray(128)
        third[0] = 0x70
        tool.checksum(third)
        data.extend(third)
        out, _ = tool.transform(bytes(data))
        self.assertEqual(out[256:], bytes(third))


if __name__ == "__main__":
    unittest.main()
