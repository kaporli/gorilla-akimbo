# Authoring an arm clip

One first-person arm clip moves both guns; the arms follow by IK. Write a spec, build the glb with `author.py`,
look at it with `render.py`, change the spec, repeat. Paths (Blender, ffmpeg, meshes, output) come from the `paths`
block of `tools/anim/weapons.json`. Run the commands from this folder.

## Files
- `author.py <spec.json> [--out clip.glb]`: builds the clip. Also a module: `setup(spec)`, `gun_pose(S, f)`, `solve(f)`,
  `build(spec, out)`.
- `aimsmack.py <spec.json>`: where the struck magazine is in world space at given frames, to aim a hit.
- `scene.py`: the Blender scene (arms, guns, magazines). Config keys are listed in its docstring.
- `render.py sheet | gif | mp4 | strip | compare`: runs `scene.py` and ffmpeg. Output in `<authoring_work>/author/prev`.
- `scene_bake.py`: the same scene saved as a playable `.blend` (config key `blend`).

## Spec
```json
{"body": "pma", "template": "reload", "clip": "smack", "frames": 96, "out": "my.glb",
 "keys": {"Left": [[0, [0,0,0], [0,0,0]], [25, [0.02,0.05,0.03], [10,0,0]], [95, [0,0,0], [0,0,0]]],
          "Right": [[0, [0,0,0], [0,0,0]], [95, [0,0,0], [0,0,0]]]},
 "shakes": {"Left": [{"type": "kick", "f": 25, "move": [0,0,0.02], "rot": [4,0,0], "attack": 0.8, "release": 5.5, "lag": 0.8}]}}
```
- `src` (a glb path) or `body` (pma, pwa): the rig. Without `src` it is the Lexington dual-wield set of the body.
  Frame 0 of `template` is the idle pose every offset is measured from.
- `keys.Left`, `keys.Right`: `[frame, [dx,dy,dz], [pitch,yaw,roll]]`, the gun's offset from idle. Interpolation is
  Catmull-Rom; a key equal to its neighbour gets a flat tangent.
- `shakes`: impacts added on top. `kick` is a recoil: fast attack, smooth return, no oscillation, peak 1.
- Other keys (`bumps`, `twist_share`, `shoulder`, `pole`, `swivel`, `elbow`, `reach`, bank angle, key tangents): see
  the docstring of `author.py`.

## Axes
- Metres, glTF axes: x = V's right, y = up, z = back toward the camera (forward is -z).
- Angles in degrees about the gun's own axes: pitch + = muzzle up, yaw + = muzzle turns left, roll + = top tilts left.
- pma idle: right gun origin (0.148, 1.492, -0.381), left gun origin (-0.149, 1.485, -0.381), eye (0, 1.693, -0.044).
- Gun axes are the axes of its mesh glb. To put a strike point S (gun axes) on a world target T at frame f, the gun
  origin must be T - R(gun rotation) * S. Check with `author.gun_pose` (as `aimsmack.py` does); aim for under 2 cm.

## Rules for a reload clip
- 96 frames at 30 fps. Frames 0 and 95 are the idle pose (all offsets zero), or the clip pops when the graph returns.
- The game plays the gun's own magazine animation in sync and it cannot be changed. For the Shingen: still until f15,
  slides out from f25, gone by f33, the new one comes from f44 and is seated by about f62. A hit that knocks it out
  lands on f25, pushing along the exit direction.
- Both guns are out of view (offset y about -0.5 or lower) while the new magazine goes in (f46 to f62).
- Motion: anticipation, a fast strike (2 to 4 frames), a clear contact, a recoil kick on the struck gun, follow-through.
  No frozen holds, no oscillating shake.

## Preview
```
python author.py my.json
python render.py sheet my.glb smack my 0,15,25,30,46,62,95 --left shingen --right saratoga
python render.py mp4 my.glb smack my --left shingen --right saratoga
python render.py strip my.glb smack my 0=idle 20=anticipation 25=contact 28=recoil 46=down 95=idle
```
`--left` / `--right` take a manifest gun id (draws all its `parts`) or a mesh stem (draws `<stem>__base1_01` only).
`--body pwa` for female V. `--reload right` when the right gun is the one reloading. `--cam game` for the in-game camera.

What to look at:
- First person row: is the contact visible and readable, does anything cross the camera, are the guns out of view
  while the magazine goes in.
- Outside row: elbows and wrists (no broken wrist, no arm through the body or the other gun), hands on the grips.
- The magazine (orange): it leaves the gun on the contact frame, not before.
- Frames 0 and 95 look the same.
- `render.py compare <name> <before.glb> <after.glb>`: the end of two versions and the idle pose after them; the last
  strip column must be black (no jump at the switch to idle).

## Meshes a gun needs
- `<mesh>__base1_01.glb` in one of the `weapon_meshes` folders, plus any other part listed in the gun's `parts`.
- For a magazine: `<mesh>__base1.anims.glb` (has the `mag_slot` joint; else `<mesh>__rcv1.anims.glb`) and
  `<mesh>__mag_std.anims.glb` in `weapon_anims`, and `<mesh>__mag_std_01.glb` in `weapon_meshes`. Without them the gun
  is drawn without a magazine.
- V's arms: `a0_000_<body>_base_hq__l.glb` and `__r.glb` in `arm_meshes`.
