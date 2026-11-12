# Animation tools

Everything generated that the mod ships, and the tools that author and check the clips. Not needed to use the mod.

## Products

| Product | What it is | Made by |
|---|---|---|
| `GorillaAkimbo.archive`: `<body>_dual_wield_<side>_reload.anims` (4) | Per-hand reload arm clips for SMGs, shotguns and rifles held one-handed (tip up, drop out of view, rise). Named `_lowered` up to 3.2.0. | `build.sh reload` (`flick.py`, from the game's Lexington dual-wield sets). No authoring. |
| `GorillaAkimbo.archive`: `<body>_topmag_*.anims` (66) | Two-handed reload of a top-magazine gun (Shingen): the other gun knocks the magazine out. One set per partner size category, per long partner gun, and for two Shingens. | Authored arm clips (`paths.clips`), packed by `build.sh topmag`. |
| `GorillaAkimbo.archive`: `w_smg__arasaka_shingen__mag_*.anims` (6) | The Shingen magazine's flight after the hit. | Flight spec (`authoring/magtrack/spec.json`), written by `build.sh mag` (`magtrack.py`). |
| `GorillaAkimbo.archive`: `<body>_dual_wield_<side>_raised_<pose>.anims`, `<body>_dual_wield_<side>_reload_<pose>.anims`, `<body>_topmag_*_raised_<pose>.anims` | Raised pose of a gun that is too bulky for the game's pistol pose (rifles): its pose clips, its own per-hand reload set (ends in that pose, with its equip, unequip, melee) and the top-magazine sets with it as partner. Only guns with a `raised` entry. | Authored clips (`paths.raised_clips`), packed by `build.sh raised`, `reload`, `topmag`. |
| `GorillaAkimboRifles.archive`: `<body>_dual_wield_<side>_rreload_<gun>.anims`, `<gun>__rmag_<body>_<side>.anims` | Rifles' own one-handed reloads that fit the magazine (front magazine, Masamune, Hercules cassette), each with its own magazine track. One arm set and one magazine set per owner gun, body and hand. | Authored clips (`paths.rreload_clips`, `authoring/reload/prod.py`), packed by `build.sh rreload` (`rreload.py`, `rarmset.py`, `rmagset.py`, `genrxl.py`). |
| `GorillaAkimboLowered.archive` (48) | Lowered (safe) stance per hand and gun: v1 low ready, v2 high port. | Authored clips (`paths.low_clips`), packed by `build.sh lowered`. |
| The `.archive.xl` files | Which set plays for which model variables. | `build.sh xl`; the rifles' one by `build.sh rreload` |
| `GorillaAkimboSounds.reds`, `GorillaAkimboGuns.reds` | Reload sound times; types, long partners, top-magazine timing. | `build.sh sounds`, `guns` |

## Build

```
tools/anim/build.sh extract          # once: game files from the game's archives (about 2 minutes)
tools/anim/build.sh all              # build everything into the checkout (about 25 minutes)
tools/anim/build.sh verify           # compare with git HEAD of the reference repo, or --ref <folder>
tools/anim/build.sh check            # numeric checks of the shipped clips and built sets (about 10 minutes)
tools/anim/build.sh all --with-test  # also the "test" content of weapons.json, into WORK/test-out only
```

`all` includes `rreload` (its round trip is about 10 to 15 minutes of the total). It runs after `reload` (it copies the per-hand reload sets
that step built, the raised-pose ones included) and ends with the round trip: every set exported back and compared
with its source glb (`WORK/rreload/roundtrip.txt`).

Single steps: `reload`, `topmag`, `mag`, `lowered`, `raised`, `rreload`, `xl`, `sounds`, `guns`, `tables`. A step that makes anim sets
repacks its archive from the sets built so far and stops if some are missing. `tools/anim/gen <step>` is the same.
Run one build per work folder at a time.

Needs WolvenKit CLI 9.1, .NET, Python 3 with numpy and scipy, PowerShell 7 and the game; previews also need Blender,
ffmpeg and Pillow. Paths are in the `paths` block of `weapons.json`; each has an environment variable that overrides
it. A relative default is relative to `tools/anim`; an entry with `;` lists folders searched in order.

| Variable | What |
|---|---|
| `GAME` | Cyberpunk 2077 folder |
| `WK`, `DOTNET_ROOT` | WolvenKit.CLI.exe and the .NET root it runs on |
| `GAMEFILES` | extracted game files (`build.sh extract` fills it, depot folder layout) |
| `CLIPS` | shipped top-magazine arm clips, `<body>/<clip>.glb` |
| `CLIPS_PRE_ENDPOSE` | the same clips before the end-pose fix (its input) |
| `MAGSPEC` | magazine flight spec (default `authoring/magtrack/spec.json`) |
| `LOWCLIPS`, `LOWCLIPS_TEST` | lowered stance clips, `<body>/lowered_<pose>.glb`; test guns' clips |
| `RAISEDCLIPS` | raised pose clips, `<body>/raised_<pose>.glb`, `raised_<pose>_hands.glb`, `topmag/<clip>__<pose>.glb` |
| `RRELOADCLIPS` | rifle reload clips, `<body>/<gun>_<side>_<pick><take>_<clip>.glb` with `.json` (spec), `_track.json`, `_gate.json`; `layout.json` |
| `RRELOADGAMEFILES` | rifles' own game anim sets (weapon, magazine, two-handed arm sets) for timing and magazine paths |
| `WORK` | build work folder, outside the repo. Sets in `WORK/sets`, test output in `WORK/test-out`, check report in `WORK/check` |
| `REF` | repo whose git HEAD `verify` compares with |
| `ANIMWORK` | authoring data folder (specs, drafts, renders, every clip generation; never deleted) |
| `AUTHORING` | folder for new authoring output |
| `BLENDER`, `FFMPEG` | blender.exe, ffmpeg.exe |
| `WMESH`, `WANIM`, `VMESH` | weapon mesh glbs, weapon anim glbs, V's arm mesh glbs (WolvenKit exports) |
| `JOBS` | parallel jobs (4) |

`verify` reads the reference with `git cat-file blob HEAD:<path>` (no checkout), compares the two `.archive.xl` files
and `GorillaAkimboSounds.reds` byte for byte and the archives per packed file. A set renamed since the reference
(`set_names` in `weapons.json`) is compared with its old name and reported as "renamed, content identical".

### Game files (`build.sh extract`)

The list comes from `weapons.json` (`python manifest.py files`). Most of these files are not in WolvenKit's name
list, so they are unbundled by the FNV1a64 hash of the lower-case depot path:

```
WolvenKit.CLI unbundle "<game>\archive\pc\content" -o <dir> --hash <file with one decimal hash per line>
WolvenKit.CLI export <file.anims> -o <its folder> -gp "<game>"      # <file>.anims.glb
WolvenKit.CLI convert s <file.anims> -o <its folder>                # <file>.anims.json
```

The unbundle exit code is not 0 when an archive lacks one of the hashes, which is always.

Not extracted by the build (authoring only): a gun's mesh parts (`<mesh>__base1_01.mesh`, receiver, stock, magazine
`__mag_std_01`), its weapon anim sets (`<mesh>__base1.anims`, `__mag_std.anims`) and V's arm meshes. Unbundle them
the same way and `WolvenKit.CLI export` each into a folder of `WMESH`, `WANIM` or `VMESH`.

