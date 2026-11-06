#!/usr/bin/env bash
# WhateverXe A7A0 D source build. This script DOES NOT install kexts or modify EFI.
set -euo pipefail
IFS=$'\n\t'
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORK="$ROOT/work_D"
SRC="$WORK/WhateverXe"
SDK="$WORK/MacKernelSDK"
LILU="$WORK/Lilu"
OUT="$ROOT/OUTPUT_D"
UPSTREAM_SHA="d0b7fb6275ca51fde088fa7e91595462bd457ec9"
SDK_SHA="05094e5e88cec7caedbfb35e8449ed0db94bf95b"

if [[ "$(uname -s)" != Darwin ]]; then
  echo "ERROR: Build must run on macOS with Apple CLT/Xcode." >&2; exit 1
fi
for c in git python3 xcrun ditto unzip shasum tee; do
  command -v "$c" >/dev/null || { echo "Missing tool: $c" >&2; exit 1; }
done
xcrun --find clang++ >/dev/null || { echo "Install Apple Command Line Tools: xcode-select --install" >&2; exit 1; }
# Keep partially downloaded source and cached dependencies for retries.
mkdir -p "$WORK" "$OUT"
exec > >(tee "$OUT/build.log") 2>&1

echo "=== WhateverXe D1.1: native source-first build (D eDP panel-only) ==="
echo "Host: $(uname -sm)"
echo "Source revision: $UPSTREAM_SHA"

# Prefer C/D caches already present on this Mac. Network is only a fallback.
CACHE_SOURCE=""
CACHE_SDK=""
CACHE_LILU=""
shopt -s nullglob
CANDIDATES=()
if [[ -n "${WEX_CACHE_WORK:-}" ]]; then CANDIDATES+=("$WEX_CACHE_WORK"); fi
CANDIDATES+=("$HOME"/Downloads/WhateverXe_A7A0_C_OneClick_Builder*/work)
CANDIDATES+=("$HOME"/Downloads/WhateverXe_A7A0_D_OneClick_Builder*/work)
CANDIDATES+=("$HOME"/Desktop/WhateverXe_A7A0_C_OneClick_Builder*/work)
for candidate in "${CANDIDATES[@]}"; do
  [[ -d "$candidate" ]] || continue
  if [[ -z "$CACHE_SOURCE" && -d "$candidate/Source/.git" ]] &&
     [[ "$(git -C "$candidate/Source" rev-parse HEAD 2>/dev/null || true)" == "$UPSTREAM_SHA" ]]; then
    CACHE_SOURCE="$candidate/Source"
  fi
  if [[ -z "$CACHE_SDK" && -d "$candidate/MacKernelSDK/.git" ]] &&
     [[ "$(git -C "$candidate/MacKernelSDK" rev-parse HEAD 2>/dev/null || true)" == "$SDK_SHA" ]]; then
    CACHE_SDK="$candidate/MacKernelSDK"
  fi
  if [[ -z "$CACHE_LILU" && -f "$candidate/Lilu/Lilu/Headers/kern_api.hpp" &&
        -f "$candidate/Lilu/Lilu/Library/plugin_start.cpp" ]]; then
    CACHE_LILU="$candidate/Lilu"
  fi
done

if [[ ! -d "$SRC/.git" ]]; then
  if [[ -n "$CACHE_SOURCE" ]]; then
    echo "Reusing C source locally: $CACHE_SOURCE"
    git clone --local --no-hardlinks "$CACHE_SOURCE" "$SRC"
  else
    echo "No local source cache; downloading public upstream source"
    git clone https://github.com/b00t0x/WhateverXe.git "$SRC"
  fi
  git -C "$SRC" checkout --detach "$UPSTREAM_SHA"
