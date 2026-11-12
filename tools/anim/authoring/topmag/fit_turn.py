"""Turn fit of long partner clips: the striking gun is turned about its contact point (author.py "turns") and moved
(an extra bump, same window) so that, at once:
  the gun itself (no hand) is 0.5 to 4 mm into the SEATED magazine at the hit frame (the magazine track holds it seated
  until the hit; magtrack/mag_contacts.py measures the same), and checks.py's contact (gun and hand against the magazine
  where the game's reload has it at f25) stays in its limits (depth <= 0.4 cm, miss <= 0.8 cm), every gun of the clip,
  no gun sinks into the top-magazine gun's body over f18..34 (geo.shingen_depth; a rifle's magazine hangs below the
  receiver and went into the Shingen in the axe),
  the eye stays 20 cm away (checks.py eye_distance, over the clip),
  the peak view cover stays within the reference gun's clip + 2.5 points (checks.py face_cover),
  the striking wrist stays under checks.py's limit,
with the smallest turn and move. Nelder-Mead over (turn vector deg, move cm) from a few starts.
usage: fit_turn.py <gen out dir> <clip>[,<clip>] [--share copperhead:umbra] [--seeds f.json] [--out dir] [--jobs n] [--nobuild]
  --eyew: weight of the eye distance term per cm (default 10)
  --seat: least depth of the gun alone in the seated magazine, cm (default 0.05)
  --cover: cover target over the reference gun's clip, points (default 2.5)
  --seeds: {clip: [[turn x,y,z deg, move x,y,z cm], ...]} extra starting points (e.g. the other hand's fit, mirrored)
  clip: <body>/shingen_<side>_<pick>_<gun>; reads <gen out>/specs/<pick>/<side>_<body>_<gun>.json (gen_long.py)
  writes <out>/specs/<pick>/<side>_<body>_<gun>.json (with _turn: the fit and its numbers) and <out>/clips/<body>/<clip>.glb"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import geo
from geo import load_spec, gunM, magJ, app, box_signed, M4, EYES

HIT = 25
WIN = {'lupper': [9, 18, 28, 36], 'axe': [14, 22, 28, 36], 'hang': [9, 18, 28, 36]}
LIM = {'depth': 0.4, 'miss': 0.8, 'seat': (0.05, 0.4), 'body': 0.1, 'eye': 20.6, 'cover': 2.5, 'wrist': 112.0}
REF = 'carnage'


def wrist_deg(W, rest, idx, S):
    """checks.py wrist: hand swing against the forearm, relative to the template's first frame (deg)"""
    from fk import qmul, qinv
    hq0, fq0 = rest[idx[f'{S}Hand']][1], rest[idx[f'{S}ForeArm']][1]
    hp, hq = W[idx[f'{S}Hand']]; ep, fq = W[idx[f'{S}ForeArm']]
    uf = (hp - ep) / np.linalg.norm(hp - ep)
    rel = qmul(hq, qinv(qmul(fq, qmul(qinv(fq0), hq0))))
    return float(2 * np.degrees(np.arccos(min(1.0, np.sqrt(rel[3] ** 2 + np.dot(rel[:3], uf) ** 2)))))


def fast_cover(Pw, eye, W=128, H=72):
    """share of the view (%) covered by surface points: geo.coverage's camera, a coarse raster, one pixel dilation"""
    from scipy.ndimage import binary_dilation
    d = Pw - eye; z = d @ geo.FWD; m = z > 0.02
    fx = (W / 2) / geo.TH
    X = (W / 2 + fx * (d[m] @ geo.RGT) / z[m]).astype(int); Y = (H / 2 - fx * (d[m] @ geo.UP) / z[m]).astype(int)
    k = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
    A = np.zeros((H, W), bool); A[Y[k], X[k]] = True
    return float(binary_dilation(A).mean()) * 100


