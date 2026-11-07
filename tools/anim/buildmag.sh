# Builds the dual-wield Shingen magazine sets (magtrack.py): one glb per family and side, each imported into a copy of
# the vanilla magazine set, every clip but the six reload clips renamed out of the way (animrename.py).
# usage: buildmag.sh <spec.json> <out anims dir> [--probe]
# Needs WK (WolvenKit.CLI.exe), DOTNET_ROOT, Python 3 + numpy + scipy, PowerShell 7. VANILLA: the vanilla magazine set.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SPEC="$1"; OUT="$2"; PROBE="$3"
VANILLA="${VANILLA:-C:/Modding/_tools/gamefiles/wanim3/base/animations/weapon/firearms/smg/arasaka_shingen/w_smg__arasaka_shingen__mag_std.anims}"
TMP="$(mktemp -d)"
python "$HERE/magtrack.py" "$SPEC" "$TMP" $PROBE
mkdir -p "$OUT"
for glb in "$TMP"/*.glb; do
  NAME="$(basename "$glb" .glb)"
  cp "$VANILLA" "$TMP/$NAME.anims"
  pwsh -NoProfile -File "$HERE/animimport.ps1" "$glb" "$TMP/$NAME.anims" | grep -E "import ok|Success"
  "$WK" convert s "$TMP/$NAME.anims" -o "$TMP" > /dev/null
  python "$HERE/animrename.py" "$TMP/$NAME.anims.json" reload reload_01 reload_02 empty_reload empty_reload_01 empty_reload_02
  mkdir -p "$TMP/out"
  "$WK" convert d "$TMP/$NAME.anims.json" -o "$TMP/out" > /dev/null
  cp "$TMP/out/$NAME.anims" "$OUT/$NAME.anims"
  echo "built $OUT/$NAME.anims"
done
rm -rf "$TMP"
