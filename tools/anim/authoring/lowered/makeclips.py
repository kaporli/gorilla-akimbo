"""Writes the lowered stance clip glbs of the guns in weapons.json: <out>/<body>/lowered_<pose>.glb with
friendly_idlepose, safe_action, equip_safe and their _l copies (+ _spec.json and _ik.json per clip), and
<out>/poses.json {model variable: pose}. Poses come from each gun's lowered entry: family (v1, v2) and tune.

usage: makeclips.py [--out <dir>] [--poses p,p] [pma] [pwa]
  --out   default: <authoring work>/lowered/clips. The shipped clips are in paths.low_clips, test ones in
          paths.low_clips_test; write there only on purpose (existing files are replaced).
  GA_TEST=1 includes the guns with status "test".
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import poses, lauthor as A

argv = sys.argv[1:]
OUT = common.opt(argv, '--out') or common.work('lowered', 'clips')
only = common.opt(argv, '--poses')
plan = poses.production()
os.makedirs(OUT, exist_ok=True)
json.dump(common.manifest.poses(), open(OUT + '/poses.json', 'w'), indent=1)
for body in argv or common.BODIES:
    os.makedirs(f'{OUT}/{body}', exist_ok=True)
    for pose, (fam, tune) in plan.items():
        if only and pose not in only.split(','): continue
        s = poses.spec(fam, body, f'{OUT}/{body}/lowered_{pose}.glb', tune)
        json.dump(s, open(f'{OUT}/{body}/lowered_{pose}_spec.json', 'w'), indent=1)
        c, r = A.build(s)
        print(body, pose, json.dumps({k: {S: v[S]['max_wrist_deg'] for S in v} for k, v in r.items()}), flush=True)
