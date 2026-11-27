# ga ingame

Scripted in-game test of one gun, with every file it changes backed up and restored.

```
tools/anim/ga.sh ingame <gun> [--partner <gun>] [--item <Items.Preset_X_Default>] [--record] [--build | --overlay <folder>]
                              [--baseline] [--visual] [--spec <json>] [--work <dir>]
tools/anim/ga.sh ingame --dry-run          # whole run on copies, no game: the acceptance test
tools/anim/ga.sh ingame --restore <run>    # put back an interrupted run from its journal.json
```

## What a run does

1. Refuses if `Cyberpunk2077.exe` runs (the owner may be playing). Takes `C:\Modding\gg-work\gamelock`.
2. Closes MO2 if open (normal close, 60 s; refuses otherwise). It is reopened at the end.
3. Backs up, verified by SHA-256, before anything changes: every `AutoSave-*`, `QuickSave-*`, `PointOfNoReturnSave-*`
   folder and the top level files of the save folder (all other folders are hashed only); `UserSettings.json`,
   `modlist.txt`, `settings.ini` of profile 3077, the Mod Settings `user.ini`, the MO2 instance ini.
   Default run folder: `C:\Modding\_tools\ingame-runs\<time>-<gun>\` (`backup/`, `quarantine/`, `run.log`, `journal.json`, `evidence/`).
4. Sets music 0; unless `--visual`: monitor 2, 2560x1440, HDR off when two displays are attached (one display: used as is,
   HDR off). Edited in the file with the game closed, never in the running game.
5. Enables the probe mod `GA Ingame Probe` (from `probe/gaingame`) in the modlist; `--build` runs `ga.sh produce <gun> --out`
   with a WORK in the run folder and enables its partial archives as the mod `GA Ingame Build` (top priority);
   `--overlay` does the same with archives you built. `--baseline` switches Gorilla Akimbo and the overlay off.
6. Launches through MO2, screenshots the menu, loads the save, checks the player level (`expect_level`), teleports to North Oak.
7. Runs the battery from the spec for the pair: equip, stats per slot, frozen dummy 6 m ahead (after a civilian check),
   N shots per hand (probe counts them), reload in the lowered and the raised stance, screenshots, optional recording.
   Results: `run.log`, `results.json`, `evidence/out.txt`.
8. Teardown (also on any error, Ctrl+C and exit): stops the game, closes MO2, moves the deployed mod folders aside, puts every
   file back, puts every backed-up save folder back (the differing one is moved to `quarantine/changed` first), moves saves the
   run created to `quarantine/created`, then hashes the whole save folder against the snapshot. The lock is released only
   when that matches. Nothing is deleted.

`--baseline`: one fresh launch per pair, one backup and one restore around all of them; nothing is carried between pairs.

## Dry run (acceptance)

Copies the save folder and settings into the run folder, runs steps 1 to 5 and 8 on the copies, replaces the game with a
function that overwrites an autosave, deletes one, adds a junk one, changes a quicksave, the settings, the modlist and the
ini files, then restores and compares. It also checks that the real saves and settings did not change and that the copies
equal the real ones. Takes about 10 s.

## Not verified without a game run

- The save is loaded with "Continue" (clicks at a fraction of the window). Continue loads the newest save, not necessarily
  `ManualSave-62`; the level check stops the run on a wrong save, and the restore still runs.
- `OutputMonitor` 2 means monitor 2 (only 1 appears in the settings backups); `HDRModes` `None` is HDR off (seen in backups).
- Probe commands `civ` (NPC count API), `shots` (Observe on `WeaponObject.OnShoot`), `tp`, `dummy` follow the earlier perk probe
  where they exist; the rest are new. The first run shows which fail (`error ...` lines in `evidence/out.txt`).
- Stance: `lowered` is the safe-zone default after drawing; `raised` fires one shot first. Recording uses ffmpeg `gdigrab`
  of the game window.
- `--build` is not run here; it needs the WolvenKit lock by hand (`C:\Modding\gg-work\wkitlock`).
