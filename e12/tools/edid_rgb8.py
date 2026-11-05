#!/usr/bin/env python3
"""Build per-monitor RGB EDID overrides. No sudo, EFI or automatic installation."""
import argparse
import hashlib
import json
import plistlib
import re
from pathlib import Path

HEADER = bytes.fromhex("00ffffffffffff00")
VIC_4K60 = {97, 102, 107}


class EDIDError(ValueError):
    pass


def validate(raw):
    if len(raw) < 128 or len(raw) % 128 or len(raw) > 128 * 32:
        raise EDIDError("Expected 1-32 complete 128-byte EDID blocks")
    if raw[:8] != HEADER:
        raise EDIDError("Invalid EDID base header")
    if raw[126] + 1 != len(raw) // 128:
        raise EDIDError("Extension count disagrees with file size")
    for i in range(len(raw) // 128):
        if sum(raw[128*i:128*(i+1)]) % 256:
            raise EDIDError("Invalid checksum in EDID block %d" % i)
    if not raw[20] & 0x80:
        raise EDIDError("Analog-input EDID is not suitable")


def load_edid(path, index=None):
    raw = Path(path).read_bytes()
    if raw.startswith(HEADER):
        if index not in (None, 0):
            raise EDIDError("Binary EDID has index 0 only")
        validate(raw)
        return raw
    try:
        text = raw.decode("ascii")
    except UnicodeError as exc:
        raise EDIDError("Not raw EDID or ASCII ioreg/hex") from exc
    matches = re.findall(r'IODisplayEDID\s*=\s*<([a-fA-F0-9\s]+)>', text)
    if not matches and re.fullmatch(r'[\s<>{}a-fA-F0-9]+', text):
        matches = [re.sub(r'[^a-fA-F0-9]', '', text)]
    if not matches:
        raise EDIDError("No EDID found in file")
    if len(matches) > 1 and index is None:
        raise EDIDError("%d displays found: choose --index after identifying external monitor" % len(matches))
    chosen = 0 if index is None else index
    if chosen < 0 or chosen >= len(matches):
        raise EDIDError("EDID index outside available range")
    try:
        edid = bytes.fromhex(matches[chosen])
    except ValueError as exc:
        raise EDIDError("Invalid EDID hex string") from exc
    validate(edid)
    return edid


def identity(edid):
    vendor = int.from_bytes(edid[8:10], "big")
    name = ''.join(chr(64+x) for x in ((vendor >> 10) & 31, (vendor >> 5) & 31, vendor & 31))
    model = ""
    for pos in (54, 72, 90, 108):
        d = edid[pos:pos+18]
        if d[:5] == b'\x00\x00\x00\xfc\x00':
            model = d[5:].decode("ascii", "replace").strip("\x00\r\n ")
            break
    return {"vendor": name, "vendor_id": vendor,
            "product_id": int.from_bytes(edid[10:12], "little"),
            "model": model or "External Display"}


def cta(ext):
    if len(ext) != 128 or ext[0] != 2:
        raise EDIDError("Expected CTA-861 extension")
    start = ext[2]
    if start == 0:
        if any(ext[4:127]):
            raise EDIDError("CTA zero-offset extension contains nonzero data")
        return [], b""
    if start < 4 or start > 127:
        raise EDIDError("Invalid CTA DTD start")
    blocks = []
    pos = 4
    while pos < start:
        header = ext[pos]
        end = pos + 1 + (header & 31)
        if end > start:
            raise EDIDError("CTA block crosses DTD boundary")
        blocks.append((header >> 5, bytes(ext[pos+1:end])))
        pos = end
    return blocks, bytes(ext[start:127])


def is_4k60_dtd(d):
    if len(d) != 18:
        return False
    clock = int.from_bytes(d[:2], "little") * 10000
    width = d[2] + ((d[4] >> 4) << 8)
    height = d[5] + ((d[7] >> 4) << 8)
    total = (width + d[3] + ((d[4] & 15) << 8)) * (height + d[6] + ((d[7] & 15) << 8))
    return bool(clock and total and width in (3840, 4096) and height == 2160
                and 59 <= clock / total <= 61)


def rgb_4k60(edid):
    if any(is_4k60_dtd(edid[i:i+18]) for i in (54, 72, 90, 108)):
        return True
    for pos in range(128, len(edid), 128):
        ext = edid[pos:pos+128]
        if ext[0] != 2:
            continue
        blocks, timings = cta(ext)
        if any(tag == 2 and any((vic & 127) in VIC_4K60 for vic in payload)
               for tag, payload in blocks):
            return True
        if any(is_4k60_dtd(timings[i:i+18]) for i in range(0, len(timings)-17, 18)):
            return True
    return False


def only_420_4k60(edid):
    for pos in range(128, len(edid), 128):
        ext = edid[pos:pos+128]
        if ext[0] != 2:
            continue
        blocks, _ = cta(ext)
        if any(tag == 7 and len(value) > 1 and value[0] == 14
               and any((v & 127) in VIC_4K60 for v in value[1:])
               for tag, value in blocks):
            return True
    return False


def checksum(data):
    data[127] = (-sum(data[:127])) & 255


def transform(source, strict=False):
    validate(source)
    if not rgb_4k60(source) and only_420_4k60(source):
        raise EDIDError("Detected 4K60 as YCbCr420-only; refuse to remove its only mode")
    out = bytearray(source)
    changes = {"cta": 0, "ycbcr_flag": 0, "removed_y420": 0,
               "removed_hdr": 0, "vsdb_deep_color": 0, "forum_420_deep_color": 0,
               "base_8bpc": 0}
    if strict:
        previous = out[20]
        out[20] = (out[20] & 0x8f) | 0x20  # Digital 8 bpc, other EDID info untouched
        changes["base_8bpc"] = int(previous != out[20])
        base = bytearray(out[:128])
        checksum(base)
        out[:128] = base
    for offset in range(128, len(source), 128):
        ext = source[offset:offset+128]
        if ext[0] != 2:
            continue
        blocks, dtd = cta(ext)
        changes["cta"] += 1
        result = bytearray()
        for tag, value in blocks:
            payload = bytearray(value)
            if tag == 7 and payload and payload[0] in (14, 15):
                changes["removed_y420"] += 1
                continue
            if strict and tag == 7 and payload and payload[0] in (6, 7):
                changes["removed_hdr"] += 1
                continue
            if strict and tag == 3 and len(payload) >= 6 and payload[:3] == b'\x03\x0c\x00':
                before = payload[5]
                payload[5] &= ~0x78  # HDMI VSDB deep-color bits; keep TMDS max clock
                changes["vsdb_deep_color"] += int(payload[5] != before)
            if strict and tag == 3 and len(payload) >= 7 and payload[:3] == b'\xd8\x5d\xc4':
                before = payload[6]
                payload[6] &= ~0x07  # Forum 420 deep color; retain SCDC bits
                changes["forum_420_deep_color"] += int(payload[6] != before)
            result.append((tag << 5) | len(payload))
            result.extend(payload)
        if len(result) + len(dtd) > 123:
            raise EDIDError("CTA payload overflow")
        updated = bytearray(128)
        updated[:4] = ext[:4]
        previous = updated[3]
        updated[3] &= ~0x30  # CTA YCbCr444 / YCbCr422
        changes["ycbcr_flag"] += int(updated[3] != previous)
        updated[2] = 4 + len(result) if ext[2] or result else 0
        updated[4:4+len(result)] = result
        updated[4+len(result):4+len(result)+len(dtd)] = dtd
        checksum(updated)
        out[offset:offset+128] = updated
    out = bytes(out)
    validate(out)
    if not changes["cta"]:
        raise EDIDError("No CTA extension for HDMI capability adjustment")
    if rgb_4k60(out) != rgb_4k60(source):
        raise EDIDError("RGB 4K60 advertisement changed unexpectedly")
    if out == source:
        raise EDIDError("No relevant capability to change")
    return out, {**changes, "rgb_4k60_advertised": rgb_4k60(source)}


def plist_override(edid, ident):
    record = {"DisplayVendorID": ident["vendor_id"],
              "DisplayProductID": ident["product_id"],
              "DisplayProductName": {"en": ident["model"]},
              "IODisplayEDID": edid}
    return plistlib.dumps(record, fmt=plistlib.FMT_XML, sort_keys=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edid", type=Path)
    parser.add_argument("--index", type=int, help="Index within a multi-monitor ioreg text dump")
    parser.add_argument("--out", type=Path, default=Path("E1.2_RGB8_Output"))
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    try:
        source = load_edid(args.edid, args.index)
        info = identity(source)
        print("Candidate: %s %s VID=%04x PID=%04x" %
              (info["vendor"], info["model"], info["vendor_id"], info["product_id"]))
        print("RGB 4K60 advertised:", rgb_4k60(source))
        print("Source SHA256:", hashlib.sha256(source).hexdigest())
        if args.inspect_only:
            return
        variants = {name: transform(source, strict)
                    for name, strict in (("RGB_ONLY", False), ("RGB8_STRICT", True))}
        if args.out.exists() and any(args.out.iterdir()):
            raise EDIDError("Output directory must be absent or empty")
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "ORIGINAL_EDID_BACKUP.bin").write_bytes(source)
        report = {"display": info, "source_sha256": hashlib.sha256(source).hexdigest(),
                  "variants": {}}
        dirname = "DisplayVendorID-%x" % info["vendor_id"]
        basename = "DisplayProductID-%x" % info["product_id"]
        for name, (raw, changes) in variants.items():
            target = args.out / name / dirname / basename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(plist_override(raw, info))
            (args.out / (name + ".bin")).write_bytes(raw)
            report["variants"][name] = {"changes": changes,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "override": str(target.relative_to(args.out))}
            print(name, str(target), "SHA256", report["variants"][name]["sha256"])
        (args.out / "REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
        print("No Kext, EFI or macOS system files were touched.")
    except (EDIDError, OSError) as error:
        parser.exit(2, "REFUSED: %s\n" % error)


if __name__ == "__main__":
    main()
