#!/usr/bin/env bash
# D1.1.2: capture the exact native-driver crash site (opt-in only).
# Runs the already-known crashing VTPixelTransferSession test under LLDB.
# No sudo, SIP/EFI changes, debugger attachment to other processes, or VA modification.
set -uo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/output"
mkdir -p "$OUT"
if [[ "$#" -ne 1 || "$1" != "--i-accept-native-crash" ]]; then
  echo "Usage: bash collect_vphal_backtrace.command --i-accept-native-crash" >&2
  echo "The 64x64 BGRA->NV12 native transfer already SEGFAULTED on this machine." >&2
  echo "Run only after saving your work; this will deliberately reproduce the crash." >&2
  exit 2
fi
command -v xcrun >/dev/null || { echo "Apple Command Line Tools required" >&2; exit 2; }
# Recompile from the exact repository source so symbols are available for our probe.
echo "Compiling VPHAL transfer test with debug symbols..."
xcrun clang -arch x86_64 -O0 -g -fobjc-arc -Wall -Wextra -Wno-unused-parameter \
  -framework Foundation -framework VideoToolbox -framework CoreMedia -framework CoreVideo \
  "$ROOT/wex_vphal_transfer_probe.m" -o "$OUT/wex_vphal_transfer_probe" || exit 2
LOG="$OUT/vphal-lldb-64x64-$(date +%Y%m%d-%H%M%S).txt"
echo "LOG=$LOG"
echo "WARNING: This executes the known-crashing native pixel-transfer call."
echo "Capturing registers, disassembly, ALL thread stacks and image base/slide."
# -k commands run only on crash; no need to type at the LLDB prompt.
xcrun lldb --batch \
  -o 'run 64 64 bgra-nv12' \
  -k 'thread backtrace all' \
  -k 'register read rdi rsi rdx rcx rip' \
  -k 'disassemble -p -c 20' \
  -k 'image list -o -f' \
  -- "$OUT/wex_vphal_transfer_probe" 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
echo "LLDB_EXIT_STATUS=$rc" | tee -a "$LOG"
echo "NOTE=LLDB exit code is not a replacement for the native stack trace." | tee -a "$LOG"
echo "LOG=$LOG"
exit "$rc"
