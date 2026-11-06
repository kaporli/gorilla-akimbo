# Animation tools

Scripts that build the dual-wield arm animations and the reload sound table. Not needed to use the mod.

| File | What it does |
|---|---|
| `flick.py` | Builds the reload clips for one hand from a Lexington dual-wield set (glb): the pistol's tip-up (half height, smoothed), a drop out of view with the muzzle tipped down, a hold, and the pistol's empty-reload rise (40% of its rotation). The `_02` variants drop straight down, for shell-by-shell shotguns. The arm moves rigidly with the gun, so the arm and its IK targets agree. |
| `glb.py`, `fk.py` | Minimal glb reader/writer and forward kinematics used by `flick.py`. |
| `animimport.ps1` | Imports a glb into an `.anims` file through WolvenKit's library (the CLI can export animations but not import them). |
| `build.sh` | Runs the above for male and female V, packs `archive/pc/mod/GorillaAkimbo.archive` and writes the `.archive.xl`. |
| `genxl.py` | Writes `GorillaAkimbo.archive.xl`: one entry per hand per SMG or shotgun model variable, for male and female V. |
| `gensounds.py` | Writes `r6/scripts/GorillaAkimbo/GorillaAkimboSounds.reds` from the weapons' two-handed reload clips (WolvenKit JSON). |
| `sounds.py`, `inktree.py` | Inspection helpers: reload sound events of an anim set, widget tree of an `.inkwidget`. |

Export the Lexington sets to glb with `WolvenKit.CLI export <anims> -o <dir> -gp <game folder>`, convert anim sets to
JSON with `WolvenKit.CLI convert s`.
