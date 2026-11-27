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
| `GorillaAkimboLowered.archive` (48) | Lowered (safe) stance per hand and gun: v1 low ready, v1d deep low ready (over 90 cm). | Authored clips (`paths.low_clips`), packed by `build.sh lowered`. |
| The `.archive.xl` files | Which set plays for which model variables. | `build.sh xl`; the rifles' one by `build.sh rreload` |
| `GorillaAkimboSounds.reds`, `GorillaAkimboGuns.reds` | Reload sound times; types, long partners, top-magazine timing. | `build.sh sounds`, `guns` |

## Build

```
tools/anim/build.sh extract          # once: game files from the game's archives (about 2 minutes)
tools/anim/build.sh all              # build everything into the checkout (about 25 minutes)
tools/anim/build.sh verify           # compare with git HEAD of the reference repo (REF), or --ref <folder>: that folder's files as they are on disk
tools/anim/build.sh check            # numeric checks of the shipped clips and built sets (about 10 minutes)
tools/anim/build.sh check --only draft   # the owner's reload rules (R1 to R6, R2b, R4a, R7, R8; physics rules for free parts, finger torque of in-hand turns) on every reload clip, shipped and parked (no WolvenKit, about 2 minutes)
python tools/anim/authoring/checks/draftcheck.py --family smg_front <clip.json or folder>   # the same rules on drafts outside the manifest; writes <clip>_draft.json
tools/anim/build.sh all --with-test  # also the "test" content of weapons.json, into WORK/test-out only
tools/anim/build.sh reload rreload --guns <id>   # only the sets one gun plays (partial archives in WORK/guns-out, never the checkout)
tools/anim/build.sh verify --guns <id>           # that gun's packed files in the rreload archives against the reference
tools/anim/ga.sh produce <gun> [--out <dir>] [--dry-run] [--write-layout]   # clips, layout, its build steps and its checks for one gun; --write-layout copies a differing layout into weapons.json (see below)
```

`all` includes `rreload` (its round trip is about 10 to 15 minutes of the total). It runs after `reload` (it copies the per-hand reload sets
that step built, the raised-pose ones included) and ends with the round trip: every set exported back and compared
with its source glb (`WORK/rreload/roundtrip.txt`).

`--guns id,id` works on `reload`, `rreload` and `verify` only: `reload` builds just the per-hand sets those guns play, `rreload` just their own sets.
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
| `REF` | repo whose git HEAD `verify` compares with (not used with `--ref <folder>`) |
| `ANIMWORK` | authoring data folder (specs, drafts, renders, every clip generation; never deleted) |
| `AUTHORING` | folder for new authoring output |
| `BLENDER`, `FFMPEG` | blender.exe, ffmpeg.exe |
| `WMESH`, `WANIM`, `VMESH` | weapon mesh glbs, weapon anim glbs, V's arm mesh glbs (WolvenKit exports) |
| `JOBS` | parallel jobs (4) |

`verify` reads the reference with `git cat-file blob HEAD:<path>` (no checkout); with `--ref <folder>` it reads `<folder>/<path>` from the
working tree and git is not consulted. It compares the two `.archive.xl` files
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

- `paths`: above. `output`: a note, the entry is only written by the build. `build.sh check --only manifest` fails on any input component under gg-work or a scratchpad / Temp folder; there are no exceptions.
- `game_files`: player entities per body, the reload source sets, the lowered base set, the magazine entity.
- `set_names`: name of the per-hand reload sets, and their name before the rename.
- `reload_clip`: layout of the per-hand reload clips in frames (`flick.py`) and seconds (the script).
- `checks`: limits of `build.sh check`. "baseline" in a note: the worst value of the shipped clips, kept as the limit.
- `lowered_families`: v1, v2 and v1d (deep low ready) lowered poses (template, right-hand offset and angles, clavicle).
  Pose rule (owner, measures only; `build.sh check --only pose`): the length gives the preferred lowered family (v1d when the assembled gun is longer than
  `checks.lowered.v1d_over_cm` (90), else v1); it applies only if a tune passes every lowered check (`lowered/fit.py`), else the other family; and family C raised when its idle cover in the game pose is over
  `checks.raised.limit_pct`, else the game pose. v2 has no user.
