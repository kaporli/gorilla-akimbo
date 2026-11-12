"""Per-gun tuning of v1 low ready: the gun's top edge on screen near -0.78 (the bottom 11 % of the view, as the
Saratoga + Shingen pair tested in game), at least 25 cm from the eye, wrist bend at most 20 deg.

Prints, per gun with a mesh, the tune found and the tune in weapons.json (lowered.tune). The result is entered in
weapons.json by hand: "lowered": {"family": "v1", "pose": "v1_<name>", "tune": [0, dy, dz]}.
Target and limits: weapons.json checks.lowered (autotune_top_edge, eye_min_cm, wrist_idle_max_deg).

usage: autotune.py [--guns id,id] [--all]
  without --guns: every v1 gun of this build (GA_TEST=1 includes test guns); --all also tunes guns of another family
  (to see whether a long gun would fit v1).
"""
import os, sys, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from tune import footprint

T = common.manifest.load()['checks']['lowered']
TARGET, EYE_MIN, WRIST_MAX = T['autotune_top_edge'], T['eye_min_cm'], T['wrist_idle_max_deg']


def tune(G):
    best = None
    for ddy, ddz in itertools.product(np.arange(-0.06, 0.101, 0.01), (0.0, -0.03, -0.06)):
        t = {'d': [0, round(float(ddy), 3), ddz]}
        f = footprint('v1', G, t)
        if f['box'] is None: continue
        sc = abs(f['box'][3] - TARGET) + (10 if f['eye'] < EYE_MIN else 0) + (10 if f['wrist'] > WRIST_MAX else 0) + abs(ddz) * 0.5 + abs(ddy) * 0.3
        if best is None or sc < best[0]: best = (sc, t, f)
    return best


if __name__ == '__main__':
    every = '--all' in sys.argv
    picked = common.opt(sys.argv, '--guns')
    done, bad = set(), 0
    for g in common.gun_list(picked):
        G, low = g.get('mesh'), g.get('lowered') or {}
        if not G or G in done or (low.get('family') != 'v1' and not (every or picked)): continue
        done.add(G)
        sc, t, f = tune(G)
        have = low.get('tune') if low.get('family') == 'v1' else None
        same = have is not None and np.allclose(have, t['d'])
        bad += have is not None and not same
        print(f'{g["id"]:14s} {G:40s} tune {t["d"]} {f} score {sc:.3f}  weapons.json: '
              f'{have if have is not None else "none (" + low.get("family", "no lowered entry") + ")"}{"" if same or have is None else "  DIFFERENT"}')
    sys.exit(1 if bad else 0)
