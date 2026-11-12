"""Smallest striker translation delta (keys K-4 to K-1, zero at K-5 and from K on: the pose and contact depth at the
hit stay) that turns the push of EVERY clip of the pick (mean over its touching partner guns, as mag_flight.py measures
it) toward a target direction. Contact frames / points are taken from the clips as they are (they move < 0.05 f with
these deltas; mag_flight.py --delta measures again).
usage: opt.py <set>_<pick> <el deg> <az deg> <out.json> [--bodies pma] [--clips <dir>] [--spec <spec.json>]
  el: degrees above horizontal. az: 0 = -z (away from the camera), 90 = +x (V's right), 180 = +z (toward the camera).
  --bodies: default the first body (the delta is then checked on all bodies by mag_flight.py --delta).
  feas.py shows which directions allow a passing flight.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.optimize import minimize
from reaim_core import g, Delta, m4, quat
from mag_geom import app, partner_pts, FPS
from mag_contacts import signed, contact
import mag_flight as fl


def delta_of(p, K):
    p = np.asarray(p).reshape(-1, 3); fr = range(K - 4, K)
    return Delta([[K - 5, [0, 0, 0]]] + [[f, [float(x) for x in v]] for f, v in zip(fr, p)] + [[K, [0, 0, 0]], [K + 1, [0, 0, 0]]])


class Fast:
    """per clip: touching guns' (contact frame, striker-local point); base striker / magazine gun poses on integer frames"""
    def __init__(self, path, body, sh, st, keys, K):
        a = g.Arm(path); self.items = []; lo, hi = K + fl.GATES['touch'][0], K + fl.GATES['touch'][1]
        for k in keys:
            P = partner_pts(k); c, i = contact(a, sh, st, P, lo=18, hi=32)
            if c is not None and lo <= c <= hi: self.items.append((c, P[i]))
        if not self.items:
            best = max(keys, key=lambda k: signed(a, sh, st, partner_pts(k), float(K))[0]); P = partner_pts(best)
            self.items.append((float(K), P[signed(a, sh, st, P, float(K))[1]]))
        self.S = {f: a.W(st, f) for f in range(K - 7, K + 6)}
        self.Hf = {}
        for c, _ in self.items:
            for t in (c - 1.0, c, c - 0.5):
                self.Hf[t] = a.W(sh, t)

    def push(self, delta):
        D = {f: delta.at(f) @ self.S[f] for f in self.S}
        def Sw(t):
            f0 = int(np.floor(t)); a = t - f0
            A, B = D[f0], D[f0 + 1]
            qa, qb = quat(A[:3, :3]), quat(B[:3, :3])
            if qa @ qb < 0: qb = -qb
            return m4(A[:3, 3] * (1 - a) + B[:3, 3] * a, qa * (1 - a) + qb * a)
        us = []
        for c, p in self.items:
            def rel(t): return app(np.linalg.inv(self.Hf[t]) @ Sw(t), p[None])[0]
            v = self.Hf[c][:3, :3] @ (rel(c) - rel(c - 1.0)) * FPS
            us.append(v / np.linalg.norm(v))
        u = np.mean(us, 0); return u / np.linalg.norm(u)


def direction(el, az):
    e, a = np.radians(el), np.radians(az)
    return np.array([np.cos(e) * np.sin(a), np.sin(e), -np.cos(e) * np.cos(a)])


if __name__ == '__main__':
    a = sys.argv[1:]; opt = g.common.opt
    spec = g.load_spec(opt(a, '--spec')); cdir = opt(a, '--clips'); b = opt(a, '--bodies')
    bodies = g.common.body_list(b) if b else g.common.BODIES[:1]
    if len(a) != 4: raise SystemExit(__doc__)
    name, el, az, out = a[0], float(a[1]), float(a[2]), a[3]
    tgt = direction(el, az)
    key, pi = g.find_pick(spec, name); K = spec[key][pi]['K']
    clips = [Fast(p, b, sh, st, keys, K) for p, b, sh, st, keys in g.spec_cases(spec, key, pi, cdir, bodies)]
    n0 = [c.push(Delta()) for c in clips]

    def angs(p):
        d = delta_of(p, K); return np.array([np.degrees(np.arccos(np.clip(c.push(d) @ tgt, -1, 1))) for c in clips])

    def obj(p):
        gg = angs(p); P = np.asarray(p).reshape(-1, 3) * 100
        acc = np.diff(np.vstack([[0, 0, 0], P, [0, 0, 0]]), 2, axis=0)
        return (gg ** 2).mean() + 0.5 * gg.max() ** 2 + 0.3 * (P ** 2).sum() + 0.3 * (acc ** 2).sum()

    r = minimize(obj, np.zeros(12), method='Powell', options=dict(xtol=1e-4, ftol=1e-4, maxfev=6000))
    p = r.x.reshape(-1, 3); d = delta_of(r.x, K)
    res = dict(pick=name, el=el, az=az, target=tgt.tolist(), delta=d.to_json(),
               keys_cm={f: (v * 100).round(2).tolist() for f, v in zip(range(K - 4, K), p)},
               push_before=[x.tolist() for x in n0], push_after=[c.push(d).tolist() for c in clips],
               ang_to_target=angs(r.x).round(1).tolist(),
               turn_deg=[round(float(np.degrees(np.arccos(np.clip(c.push(d) @ x, -1, 1)))), 1) for c, x in zip(clips, n0)])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(res, open(out, 'w'), indent=1)
    print(name, el, az, 'keys cm', res['keys_cm'], 'ang to target', res['ang_to_target'], 'turn', res['turn_deg'])
