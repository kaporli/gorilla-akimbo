"""Magazine flight of one pick: the gates and the search.

A flight (direction within 25 deg of the hit, push 0.8-1.5 m/s, spin <= 720 deg/s) must, in EVERY arm clip that plays
it (male and female, all partner guns / categories):
  - leave within 25 deg of that clip's push, rise <= 12 cm, never accelerate upward or reverse while visible,
  - stay >= 20 cm from the eye E while any part is visible,
  - be fully off screen by K+12 (and before f40) and never come back,
  - not be re-entered by the striking gun after release (<= 5 mm into the magazine box, K+0.5 to K+4),
  - on screen: leave within 25 deg of the striker's approach, no down-then-up, no upward acceleration, no horizontal
    reversal, apparent height <= 1.4x the height at release.
GATES holds these numbers. The gun-relative exit angle is the soft gate of the search (reported when it cannot be met).

usage: mag_flight.py <set>_<pick index or name> ... [--spec <spec.json>] [--clips <dir>] [--out <dir>]
                     [--rings 6] [--per 24] [--lo 20] [--delta <delta.json>]
  Searches each pick and writes <out>/flight_<pick>.json {entry, report}; entry is the pick's spec entry (paste it into
  the spec). default out: <authoring work>/magtrack/flight. --delta: striker delta of reaim/ simulated on the clips.
  --lo: first frame of the contact scan (20: the first search of 2026-11-07; 18: the re-aimed picks).
"""
import os, sys, json
import numpy as np
import mag_geom as g
from mag_geom import app, box_signed, partner_pts, onscreen_frac, screen, E, EYES, TX, FPS, G0, MAGC, MAGS, MT
from mag_contacts import signed, contact

SPEEDS = (0.8, 1.0, 1.2, 1.5); SPINS = (0, 90, -90, 180, -180, 360, -360, 540, 720); GUNVEL = ('pre', 'post', 'none')
UPJ = np.array([0, 1.0, 0])
LAST = MT.INSERT                      # last frame of the flight (the vanilla insertion takes over)
NFR = g.FRAMES['length']
GATES = {
    'exit_deg': 25,           # max angle between the exit relative to the gun (K to K+3) and the clip's push
    'eye_cm': 20,             # min distance of the visible magazine to the eye E
    'rise_cm': 12,            # max rise of the magazine centre above its release height while visible
    'ay_mm_f2': 0,            # max vertical acceleration of the centre while visible (mm per frame^2)
    'rev_mm': 2,              # horizontal step against the exit direction that counts as a reversal (mm per frame)
    'restrike_mm': 5,         # max depth of the striking gun in the magazine box after release
    'screen_exit_deg': 25,    # max angle on screen between the exit and the striker's approach
    'screen_upacc_px': 1.0,   # screen upward acceleration that counts (px per frame^2, 1280x720)
    'screen_rev_px': 1.0,     # screen step that counts as a reversal or a down-then-up (px per frame; 0.5 vertical)
    'size_ratio': 1.4,        # max apparent height relative to the release frame
    'hide_after': 12,         # last visible frame <= K + this
    'hide_before': 40,        # and < this frame
    'touch': (-1.5, 0.6),     # a partner gun touches when its contact frame is within K + this window
}


def push_at(arm, sh, st, p, c):
    """approach velocity of the striker point relative to the magazine gun over [c-1, c] (m/s, world at c): the clips
    key the hit as a turning point, so the velocity AT contact is near zero in some of them"""
    f, h = c - 0.5, 0.5
    def rel(t): return app(np.linalg.inv(arm.W(sh, t)) @ arm.W(st, t), p[None])[0]
    return arm.W(sh, c)[:3, :3] @ (rel(f + h) - rel(f - h)) / (2 * h) * FPS


def clip_push(arm, sh, st, keys, contacts, K=25):
    """unit push (world, at contact) for one clip: mean over the partner guns that touch; closest approach otherwise.
    contacts: {partner: contact frame or None}"""
    vs, cs = [], []; a, b = K + GATES['touch'][0], K + GATES['touch'][1]
    for key in keys:
        c = contacts.get(key); P = partner_pts(key)
        if c is None or not a <= c <= b: continue
        d, k = signed(arm, sh, st, P, c); vs.append(push_at(arm, sh, st, P[k], c)); cs.append((key, c))
    if not vs:   # no touch: the closest partner gun at K
        best = max(keys, key=lambda k: signed(arm, sh, st, partner_pts(k), float(K))[0])
        P = partner_pts(best); d, k = signed(arm, sh, st, P, float(K))
        vs.append(push_at(arm, sh, st, P[k], float(K))); cs.append((best, None))
    u = np.mean([v / np.linalg.norm(v) for v in vs], 0)
    return u / np.linalg.norm(u), cs, float(np.mean([np.linalg.norm(v) for v in vs]))


