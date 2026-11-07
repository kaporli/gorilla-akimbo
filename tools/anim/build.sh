# Builds archive/pc/mod/GorillaAkimbo.archive: the dual-wield arm clips for male (pma) and female (pwa) V, made from
# the game's Lexington dual-wield sets. See README.md in this folder.
#
# Needs: WolvenKit CLI 9.1 (WK), Python 3 with numpy, PowerShell 7, and the extracted Lexington sets (SRC) as
#   SRC/pma_w_handgun_dual_wield_{right,left}__militech_lexington.anims (+ their .glb exports in SRC/glb)
#   SRC/pwa_w_handgun_dual_wield_{right,left}__militech_lexington.anims (+ .glb)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
WK="${WK:?set WK to WolvenKit.CLI.exe}"
SRC="${SRC:?set SRC to the folder with the extracted Lexington sets}"
WORK="${WORK:-$ROOT/tools/anim/work}"
PACK="$WORK/pack/gorillaakimbo/animations"
mkdir -p "$PACK"
for sex in pma pwa; do
  for side in right left; do
    base="${sex}_w_handgun_dual_wield_${side}__militech_lexington"
    python "$HERE/flick.py" "$SRC/glb/$base.anims.glb" "$WORK/${sex}_$side.glb" $side
    cp "$SRC/$base.anims" "$WORK/${sex}_$side.anims"
    pwsh -NoProfile -File "$HERE/animimport.ps1" "$WORK/${sex}_$side.glb" "$WORK/${sex}_$side.anims"
    cp "$WORK/${sex}_$side.anims" "$PACK/${sex}_dual_wield_${side}_lowered.anims"
  done
done
# Top-magazine reloads (Shingen, Midnight Borg): two-handed clips authored in Blender, one glb per clip in CLIPS/<body>/
# (see topmagsets.py for the sets and their names).
export CLIPS="${CLIPS:-C:/Modding/anim-work/clips}"
python "$HERE/topmagsets.py" "$CLIPS" sets | tr -d '\r' | while read -r body name clips; do
  bash "$HERE/buildtopmag.sh" "$body" "$PACK/$name.anims" $clips
done
"$WK" pack "$WORK/pack" -o "$WORK"
cp "$WORK/pack.archive" "$ROOT/archive/pc/mod/GorillaAkimbo.archive"
python "$HERE/genxl.py" "$ROOT/archive/pc/mod/GorillaAkimbo.archive.xl" "$PACK"
echo "built $ROOT/archive/pc/mod/GorillaAkimbo.archive"
