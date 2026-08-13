#!/usr/bin/env bash
# Copy the MXL 3D-ICE source fixes into the vendored 3d-ice/ tree.
#
#   ./MXL_3DICE_fixes/apply.sh            apply (backs up anything it overwrites)
#   ./MXL_3DICE_fixes/apply.sh --check    report differences, change nothing
#
# Run this after any fresh get_and_patch_3DICE.sh. See README.md in this directory for what
# each file fixes and why upstream's patches undo two of them.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
SRC="$HERE/files"
DST="$REPO/3d-ice"
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

[ -d "$DST" ] || { echo "no 3d-ice/ tree at $DST -- run get_and_patch_3DICE.sh first" >&2; exit 1; }

differs=0
applied=0
while IFS= read -r rel; do
    src="$SRC/$rel"
    dst="$DST/$rel"
    if [ ! -e "$dst" ]; then
        echo "  MISSING in 3d-ice: $rel"
        differs=$((differs + 1))
        [ "$CHECK" -eq 1 ] && continue
    elif cmp -s "$src" "$dst"; then
        echo "  ok        $rel"
        continue
    else
        echo "  DIFFERS   $rel"
        differs=$((differs + 1))
        [ "$CHECK" -eq 1 ] && continue
        cp -a "$dst" "$dst.pre-mxl.$(date +%Y%m%d%H%M%S)"
    fi
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    applied=$((applied + 1))
done < <(cd "$SRC" && find . -type f -printf '%P\n' | sort)

echo
if [ "$CHECK" -eq 1 ]; then
    if [ "$differs" -eq 0 ]; then
        echo "3d-ice tree already has the MXL fixes."
    else
        echo "$differs file(s) differ. Run without --check to apply."
        exit 1
    fi
else
    if [ "$applied" -eq 0 ]; then
        echo "Nothing to do -- already applied."
    else
        echo "Applied $applied file(s). Rebuild:"
        echo "    make -C 3d-ice/heatsink_plugin && make -C 3d-ice"
        echo "Then verify:"
        echo "    python examples/fmu_acceptance_test.py"
    fi
fi
