"""Grid search for a lowered pose with a natural wrist (how v2 high port was found): wrist bend, screen box and eye
distance of one gun over hand offsets, gun angles and a clavicle pitch. Prints the 15 candidates with the smallest
wrist bend among those in reach, at least 28 cm from the eye and partly on screen at the side. The pick goes into
weapons.json lowered_families by hand.

usage: wristsearch.py <body> <gun id>
"""
import os, sys, math, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
import lauthor as A
from guns import verts
from lpose import qrot
EYE = np.array([0, 1.605, 0.0]); HH = math.radians(34); HV = math.atan(math.tan(HH) * 0.75)


def evaluate(body, G, o, e, clav=(0, 0, 0)):
    sp = {'base': common.need(common.idle_glb(body)), 'lowered': {'Right': [o, e], 'Left': [[-o[0], o[1], o[2]], [e[0], -e[1], -e[2]]]},
          'clavicle': {'Right': list(clav), 'Left': [clav[0], -clav[1], -clav[2]]}}
    A.setup(sp)
    L, st = A.solve_offsets({S: (A.LOW[S][0], A.LOW[S][1], 1.0) for S in ('Right', 'Left')})
    W = A.rig.world(L); t, q = W[A.idx['WeaponRight']]
    P = np.array([t + qrot(q, x) for x in verts(G)[::3]]) - EYE
    fwd = -P[:, 2]; ok = fwd > 0.02
    sx = np.arctan2(P[ok, 0], fwd[ok]) / HH; sy = np.arctan2(P[ok, 1], fwd[ok]) / HV
    on = (np.abs(sx) < 1) & (np.abs(sy) < 1)
    return {'wrist': round(st['Right']['wrist'], 1), 'shift': round(st['Right']['shift'] * 100, 1),
            'eye': round(float(np.linalg.norm(P, axis=1).min()) * 100, 1), 'on': round(float(on.sum()) / len(P), 2),
            'xmin': round(float(sx[on].min()), 2) if on.any() else None, 'ytop': round(float(sy[on].max()), 2) if on.any() else None}


if __name__ == '__main__':
    body = sys.argv[1]; G = common.gun(sys.argv[2])['mesh']
    res = []
    for dx, dy, dz, p, yw, rl, cp in itertools.product([0.06, 0.10, 0.14], [-0.20, -0.14, -0.08], [-0.04, 0.02, 0.08],
                                                      [35, 45], [-15], [-25, -10], [0, -15]):
        r = evaluate(body, G, [dx, dy, dz], [p, yw, rl], (cp, 0, 0))
        res.append(((dx, dy, dz, p, yw, rl, cp), r))
    good = [x for x in res if x[1]['shift'] == 0 and x[1]['eye'] >= 28 and x[1]['on'] > 0.03 and (x[1]['xmin'] or 0) > 0.35]
    for k, r in sorted(good, key=lambda x: x[1]['wrist'])[:15]: print(k, r)
