# Builds one top-magazine anim set: authored two-handed clips (glb) stored under the game's reload clip names in
# a copy of the Lexington right-hand dual-wield set, every other clip of that set renamed out of the way.
# usage: buildtopmag.sh <pma|pwa> <out .anims> <clip glb>=<name> [...]
# Needs WK (WolvenKit.CLI.exe), DOTNET_ROOT, Python 3 + numpy, PowerShell 7. LEX: folder with the Lexington sets.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
BODY="$1"; OUT="$2"; shift 2
LEX="${LEX:-C:/Modding/_tools/gamefiles}"
case "$BODY" in
  pma) GLB="$LEX/anim/raw/dw_right__militech_lexington.anims.glb"; ANIMS="$LEX/dw/dw_right__militech_lexington.anims" ;;
  pwa) GLB="$LEX/anim/raw/pwa_w_handgun_dual_wield_right__militech_lexington.anims.glb"
       ANIMS="$LEX/arm/base/animations/weapon/firearms/dual_wield/handgun/militech_lexington/pwa_w_handgun_dual_wield_right__militech_lexington.anims" ;;
  *) echo "body must be pma or pwa"; exit 1 ;;
esac
TMP="$(mktemp -d)"
NAME="$(basename "$OUT" .anims)"
names=()
for a in "$@"; do names+=("${a##*=}"); done
python "$HERE/topmag.py" "$GLB" "$TMP/$NAME.glb" "$@"
cp "$ANIMS" "$TMP/$NAME.anims"
pwsh -NoProfile -File "$HERE/animimport.ps1" "$TMP/$NAME.glb" "$TMP/$NAME.anims" | grep -E "import ok|Success"
"$WK" convert s "$TMP/$NAME.anims" -o "$TMP" > /dev/null
python "$HERE/animrename.py" "$TMP/$NAME.anims.json" "${names[@]}"
mkdir -p "$TMP/out"
"$WK" convert d "$TMP/$NAME.anims.json" -o "$TMP/out" > /dev/null
mkdir -p "$(dirname "$OUT")"
cp "$TMP/out/$NAME.anims" "$OUT"
rm -rf "$TMP"
echo "built $OUT"