## weapons.json

The single source of gun knowledge. No script holds a gun list or a path.

- `paths`: above.
- `game_files`: player entities per body, the reload source sets, the lowered base set, the magazine entity.
- `set_names`: name of the per-hand reload sets, and their name before the rename.
- `reload_clip`: layout of the per-hand reload clips in frames (`flick.py`) and seconds (the script).
- `checks`: limits of `build.sh check`. "baseline" in a note: the worst value of the shipped clips, kept as the limit.
- `lowered_families`: v1, v2 and v1d (deep low ready, the longest rifles) lowered poses (template, right-hand offset
  and angles, clavicle).
- `raised_families`: raised poses for guns too bulky for the game's pistol pose. A family is a direction for the idle
  clips and one for the aim clip (metres per unit s, right hand), a roll about the barrel and a screen cover target;
  the muzzle direction never changes.
- `types`: per weapon type: `name`, `plural`, `group`, `status`, `needs_arms`, `arm_clips` (uses the mod's arm clips
  and lowered stance), `item_types` with `base_var`, `fallback_audio`, `fallback_audio_shells`.
- `guns`: `id`, `name`, `type`, `item_type`, `vars` (model variables; the left hand's are these plus `_left`),
  `audio`, `arm_set` (male two-handed arm set, for the sound table), `mesh` (mesh stem), `parts` (mesh parts drawn in
  previews and used by the top-magazine checks), `mesh_parts` (parts added to body, receiver and stock in the lowered
  checks), `weapon_anim` (stem of its weapon anim set if not the mesh stem), `length` (long or short), `long_partner`
  (whose long-partner clips it plays; its own id if it has its own), `long_partner_vars`, `lowered` (`family`, `pose`,
  `tune`), `raised` (`family`, `pose`, `s` per body; `{"family": "none"}` keeps the game pose on purpose; no entry is
  the game pose too), `partner` (per top-magazine gun: flip, doubletap, uppercut category), `topmag` (`enabled`, `kind`,
  `clip_name`, `pair_code`, `frames`, `partner_default`, `magazine`), `generic`, `status`, `note`.
- `status`: `release` is built and shipped, `test` only with `--with-test` (or `GA_TEST=1`), `disabled` never.

Guns that share a model variable (Kyubi uses the Ajax's, Umbra the Copperhead's, Kappa the Yukimura's) have an empty
`vars` list: they add their audio sets to the script tables and get the other gun's animation sets.

## Authoring tools (`authoring/`)

Run each script from its own folder. Output goes to `AUTHORING` unless a path is given; nothing is written into the
repo or into `ANIMWORK`.

| Folder | What |
|---|---|
| `common.py` | Paths and gun lookups from the manifest, for every script below. |
| `author/` | Clip author (`author.py <spec.json>`: gun keyframes, two-bone IK, recoil kicks), Blender preview (`scene.py`, `render.py sheet/gif/mp4/strip/compare`, `scene_bake.py`), `aimsmack.py`. Guide: `author/AUTHORING.md`. |
| `topmag/` | Top-magazine arm clip generators: `gen_long.py` (lupper, axe, hang per long gun), `gen_smg.py` (flip, doubletap, uppercut per partner category; the pairs), `partner.py` (which category fits a gun), `fit_turn.py` (turns and moves a long partner about its contact point until contact, body, eye, cover and wrist pass), `checks.py`, `compare.py`. Pick specs and category tables in `data/`. |
| `magtrack/` | Magazine flight: `mag_contacts.py` (contact frame per clip), `retime.py` (move a late or early hit to the hit frame), `mag_flight.py` (flight search and gates), `checks.py`, `preview.py`, `roundtrip.py`, `spec.json`. `reaim/`: change the push direction of a pick (`feas.py`, `opt.py`, `reaim_pick.py`, `armchecks.py`). |
| `endpose/` | `fix_endpose.py`, `batch.py`: the arms flow into the idle pose over the last frames. `verify.py`. |
| `raised/` | Raised pose: `rautotune.py` (s per gun and body), `rmakeclips.py` (pose clips, hand clips, top-magazine partner clips), `checks.py`, `rpreview.py` (before and after sheets and videos), `rpose.py` (IK shift, families, the screen metric). |
| `reload/` | Rifle reloads. Classify a gun from its own reload: `timing.py`, `magpath.py`, `armhands.py`, `gungeo.py`, `dumpanim.py`, `classify.py`, `sideview.py`; weight class sheet `weight.py`. Drafts: `make.py` with `front.py`, `masa.py`, `herc.py` (round 1), `round2.py` (round 2). Production: `prod.py list / build / layout` (picks, takes, stations, the magazine track `magtrack2.py`, the motion timeline `rlib2.py`), `rgate.py` (per clip gate), `checks.py`, `motionstats.py` (motion against the approved clips), `rrender3.py` (previews). |
| `lowered/` | Lowered stance: `autotune.py` (per-gun tune), `makeclips.py`, `seq.py` + `render.py` (preview), `checks.py`, `tune.py`, `wristsearch.py`, `cmp2.py`. |
| `checks/` | `gate.py` (`build.sh check`), `cmpclips.py` (two clips or folders: byte and numeric difference), `hashscan.py` (which other archives contain a game file the mod builds on). |

A top-magazine arm clip passes these stages, each a folder of `<body>/<clip>.glb`:
generator (`topmag/gen_*.py`) -> re-time where the hit is off the hit frame (`magtrack/retime.py`) -> re-aim where no
flight passes (`magtrack/reaim`) -> `CLIPS_PRE_ENDPOSE` -> end-pose fix (`endpose/batch.py`) -> `CLIPS`.

## Checks (`build.sh check`)

`build.sh check [--guns id,id] [--bodies pma,pwa] [--clips <dir>] [--only area,area] [--with-test]`. Each line is
pass or FAIL, the worst value, its limit, the worst item. Exit code 1 on a failure. Report: `WORK/check/report.txt`.
`--clips` checks another arm clips folder (the set checks are skipped then).

| Area | Checks |
|---|---|
| `clips` | last frame = `idlepose_shoulder`, per hand (0.01 cm, 0.01 deg); frames before the seated frame equal the clip before the fix; hands and guns moved by the fix; one clip of 96 frames |
| `sets` | every shipped clip of every built set is a SIMD buffer, has the frame count of its glb and lasts (frames - 1) / 30 s |
| `lowered` | seam and clip ends against the idle; eye distance in the lowered idle (25 cm); nearer than the raised pose; gun gap; wrist bend |
| `raised` | per raised pose: screen cover at the family target, eye distance, reach, wrist, gun gap, muzzle direction and hand on the grip against the game pose; pose clips start and end in the raised idle; the gun's reload clips, equip, unequip, melee and the top-magazine partner clips start and end there; everything else equals the source clip |
| `topmag` | contact miss and depth at the hit frame, hands gap, wrist, guns out of view in the hidden window, eye distance, face cover, hands on the guns, constant w < 0 rotation tracks |
| `magtrack` | magazine still before the hit, scale, flight gates (exit, eye, rise, acceleration, reversal, reappearance, screen, size), insertion, empty variants, contact frame of the arm clips |
| `rreload` | rifle reload clips (`rgate.py`): start and end against the gun's raised idle, hidden window (gun, hand, forearm, magazines off screen in first person, both bodies), no hanging magazine, release velocity, insertion and exit on the well axis, eye distance, cover, wrist, reach, shoulder, body, gun gap; per built set (with `WORK/rreload/roundtrip.txt`): key count, SIMD, path against the source glb |
| `roundtrip` | only with `--only roundtrip`: built sets exported back to glb against their source glb (one set of each kind; `--roundtrip-all`) |

Known misses of the shipped clips are kept as baselines, named in the `checks` notes of `weapons.json` and in
`authoring/magtrack/baseline.json`: a new clip must not be worse. They are: Burya misses the magazine by 2.5 cm in
one uppercut clip (rule 2 cm); double tap brings some SMGs within 0.5 cm of the eye; two pair clips move in the
hidden hold; four magazine flights leave more than 25 deg off the push; the import stores the per-hand reload clips
(139 keys) and the lowered clips (121, 43, 16 keys) with one frame less, resampled (96 and 112 keys come back exact).

## Add a gun (to a type the mod already handles)

1. `weapons.json`: add the gun (`id`, `name`, `type`, `item_type`, `vars`, `audio`, `arm_set`, `mesh`, `length`,
   `status: test`). Model variable: the gun's anim set entries in the player entity. A gun without its own variable
   gets an empty `vars` and nothing below.
2. Export its meshes and weapon anims (see Game files) into a `WMESH` / `WANIM` folder. Check:
   `python authoring/lowered/guns.py` prints its extents; list extra parts in `parts` / `mesh_parts`.
3. `build.sh extract` (its arm set, for the sound table).
4. Lowered stance. `GA_TEST=1 python autotune.py --guns <id>` (in `authoring/lowered`). Rule: the gun's top edge at
   -0.78 of the half view height, at least 25 cm from the eye, wrist at most 20 deg. Enter the result as
   `"lowered": {"family": "v1", "pose": "v1_<name>", "tune": [0, dy, dz]}`. A long gun (muzzle reach over about
   0.9 m in v1, or no passing tune) gets `{"family": "v2", "pose": "v2"}`. Then
   `GA_TEST=1 python makeclips.py --out <LOWCLIPS_TEST> --poses v1_<name>` and
   `GA_TEST=1 python checks.py --guns <id>`; preview `python render.py --pair <id> carnage pma <prefix> "<title>"`.
   Look at: the gun low at the screen edge, not across the centre; no wrist break in the outside view; the draw
   (`equip_safe`) does not swing past the camera.
4a. Raised pose, only if the gun fills the view in the game's pistol pose. `GA_TEST=1 python rautotune.py --guns <id>`
   (in `authoring/raised`) prints its screen cover in the game pose and says whether it is over `checks.raised.limit_pct`
   (8.5 %; the Ajax has 8.0, the Masamune 15.0). To give it a pose: `--family C` prints s per body; enter
   `"raised": {"family": "C", "pose": "C_<name>", "s": {"pma": s, "pwa": s}}`, then
   `GA_TEST=1 python rmakeclips.py --poses C_<name>` (writes into `RAISEDCLIPS`), `python rpreview.py sheet <id>`,
   `build.sh reload raised topmag xl --with-test`, `python checks.py --guns <id>`. A gun that is over the limit but
   looks fine in game gets `"raised": {"family": "none", "note": ...}`. Look at in game: raised idle, aim, sprint,
   the reload's last frame (no jump), draw, the Shingen reload with the gun as partner.
5. Partner of the Shingen, short gun. `python partner.py measure <id>` (in `authoring/topmag`) prints the `partner`
   row (flip, doubletap, uppercut category). No new clips unless it prints "NEW CATEGORY?": then add the category to
   `data/categories.json` and run `python gen_smg.py --cats <name> --out <dir>`.
6. Partner of the Shingen, long gun. Either borrow (`"long_partner": "<id of a gun of similar length>"`) or make its
   own: `"long_partner": "<own id>"`, `python gen_long.py --guns <id> --out <dir>`. Guns that share a model variable
   play one clip: `--share <id>:<other id>` fits it for both. List the gun's mesh parts in `parts` first (receiver,
   stock); a rifle's magazine is added by the tools.
7. New arm clips only (5 or 6), in this order:
   `python checks.py <dir>/clips --guns <id>` (topmag: contact, hands gap, wrist, hidden window, eye 20 cm for long
   guns, face cover); where it fails, `python fit_turn.py <dir> <body>/<clip>,... --out <dir2>` (same `--share`);
   `python mag_contacts.py --clips <dir>/clips` (in `authoring/magtrack`; the gun alone against the seated magazine,
   while checks.py counts the hand too): contact frame must be the hit frame f25
   (K - 0.3 to K + 0.05), else `python retime.py <dir>/clips <dir2>`;
   add the clip names to the pick's `clips` list in `authoring/magtrack/spec.json` (`pose_clips` keeps the track as
   it was made); the right lupper clips need the shipped re-aim (`reaim_pick.py long_right_lupper
   delta_long_right_lupper.json`);
   `python checks.py --clips <dir>/clips <set>_<pick>` (magtrack): if the pick's flight fails with the new clip,
   `python mag_flight.py <set>_<pick> --clips <dir>/clips` searches a flight for all its clips (paste the entry into
   the spec); if none passes, re-aim the pick (`reaim/feas.py`, `opt.py`, `reaim_pick.py`);
   copy the clips into `CLIPS_PRE_ENDPOSE`, then `python batch.py --only <clip name part> --dst <dir3>` (in
   `authoring/endpose`) and copy the result into `CLIPS`. A gun with a raised pose plays the copies of
   `rmakeclips.py --only topmag`; the topmag check measures those.
   Preview each: `python render.py mp4 <clip.glb> smack <name> --left shingen --right <id>` (in `authoring/author`,
   `--reload right` and swapped guns for the right-hand clips, `--body pwa`, `--cam game`). Look at: the contact is
   readable in first person; nothing crosses the face; the magazine leaves on the contact frame; the guns are out of
   view while the magazine goes in; wrists and elbows in the outside view; first and last frame equal.
