#!/usr/bin/env bash
# Read-only codec inventory with built-in macOS API.
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v xcrun >/dev/null || { echo "Requires Apple Command Line Tools" >&2;exit 2; }
mkdir -p "$ROOT/output"
xcrun clang -arch x86_64 -fobjc-arc -Wall -Wextra -Wno-unused-parameter \
   -framework Foundation -framework VideoToolbox -framework CoreMedia \
   "$ROOT/wex_encoder_inventory.m" -o "$ROOT/output/wex_encoder_inventory"
log="$ROOT/output/encoder-inventory-$(date +%Y%m%d-%H%M%S).txt"
{
  echo "== macOS =="
  /usr/bin/sw_vers
  echo "== VideoToolbox hardware encoder registration =="
  "$ROOT/output/wex_encoder_inventory"
  echo "== accelerator HEVC/H264 advertised capabilities (not proof of registration) =="
  ioreg -p IOService -l -w0 | grep -E 'IOGVA(H264|HEVC)(Encode|Decode)' | head -n 30 || true
} 2>&1 | tee "$log"
echo "Log: $log"