def cone(n, maxdeg=25, rings=6, per=24):
    n = n / np.linalg.norm(n); a = np.cross(n, [0, 1, 0])
    a = a / np.linalg.norm(a) if np.linalg.norm(a) > 1e-6 else np.array([1., 0, 0])
    b = np.cross(n, a); out = [n]
    for i in range(1, rings + 1):
        th = np.radians(maxdeg * i / rings)
        for j in range(per):
            ph = 2 * np.pi * j / per; out.append(np.cos(th) * n + np.sin(th) * (np.cos(ph) * a + np.sin(ph) * b))
    return out


class Case:
    """One arm clip of a pick: its partner guns' contact frames against the seated magazine and its push.
    contacts: {partner: frame} measured before (mag_contacts rows); else measured here over f lo..hi.
    arm_of: path -> clip reader, instead of the plain file (reaim: a delta on the striker). n_override: push to assume."""
    def __init__(self, path, body, sh, st, keys, K=25, contacts=None, arm_of=None, n_override=None, lo=20, hi=32):
        self.path, self.body, self.sh, self.st, self.K = path, body, sh, st, K
        self.arm = arm_of(path) if arm_of else g.Arm(path)
        self.name = os.path.basename(path)[:-4]
        if contacts is None:
            contacts = {k: contact(self.arm, sh, st, partner_pts(k), lo=lo, hi=hi)[0] for k in keys}
        self.contacts = contacts
        self.n, self.cs, self.vrel = clip_push(self.arm, sh, st, keys, contacts, K)
        if n_override is not None: self.n = np.asarray(n_override, float) / np.linalg.norm(n_override)
        self.W = {f: self.arm.W(sh, f) for f in range(0, NFR)}
        self.keys = [k for k, c in self.cs]


def cases(spec, key, pick, clips_dir=None, bodies=None, rows=None, **kw):
    """Case per clip of a pick. rows: mag_contacts.by_clip() of earlier measurements, to skip measuring."""
    K = spec[key][pick]['K']; out = []
    for p, body, sh, st, keys in g.spec_cases(spec, key, pick, clips_dir, bodies):
        c = None
        if rows is not None:
            r = rows.get((body, os.path.basename(p)[:-4]), {}); c = {k: r[k]['contact'] if k in r else None for k in keys}
        out.append(Case(p, body, sh, st, keys, K, c, **kw))
    return out


def interp(A, B, a):
    from scipy.spatial.transform import Rotation as Rot, Slerp
    s = Slerp([0, 1], Rot.from_matrix([A[:3, :3], B[:3, :3]]))
    M = np.eye(4); M[:3, :3] = s([a]).as_matrix()[0]; M[:3, 3] = A[:3, 3] * (1 - a) + B[:3, 3] * a; return M


def size_ratio(Mw, last, K):
    """apparent height (screen px of the magazine's vertical extent) relative to the release frame, max while visible"""
    def h(f):
        P = app(Mw[f], MAGS); q = P - E
        if (q[:, 2] > -0.03).any(): return 1e9
        y = 360 - (640 / TX) * q[:, 1] / -q[:, 2]; return y.max() - y.min()
    h0 = h(K); return round(max(h(f) for f in range(K, last + 1)) / h0, 2)


