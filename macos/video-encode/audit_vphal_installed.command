#!/usr/bin/env bash
# Pure read-only exact SHA+signature audit: NO sudo, no driver writes.
set -euo pipefail
HERE="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BIN='/Library/GPUBundles/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver'
if [[ ! -f "$BIN" ]]; then echo "ERROR=installed VA driver missing: $BIN" >&2; exit 2; fi
LOG="$HERE/output/vphal-audit-$(date +%Y%m%d-%H%M%S).txt"
mkdir -p "$HERE/output"
python3 "$HERE/vphal_guard_offline.py" "$BIN" 2>&1 | tee "$LOG"
echo "LOG=$LOG"