- `raised_families`: raised poses for guns too bulky for the game's pistol pose. A family is a direction for the idle
  clips and one for the aim clip (metres per unit s, right hand), a roll about the barrel and a screen cover target;
  the muzzle direction never changes.
- `types`: per weapon type: `name`, `plural`, `group`, `status`, `needs_arms`, `arm_clips` (uses the mod's arm clips
  and lowered stance), `item_types` with `base_var`, `fallback_audio`, `fallback_audio_shells`.
- `guns`: `id`, `name`, `type`, `item_type`, `vars` (model variables; the left hand's are these plus `_left`),
  `audio`, `arm_set` (male two-handed arm set, for the sound table), `mesh` (mesh stem), `parts` (mesh parts drawn in
  previews and used by the top-magazine checks; the lowered and raised checks measure these plus the receiver and fixed stock),
  `mesh_parts` (further parts added to that body in the checks), `weapon_anim` (stem of its weapon anim set if not the mesh stem), `length` (long or short), `long_partner`
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
| `manifest` | no `paths` entry the build reads has a component under `C:/Modding/gg-work` or in a scratchpad / Temp folder; an entry with `output` (a note why) is only written and skipped; the defaults of the file are read, not the environment (no WolvenKit, about 1 second) |
| `rules` | the rule manifest `rules.json` (the standard, `STANDARD.md`): ids unique, every field filled, every gate rule resolves to a check that emits it and a limit in `weapons.json`, no baselines, every stance plays a variant that passes R9 (no WolvenKit, under 1 second) |
| `draft` | the owner's reload rules R1 to R14 on every reload clip, shipped and parked, and the stance variants (`authoring/checks/draftcheck.py`, `stdrules.py`; limits in `checks.draft`; about 5 minutes; also run by `ga produce` and `ga drafts`) |
| `lowvar` | the stance variants: whole gun and hand in the discard window (R9 on the idle margin), wrist from the bind pose, generator gate rules |
| `clips` | last frame = `idlepose_shoulder`, per hand (0.01 cm, 0.01 deg); frames before the seated frame equal the clip before the fix; hands and guns moved by the fix; one clip of 96 frames |
| `sets` | every shipped clip of every built set is a SIMD buffer, has the frame count of its glb and lasts (frames - 1) / 30 s |
| `pose` | the pose rule: every gun's lowered family (v1d over `checks.lowered.v1d_over_cm`, else v1) and raised family (C over `checks.raised.limit_pct`, else none) equals the rule (a gun in its other family must have no passing tune in the preferred one); a gun that shares another's variable follows it; no clips needed |
| `lowered` | seam and clip ends against the idle; eye distance in the lowered idle (25 cm); nearer than the raised pose; gun gap; wrist bend |
| `raised` | per raised pose: screen cover at the family target, eye distance, reach, wrist, gun gap, muzzle direction and hand on the grip against the game pose; pose clips start and end in the raised idle; the gun's reload clips, equip, unequip, melee and the top-magazine partner clips start and end there; everything else equals the source clip |
| `topmag` | contact miss and depth at the hit frame, hands gap, wrist, guns out of view in the hidden window, eye distance, face cover, hands on the guns, constant w < 0 rotation tracks |
| `magtrack` | magazine still before the hit, scale, flight gates (exit, eye, rise, acceleration, reversal, reappearance, screen, size), insertion, empty variants, contact frame of the arm clips |
| `rreload` | rifle reload clips (`rgate.py`): start and end against the gun's raised idle, hidden window (gun, hand, forearm, magazines off screen in first person, both bodies), no hanging magazine, release velocity, insertion and exit on the well axis, eye distance, cover, wrist, reach, shoulder, body, gun gap; per built set (with `WORK/rreload/roundtrip.txt`): key count, SIMD, path against the source glb |
| `roundtrip` | only with `--only roundtrip`: built sets exported back to glb against their source glb (one set of each kind; `--roundtrip-all`) |

The standard is `rules.json` (table in `STANDARD.md`, made by `python authoring/checks/rules.py --markdown`). Every rule has an id (reload clip rules R1 to R17, poses P, stance variants V, transitions T, generator gates G, build B, media M, process W), its source, population, limit, scope, stance (inactive = lowered, game Safe; active = raised) and how it is enforced: `gate` (a check item that runs in `build.sh check`, `ga produce` and `ga drafts`), `owner-eye` or `not-enforceable` with the reason. `draftcheck.py` raises an error for a check item that is not registered in `rules.json`, and the area `rules` fails a gate rule whose item or limit does not exist. Limits stay in `weapons.json` `checks` (`limit_ref`). Limits measured on the Warden mesh (R7, R11, R14) are marked Warden-only and are not applied to other guns.

Known misses of the shipped clips are kept as baselines, named in the `checks` notes of `weapons.json` and in
`authoring/magtrack/baseline.json`: a new clip must not be worse. They are: Burya misses the magazine by 2.5 cm in
one uppercut clip (rule 2 cm); double tap brings some SMGs within 0.5 cm of the eye; two pair clips move in the
hidden hold; four magazine flights leave more than 25 deg off the push; the import stores the per-hand reload clips
(139 keys) and the lowered clips (121, 43, 16 keys) with one frame less, resampled (96 and 112 keys come back exact).

## Regenerate the shipped clips (`authoring/checks/regen.py`)

Checks that a tool tree still makes the shipped reload clips. `regen.py list` prints the acceptance set from
`weapons.json`: every `reload.slots` pick, per body and side, reload and empty reload, plus the `reload.fallback`
clips (FB, FBloop); guns with `reload.parked` are left out unless `--include-parked`.

`regen.py run <tree>/anim/authoring <family> --out <dir> [--guns ..] [--picks ..] [--sides ..] [--bodies ..] [--clips ..] [--limit n] [--jobs n]`
runs the tree's own generator for the family (`grip`, `bullpup`, `top`, `smg_front`, `tube`, `break`, `front`,
`masamune`, `hercules`, `fallback`) into `<dir>/clips` or `<dir>/fallback` and compares each glb with the shipped one
(`cmpclips.py`) and each `_track.json`. The report (`<dir>/report_<family>.md`, or `--report`) gives clip count,
largest position (cm) and rotation (deg) difference, byte-identical count and the failing clips. Exit code 0 pass,
1 a clip differs, 2 a shipped file changed, 3 refused to start.
The families of one `--out` share its `rest` folder and `fallback` reads the clips and rest glbs of the others: run them one after the other, `fallback`
last. A run marks `<out>/.regen_running/<family>` and a second run in the same `--out` exits 3 at once (no waiting); a marker left by a killed run is
removed by hand. `fallback.py` takes `--set smg|rifle` or `--guns` (it no longer picks the set from the output folder name).