def evaluate(cs, G, S=None, full=True):
    """metrics per case for one gun-local track (G: 4x4 per frame)"""
    res = []
    for c in cs:
        K = c.K
        Mw = {f: c.W[f] @ G[f] for f in range(K, LAST + 1)}
        cen = {f: (Mw[f] @ np.r_[MAGC, 1])[:3] for f in Mw}
        r = dict(clip=c.name, body=c.body)
        vis = {}; eye = 9.0; feye = None
        for f in range(K, LAST + 1):
            Pw = app(Mw[f], MAGS); vis[f] = onscreen_frac(Pw) > 0
        last = max([f for f in vis if vis[f]], default=K)
        first_off = next((f for f in range(K + 1, LAST + 1) if not vis[f]), LAST + 1)
        r['last_vis'] = last; r['reappear'] = [f for f in range(first_off, LAST + 1) if vis[f]]
        eye2, feye2 = 9.0, None
        for f in range(K, last + 1):
            Pw = app(Mw[f], MAGS)
            d = np.linalg.norm(Pw - E, axis=1).min(); d2 = np.linalg.norm(Pw - EYES[c.body], axis=1).min()
            if d < eye: eye, feye = d, f
            if d2 < eye2: eye2, feye2 = d2, f
        # gate: the eye E of the camera fit; eye2: the arm checks' eye point, reported only
        r['eye_cm'] = round(eye * 100, 1); r['eye_f'] = feye; r['eye2_cm'] = round(eye2 * 100, 1); r['eye2_f'] = feye2
        r['rise_cm'] = round(max(cen[f][1] - cen[K][1] for f in range(K, last + 1)) * 100, 1)
        ay = [cen[f + 1][1] - 2 * cen[f][1] + cen[f - 1][1] for f in range(K + 1, max(K + 2, last))]
        r['max_ay_mm_f2'] = round(max(ay) * 1000, 2) if ay else None
        hz = cen[K + 3] - cen[K]; hz[1] = 0; hz /= np.linalg.norm(hz) + 1e-9
        hv = [(cen[f] - cen[f - 1]) @ hz for f in range(K + 2, last + 1)]
        r['rev'] = [K + 2 + i for i, x in enumerate(hv) if x < -GATES['rev_mm'] / 1000]
        # exit relative to the gun: flight position minus where the seated magazine would be, K+3 (world), vs the push
        loc = cen[K + 3] - (c.W[K + 3] @ G0 @ np.r_[MAGC, 1])[:3]
        r['exit_deg'] = round(float(np.degrees(np.arccos(np.clip(loc @ c.n / np.linalg.norm(loc), -1, 1)))), 1)
        # screen (what the in-game test measures): exit over the first 3 frames vs the striker's approach on screen
        # (K-1 to K, at the magazine centre), vertical sign changes, upward screen acceleration, horizontal reversal
        sc = {f: screen(cen[f]) for f in range(K, last + 1)}
        pc = (np.linalg.inv(c.arm.W(c.st, K)) @ np.r_[cen[K], 1])[:3]
        sv = screen(app(c.arm.W(c.st, K), pc[None])[0]) - screen(app(c.arm.W(c.st, K - 1), pc[None])[0])
        e = sc[min(K + 3, last)] - sc[K] if last > K else np.zeros(2)
        r['screen_exit_deg'] = round(float(np.degrees(np.arccos(np.clip(e @ sv / (np.linalg.norm(e) * np.linalg.norm(sv) + 1e-9), -1, 1)))), 1)
        vy = [-(sc[f][1] - sc[f - 1][1]) for f in range(K + 1, last + 1)]          # + = up on screen
        px = GATES['screen_rev_px']
        r['screen_down_up'] = any(a < -px / 2 and b > px / 2 for a, b in zip(vy, vy[1:]))
        r['screen_upacc'] = [K + 2 + i for i, (a, b) in enumerate(zip(vy, vy[1:])) if b - a > GATES['screen_upacc_px']]
        vx = [sc[f][0] - sc[f - 1][0] for f in range(K + 1, last + 1)]
        sx = np.sign(e[0]) if abs(e[0]) > 1 else 0
        r['screen_hrev'] = [K + 1 + i for i, x in enumerate(vx) if sx and x * sx < -px]
        r['size_ratio_max'] = size_ratio(Mw, last, K)
        if full:
            pen = -1.0
            for key in c.keys[:3]:
                P = partner_pts(key)
                for f in np.arange(K + 0.5, K + 4.01, 0.5):
                    f0 = int(np.floor(f)); a = f - f0
                    Gf = G[f0] if a == 0 else interp(G[f0], G[f0 + 1], a)
                    M = np.linalg.inv(c.arm.W(c.sh, f) @ Gf) @ c.arm.W(c.st, f)
                    pen = max(pen, box_signed(app(M, P)).max())
            r['restrike_mm'] = round(pen * 1000, 1)
        res.append(r)
    return res


def hard(bad): return [b for b in bad if ' exit ' not in b or 'screen exit' in b]


