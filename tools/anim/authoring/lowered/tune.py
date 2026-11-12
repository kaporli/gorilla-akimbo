"""Lowered pose footprint per gun (right hand; the left is the mirror): wrist bend, eye distance, screen box.

usage: tune.py [--guns id,id]   -> family, mesh and footprint of each gun's manifest pose
"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
import poses, lauthor as A
from guns import verts
from lpose import qrot
EYE = np.array([0, 1.605, 0.0]); HH = math.radians(34); HV = math.atan(math.tan(HH) * 0.75)


def footprint(fam, G, tune=None, body='pma'):
    s = poses.spec(fam, body, 'x.glb', tune); A.setup(s)
    L, st = A.solve_offsets({S: (A.LOW[S][0], A.LOW[S][1], 1.0) for S in ('Right', 'Left')})
    W = A.rig.world(L); t, q = W[A.idx['WeaponRight']]
    P = np.array([t + qrot(q, x) for x in verts(G)[::2]]) - EYE
    fwd = -P[:, 2]; ok = fwd > 0.02
    sx = np.arctan2(P[ok, 0], fwd[ok]) / HH; sy = np.arctan2(P[ok, 1], fwd[ok]) / HV
    on = (np.abs(sx) < 1) & (np.abs(sy) < 1)
    return {'wrist': round(st['Right']['wrist'], 1), 'eye': round(float(np.linalg.norm(P, axis=1).min()) * 100, 1),
            'on': round(float(on.sum()) / len(P), 2), 'box': [round(float(v), 2) for v in (sx[on].min(), sx[on].max(), sy[on].min(), sy[on].max())] if on.any() else None}


if __name__ == '__main__':
    seen = set()
    for g in common.gun_list(common.opt(sys.argv, '--guns')):
        G, low = g.get('mesh'), g.get('lowered')
        if not G or not low or G in seen: continue
        seen.add(G)
        print(f'{low["family"]} {G:40s}', footprint(low['family'], G, {'d': low['tune']} if 'tune' in low else None))
