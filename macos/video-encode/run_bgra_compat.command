#!/usr/bin/env bash
# D1.1 app-level BGRA -> NV12 software conversion -> hardware H.264 encode.
# Does NOT alter system-wide VideoToolbox, kexts, EFI, SIP, or installed Graphics.
set -uo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
frames="${1:-1}"
if [[ ! "$frames" =~ ^[0-9]+$ ]] || (( frames<1 || frames>180 )); then
  echo "Usage: bash run_bgra_compat.command [frames 1..180]" >&2;exit 2
fi
command -v xcrun >/dev/null || { echo "Requires Apple Command Line Tools" >&2;exit 2; }
cd "$ROOT" || exit 2
# Do not write compiled executables or logs to a read-only Git checkout.
OUTPUT="$ROOT/output";mkdir -p "$OUTPUT"
cc=xcrun
"$cc" clang -arch x86_64 -O0 -g -fobjc-arc -Wall -Wextra -Wno-unused-parameter \
  -framework Foundation -framework CoreMedia -framework CoreVideo -framework VideoToolbox \
  "$ROOT/wex_bgra_compat_encode.m" -o "$OUTPUT/wex_bgra_compat_encode" || exit 2
log="$OUTPUT/bgraworkaround-$(date +%Y%m%d-%H%M%S).txt"
echo "Application-level BGRA -> CPU NV12 -> VideoToolbox hardware H.264, frames=$frames"
echo "This does NOT repair system-wide AVFPixelProcess; it avoids that code path in this test."
"$OUTPUT/wex_bgra_compat_encode" H264 "$frames" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
echo "Log: $log"
exit "$status"