8. `build.sh all --with-test`, `build.sh check --with-test --guns <id>`. All checks pass, or the miss is explained.
9. In game (test output from `WORK/test-out`): both hands reload; with a Shingen in each hand in turn the hit lands
   and the magazine flies off; no arm snap when the reload ends; lowered stance in a safe zone, fire and return;
   first-person camera steady during the reload (a compressed buffer shakes it); male and female V.
10. Own reload (rifles and other magazine guns): classify the gun from its own reload (`authoring/reload/classify.py`,
    check against `sideview.py`). A gun of an existing category gets `reload` (`category`, `picks`, `weight`, `slots`,
    `magazine`) in `weapons.json`; a new category needs draft rounds (picked by the owner) and a generator in
    `prod.PICKS`. `GA_TEST=1 python prod.py build --guns <id>`, then `prod.py layout` and copy the gun's rows of
    `layout.json` into `reload.layout`, then `build.sh rreload --with-test` (round trip included),
    `build.sh check --only rreload --with-test`. The clips start and end in the raised idle: rebuild them after a
    raised tune changes.
11. Set `status: release`, `build.sh all`, `build.sh check`, `build.sh verify` (only the expected sets differ).

## Add a weapon type

1. `weapons.json` `types`: `name`, `plural`, `group`, `status: test`, `needs_arms`, `arm_clips`, `item_types` (the
   game's item type, `base_var` = the `w_base_*` variable its guns fall back to, fallback audio sets).
2. A `generic` gun entry per item type (stands for the base variable: modded guns of the type), with `length`,
   `lowered` and, for a long type, `long_partner`.
3. Every gun of the type: "Add a gun" above. Sort the guns by length first (`authoring/lowered/guns.py` extents):
   it decides v1 or v2 and short or long partner.
4. `arm_clips: true`: the per-hand reload sets need nothing new (`genxl.py` adds the type's variables). If the type's
   guns sit differently in the hand than a pistol, look at the reload in game before anything else.
   `arm_clips: false` (pistol-like types the game dual-wields itself): `game_dual` per gun (`own_sets`,
   `borrow_sets`).
5. Scripts: `build.sh guns sounds` regenerate the tables; the gate (`IsGripWeaponType`) and the settings group are
   hand edits in `r6/scripts`.
6. `build.sh all --with-test`, `build.sh check --with-test`, in game as above, then `status: release`.

Manual by nature: picking a new reload motion (a new pick is a spec written by hand with `author/author.py` and
judged in the preview and in game), the family poses, the flight when the search finds none, and all in-game looks.

## Lessons

| Failure seen | Check that catches it |
|---|---|
| Arms snap when the reload ends: the clip did not end in the idle pose (clavicles 9 deg off) | `clips`: end pose = idle pose, per hand |
| A gun with its own raised pose jumps for one frame when its reload ends (the shared reload clip ends in the pistol pose) | `raised`: reload clips first and last frame = raised idle |
| A clip whose tracks are all constant (a static pose) has no length: WolvenKit cannot export the set afterwards | `roundtrip`; `raised/rpose.write_full` keeps every key |
| End-pose fix changed the reload itself | `clips`: frames before the seated frame unchanged; hands and guns moved |
| A long gun swings across the face (Carnage with flip and double tap) | `topmag`: eye distance, face cover; long guns get their own picks |
| Wrists bent too far (v2 lowered 55 deg; axe, hang) | `lowered`: wrist bend; `topmag`: wrist |
| Hands apart from the gun, or the two hands through each other | `topmag`: hands on the guns, hands gap |
| Guns too close to the eye (Shingen magazine at the camera in the pistol pose) | `lowered`: eye distance; `topmag`: eye distance |
| Compressed anim buffer breaks the first-person camera | `sets`: SIMD buffers (`animimport.ps1` imports with SIMD) |
| Some clip lengths come back resampled (114 and 116 keys: one less, 7 mm off; 96 and 112 are exact) | `sets`: frame count and duration; `roundtrip`. Author new clips with 96 or 112 keys. |
| A constant quaternion with w < 0 is mis-encoded by the import | `topmag`: constant w < 0 tracks; `roundtrip`. `lowered/lpose.py` writes w >= 0. |
| Magazine moves before the hit, or the hit lands off the hit frame | `magtrack`: still, first move, contact |
| Magazine flies toward the eye, back up, or reappears | `magtrack`: flight gates |
| The striking gun misses the magazine with another partner gun | `topmag`: contact miss; partner categories |
| The elbow flips to the other side in one frame where the hand dives to the belt or hip (IK reference along the shoulder-hand line); the import broke the middle key of that jump (Masamune, 4 to 11 cm) | `author.py` `pole_tilt` (`prod.POLE_TILT`); `rreload` round trip |
| Rotation keys in the `empty_reload` slots came back wrong unless w >= 0 | `rarmset.py` writes w >= 0 there; `rreload` round trip |
| Only some key counts survive the import (it derives the frame count from the float32 duration) | `rarmset.good_keys` pads clips; `sets`, round trip |
| A detached magazine glided and slowed in the air (looked like an insertion played backwards) | `rreload`: no hanging magazine, release velocity |

## Files

| File | What it does |
|---|---|
| `build.sh`, `build.py`, `gen` | The build, `verify` and `check`. |
| `weapons.json`, `manifest.py` | The manifest and its reader. |
| `flick.py` | The per-hand reload clips from a Lexington dual-wield set: the pistol's tip-up, a drop out of view, a hold, the pistol's empty-reload rise. The `_02` variants drop straight down, for shell-by-shell shotguns. |
| `glb.py`, `fk.py` | Minimal glb reader/writer and forward kinematics. |
| `animimport.ps1` | Imports a glb into an `.anims` file through WolvenKit's library (the CLI cannot import animations). |
| `topmagsets.py`, `topmag.py`, `animrename.py` | The top-magazine sets: which clips go into which set and their archive.xl entries; one set (clips under the game's reload clip names in a copy of the Lexington right-hand set, other clips renamed away). |
| `magtrack.py`, `magapp.py` | The magazine sets from the flight spec; fallback that edits the weapon `.app` instead of using archive.xl. |
| `lowsets.py`, `lowset.py`, `genlowxl.py` | The lowered stance sets and `GorillaAkimboLowered.archive.xl`. |
| `raisedsets.py`, `raisedset.py` | The raised pose sets and per-gun reload sets: which clips go into which set and their archive.xl entries; one raised pose set (pose clips under their names in a copy of the game's dual-wield base set). `flick.py --rest --hands` makes the per-gun reload set. |
| `genxl.py` | `GorillaAkimbo.archive.xl`. |
| `rreload.py`, `rarmset.py`, `rmagset.py`, `genrxl.py` | The rifle reload step: arm sets (pick clips in a copy of the gun's per-hand reload set, key padding, rotation signs), magazine sets, `GorillaAkimboRifles.archive.xl`, round trip. |
| `gensounds.py`, `genguns.py` | `GorillaAkimboSounds.reds`, `GorillaAkimboGuns.reds`. |
| `sounds.py`, `inktree.py` | Inspection helpers. |
| `authoring/` | Above. |