Set `WORK` and `AUTHORING` to scratch folders first. The tree's `renv.py` must write under `--out` (`ROUND_OUT`);
`prod.py` takes `--out`. The shipped clip folders are only read: size, mtime and SHA-256 of the accepted files are
checked before and after the run. `fallback.py` needs the seated magazine track of the gun's reload clip and the
`ref/` geometry files: both are copied from the shipped folders and named in the report.

## One command per stage (`ga.sh`)

`ga.sh produce <gun> [--out <dir>] [--dry-run] [--jobs n] [--write-layout]`: from the gun's `reload` entry in `weapons.json` (picks, family, take, fallback) it makes
the gun's production clips with the family's generator (`regen.py`'s command table), the quick-drop fallback clips if the entry has them, runs the
family's layout and compares the gun's entry with `reload.layout`, then `build.py reload rreload --guns <gun>` (none for a parked gun), then
`build.sh check --guns <gun> --only manifest,draft` (plus `parts` for a shell-fed gun, `rreload` for a rifle). `--out <dir>` makes the clips in
`<dir>/clips` and `<dir>/fallback` and points the build and the check there. Without it the clips are made in `WORK/produce_<gun>/stage-<time>`, the build
and the check read them there, and when every step passed and the layout equals the manifest, each shipped clip of the gun that differs moves to
`<folder>.prev-<YYYYMMDD>` (`clips`, `fallback`) and is replaced; equal clips stay, nothing is deleted, the moved files are printed.
`--dry-run` prints every step with command, inputs and outputs and runs nothing. `--no-build` skips the WolvenKit archive build.
Lowered-stance variants (a gun with a `lowered` entry and a reload entry; step `lowered variants`, `authoring/reload/lowprod.py`): the reload clips that start and end in the gun's lowered idle,
keep the shipped motion, show the whole gun only around the magazine discard and have the insert off screen. They go to `<root>/lowered/clips` (with `solve/`, `bs_<pick>/`, `layout.json`,
`magsets/`, `report.json`); the game plays them in the lowered stance and the shipped clips in the raised stance (`reload.lowered_variant`: wrapper, priority, clips path key, layout;
the xl entries, the script tables and the magazine sets are generated from it). Rules, stated in the `lowprod.py` header and `checks.lowered_variant`:
per pick the generator's `STOP_DRIVE` table gives the kind (stop: the arm-driven stop of the discard moves; hold: the in-hand hold moves) and the arrival; the offset is solved by `lift.py`
from the shipped clips (R9 target = the shipped idle's own worst gun vertex margin, game camera, both bodies and hands; from the arrival with the highest stop, else from the release with the smallest move);
the post-seat gesture scale `s` is bisected on the reach and shoulder limits; the layout is the latest `hide_start` and earliest `hide_end` over bodies and hands.
The same solved offsets also make raised-stance variants (`<root>/raised/clips`, no lowered overlay, start and end in the raised idle; `reload.raised_variant`): the discard must be in view in every stance, so a raised variant replaces the shipped clip. The `lowvar` check area runs R9, the wrist rule and the gate fails on every clip of every stance.
A gun whose generator has no hook (only `top3` has one) is not made: the step prints the reason and `ga produce` ends with "lowered variants not made".
`lowprod.py measure <gun>` gives R9 on its shipped clips. `--write-layout` also writes `reload.lowered_variant.layout`.
`--write-layout` writes the layout the generator computed into the gun's `reload.layout` and `reload.fallback.layout` of `weapons.json` where it differs (the gun's `reload` line only; keys the manifest already has; tube shells go to `loads` and `late_loads` as the manifest splits them), then the checks run on the new values.

`ga.sh gun add <id> [--from <seed.json>] [--out <dir>] [--dry-run] [--apply] [--ack step,step|all] [--render]`: checks that the game files of steps 2 and 3 are there, measures steps 4, 4a and 5, and proposes the weight, category and magazine of step 10, with the existing tools (`guns.py`, `rautotune.py`, `weight.py`, `classify.py`, `autotune.py`, `rautotune.py --family C`, `partner.py measure`), written to `--out` (`<id>.proposed.json`, `<id>.diff.md`, `steps.md`, sheets). The hand-entered fields (id, name, type, item_type, vars, audio, arm_set, mesh, parts, length) come from `--from` or, for a gun already in `weapons.json`, from its entry with every derived field stripped (a reproduction). It stops with a sheet after each step that needs the owner's eye (weight, classify, lowered, raised, partner; exit 10) until it is named in `--ack`. A missing game file stops it (exit 3); it never starts WolvenKit. Pose rule: the assembled length gives the preferred lowered family (v1d over `checks.lowered.v1d_over_cm`, else v1), taken only if a tune passes every lowered check, else the other family (`autotune.py` does this, minutes per gun) and a C raised pose exists only over `checks.raised.limit_pct`; a gun that does not follow it is refused (exit 2) with the field named. `weapons.json` changes only with `--apply`, for a new id. Not covered: reload picks, slots and layout (`ga drafts`, `ga pick`, `ga produce`), the long partner, the Borg partner row.

`ga.sh drafts <family> --round N [--out <dir>] [--take A|B] [--only id,id] [--jobs n] [--no-render] [--no-generate] [--dry-run] [--compare <clips folder> [--compare-root <root>]] [--scores <file>] [--rest-archive <dir>]`:
one draft round into `<out>/<family>/round<N>` (out defaults to `paths.anim_work`). `authoring/draft/rounds.json` names the round's generator, its draft list,
its rest glbs and its review tool (`sf1.py` to `sf4.py`, `grip1.py`, `grip2.py`, `bull1.py` to `bull3.py`, `top1.py` to `top3.py`, `tube1.py`, `tube2.py`, `break1.py`, `break2.py`, `front3.py`, `masa3.py`, `herc3.py` (rifle round 3; no review tool is wired for it: `rrender3.py frames <spec.json>` renders one draft's frames); `make.py` (rifle round 1, `<out>/<category>/<id>/<id>.glb`) and `round2.py` (round 2, `<out>/round2/<pick>/<take>.glb`, split per family) run through the `spec` layout of `rounds.json`, which reads id, take and body from each draft's spec; those rounds were authored on the first rest poses, so `--rest-archive <dir>` (or `rest_archive` in the entry) copies the archived `rest_*.glb` instead of making them; `unwired` is empty;
`bull1.py` and `top1.py` run on `r1lib_round1.py`, the round 1 engine with its own speed rules, beside the shared `r1lib.py`; a round with an `archive` path is an archived round); the generator runs unchanged. Order: the R4 budget of every take must exist in `checks.draft.r4_budget`
(else it stops and names the key) -> `authoring/draft/history.json` is searched (never a refusal: the rejected drafts were badly executed, not banned techniques) and a draft whose name matches an old rejected or picked idea prints the old draft id and its archive path, and the pair is listed in `DRAFTS.md` and `drafts.json` (`history`) so the old draft can be shown next to the new one (the `review.labels` mechanism renders a second clip only where a review tool has one, tube round 2 `O`; no new renderer) -> a
warning when the round is not about 10 drafts -> generator -> `draft` checks on every draft (`<clip>_draft.json`, R1 to R6 plus R2b, R4a, R7, R8 and R10; R8 bounds the gun path and the 90th percentile gun speed (whole clip and release phase) from below, per family and take (`checks.draft.r8_min`); R7 gates the net finger torque of in-hand turn frames only (checks.draft.finger_torque_nm; `r3lib` stretches a spin that needs more and puts the reaction into the arm); R3 and R4a are physics gates with the measured noise floor `checks.draft.phys_floor`: a detached magazine and every shell outside contact move at g, a fresh magazine with no contact is still; loading and ejection near the hands are not judged; R1 reports the release impulse and carrier-energy bound, not gated; R2b on a pump family (`checks.draft.r2b_pump_families`) without a pump track or closing run fails as "not measurable"; exit ratio and mechanism are reported, not gated) -> frame sheets, contact sheet, grid MP4 and the review
page (the page reads `<round folder>/scores.json`, the reviewer's scores; `--scores` copies one in, a new round without one gets an unscored file, every score 0, flagged `unscored`). `--compare` lists byte differences against an earlier output of the round; `--no-generate` reuses the drafts already in the round folder (checks, compare, review only).
`ga.sh pick <family> <id>[,id] --round N [--replace] [--allow-fail] [--dry-run]` records the owner's picks in `weapons.json` (`reload.picks` and `reload.slots` of every gun of
the family, at most 3) and in `<round folder>/PICKS.md`; a picked draft must pass the draft checks.

## Homelab build container (`GA_ROOT`, `plab/lab.sh`)

The authoring tools (no WolvenKit, no game) also run on Linux. `GA_ROOT` replaces the `C:/Modding` prefix of every path default (`weapons.json` paths, legacy script constants, `src` paths inside shipped clip specs; `manifest.mp`); unset, paths and outputs are unchanged. The lab is the unprivileged LXC `gabuild` (CT 110 on the homelab host, no network interface; Python 3.12.4, numpy 2.2.1, Pillow 11.1.0, scipy 1.15.1 installed from wheels carried in through the bind mount `/rpool/data/gabuild` = `/srv/ga`; no Blender). The runner scripts live in `C:/Modding/gg-work/migration/plab` (outside the repo).

```
plab/put.sh <path under C:/Modding> ...        # copy inputs to /srv/ga/root/<same path>, SHA-256 lists compared on both sides
plab/lab.sh [--job name] <ga args>             # e.g. produce warden | drafts top --from-vanilla --only SV13,SV14 --no-render
plab/lab.sh --job J py:authoring/reload/lowprod.py raised warden --root /srv/ga/out/J   # any other tool script
python plab/cmp_approved.py vanilla|warden <out folder>   # compare with approved.json
```

`lab.sh` sends the committed branch (`git archive HEAD tools/anim`), runs `ga.py` in the container with `WORK`, `AUTHORING` and `--out` under `/srv/ga` (`produce` gets `--no-build`), pulls `/srv/ga/out/<job>` to `plab/out/<job>` and compares SHA-256 lists. `plab/sitecustomize.py` (lab only) makes text writes use CRLF as on Windows.

Proof (2026-11-25), `drafts top --from-vanilla --only SV13,SV14` and `produce warden` against `approved.json`: with the CRLF shim all text, gate and track files are equal; every glb differs in a few float32 values (at most 2.7e-16, values that should be 0). The solver chose the same branches and offsets as on this PC. The likely cause is that the Windows C runtime and glibc round `sin`, `cos`, `exp`, `acos` differently on 1 to 7 percent of inputs; BLAS kernels also differ for large products. Lab output is not trusted for shipped clips: use the lab for drafts and trial runs, make shipped clips on this PC.

## Add a gun (to a type the mod already handles)

1. By hand: the seed fields of the gun as one json object (`id`, `name`, `type`, `item_type`, `vars`, `audio`, `length`, and for a type with arm clips
   `arm_set`, `mesh`; also `parts`, `mesh_parts`, `weapon_anim`, `note`, and `status: test` while it is new). Model variable: the gun's anim set entries in the player entity. A gun
   without its own variable gets an empty `vars` and nothing below. Export its meshes and weapon anims (see Game files) into a `WMESH` / `WANIM`
   folder and run `build.sh extract` (its arm set, for the sound table).
2. `ga.sh gun add <id> --from <seed.json> --out <dir>`: extents, size, weight, reload category, lowered tune (its own v1 or v1d pose, by length), raised pose
   (its own C pose over the cover limit) and Shingen partner row, with the tools of `authoring/lowered`, `raised`, `reload`, `topmag`. It writes
   `<id>.proposed.json`, `<id>.diff.md`, `steps.md` and sheets, and stops (exit 10) after each step that needs your eye: look at the sheet,
   then rerun with `--ack <step>` (or `all`). A missing game file stops it (exit 3). A gun that does not follow the pose rule (family by length,
   C over `checks.raised.limit_pct`) is refused (exit 2) with the field named. `--apply` adds the entry to `weapons.json` (new
   ids only).
3. Reload clips. For a gun of an existing category the entry from step 2 already has `reload` (`category`, `picks`, `weight`, `slots`, `magazine`).
   To choose motions: `ga.sh drafts <family> --round N` makes about 10 drafts with the draft checks, frame sheets, contact sheet and review
   page; you pick; `ga.sh pick <family> <id>[,id] --round N` records at most 3 in `reload.picks` and `reload.slots`. A new category needs a
   generator first (see "Add a weapon type").
4. `ga.sh produce <gun>`: clips, layout, the build steps of that gun and its checks. The first run reports that `reload.layout` is missing: copy
   the gun's rows from `<root>/clips/layout.json` (and `reload.fallback.layout` from `fallback/layout_fallback.json`) into `weapons.json` and run
   it again. Without `--out` it makes the clips in `WORK/produce_<gun>/stage-<time>` and, when everything passed, moves each shipped clip it
   replaces to `<folder>.prev-<YYYYMMDD>` and prints the moved files. With `--out <dir>` nothing shipped is touched. A gun that shares another
   gun's clips (`reload.shares`) is produced through that gun. The clips start and end in the raised idle: produce again after a raised tune changes.
5. Long partner of the Shingen (manual). Either borrow (`"long_partner": "<id of a gun of similar length>"`) or make its own:
   `"long_partner": "<own id>"`, `python gen_long.py --guns <id> --out <dir>`. Guns that share a model variable play one clip:
   `--share <id>:<other id>` fits it for both. List the gun's mesh parts in `parts` first (receiver, stock); a rifle's magazine is added by the
   tools. If `ga gun add` prints "NEW CATEGORY?" for the partner row: add the category to `data/categories.json` and run
   `python gen_smg.py --cats <name> --out <dir>`.
6. New Shingen partner arm clips only (step 5), in this order:
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
7. `build.sh all --with-test`, `build.sh check --with-test --guns <id>`. All checks pass, or the miss is explained.
8. In game (test output from `WORK/test-out`): both hands reload; with a Shingen in each hand in turn the hit lands
   and the magazine flies off; no arm snap when the reload ends; lowered stance in a safe zone, fire and return;
   first-person camera steady during the reload (a compressed buffer shakes it); male and female V.
9. Set `status: release`, `build.sh all`, `build.sh check`, `build.sh verify` (only the expected sets differ).

## Add a weapon type

1. `weapons.json` `types`: `name`, `plural`, `group`, `status: test`, `needs_arms`, `arm_clips`, `item_types` (the
   game's item type, `base_var` = the `w_base_*` variable its guns fall back to, fallback audio sets).
2. A `generic` gun entry per item type (stands for the base variable: modded guns of the type), with `length`,
   `lowered` and, for a long type, `long_partner`.
3. Every gun of the type: "Add a gun" above (`ga.sh gun add`, then `ga.sh drafts`, `ga.sh pick`, `ga.sh produce`). Sort the guns by length first
   (`authoring/lowered/guns.py` length): it decides v1 or v1d (over 90 cm) and short or long partner.
4. `arm_clips: true`: the per-hand reload sets need nothing new (`genxl.py` adds the type's variables). If the type's
   guns sit differently in the hand than a pistol, look at the reload in game before anything else.
   `arm_clips: false` (pistol-like types the game dual-wields itself): `game_dual` per gun (`own_sets`,
   `borrow_sets`).
5. A reload that no existing category fits needs its own category, by hand: a generator in `authoring/reload`, its command in `regen.py` (`command`)
   and its layout command in `ga.py` (`LAYOUT`), a round in `authoring/draft/rounds.json` and an R4 budget in `checks.draft.r4_budget`
   (`ga.sh drafts` stops and names the missing key).
6. Scripts, by hand: `build.sh guns sounds` regenerate the tables; the gate (`IsGripWeaponType`) and the settings group are
   edits in `r6/scripts`.
7. `build.sh all --with-test`, `build.sh check --with-test`, in game as above, then `status: release`.

Manual by nature: picking a new reload motion (judged in the review and in game), the family poses, the flight when the search finds none,
and all in-game looks.

## Vanilla reloads as the reference (`reload/vanillainv.py`, `vref.py`, `vtop.py`)

`vanillainv.py [--guns id,id]` measures every player reload clip of the arm sets of `weapons.json` (exported glbs under `GAMEFILES/gripsets`, `ga-reloads`, `ga-build`) and the Lexington dual-wield set:
frames, magazine events (out, seated, exit axis and speed), the left palm's distance to the gun body per frame, the left hand's actions (strip, insert, handle), the gun's path in the chest frame.
One-handed = the left palm never within 7 cm of the body, no action, and a dual-wield set (the left hand holds its own gun). Output `inventory.json` and `inventory.md`.
Result (2026-11-24): the Lexington dual-wield reloads are the only one-handed ones; every other set is two-handed, and their gun moves 5 to 23 cm (the left hand does the work).

Translation (`vtop.py`, rule in its docstring): time by the budget ratio (anchors out, seated, last), the gun's world increments on the idle, the strip kept if the path alone frees the magazine (well model) within 6 frames,
else the arm's inertia release (drive length from the clip's exit speed), the insert at the place a one-handed source reloaded at or on the belt rig, the rack by the part's measured direction.
`vtop.py solve <ids>` lengthens the travel (amplitude, drive) until the draft checks pass (R5 and R8 are floors); a geometry fail at amplitude 1 ends it.
`ga.sh drafts top --from-vanilla [--out dir] [--only ids]`: solve, lowered builds (`smgprod build vtop --lowered`), draft checks R1 to R10, R9 on the whole gun, game-camera review (`vreview.py`).
Shingen as the target is not wired: it has no reload entry, family, R4 budget or rest/layout support (its clips are used as sources for the Warden).

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
| `rpartset.py` | Gun part sets of the shell-fed shotguns (`reload.parts`): pump or barrels from the drafts' part frames, shells from `_objects.json`, on the gun's Barrel and shell components, keyed on the magazine wrapper; `check()` rebuilds every frame against the draft. |
| `gensounds.py`, `genguns.py` | `GorillaAkimboSounds.reds`, `GorillaAkimboGuns.reds`. |
| `sounds.py`, `inktree.py` | Inspection helpers. |
| `authoring/` | Above. |
