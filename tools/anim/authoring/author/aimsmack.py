"""Strike aiming for a spec: the struck gun's magazine in world space at given frames, and the striking hand's knuckle
relative to its gun at rest.

usage: aimsmack.py <spec.json> [--gun shingen] [--side Left] [--frames 20,24,25,26,28,30] [--joint RightHandIndex1]
gun: manifest id or mesh stem of the gun whose magazine is struck; side: the hand that holds it.
Prints per frame the magazine's mid point (7 cm behind its origin) and its right face (3.5 cm to the right), then the
joint's position in the other gun's axes and that gun's rest origin. Gun origin for a strike point S (gun axes) on a
world target T: T - R(gun rotation) * S."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
import author
from glb import Glb
from fk import Clip, qinv, qrot

argv = sys.argv[1:]
key = common.opt(argv, '--gun', 'shingen'); side = common.opt(argv, '--side', 'Left')
frames = [int(x) for x in common.opt(argv, '--frames', '20,24,25,26,28,30').split(',')]
other = 'Right' if side == 'Left' else 'Left'
joint = common.opt(argv, '--joint', f'{other}HandIndex1')
author.setup(json.load(open(argv[0])))
mesh = next((g['mesh'] for g in common.manifest.guns(all_=True) if g['id'] == key), key)
gw = Glb(common.need(common.find('weapon_anims', f'{mesh}__base1.anims.glb')))
st, sq = Clip(gw, 'reload').world(0)[gw.names.index('mag_slot')]
mg = Glb(common.need(common.find('weapon_anims', f'{mesh}__mag_std.anims.glb'))); mc = Clip(mg, 'reload'); mi = mg.names.index('mag_std')
for f in frames:
    gp, gq = author.gun_pose(side, f)
    t, q = mc.world(f)[mi]; mp = st + qrot(sq, t)
    mid = mp + np.array([0.0, 0.0, 0.07]); face = mid + np.array([0.035, 0.0, 0.0])
    print(f, 'mag mid', np.round(gp + qrot(gq, mid), 3), 'right face', np.round(gp + qrot(gq, face), 3))
rk = author.idx[joint]; wr = author.idx[f'Weapon{other}']; rest = author.rest
print('knuckle rel gun', np.round(qrot(qinv(rest[wr][1]), rest[rk][0] - rest[wr][0]), 3), 'gun rest', np.round(rest[wr][0], 3))