def exit_excess(rs): return max(0.0, max(r['exit_deg'] for r in rs) - GATES['exit_deg'])


def severity(rs):
    """how far the worst case misses the hard gates (for the fallback when none passes)"""
    T = GATES
    return max(max(0, r['size_ratio_max'] - T['size_ratio']) * 20 + max(0, T['eye_cm'] - r['eye_cm']) * 5
               + max(0, r['screen_exit_deg'] - T['screen_exit_deg']) + max(0, r['rise_cm'] - T['rise_cm']) * 3
               + max(0, r.get('restrike_mm', -1) - T['restrike_mm']) * 3 for r in rs)


def ok(rs, H, K=25):
    """the failed gates, one line per clip and gate"""
    T = GATES; bad = []
    for r in rs:
        n = f"{r['clip']}/{r['body']}"
        if r['eye_cm'] < T['eye_cm']: bad.append(f"{n} eye {r['eye_cm']}@{r['eye_f']}")
        if r['rise_cm'] > T['rise_cm']: bad.append(f"{n} rise {r['rise_cm']}")
        if r['exit_deg'] > T['exit_deg']: bad.append(f"{n} exit {r['exit_deg']}")
        if r['reappear']: bad.append(f"{n} reappears {r['reappear'][:3]}")
        if r['max_ay_mm_f2'] is not None and r['max_ay_mm_f2'] > T['ay_mm_f2']: bad.append(f"{n} upward accel {r['max_ay_mm_f2']}")
        if r['rev']: bad.append(f"{n} reversal {r['rev'][:3]}")
        if r.get('restrike_mm', -1) > T['restrike_mm']: bad.append(f"{n} restrike {r['restrike_mm']}")
        if r['screen_exit_deg'] > T['screen_exit_deg']: bad.append(f"{n} screen exit {r['screen_exit_deg']}")
        if r['screen_down_up']: bad.append(f"{n} screen down-then-up")
        if r['screen_upacc']: bad.append(f"{n} screen upward accel {r['screen_upacc'][:3]}")
        if r['screen_hrev']: bad.append(f"{n} screen h reversal {r['screen_hrev'][:3]}")
        if r['size_ratio_max'] > T['size_ratio']: bad.append(f"{n} size x{r['size_ratio_max']}")
    if H > K + T['hide_after'] or H >= T['hide_before']: bad.append(f'hidden only at f{H}')
    return bad


def solve(cs, rings=6, per=24, speeds=SPEEDS, spins=SPINS, gunvels=GUNVEL, top=40):
    """Search the flight of one pick over its cases. Returns (flight fields of the spec entry, report).
    Grid: directions in a 25 deg cone around the mean push (rings x per), speeds, gun velocity modes, spins. Order: hard
    gates, severity, gun-relative exit excess, cost; the best `top` are re-checked with the restrike test."""
    K = cs[0].K; Sd = cs[0].sh
    Wm = MT.mean_pose([c.arm for c in cs], Sd)
    nbar = np.mean([c.n for c in cs], 0); nbar /= np.linalg.norm(nbar)
    up = Wm[K][:3, :3] @ UPJ
    best = []
    for d in cone(nbar, GATES['exit_deg'], rings, per):
        if max(np.degrees(np.arccos(np.clip(d @ c.n, -1, 1))) for c in cs) > GATES['exit_deg']: continue
        ax = np.cross(d, up)
        for s in speeds:
            for gv in gunvels:
                for w in spins:
                    G, S_ = MT.flight(Wm, K, s * d, ax, w, 99, centre=MAGC, gunvel=gv)
                    rs = evaluate(cs, G, S_, full=False)
                    H = max(r['last_vis'] for r in rs)
                    bad = ok(rs, H, K)
                    ang = float(np.degrees(np.arccos(np.clip(d @ nbar, -1, 1))))
                    cost = (100 * len(bad) + sum(max(0, 20 - r['eye_cm']) * 10 for r in rs) + ang * 0.5 + (H - K) * 2
                            + abs(s - 1.2) * 5 + abs(abs(w) - 360) / 360 + GUNVEL.index(gv) * 3)
                    best.append((cost, d, s, (w, gv), H, bad, (severity(rs), exit_excess(rs))))
    if not best:
        raise SystemExit('no direction is within the exit gate of every clip push: the clips of this pick push too far apart')
    best.sort(key=lambda x: (len(hard(x[5])) > 0, x[6][0], len(hard(x[5])), x[6][1], x[0]))
    chosen = None
    for cost, d, s, (w, gv), H, bad, _ in best[:top]:
        G, S_ = MT.flight(Wm, K, s * d, np.cross(d, up), w, H, centre=MAGC, gunvel=gv)
        rs = evaluate(cs, G, S_, full=True)
        b2 = ok(rs, H, K)
        k2 = (len(hard(b2)) > 0, severity(rs), len(hard(b2)), exit_excess(rs), cost)
        if chosen is None or k2 < chosen[7]: chosen = (cost, d, s, (w, gv), H, b2, rs, k2)
        if not b2: break
    cost, d, s, (w, gv), H, bad, rs, _ = chosen
    entry = dict(side=Sd, K=K, v=(s * d).tolist(), axis=np.cross(d, up).tolist(), spin=w, H=int(H),
                 centre=MAGC.tolist(), gunvel=gv)
    rep = dict(push_mean=nbar.tolist(), dir=d.tolist(), speed=s, spin=w, gunvel=gv, H=int(H),
               dir_vs_mean_deg=round(float(np.degrees(np.arccos(np.clip(d @ nbar, -1, 1)))), 1),
               dir_vs_clip_push_max_deg=round(max(float(np.degrees(np.arccos(np.clip(d @ c.n, -1, 1)))) for c in cs), 1),
               fails=bad, cases=rs, contacts={c.name + '/' + c.body: c.contacts for c in cs})
    return entry, rep


