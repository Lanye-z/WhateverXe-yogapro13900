#!/usr/bin/env bash
# Read-only static inspection of installed VADriver, no loading/patching.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/output"
mkdir -p "$OUT"
BUNDLE='/Library/GPUBundles/AppleIntelTGLGraphicsVADriver.bundle'
BIN="$BUNDLE/Contents/MacOS/AppleIntelTGLGraphicsVADriver"
LOG="$OUT/d11-va-fingerprint-$(date +%Y%m%d-%H%M%S).txt"
{
 echo 'PROBE=READ_ONLY_INSTALLED_VA_BINARY_FINGERPRINT'
 if [[ ! -f "$BIN" ]]; then echo "ERROR=NOT_FOUND $BIN";exit 3;fi
 echo "BINARY=$BIN"
 /usr/bin/shasum -a 256 "$BIN"
 /usr/bin/file "$BIN"
 /usr/bin/dwarfdump --uuid "$BIN" 2>&1 || true
 /usr/bin/codesign -dv --verbose=2 "$BUNDLE" 2>&1 || true
 /usr/bin/codesign --verify --verbose=2 "$BUNDLE" 2>&1 || true
 echo 'LOAD_COMMAND_DEPENDENCIES='
 /usr/bin/otool -L "$BIN" 2>&1 || true
 echo 'INFO_PLIST='
 /usr/bin/plutil -p "$BUNDLE/Contents/Info.plist" 2>&1 || true
 echo 'NOTE=Fingerprint is not a proof of whether HEVC encoding exists. No binary modifications made.'
} | tee "$LOG"
echo "LOG=$LOG"
