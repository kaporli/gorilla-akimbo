"""The raised pose anim sets: which clip glb goes into which set, and their archive.xl entries.

A gun with a raised pose of its own (weapons.json "raised": a family and s per body; assault rifles too bulky for the
game's pistol pose) gets, per body and hand:
  <body>_dual_wield_<side>_raised_<pose>   the pose clips of the game's dual-wield base set (POSE_CLIPS) with the gun
                                           moved; the base set's other clips are renamed away
  <body>_dual_wield_<side>_reload_<pose>   its own per-hand reload set: flick.py from the raised idle, plus equip,
                                           unequip and melee moved the same way (HAND_CLIPS); replaces the shared set
                                           for the gun's variables
Clips are authored outside the repo (authoring/raised/rmakeclips.py) into RAISEDCLIPS/<body>/raised_<pose>.glb and
raised_<pose>_hands.glb. A pose without clips there is left out: the gun keeps the game pose and the shared set.

usage: raisedsets.py sets  -> one line per set: <body> <side> <kind> <set name> <clip glb>
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifest

SIDES = ('right', 'left')
# Pose clips the Ready and Equip states play from the base set (the lowered sets own friendly_idlepose, safe_action
# and equip_safe).
POSE_CLIPS = ('idlepose_shoulder', 'idlepose_ironsight', 'idlepose_sprint', 'idlepose_slide', 'idlepose_frenzy', 'sprint_start',
              'sprint_stop', 'sprint_to_slide', 'vault', 'equip_sprint', 'first_equip')
# Arm motion clips of the per-hand reload set besides the reload clips.
HAND_CLIPS = ('equip', 'unequip', 'melee')
# archive.xl priorities (a lower number wins): the raised pose sets sit with the lowered sets (61, base variables 62;
# no clip name in common), under the per-hand reload sets (64) and the game's base set (100). The gun's own reload
# set takes the shared set's place at 64.
PRIO = {'model': 61, 'base': 62, 'reload': 64}


def clips(body, pose):
    d = manifest.path('raised_clips')
    return f'{d}/{body}/raised_{pose}.glb', f'{d}/{body}/raised_{pose}_hands.glb'


def built(pose):
    """Whether the pose has its clips for every body."""
    return all(os.path.exists(p) for body in manifest.bodies() for p in clips(body, pose))


def poses():
    """{model variable: raised pose} of the poses with clips."""
    return {v: p for v, p in manifest.raised_poses().items() if built(p)}


def plan():
    """[(body, side, kind 'base' or 'reload', set name, pose clips glb, hand clips glb, [(vars, priority)])]"""
    by_pose = {}
    for var, pose in poses().items():
        by_pose.setdefault(pose, []).append(var)
    base_vars = manifest.base_vars()
    out = []
    for body in manifest.bodies():
        for side in SIDES:
            suffix = '_left' if side == 'left' else ''
            for pose, vars_ in sorted(by_pose.items()):
                glb, hands = clips(body, pose)
                out.append((body, side, 'base', manifest.raised_base_set(body, side, pose), glb, hands,
                            [(['dual_wield', v + suffix], PRIO['base' if v in base_vars else 'model']) for v in vars_]))
                out.append((body, side, 'reload', manifest.raised_reload_set(body, side, pose), glb, hands,
                            [(['dual_wield', v + suffix], PRIO['reload']) for v in vars_]))
    return out


def names(kind=None):
    return [n for _, _, k, n, _, _, _ in plan() if kind in (None, k)]


if __name__ == '__main__':
    for body, side, kind, name, glb, hands, _ in plan():
        print(body, side, kind, name, glb if kind == 'base' else hands)