fi
test "$(git -C "$SRC" rev-parse HEAD)" = "$UPSTREAM_SHA" || {
  echo "Existing source is not the pinned upstream commit. Aborting." >&2; exit 1;
}
if [[ ! -d "$SDK/.git" ]]; then
  if [[ -n "$CACHE_SDK" ]]; then
    echo "Reusing pinned MacKernelSDK cache: $CACHE_SDK"
    ln -s "$CACHE_SDK" "$SDK"
  else
    echo "No SDK cache; downloading public MacKernelSDK"
    git clone https://github.com/acidanthera/MacKernelSDK.git "$SDK"
    git -C "$SDK" checkout --detach "$SDK_SHA"
  fi
fi
test "$(git -C "$SDK" rev-parse HEAD)" = "$SDK_SHA" || {
  echo "SDK revision mismatch." >&2; exit 1;
}
if [[ ! -f "$LILU/Lilu/Headers/kern_api.hpp" ]]; then
  if [[ -n "$CACHE_LILU" ]]; then
    echo "Reusing Lilu headers/library: $CACHE_LILU"
    ln -s "$CACHE_LILU" "$LILU"
  else
    echo "No Lilu cache; downloading public Lilu 1.7.2"
    git clone --branch 1.7.2 --depth 1 https://github.com/acidanthera/Lilu.git "$LILU"
  fi
fi

# Source-first D1.1: replace pinned upstream files with reviewed complete source.
# No git apply, no VA binary patching, no EFI/Graphics modification.
for f in WhateverXe/kern_alderlake_n.hpp WhateverXe/kern_xe.cpp tests/adlp_fb_candidate.py tests/fixtures/boot_argument_names.json; do
  test -s "$ROOT/src/$f" || { echo "Missing D1.1 full source: src/$f" >&2; exit 1; }
  cp "$ROOT/src/$f" "$SRC/$f"
done
git -C "$SRC" diff --check
grep -Fq 'checkKernelArgument("-wex-a7a0-panel-only")' "$SRC/WhateverXe/kern_xe.cpp"
grep -Fq '"-wex-a7a0-panel-only": []' "$SRC/tests/fixtures/boot_argument_names.json"
echo "D1.1 source overlay synchronized; no patch files applied."

mkdir -p "$SRC/Lilu.kext/Contents/Resources"
for item in Headers Library; do
  link="$SRC/Lilu.kext/Contents/Resources/$item"
  if [[ -L "$link" ]]; then
    [[ -d "$link" ]] || { echo "Broken Lilu $item symlink" >&2; exit 1; }
  elif [[ ! -e "$link" ]]; then
    ln -s "$LILU/Lilu/$item" "$link"
  else
    echo "Existing non-symlink Lilu $item; stopping rather than overwriting." >&2
    exit 1
  fi
done

cd "$SRC"
python3 tools/test.py
python3 tools/build.py --release --sdk "$SDK" --output build/RELEASE
python3 tools/check_compat_version.py build/RELEASE

KEXT="$SRC/build/RELEASE/WhateverXe.kext"
test -f "$KEXT/Contents/Info.plist"
test -f "$KEXT/Contents/MacOS/WhateverXe"
ZIP="$OUT/WhateverXe_A7A0_D1.1_Source_RELEASE.zip"
ditto -c -k --keepParent "$KEXT" "$ZIP"
unzip -t "$ZIP"
{
  echo "Upstream=$UPSTREAM_SHA"
  echo "MacKernelSDK=$SDK_SHA"
  echo "LiluDev=1.7.2"
  echo "D behavior: OFF unless boot argument -wex-a7a0-panel-only is present"
  echo "Output=$ZIP"
  xcrun dwarfdump --uuid "$KEXT/Contents/MacOS/WhateverXe"
  shasum -a 256 "$ZIP" "$KEXT/Contents/MacOS/WhateverXe"
} | tee "$OUT/BUILD_INFO.txt"

echo "SUCCESS: $ZIP"
echo "Complete D1.1 source retained at $SRC"
echo "WARNING: Kext is NOT installed; use a separate USB EFI. No hardware test was performed."
