# Animation tools

Scripts that build the dual-wield arm animations and the reload sound table. Not needed to use the mod.

| File | What it does |
|---|---|
| `flick.py` | Builds the reload clips for one hand from a Lexington dual-wield set (glb): the pistol's tip-up (half height, smoothed), a drop out of view with the muzzle tipped down, a hold, and the pistol's empty-reload rise (40% of its rotation). The `_02` variants drop straight down, for shell-by-shell shotguns. The arm moves rigidly with the gun, so the arm and its IK targets agree. |
| `glb.py`, `fk.py` | Minimal glb reader/writer and forward kinematics used by `flick.py`. |
| `animimport.ps1` | Imports a glb into an `.anims` file through WolvenKit's library (the CLI can export animations but not import them). |
| `build.sh` | Runs the above for male and female V, packs `archive/pc/mod/GorillaAkimbo.archive` and writes the `.archive.xl`. |
| `topmagsets.py` | Lists the top-magazine reload sets (Shingen): which authored clips go into which set, per hand, body and partner-gun category (`partner_categories.json` in the clips folder), and their archive.xl entries. Long shotguns (Carnage, Tactician, Zhuo, Igla, Testera, Satara) get a set of their own three clips per gun. |
| `buildtopmag.sh` | Builds one top-magazine set: the clips stored under the game's reload clip names in a copy of the Lexington right-hand set (`topmag.py`, then `animimport.ps1`), every other clip renamed out of the way (`animrename.py`). |
| `topmag.py`, `animrename.py` | Used by `buildtopmag.sh`. The clips themselves are authored in Blender; the work files are kept outside the repo. |
| `magtrack.py`, `buildmag.sh` | The Shingen magazine while dual-wielding: it stays seated until the other gun hits it (f25), then flies off along the hit under gravity, is shrunk once out of view and comes back with the vanilla insertion at f46. One set per family (long partner, other partner, two Shingens) and side, keyed on wrappers the script sets on the gun. The flight parameters (spec json) are chosen and checked outside the repo. ArchiveXL adds the sets to the "Magazine" component of the weapon entity (`base\weapons\weapon_root.ent`, `component: Magazine`): the Shingen's appearance embeds the magazine there. The sets are added to every weapon's Magazine component but only play on a Shingen, where the script sets their wrapper. |
| `magapp.py` | Fallback if those entries do not apply: adds the six sets to the Magazine component of every appearance of `w_smg__arasaka_shingen.app`. Shipping the edited `.app` overrides the vanilla file, so another mod that edits it conflicts. |
| `genxl.py` | Writes `GorillaAkimbo.archive.xl`: one entry per hand per SMG or shotgun model variable, for male and female V. |
| `gensounds.py` | Writes `r6/scripts/GorillaAkimbo/GorillaAkimboSounds.reds` from the weapons' two-handed reload clips (WolvenKit JSON). |
| `sounds.py`, `inktree.py` | Inspection helpers: reload sound events of an anim set, widget tree of an `.inkwidget`. |

Export the Lexington sets to glb with `WolvenKit.CLI export <anims> -o <dir> -gp <game folder>`, convert anim sets to
JSON with `WolvenKit.CLI convert s`.
