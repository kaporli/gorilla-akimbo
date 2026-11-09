"""The lowered (safe) stance anim sets: which clip glb goes into which set, and their archive.xl entries.

In public safe zones the dual-wield graph plays friendly_idlepose (the lowered idle), safe_action and equip_safe,
per hand (_l on the left). The game has them only in its pistol base set, so each SMG and shotgun hand gets a set of
its own here. Clips are authored outside the repo (anim-work/lowered), one glb per body and pose in
LOWCLIPS/<body>/lowered_<pose>.glb, holding the three clips and their _l copies; LOWCLIPS/poses.json maps each model
variable to its pose (v1 low ready for SMGs and short shotguns, v2 high port for long shotguns, some tuned per gun).

usage: lowsets.py <lowclips dir> sets  -> one line per set: <body> <side> <set name> <clip glb>
"""
import json, os, sys

BODIES = ('pma', 'pwa')
SIDES = ('right', 'left')
# Base variables some weapons set besides their model variable: a lower tier, so the model variable's set wins.
BASE_VARS = {'w_base_submachinegun', 'w_base_shotgun', 'w_base_shotgun_dual'}
# archive.xl priorities (a lower number wins). The sets hold only the three safe-stance clips, so they override the
# game's dual-wield base set (100) for those clips and nothing else.
PRIO = {'model': 61, 'base': 62}


def set_name(body, side, pose):
    return f'{body}_dual_wield_{side}_safe_{pose}'


def plan(lowclips):
    """[(body, side, set name, clip glb, [(vars, priority)])]"""
    poses = json.load(open(os.path.join(lowclips, 'poses.json'), encoding='utf-8'))
    out = []
    for body in BODIES:
        for side in SIDES:
            by_pose = {}
            for var, pose in poses.items():
                by_pose.setdefault(pose, []).append(var)
            for pose, vars_ in sorted(by_pose.items()):
                glb = f'{lowclips}/{body}/lowered_{pose}.glb'
                if not os.path.exists(glb):
                    continue
                entries = [(['dual_wield', v + ('_left' if side == 'left' else '')], PRIO['base' if v in BASE_VARS else 'model'])
                           for v in vars_]
                out.append((body, side, set_name(body, side, pose), glb, entries))
    return out


if __name__ == '__main__':
    for body, side, name, glb, _ in plan(sys.argv[1]):
        print(body, side, name, glb)
