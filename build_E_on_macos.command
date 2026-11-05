#!/usr/bin/env bash
# E1.0: local macOS source build ONLY. Never installs drivers or changes EFI.
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORK="$ROOT/work_E"
SRC="$WORK/WhateverXe"
SDK="$WORK/MacKernelSDK"
LILU="$WORK/Lilu"
OUT="$ROOT/OUTPUT_E"
ACER_REV="f7b9bf2229d323e37e8b1dfb87182f005eb7a277"
SDK_REV="05094e5e88cec7caedbfb35e8449ed0db94bf95b"
ACER_HEADER="11c68039074139aa25855e19ec1cfd550df0c748"
D_HEADER="c6fa4c05799e326e91cce659435fbc56a5068e96"

if [[ "$(uname -s)" != Darwin ]]; then
  echo "Build requires macOS with Apple Command Line Tools / Xcode" >&2; exit 1
fi
for cmd in git python3 xcrun ditto unzip shasum tee; do
  command -v "$cmd" >/dev/null || { echo "Missing tool: $cmd" >&2; exit 1; }
done
xcrun --find clang++ >/dev/null || { echo "Install Apple CLT: xcode-select --install" >&2; exit 1; }
mkdir -p "$WORK" "$OUT"
exec > >(tee "$OUT/build.log") 2>&1
echo "=== E1.0 Yoga A7A0 multi-output test: acer/current + D1.1 CTL2 ==="
if [[ ! -d "$SRC/.git" ]]; then
  git clone https://github.com/Thatisjigen/WhateverXe.git "$SRC"
  git -C "$SRC" checkout --detach "$ACER_REV"
fi
if [[ "$(git -C "$SRC" rev-parse HEAD)" != "$ACER_REV" ]]; then
  echo "REFUSED: cached source is not pinned acer/current" >&2; exit 1
fi
# Rebuilds may revert *only* our exact previous header overlay.
actual="$(git hash-object "$SRC/WhateverXe/kern_alderlake_n.hpp")"
if [[ "$actual" == "$D_HEADER" ]]; then
  git -C "$SRC" restore --source=HEAD -- WhateverXe/kern_alderlake_n.hpp
elif [[ "$actual" != "$ACER_HEADER" ]]; then
  echo "REFUSED: unexpected changes to cached header" >&2; exit 1
fi
if [[ -n "$(git -C "$SRC" status --porcelain --untracked-files=no)" ]]; then
  echo "REFUSED: other tracked changes in cached upstream" >&2; exit 1
fi
if [[ ! -d "$SDK/.git" ]]; then
  git clone https://github.com/acidanthera/MacKernelSDK.git "$SDK"
  git -C "$SDK" checkout --detach "$SDK_REV"
fi
if [[ "$(git -C "$SDK" rev-parse HEAD)" != "$SDK_REV" ]]; then
  echo "REFUSED: MacKernelSDK revision mismatch" >&2; exit 1
fi
if [[ ! -f "$LILU/Lilu/Headers/kern_api.hpp" ]]; then
  git clone --branch 1.7.2 --depth 1 https://github.com/acidanthera/Lilu.git "$LILU"
fi
python3 "$ROOT/e/tools/prepare_e.py" "$SRC"
mkdir -p "$SRC/Lilu.kext/Contents/Resources"
for item in Headers Library; do
  link="$SRC/Lilu.kext/Contents/Resources/$item"
  if [[ -L "$link" ]]; then
    [[ -d "$link" ]] || { echo "Broken Lilu $item symlink" >&2; exit 1; }
  elif [[ ! -e "$link" ]]; then
    ln -s "$LILU/Lilu/$item" "$link"
  else
    echo "REFUSED: non-symlink Lilu dependency: $link" >&2; exit 1
  fi
done
cd "$SRC"
python3 tools/test.py
python3 tools/build.py --release --sdk "$SDK" --output build/RELEASE
python3 tools/check_compat_version.py build/RELEASE
KEXT="$SRC/build/RELEASE/WhateverXe.kext"
test -s "$KEXT/Contents/MacOS/WhateverXe"
test -f "$KEXT/Contents/Info.plist"
ZIP="$OUT/WhateverXe_A7A0_E1.0_Experimental_RELEASE.zip"
ditto -c -k --keepParent "$KEXT" "$ZIP"
unzip -t "$ZIP"
git -C "$SRC" diff -- WhateverXe/kern_alderlake_n.hpp > "$OUT/E1.0_REVIEWED_SOURCE_DIFF.patch"
{
  echo "E1.0=acer/current multi-output + D1.1 eDP CTL2 only"
  echo "acer/current=$ACER_REV"
  echo "Archived D1.1=aac27153cf010cbd77fda2df30d321db327ee37f"
  echo "MacKernelSDK=$SDK_REV"
  echo "Lilu=1.7.2"
  echo "Graphics=existing signed 0.4.0 (NOT modified)"
  echo "No panel-only parameter and no forced software port mode"
  echo "WARNING: NOT tested on Yoga; separate recovery/test EFI only"
  xcrun dwarfdump --uuid "$KEXT/Contents/MacOS/WhateverXe"
  shasum -a 256 "$ZIP" "$KEXT/Contents/MacOS/WhateverXe"
} | tee "$OUT/BUILD_INFO.txt"
echo "BUILD SUCCESS: $ZIP"
