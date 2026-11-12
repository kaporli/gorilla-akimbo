"""Which push directions allow a passing flight: the flight search on one clip of a pick (all bodies) with the push
overridden by each direction of a grid. Picks the target direction for opt.py.
usage: feas.py <set>_<pick> <clip name> <partner gun> [<els>] [<azs>] [--clips <dir>] [--spec <spec.json>] [--jobs 7]
  clip name: no folder, no .glb. els, azs: comma separated degrees (default 30,45,60,75 and -135,...,180).
  el: above horizontal. az: 0 = -z (away from the camera), 90 = +x (V's right), -90 = -x, 180 = +z.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from reaim_core import g
import mag_flight as fl
from opt import direction


def job(args):
    cases, K, n = args
    cs = [fl.Case(*c, K=K, lo=18, n_override=None if n is None else np.array(n)) for c in cases]
    if n is None: return cs[0].n.tolist(), None
    e, r = fl.solve(cs, rings=3, per=12, top=15)
    return n, r


if __name__ == '__main__':
    a = sys.argv[1:]; opt = g.common.opt
    spec = g.load_spec(opt(a, '--spec')); cdir = opt(a, '--clips'); jobs = int(opt(a, '--jobs', 7))
    if len(a) < 3: raise SystemExit(__doc__)
    key, pi = g.find_pick(spec, a[0]); K = spec[key][pi]['K']
    cases = [(p, b, sh, st, [a[2]]) for p, b, sh, st, _ in g.spec_cases(spec, key, pi, cdir) if os.path.basename(p)[:-4] == a[1]]
    if not cases: raise SystemExit(f'{a[0]} has no clip {a[1]}')
    base = np.array(job((cases, K, None))[0]); print('push now', np.round(base, 3), flush=True)
    els = [float(x) for x in a[3].split(',')] if len(a) > 3 else (30, 45, 60, 75)
    azs = [float(x) for x in a[4].split(',')] if len(a) > 4 else (-135, -90, -45, 0, 45, 90, 135, 180)
    cands = [direction(el, az).tolist() for el in els for az in azs] + [base.tolist()]
    t = time.time()
    from multiprocessing import Pool
    with Pool(jobs) as p: out = p.map(job, [(cases, K, n) for n in cands])
    for n, r in out:
        n = np.array(n); el = np.degrees(np.arcsin(n[1])); az = np.degrees(np.arctan2(n[0], -n[2]))
        print(f'push el {el:5.1f} az {az:6.1f} ({np.round(n, 2)}) to now {np.degrees(np.arccos(np.clip(n @ base, -1, 1))):5.1f} | {fl.summary(r)}', flush=True)
    print('time', round(time.time() - t))
