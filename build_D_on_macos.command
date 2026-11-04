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
[[ ! -e "$WORK" && ! -e "$OUT" ]] || {
  echo "Existing work_D or OUTPUT_D: keep your previous results, or rename them before a new build." >&2
  exit 1
}
mkdir -p "$WORK" "$OUT"
exec > >(tee "$OUT/build.log") 2>&1

echo "=== Experimental WhateverXe D: pinned upstream + B diagnostics + C port mode + D optional panel-only ==="
echo "Host: $(uname -sm)"
echo "Source revision: $UPSTREAM_SHA"

git clone https://github.com/b00t0x/WhateverXe.git "$SRC"
git -C "$SRC" checkout --detach "$UPSTREAM_SHA"
test "$(git -C "$SRC" rev-parse HEAD)" = "$UPSTREAM_SHA"
git clone https://github.com/acidanthera/MacKernelSDK.git "$SDK"
git -C "$SDK" checkout --detach "$SDK_SHA"
test "$(git -C "$SDK" rev-parse HEAD)" = "$SDK_SHA"
git clone --branch 1.7.2 --depth 1 https://github.com/acidanthera/Lilu.git "$LILU"

for p in \
  "$ROOT/WhateverXe_A7A0_Diagnostic_0.7.0.patch" \
  "$ROOT/patches/0003-B-to-C-eDP-software-port-mode.patch" \
  "$ROOT/patches/0004-A7A0-single-panel-clock-isolation-EXPERIMENTAL.patch"
do
  echo "Applying $(basename "$p")"
  git -C "$SRC" apply --check "$p"
  git -C "$SRC" apply "$p"
done
git -C "$SRC" diff --check
grep -Fq 'checkKernelArgument("-wex-a7a0-panel-only")' "$SRC/WhateverXe/kern_xe.cpp"
grep -Fq 'WEXDiagDSinglePanelApplied' "$SRC/WhateverXe/kern_xe.cpp"
git -C "$SRC" diff > "$OUT/WhateverXe_A7A0_D_FULL_SOURCE_DIFF.patch"

mkdir -p "$SRC/Lilu.kext/Contents/Resources"
ln -s "$LILU/Lilu/Headers" "$SRC/Lilu.kext/Contents/Resources/Headers"
ln -s "$LILU/Lilu/Library" "$SRC/Lilu.kext/Contents/Resources/Library"

cd "$SRC"
python3 tools/test.py
python3 tools/build.py --release --sdk "$SDK" --output build/RELEASE
python3 tools/check_compat_version.py build/RELEASE

KEXT="$SRC/build/RELEASE/WhateverXe.kext"
test -f "$KEXT/Contents/Info.plist"
test -f "$KEXT/Contents/MacOS/WhateverXe"
ZIP="$OUT/WhateverXe_A7A0_D_PanelOnly_0.7.0_RELEASE.zip"
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
echo "Patched source retained at $SRC"
echo "WARNING: Kext is NOT installed; use a separate USB EFI. No hardware test was performed."