class Fit:
    def __init__(self, spec, side, pick, guns):
        self.base = spec; self.side = side; self.pick = pick; self.guns = guns
        self.sh, self.st = geo.SIDES[side]; self.body = spec['body']
        b = (spec.get('bumps') or {}).get(self.st)
        self.win = b[0]['f'] if b else WIN[pick]
        ns = load_spec(spec)
        self.GS = {f: gunM(ns, self.sh, f) for f in range(spec['frames'])}
        self.MJ = {f: magJ(ns, self.sh, f) for f in (HIT,)}
        H = geo.hand(self.body, self.st)
        self.P = {g: np.vstack([geo.load(g)['all'], H]) for g in guns}
        self.Pb = {g: geo.load(g)['all'][::3] for g in guns}
        self.S = {g: geo.dense(g) for g in guns}                       # gun surface only (rifle magazine included)
        self.MS = np.linalg.inv(self.GS[HIT] @ geo.mag_local(0))      # the seated magazine at the hit frame
        self.T = {g: geo.tris(g) for g in guns}
        self.eye = EYES[self.body]
        import checks
        self.tree = {g: checks.eye_tree(g) for g in guns}
        # contact point of the first gun in the base clip: the turn pivots about it
        G = gunM(ns, self.st, HIT); d = box_signed(app(self.MS @ G, self.S[guns[0]]))
        self.about = self.S[guns[0]][int(np.argmax(d))]
        self.wf = [f for f in range(self.win[0], self.win[3] + 1)]
        # eye distance outside the window does not change. A gun with a raised pose plays the raised copy of the clip,
        # whose frames after topmag_window[1] differ: only frames up to it count for that gun
        import checks, manifest
        cdict = {'kind': 'long', 'tag': guns[0]}
        last = manifest.load()['checks']['raised']['topmag_window'][1]
        self.eye_out = {g: min(self.eyed(g, gunM(ns, self.st, f)) for f in range(spec['frames'])
                               if f not in self.wf and (f <= last or not checks.raised_pose(g, cdict))) for g in guns}
        self.ref = self.ref_cover()
        # cover is searched only for guns near the limit in the base clip, on frames around its peak
        self.cov_frames = {}
        for g in guns:
            Vt, T = self.T[g]
            c = {f: geo.coverage(app(gunM(ns, self.st, f), Vt), T, self.eye, 96, 54) * 100 for f in self.wf}
            pk = max(c, key=c.get)
            if c[pk] - self.ref_fast > LIM['cover'] - 4:
                self.cov_frames[g] = [f for f in (pk - 4, pk - 2, pk, pk + 2, pk + 4) if f in c]

    def eyed(self, g, G):
        return float(self.tree[g].query(app(np.linalg.inv(G), self.eye[None]))[0][0]) * 100

    def ref_cover(self):
        import checks
        p = f'{common.path("clips")}/{self.body}/{geo.TOPGUN}_{self.side}_{self.pick}_{REF}.glb'
        W, _, N = checks.fk(p); Vt, T = geo.tris(REF)
        self.ref_fast = max(geo.coverage(app(M4(*W[f][f'Weapon{self.st}']), Vt), T, self.eye, 96, 54) for f in range(14, 40)) * 100
        return max(geo.coverage(app(M4(*W[f][f'Weapon{self.st}']), Vt), T, self.eye) for f in range(14, 40)) * 100

    def spec(self, x):
        sp = json.loads(json.dumps(self.base))
        r = [round(float(v), 3) for v in x[:3]]; m = [round(float(v) / 100, 4) for v in x[3:6]]
        if np.linalg.norm(r) > 1e-3:
            sp.setdefault('turns', {})[self.st] = [{'f': self.win, 'rot': r, 'about': [round(float(v), 4) for v in self.about]}]
        if np.linalg.norm(m) > 1e-5:
            sp.setdefault('bumps', {}).setdefault(self.st, []).append({'f': self.win, 'move': m})
        return sp

    def measure(self, x, full=False):
        sp = self.spec(x); ns = load_spec(sp)
        G = {f: gunM(ns, self.st, f) for f in self.wf}
        out = {'seat': {}, 'contact': {}, 'body': {}, 'eye': {}, 'cover': {}}
        Mi = np.linalg.inv(self.MJ[HIT])
        for g in self.guns:
            out['contact'][g] = float(box_signed(app(Mi @ G[HIT], self.P[g])).max()) * 100
            out['seat'][g] = float(box_signed(app(self.MS @ G[HIT], self.S[g])).max()) * 100
            out['body'][g] = max(geo.shingen_depth(app(np.linalg.inv(self.GS[f]) @ G[f], self.Pb[g])) for f in range(18, 35)) * 100
            out['eye'][g] = min(self.eye_out[g], min(self.eyed(g, G[f]) for f in self.wf))
            Vt, T = self.T[g]
            if full:
                out['cover'][g] = max(geo.coverage(app(G[f], Vt), T, self.eye) for f in self.wf) * 100 - self.ref
            elif g in self.cov_frames:               # coarse raster near the base peak (fast), against the same raster
                out['cover'][g] = max(geo.coverage(app(G[f], Vt), T, self.eye, 96, 54) for f in self.cov_frames[g]) * 100 - self.ref_fast
            else:                                    # far under the limit in the base clip: not searched
                out['cover'][g] = -99.0
        Wr = [ns['solveW'](f) for f in range(self.win[0] + 4, self.win[3] - 2, 2 if not full else 1)]
        out['wrist'] = max(wrist_deg(W, ns['rest'], ns['idx'], self.st) for W in Wr)
        return out

    def cost(self, x):
        m = self.measure(x); c = 0.01 * np.linalg.norm(x[:3]) + 0.05 * np.linalg.norm(x[3:6])
        for g in self.guns:
            d = m['contact'][g]
            c += 40 * max(0, d - LIM['depth']) + 40 * max(0, -d - LIM['miss'])
            e = m['seat'][g]   # the first gun must touch; a gun sharing its clip may miss by the gate's miss limit
            c += 40 * max(0, (LIM['seat'][0] if g == self.guns[0] else -LIM['miss']) - e) + 40 * max(0, e - LIM['seat'][1])
            c += 30 * max(0, m['body'][g] - LIM['body'])
            c += LIM.get('eye_w', 10) * max(0, LIM['eye'] - m['eye'][g])
            c += 3 * max(0, m['cover'][g] - LIM['cover'])
        c += 2 * max(0, m['wrist'] - LIM['wrist'])
        return c

    def run(self, seeds=()):
        from scipy.optimize import minimize
        starts = [np.zeros(6)] + [np.array(x, float) for x in seeds]
        for ax in range(3):
            for s in (-15, 15):
                x = np.zeros(6); x[ax] = s; starts.append(x)
        scored = sorted(((self.cost(x), i) for i, x in enumerate(starts)))
        best = None
        for _, i in scored[:2 + len(seeds)]:
            r = minimize(self.cost, starts[i], method='Nelder-Mead',
                         options={'maxfev': 220, 'xatol': 0.2, 'fatol': 1e-3, 'initial_simplex': starts[i] + np.vstack([np.zeros(6), np.diag([6, 6, 6, 1.5, 1.5, 1.5])])})
            if best is None or r.fun < best.fun: best = r
        return best.x, best.fun