def summary(rep):
    cs = rep['cases']
    return (f"dir {np.round(rep['dir'], 2)} {rep['speed']} m/s spin {rep['spin']} {rep['gunvel']} H{rep['H']} | "
            f"eye {min(c['eye_cm'] for c in cs)} rise {max(c['rise_cm'] for c in cs)} exit {max(c['exit_deg'] for c in cs)} "
            f"scr {max(c['screen_exit_deg'] for c in cs)} size x{max(c['size_ratio_max'] for c in cs)} "
            f"ay {max((c['max_ay_mm_f2'] if c['max_ay_mm_f2'] is not None else -99) for c in cs)} "
            f"restrike {max(c.get('restrike_mm', -99) for c in cs)} | fails {len(rep['fails'])} {rep['fails'][:3]}")


def print_cases(cs):
    for c in cs:
        print(f'{c.name:36s} {c.body} push {np.round(c.n, 3)} |v| {c.vrel:.2f} contacts {{' +
              ', '.join(f'{k}: {v:.2f}' if v is not None else f'{k}: -' for k, v in c.contacts.items()) + '}', flush=True)


def search(spec, name, clips_dir=None, rings=6, per=24, out=None, spec_path=None, **kw):
    """Search one pick ('<set>_<pick>') and write flight_<pick>.json. Returns (entry, report)."""
    key, pi = g.find_pick(spec, name)
    cs = cases(spec, key, pi, clips_dir, **kw)
    print_cases(cs)
    flight, rep = solve(cs, rings=rings, per=per)
    entry = dict(clips=g.raw_clips(key, pi, spec_path), **flight)
    print(g.pick_id(key, entry), summary(rep), flush=True)
    if out:
        p = f'{out}/flight_{g.pick_id(key, entry)}.json'
        json.dump(dict(set=key, pick=pi, entry=entry, report=rep), open(p, 'w'), indent=1, default=float); print('wrote', p)
    return entry, rep


if __name__ == '__main__':
    a = sys.argv[1:]; opt = g.common.opt
    sp = opt(a, '--spec'); spec = g.load_spec(sp); cdir = opt(a, '--clips')
    out = opt(a, '--out') or g.common.work('magtrack', 'flight')
    rings, per = int(opt(a, '--rings', 6)), int(opt(a, '--per', 24)); dj = opt(a, '--delta')
    kw = dict(lo=int(opt(a, '--lo', 20)))
    os.makedirs(out, exist_ok=True)
    if dj:
        sys.path.insert(0, os.path.join(g.HERE, 'reaim'))
        import reaim_core
    for name in a:
        if dj:
            key, pi = g.find_pick(spec, name)
            kw['arm_of'] = reaim_core.arm_of(reaim_core.load_delta(dj), reaim_core.striker(spec, key, pi))
        search(spec, name, cdir, rings, per, out, sp, **kw)
