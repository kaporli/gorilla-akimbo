# Builds archive/pc/mod/GorillaAkimboLowered.archive and its .archive.xl: the lowered (safe) stance sets of
# lowsets.py, for male (pma) and female (pwa) V, both hands. Each set is a copy of the game's dual-wield base set with
# friendly_idlepose, safe_action and equip_safe (_l for the left hand) replaced and every other clip renamed out of the
# way. GorillaAkimbo.archive is not touched.
#
# Needs: WolvenKit CLI 9.1 (WK), DOTNET_ROOT, Python 3 with numpy, PowerShell 7, and
#   BASESET: <body>_w_handgun_dual_wield_base.anims for pma and pwa (base\animations\weapon\firearms\dual_wield\
#            handgun\base\) and their .glb exports (WolvenKit.CLI export)
#   LOWCLIPS: the authored clips (lowsets.py)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
WK="${WK:?set WK to WolvenKit.CLI.exe}"
BASESET="${BASESET:-C:/Modding/anim-work/lowered/production/base}"
LOWCLIPS="${LOWCLIPS:-C:/Modding/anim-work/lowered/production/clips}"
WORK="${WORK:-$ROOT/tools/anim/work}/lowered"
PACK="$WORK/pack/gorillaakimbo/animations"
rm -rf "$WORK"; mkdir -p "$PACK"
one(){ # body side name glb
  local T="$WORK/tmp_$3"; mkdir -p "$T/out"
  python "$HERE/lowset.py" "$BASESET/${1}_w_handgun_dual_wield_base.anims.glb" "$4" "$T/$3.glb" $2 > /dev/null
  cp "$BASESET/${1}_w_handgun_dual_wield_base.anims" "$T/$3.anims"
  pwsh -NoProfile -File "$HERE/animimport.ps1" "$T/$3.glb" "$T/$3.anims" | grep -q "import ok: True" || { echo "import failed: $3"; return 1; }
  "$WK" convert s "$T/$3.anims" -o "$T" > /dev/null
  if [ $2 = right ]; then keep="friendly_idlepose safe_action equip_safe"; else keep="friendly_idlepose_l safe_action_l equip_safe_l"; fi
  python "$HERE/animrename.py" "$T/$3.anims.json" $keep > /dev/null
  "$WK" convert d "$T/$3.anims.json" -o "$T/out" > /dev/null
  cp "$T/out/$3.anims" "$PACK/$3.anims"; rm -rf "$T"; echo "built $3"
}
python "$HERE/lowsets.py" "$LOWCLIPS" sets | tr -d '\r' > "$WORK/sets.txt"
n=0
while read -r body side name glb; do
  one $body $side $name $glb &
  n=$((n+1)); [ $((n % 4)) = 0 ] && wait
done < "$WORK/sets.txt"
wait
[ "$(ls "$PACK" | wc -l)" = "$(wc -l < "$WORK/sets.txt")" ] || { echo "some sets failed"; exit 1; }
mkdir -p "$WORK/GorillaAkimboLowered"; mv "$WORK/pack/gorillaakimbo" "$WORK/GorillaAkimboLowered/"
"$WK" pack "$WORK/GorillaAkimboLowered" -o "$WORK" > /dev/null
cp "$WORK/GorillaAkimboLowered.archive" "$ROOT/archive/pc/mod/GorillaAkimboLowered.archive"
python "$HERE/genlowxl.py" "$ROOT/archive/pc/mod/GorillaAkimboLowered.archive.xl" "$LOWCLIPS"
echo "built $ROOT/archive/pc/mod/GorillaAkimboLowered.archive"