def job(a):
    src, out, clip, guns, build, seeds, lim = a
    LIM.update(lim)
    body, name = clip.split('/'); p = name.split('_'); side, pick, gun = p[1], p[2], '_'.join(p[3:])
    spec = json.load(open(f'{src}/specs/{pick}/{side}_{body}_{gun}.json'))
    F = Fit(spec, side, pick, guns)
    m0 = F.measure(np.zeros(6), full=True)
    x, c = F.run(seeds)
    m1 = F.measure(x, full=True)
    sp = F.spec(x)
    sp['_turn'] = {'rot_deg': [round(float(v), 2) for v in x[:3]], 'move_cm': [round(float(v), 2) for v in x[3:6]], 'cost': round(float(c), 3),
                   'about': [round(float(v), 4) for v in F.about], 'ref_cover': round(F.ref, 2),
                   'before': json.loads(json.dumps(m0, default=float)), 'after': json.loads(json.dumps(m1, default=float))}
    d = f'{out}/specs/{pick}'; os.makedirs(d, exist_ok=True)
    json.dump(sp, open(f'{d}/{side}_{body}_{gun}.json', 'w'), indent=1)
    if build:
        geo.build(sp, f'{out}/clips/{body}/{name}.glb')
    r = lambda m: ' '.join(f'{g}: seat {m["seat"][g]:+.2f} c {m["contact"][g]:+.2f} body {m["body"][g]:.2f} eye {m["eye"][g]:.1f} cov {m["cover"][g]:+.1f}' for g in guns) + f' wrist {m["wrist"]:.1f}'
    return f'{clip}\n  before {r(m0)}\n  after  {r(m1)}\n  turn {sp["_turn"]["rot_deg"]} deg, move {sp["_turn"]["move_cm"]} cm, cost {c:.3f}'


if __name__ == '__main__':
    a = sys.argv[1:]
    share = {}
    for x in (common.opt(a, '--share') or '').split(','):
        if x: m, o = x.split(':'); share[m] = o.split('+')
    out = (common.opt(a, '--out') or common.work('topmag', 'turn')).replace('\\', '/')
    jobs = int(common.opt(a, '--jobs') or 6); build = '--nobuild' not in a
    cv = common.opt(a, '--cover')                  # cover target over the reference (points), default LIM cover
    if cv: LIM['cover'] = float(cv)
    ew = common.opt(a, '--eyew')                   # weight of the eye distance term (default 10 per cm)
    if ew: LIM['eye_w'] = float(ew)
    se = common.opt(a, '--seat')                   # least depth of the gun in the seated magazine, cm (default 0.05)
    if se: LIM['seat'] = (float(se), LIM['seat'][1])
    sf = common.opt(a, '--seeds')                  # {clip: [[turn deg x3, move cm x3], ...]} extra starts
    seeds = json.load(open(sf)) if sf else {}
    a = [x for x in a if not x.startswith('--')]
    src = a[0].replace('\\', '/'); clips = a[1].split(',')
    todo = []
    for c in clips:
        g = c.split('_', 3)[3]
        todo.append((src, out, c, [g] + share.get(g, []), build, seeds.get(c, []), dict(LIM)))
    if jobs > 1 and len(todo) > 1:
        from multiprocessing import Pool
        with Pool(min(jobs, len(todo))) as pool:
            res = pool.map(job, todo, chunksize=1)
    else:
        res = [job(t) for t in todo]
    for r in res:
        print(r, flush=True)
