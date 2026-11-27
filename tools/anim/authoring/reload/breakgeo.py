"""Hinge geometry of a break-open shotgun from its game files (breakphys reads <OUT>/ref/<gun>_geometry.json).
Round 1 kept no script for the Palica and Satara files; this method reproduces their hinge (pivot, axis, open angle,
curve) and is used for the Igla and the Testera, which have no shell joints (closed, open_game and joints stay empty).
  hinge_axis, hinge_pivot  the barrel_hinge joint's rotation between closed (frame 0) and open (largest angle) in
                           the empty reload, as an axis through a point (gun axes)
  open_deg                 the held open angle (the plateau; open_max_deg the largest); hinge_curve: [frame, deg] every half frame of the empty reload
usage: breakgeo.py check | <gun id> [--write]
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, gungeo
import numpy as np
from glb import Glb
from wclip import TClip
from magtrack2 import m4


def hinge(gid, clip='empty_reload'):
    b = Glb(gungeo.wanim(common.gun(gid), 'base1')); c = TClip(b, clip); i = b.names.index('barrel_hinge')
    W0 = m4(*c.wf(0)[i]); ang = []; mats = []
    for k in range(c.frames * 2):
        M = m4(*c.world(k / 60.0)[i]); R = M[:3, :3] @ W0[:3, :3].T; a = math.degrees(math.acos(max(-1, min(1, (np.trace(R) - 1) / 2)))); ang.append(a); mats.append(M)
    k = int(np.argmax(ang)); M = mats[k]; R = M[:3, :3] @ W0[:3, :3].T; th = math.radians(ang[k])
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(th))
    # pivot: the point the rotation leaves fixed, nearest to the joint (least squares on M p = W0 p, i.e. (I - R) p = t)
    t = M[:3, 3] - R @ W0[:3, 3]; A = np.eye(3) - R; p, *_ = np.linalg.lstsq(A, t, rcond=None)
    p = p + ax * float((W0[:3, 3] - p) @ ax)      # along the axis, level with the joint
    sgn = 1.0
    big = [round(a, 2) for a in ang if a > 1.0]; plateau = max(set(big), key=big.count)      # the held open angle (the Satara overtravels to 55.8 for a frame before it shuts)
    return {'hinge_pivot': [float(x) for x in p], 'hinge_axis': [float(x) for x in ax * sgn], 'open_deg': float(plateau), 'open_max_deg': float(ang[k]),
            'hinge_curve': [[k2 / 2.0, round(float(a), 6)] for k2, a in enumerate(ang)], 'frames': c.frames}


def check():
    for g in ('palica', 'satara'):
        ref = json.load(open(f'{renv.OUT}/ref/{g}_geometry.json')); h = hinge(g)
        piv = np.array(ref['hinge_pivot']); ax = np.array(ref['hinge_axis']); P = np.array(h['hinge_pivot']); A = np.array(h['hinge_axis'])
        d = (P - piv) - ((P - piv) @ ax) * ax          # pivots on the same axis line are equal
        rc = np.array(ref['hinge_curve']); hc = np.array(h['hinge_curve']); n = min(len(rc), len(hc))
        print(g, 'axis dot', round(float(abs(A @ ax)), 6), 'pivot off the axis line cm', round(float(np.linalg.norm(d)) * 100, 3),
              'open deg', round(ref['open_deg'], 3), round(h['open_deg'], 3), 'curve max diff deg', round(float(np.abs(rc[:n, 1] - hc[:n, 1]).max()), 3), 'axis sign', round(float(A @ ax), 3))


if __name__ == '__main__':
    argv = sys.argv[1:]
    if argv[0] == 'check': check()
    else:
        g = argv[0]; h = hinge(g); h.update({'closed': {}, 'open_game': {}, 'joints': [], '_source': 'breakgeo.py (production): barrel_hinge of the empty reload; no shell joints'})
        print(g, {k: v for k, v in h.items() if k != 'hinge_curve'})
        if '--write' in argv: json.dump(h, open(f'{renv.OUT}/ref/{g}_geometry.json', 'w'), indent=1); print('wrote')
