#!/usr/bin/env bash
# D1.1 read-only/isolated VideoToolbox discovery and pixel-transfer probes.
# Never modifies the EFI, Graphics installation, SIP, launch services or preferences.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/output"
mkdir -p "$OUT"
usage() {
  cat <<'USAGE'
Usage:
  bash run_d11_probe.command inventory
  bash run_d11_probe.command professional
  bash run_d11_probe.command properties
  bash run_d11_probe.command pixel 64 64 bgra-nv12 --i-accept-native-crash
  bash run_d11_probe.command pixel 1920 1080 bgra-nv12 --i-accept-native-crash
  bash run_d11_probe.command pixel 1920 1080 nv12-nv12 --i-accept-native-crash

inventory     VTCopyVideoEncoderList only (read-only)
professional  process-local professional video registration, compares lists
properties    HEVC supported property selection (may load native providers)
pixel         VTPixelTransferSession only; can crash the invoking process!

No mode installs or patches any driver. Save your work before 'pixel'.
USAGE
}
compile() {
  local src="$1" dest="$2"
  command -v xcrun >/dev/null || { echo 'ERROR: Xcode command-line tools required' >&2;exit 2; }
  xcrun clang -arch x86_64 -O1 -g -fobjc-arc -Wall -Wextra -Wno-unused-parameter \
    -framework Foundation -framework VideoToolbox -framework CoreMedia -framework CoreVideo \
    "$ROOT/$src" -o "$OUT/$dest" || exit 2
}
mode="${1:-}"
case "$mode" in
  inventory|professional|properties)
    compile wex_hevc_discovery_probe.m wex_hevc_discovery_probe
    args=()
    [[ "$mode" == professional ]] && args+=(--professional)
    [[ "$mode" == properties ]] && args+=(--properties)
    LOG="$OUT/d11-hevc-${mode}-$(date +%Y%m%d-%H%M%S).txt"
    "$OUT/wex_hevc_discovery_probe" "${args[@]}" 2>&1 | tee "$LOG"
    ret=${PIPESTATUS[0]}
    echo "LOG=$LOG"
    exit "$ret"
    ;;
  pixel)
    if [[ $# -ne 5 || "${5:-}" != "--i-accept-native-crash" ]]; then
      echo 'ERROR: Explicit --i-accept-native-crash required. May crash in GPU VA driver.' >&2
      usage; exit 2
    fi
    W="$2" H="$3" PIXMODE="$4"
    if [[ ! "$W" =~ ^[0-9]+$ || ! "$H" =~ ^[0-9]+$ ]] || (( W < 2 || W > 4096 || H < 2 || H > 4096 || W%2 || H%2 )); then
      echo 'ERROR: even width/height in [2, 4096] required' >&2; exit 2
    fi
    if [[ "$PIXMODE" != bgra-nv12 && "$PIXMODE" != nv12-nv12 ]]; then echo 'ERROR: mode bgra-nv12|nv12-nv12'; exit 2; fi
    compile wex_vphal_transfer_probe.m wex_vphal_transfer_probe
    LOG="$OUT/d11-vphal-${PIXMODE}-${W}x${H}-$(date +%Y%m%d-%H%M%S).txt"
    echo 'WARNING: This native VTPixelTransfer call may crash the test process or trigger GPU instability.'
    "$OUT/wex_vphal_transfer_probe" "$W" "$H" "$PIXMODE" 2>&1 | tee "$LOG"
    ret=${PIPESTATUS[0]}
    echo "PROCESS_EXIT_STATUS=$ret" | tee -a "$LOG"
    echo "LOG=$LOG"
    exit "$ret"
    ;;
  *) usage; exit 2;;
esac
