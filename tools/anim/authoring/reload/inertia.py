"""Inertia model for one-handed reload drafts (SMG/shotgun FRONT round 4). Reusable: any draft that writes a hand
target timeline (rlib2.TL) gets a simulated gun from it and a physical magazine track.

Units: metres, radians, frames (30 fps). Gravity G = 9.81 m/s2 = 0.0109 m/frame2, no drag.

Gun (simulate_gun)
  The gun is a mass on the arm. The hand target (TL arrays: grip offset, gun angles) pulls it through an underdamped
  spring-damper, position and rotation separately (wp, zp; wr, zr per take; the heavy take is softer):
      x'' = wp^2 (xt - x) + 2 zp wp (vt - v)
      w'  = wr^2 log(qt q^-1) + 2 zr wr (wt - w) - trail * I^-1 (rc x x'')     (per gun axis, see below)
  so big moves overshoot and settle, stops rebound, rotation lags translation (wr < wp), and the muzzle trails: the
  last term is the torque of the gun's own inertia about the grip when the grip accelerates (rc: centre of the gun's
  surface points from the grip; the inertia tensor about the grip from the same points; trail < 1 because the wrist
  resists). Rotation is solved per gun axis: a gun has far less inertia about its bore than about pitch and yaw
  (Saratoga 13x, Zhuo 23x), so the roll axis is stiffer: wr * sqrt(I_pitch / I_axis), at most `cap` (2.5) times.
  Guides: while the fresh magazine is in the well (the last 10 cm of the insertion) the well steers the gun: lateral
  offset and rotation are blended onto the seat pose, the slide along the well stays simulated.
  Impulses (contacts, the cocking piece): a velocity step at a frame. Contacts: a one-sided plane (the fresh magazine
  on its rig); the grip cannot pass it, the normal velocity is reflected with restitution e and the impact speed
  gives an angular jolt. 16 substeps per frame, semi-implicit Euler. Output: per frame grip offset and gun angles.

Magazine (simulate_mag)
  Seated until the release frame (latch). Then a frictionless slide along the well: each substep it moves as a free
  body under gravity and is projected back onto the well line of the gun (position-based), so the pseudo-forces of a
  moving, turning gun (linear acceleration, centrifugal, Euler; Coriolis is taken by the walls) act along the well
  without being written out. It cannot go back past the seat. Free once `clear` metres out (default 0.11): then a
  rigid body with the velocity it has and the gun's angular velocity, gravity only; gone at the floor (centre 0.08 m).
  Fresh magazine 'rig': world-fixed at the gun's seat pose on the seated frame, from `appear` (the old one has landed).
  Track format as magtrack2/3/4: frames [{'m', 's', 'state'}], release, free_from, gone, exit_gun_axes, enter_gun_axes.

Stats: gun_stats (overshoot cm/deg and rebound at each stop, settle frames, rotation lag, muzzle trail, seat jolt),
mag_stats (slide frames, exit speed, gun speed at release, ratio, spin, share of each pseudo-force along the well).
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import author, rchecks
from fk import qmul, qinv, qrot
from magtrack2 import m4, rot_axis, log_rot, vanilla, G_ACC

GV = np.array([0.0, -G_ACC, 0.0])
# per take: position (wp rad/frame, zp), rotation (wr, zr), muzzle trail share, impulse gain, seat restitution
MODEL = {'A': {'wp': 1.45, 'zp': 0.42, 'wr': 1.05, 'zr': 0.40, 'trail': 0.30, 'imp': 1.7, 'e': 0.30, 'jolt': 1.6, 'cap': 2.5},
         'B': {'wp': 1.10, 'zp': 0.40, 'wr': 0.80, 'zr': 0.38, 'trail': 0.35, 'imp': 1.7, 'e': 0.25, 'jolt': 1.9, 'cap': 2.5}}
SUB = 16


# ------------------------------------------------------------------------------------------------ quaternion helpers
def qnorm(q): q = np.asarray(q, float); return q / np.linalg.norm(q)


def qexp(v):
    a = float(np.linalg.norm(v))
    if a < 1e-12: return np.array([0.0, 0.0, 0.0, 1.0])
    return np.array([*(v / a * math.sin(a / 2)), math.cos(a / 2)])


def qlog(q):
    """Rotation vector (world) of a unit quaternion, shortest way."""
    q = qnorm(q)
    if q[3] < 0: q = -q
    s = float(np.linalg.norm(q[:3]))
    if s < 1e-12: return np.zeros(3)
    return q[:3] / s * 2 * math.atan2(s, q[3])


def slerp(a, b, t):
    if np.dot(a, b) < 0: b = -b
    return qnorm(qmul(qexp(qlog(qmul(b, qinv(a))) * t), a))


def qmat(q): return m4(np.zeros(3), q)[:3, :3]


def euler_of(R, prev=None):
    """(pitch, yaw, roll) in degrees with R = Rx(p) Ry(y) Rz(r) (author.qeuler order), unwrapped next to prev."""
    y = math.asin(max(-1.0, min(1.0, R[0, 2]))); p = math.atan2(-R[1, 2], R[2, 2]); r = math.atan2(-R[0, 1], R[0, 0])
    e = np.degrees([p, y, r])
    if prev is not None:
        alt = np.array([e[0] + 180, 180 - e[1], e[2] + 180])        # the other solution of the same rotation
        best = None
        for cand in (e, alt):
            c = cand + 360 * np.round((np.asarray(prev) - cand) / 360)
            if best is None or np.abs(c - prev).sum() < np.abs(best - prev).sum(): best = c
        e = best
    return e


# ------------------------------------------------------------------------------------------------ gun
def gun_inertia(gid):
    """Centre of the gun's surface points from the grip (gun axes) and the inertia tensor per unit mass about the grip."""
    P = rchecks.gun_points(gid); rc = P.mean(0); I = (P ** 2).sum(1).mean() * np.eye(3) - (P.T @ P) / len(P)
    return rc, I


def simulate_gun(c, take, Pt, Rt, impulses=(), contacts=(), guides=(), fade=3, model=None):
    """Pt (N,3) grip offsets, Rt (N,3) gun angles of the hand target. impulses: [(frame, dv world m/f, dw gun-axes rad/f)].
    contacts: [{'f': [f0, f1], 'anchor': grip offset on the plane, 'n': world unit normal the gun moves into,
    'e': restitution, 'axis': gun-axes jolt axis}]. guides: [{'f': [f0, f1], 'seat': frame}] insertion windows.
    Returns dict X (N,3), E (N,3) angles, Q world quats, events."""
    M = dict(MODEL[take]); M.update(model or {}); N = len(Pt); wp, zp, wr, zr = M['wp'], M['zp'], M['wr'], M['zr']
    rc_l, I = gun_inertia(c.gun); Iinv = np.linalg.inv(I); q0 = np.array(c.q0, float)
    W = wr * np.minimum(M['cap'], np.sqrt(I[0, 0] / np.diag(I)))          # per gun axis (pitch, yaw, roll)
    QT = [qnorm(qmul(q0, author.qeuler(*Rt[f]))) for f in range(N)]
    x = np.array(Pt[0], float); v = np.zeros(3); q = QT[0].copy(); w = np.zeros(3); h = 1.0 / SUB
    X = [x.copy()]; Q = [q.copy()]; A = [np.zeros(3)]; events = []
    imp = {}
    for f, dv, dw in impulses: imp.setdefault(int(f), []).append((np.asarray(dv, float), np.asarray(dw, float)))
    for f in range(1, N):
        p0, p1 = np.asarray(Pt[f - 1], float), np.asarray(Pt[f], float); vt = p1 - p0
        wt = qlog(qmul(QT[f], qinv(QT[f - 1])))
        acc = np.zeros(3)
        for s in range(1, SUB + 1):
            t = s * h; xt = p0 + vt * t; qt = slerp(QT[f - 1], QT[f], t)
            a = wp * wp * (xt - x) + 2 * zp * wp * (vt - v)
            qi = qinv(q); el = qrot(qi, qlog(qmul(qt, qinv(q)))); dl = qrot(qi, wt - w); al_l = qrot(qi, a)
            al = W * W * el + 2 * zr * W * dl - M['trail'] * (Iinv @ np.cross(rc_l, al_l))
            v = v + a * h; x = x + v * h; w = w + qrot(q, al) * h; q = qnorm(qmul(qexp(w * h), q)); acc += a / SUB
            for ct in contacts:
                if not (ct['f'][0] <= f <= ct['f'][1]): continue
                n = np.asarray(ct['n'], float); d = float((x - ct['anchor']) @ n); vn = float(v @ n)
                if d > 0 and vn > 0:
                    x = x - d * n; v = v - (1 + ct.get('e', M['e'])) * vn * n
                    w = w + qrot(q, np.asarray(ct.get('axis', (1, 0, 0)), float)) * vn * ct.get('jolt', M['jolt'])
                    if vn > 0.005: events.append({'kind': 'contact', 'name': ct.get('name', 'seat'), 'f': round(f - 1 + t, 2), 'impact_cm_f': round(vn * 100, 2), 'rebound_cm_f': round(vn * ct.get('e', M['e']) * 100, 2)})
        for dv, dw in imp.get(f, []):
            v = v + dv * M['imp'] * wp; w = w + qrot(q, dw * W) * M['imp']
        X.append(x.copy()); Q.append(q.copy()); A.append(acc)
    X = np.array(X); Q = np.array(Q)
    for gd in guides:          # the well steers the gun onto the magazine: lateral and rotation onto the seat pose
        f0, f1 = gd['f']; se = gd['seat']; xs, qs = X[se].copy(), Q[se].copy(); ax = qrot(qs, np.asarray(gd['axis'], float)); ax /= np.linalg.norm(ax)
        for f in range(f0, f1 + 1):
            b = min(1.0, (f - f0 + 1) / 3.0); xg = xs + float((X[f] - xs) @ ax) * ax
            X[f] = X[f] + (xg - X[f]) * b; Q[f] = slerp(Q[f], qs, b)
    # last frames: blend into the target (the clip must end exactly in the idle)
    for j in range(fade):
        f = N - 1 - j; b = (j + 0.0) / fade
        X[f] = Pt[f] + (X[f] - Pt[f]) * b; Q[f] = slerp(QT[f], Q[f], b)
    E = []; prev = None
    for f in range(N):
        R = qmat(qmul(qinv(q0), Q[f])); prev = euler_of(R, prev); E.append(prev)
    return {'X': X, 'E': np.array(E), 'Q': Q, 'QT': np.array(QT), 'Pt': np.asarray(Pt, float), 'A': np.array(A), 'events': events, 'model': dict(M, W=[round(float(x), 3) for x in W])}


def target_stops(Pt, QT, vmin=2.0, wmin=3.0):
    """Frames where the target arrives after a move (translation over vmin cm/f or rotation over wmin deg/f in the
    frame before, under a quarter of that after)."""
    N = len(Pt); V = np.r_[0, np.linalg.norm(np.diff(Pt, axis=0), axis=1) * 100]
    W = np.r_[0, [math.degrees(np.linalg.norm(qlog(qmul(QT[f], qinv(QT[f - 1]))))) for f in range(1, N)]]
    out = []
    for f in range(2, N - 1):
        if (V[f] > vmin and V[f + 1] < 0.25 * V[f]) or (W[f] > wmin and W[f + 1] < 0.25 * W[f]): out.append(f)
    return out, V, W


def gun_stats(sim, marks=None):
    """Per stop: overshoot (cm along the arriving direction, deg about the arriving rotation axis), rebound (back past
    the target), settle frames (error under 0.3 cm and 1 deg until the target moves again or 12 frames); rotation lag
    (frames, cross-correlation of target and gun angular speed); muzzle trail (largest angle gun to target while the
    target moves over 3 cm/f); seat impacts."""
    X, Q, Pt, QT = sim['X'], sim['Q'], sim['Pt'], sim['QT']; N = len(X)
    stops, V, W = target_stops(Pt, QT)
    err_p = np.linalg.norm(X - Pt, axis=1) * 100
    err_r = np.array([math.degrees(np.linalg.norm(qlog(qmul(Q[f], qinv(QT[f]))))) for f in range(N)])
    rows = []
    for s in stops:
        u = Pt[s] - Pt[s - 1]; un = np.linalg.norm(u); u = u / un if un > 1e-9 else np.zeros(3)
        ax = qlog(qmul(QT[s], qinv(QT[s - 1]))); an = np.linalg.norm(ax); ax = ax / an if an > 1e-9 else np.zeros(3)
        nxt = next((f for f in range(s + 1, N) if V[f] > 0.3 or W[f] > 0.5), N); win = range(s, min(nxt, s + 12, N))
        dp = [float((X[f] - Pt[f]) @ u) * 100 for f in win]; dr = [math.degrees(float(qlog(qmul(Q[f], qinv(QT[f]))) @ ax)) for f in win]
        ov = max([0.0] + dp); orot = max([0.0] + dr)
        ipk = int(np.argmax(dp)) if dp else 0; reb = max([0.0] + [-d for d in dp[ipk:]]) if ov > 0.2 else 0.0     # back past the target after an overshoot (lag alone is not a rebound)
        st = next((j for j in range(len(win)) if all(err_p[f] < 0.3 and err_r[f] < 1.0 for f in list(win)[j:])), None)
        rows.append({'f': s, 'arrive_cm_f': round(float(V[s]), 1), 'arrive_deg_f': round(float(W[s]), 1), 'overshoot_cm': round(ov, 2), 'overshoot_deg': round(orot, 2),
                     'rebound_cm': round(reb, 2), 'settle_f': st if st is not None else f'>{len(win)}'})
    ws = np.r_[0, [math.degrees(np.linalg.norm(qlog(qmul(Q[f], qinv(Q[f - 1]))))) for f in range(1, N)]]
    def xlag(a, b):
        a = a - a.mean(); b = b - b.mean(); L = range(-2, 7); cc = [float(np.dot(a[max(0, -l):N - max(0, l)], b[max(0, l):N - max(0, -l)])) for l in L]
        i = int(np.argmax(cc))
        if 0 < i < len(cc) - 1:
            d = cc[i - 1] - 2 * cc[i] + cc[i + 1]; return round(L[i] + (0.5 * (cc[i - 1] - cc[i + 1]) / d if d != 0 else 0), 2)
        return float(L[i])
    vs = np.r_[0, np.linalg.norm(np.diff(X, axis=0), axis=1) * 100]
    moving = [f for f in range(N) if V[f] > 3.0]
    fw = lambda qq: qrot(qq, np.array([0.0, 0.0, -1.0]))       # the muzzle direction: roll about the bore does not count
    trail = max([math.degrees(math.acos(np.clip(fw(Q[f]) @ fw(QT[f]), -1, 1))) for f in moving] or [0.0])
    return {'stops': rows, 'overshoot_cm_max': round(max([r['overshoot_cm'] for r in rows] or [0]), 2), 'overshoot_deg_max': round(max([r['overshoot_deg'] for r in rows] or [0]), 2),
            'rebound_cm_max': round(max([r['rebound_cm'] for r in rows] or [0]), 2),
            'settle_f_max': max([r['settle_f'] for r in rows if isinstance(r['settle_f'], int)] or [0]),
            'rot_lag_f': xlag(W, ws), 'pos_lag_f': xlag(V, vs), 'muzzle_trail_deg': round(float(trail), 2),
            'err_peak_cm': round(float(err_p.max()), 2), 'err_peak_deg': round(float(err_r.max()), 2), 'impacts': sim['events']}


# ------------------------------------------------------------------------------------------------ magazine
class GunPath:
    """Gun world pose at fractional frames: position Catmull-Rom through the frames, rotation slerp."""
    def __init__(self, G):
        self.T = np.array([np.asarray(t, float) for t, q in G]); self.Q = [qnorm(q) for t, q in G]; self.N = len(G)
        for i in range(1, self.N):
            if np.dot(self.Q[i], self.Q[i - 1]) < 0: self.Q[i] = -self.Q[i]

    def pos(self, t):
        i = min(int(math.floor(t)), self.N - 2); u = t - i; T = self.T
        p0, p1, p2, p3 = T[max(i - 1, 0)], T[i], T[i + 1], T[min(i + 2, self.N - 1)]
        return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)

    def rot(self, t):
        i = min(int(math.floor(t)), self.N - 2); return slerp(self.Q[i], self.Q[i + 1], t - i)

    def omega(self, t):
        i = min(int(math.floor(t)), self.N - 2); return qlog(qmul(self.Q[i + 1], qinv(self.Q[i])))

    def mat(self, t): return m4(self.pos(t), self.rot(t))


def simulate_mag(gid, clip, G, plan, bodies=None):
    """plan: release (frame the latch lets go), seated, appear (earliest frame of the fresh one), lead (it exists at the
    latest this many frames before the seat, default 5), clear (m), floor (m). Returns the track."""
    v = vanilla(gid, clip); S = v['seat']; cen = np.r_[v['centre'], 1]; N = len(G); ex = np.array(plan.get('exit') or v['exit'], float); ex /= np.linalg.norm(ex)
    gp = GunPath(G); GW = [m4(np.asarray(t), np.asarray(q)) for t, q in G]; r = int(plan['release']); se = int(plan['seated'])
    clear = plan.get('clear', 0.11); floor = plan.get('floor', 0.08); lead = int(plan.get('lead', 5))
    T = lambda d: np.block([[np.eye(3), np.asarray(d, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
    c0 = (S @ cen)[:3]                                         # magazine centre in gun axes, seated
    line = lambda t: (gp.pos(t) + qrot(gp.rot(t), c0), qrot(gp.rot(t), ex))
    Wm = {f: GW[f] @ S for f in range(r + 1)}; state = {f: 'seated' for f in range(r + 1)}; svals = {}
    h = 1.0 / SUB; s = 0.0; t = float(r); L0, e = line(t); p = L0.copy(); pb, _ = line(t - h); vel = (p - pb) / h
    comp = []      # per substep along-well relative acceleration split: gravity, gun linear, gun rotation
    accs = []      # (time, world acceleration) of the guided magazine per substep
    f = r; free_t = None
    while f < N - 1 and free_t is None:
        f += 1
        for k in range(SUB):
            t1 = t + h; pred = p + vel * h + GV * h * h; L1, e1 = line(t1)
            s = max(0.0, float((pred - L1) @ e1)); pn = L1 + s * e1; vn = (pn - p) / h; accs.append((t1, (vn - vel) / h)); vel = vn; p = pn; t = t1
            if s >= clear: free_t = t; break
        Wm[f] = GW[f] @ T(ex * s) @ S if free_t is None else None; svals[f] = s; state[f] = 'guided'
        if free_t is not None: break
    # split of the along-well pull over the slide (frames r..f): gravity, the grip's acceleration, the turning
    tt = np.arange(r + 0.5, min(f, N - 2) + 0.5, 0.25)
    for t2 in tt:
        e2 = qrot(gp.rot(t2), ex); d = 0.05; P = lambda tq: gp.pos(tq) + qrot(gp.rot(tq), c0 + ex * 0.0)
        a_tot = (P(t2 + d) - 2 * P(t2) + P(t2 - d)) / d / d; a_lin = (gp.pos(t2 + d) - 2 * gp.pos(t2) + gp.pos(t2 - d)) / d / d
        comp.append((float(GV @ e2), float(-a_lin @ e2), float(-(a_tot - a_lin) @ e2)))
    om = gp.omega(min(free_t if free_t else f, N - 1.001))
    # free flight from the free moment: rigid body, gravity only, substeps; optional contacts with a body patch
    gone = None; bounces = []
    if free_t is not None:
        R = qmat(gp.rot(free_t)) @ S[:3, :3]; c = p.copy(); vf = vel.copy(); w = om.copy(); tf = free_t
        PL, Il = mag_body(gid, clip); Iinv_l = np.linalg.inv(Il); hits = plan.get('hits', []); bodies = dict(bodies or {}, gun=gp)
        def frame_pose(c, R):
            M = np.eye(4); M[:3, :3] = R; M[:3, 3] = c - R @ cen[:3]; return M
        g = int(math.ceil(free_t - 1e-9))
        while g < N:
            while tf < g - 1e-9:
                hh = min(h, g - tf); c = c + vf * hh + 0.5 * GV * hh * hh; vf = vf + GV * hh; R = rot_axis(w, np.linalg.norm(w) * hh) @ R; tf += hh
                for hit in hits:
                    if not (hit['f'][0] <= tf <= hit['f'][1]): continue
                    bp = bodies[hit['body']]; Mb = bp.mat(tf); Mb2 = bp.mat(min(tf + 0.05, N - 1.0)); n = Mb[:3, :3] @ np.asarray(hit['n'], float); n /= np.linalg.norm(n)
                    P0 = (Mb @ np.r_[hit['p'], 1])[:3]; Pw = (R @ (PL - cen[:3]).T).T + c
                    d = (Pw - P0) @ n; lat = np.linalg.norm((Pw - P0) - np.outer(d, n), axis=1); ok = (d < 0) & (lat < hit['rad'])
                    if not ok.any(): continue
                    k = int(np.argmin(np.where(ok, d, 9))); rr = Pw[k] - c; loc = np.linalg.inv(Mb) @ np.r_[Pw[k], 1]; vb = ((Mb2 @ loc)[:3] - Pw[k]) / 0.05
                    vrel = vf + np.cross(w, rr) - vb; vn = float(vrel @ n)
                    c = c - d[k] * n
                    if vn >= 0: continue
                    Iw_inv = R @ Iinv_l @ R.T; den = 1.0 + float(n @ np.cross(Iw_inv @ np.cross(rr, n), rr)); j = -(1 + hit.get('e', 0.35)) * vn / den
                    vt = vrel - vn * n; tn = np.linalg.norm(vt); J = j * n
                    if tn > 1e-9: J = J - min(hit.get('mu', 0.3) * j, tn / den) * vt / tn
                    v0 = float(np.linalg.norm(vf)); vf = vf + J; w = w + Iw_inv @ np.cross(rr, J)
                    bounces.append({'t': round(tf, 2), 'body': hit['body'], 'in_cm_f': round(-vn * 100, 2), 'speed_before': round(v0 * 100, 2), 'speed_after': round(float(np.linalg.norm(vf)) * 100, 2), 'impulse': [float(x) for x in J]})
            if c[1] < floor: gone = g; break
            if g >= free_t - 1e-9: Wm[g] = frame_pose(c, R); state[g] = 'falling'
            g += 1
    else: vf = vel; pf = p
    gone = gone or N
    appear = min(max(int(plan.get('appear', 0)), gone if gone < N else 0), se - lead)
    fresh = GW[se] @ S; out = []; FR = fresh_track(plan.get('fresh') or {'kind': 'rig'}, GW, S, ex, cen, se, appear)
    for fr in range(N):
        if fr < min(gone, appear) and Wm.get(fr) is not None:
            M = np.linalg.inv(GW[fr]) @ Wm[fr]; sc = 1.0; st = state[fr]
        elif fr in FR: Mw, st = FR[fr]; M = np.linalg.inv(GW[fr]) @ Mw if st != 'carried' else Mw; sc = 1.0
        elif appear <= fr < se: M = np.linalg.inv(GW[fr]) @ fresh; sc = 1.0; st = 'fresh'
        elif fr >= se: M = S; sc = 1.0; st = 'seated'
        else: M = S; sc = 0.0; st = 'gone'
        out.append({'m': [round(float(x), 6) for x in M.ravel()], 's': sc, 'state': st})
    ff = next((fr for fr in range(r + 1, N) if out[fr]['state'] == 'falling'), None)
    comp = np.array(comp) if comp else np.zeros((1, 3))
    phys = {'bounces': bounces, 'free_t': None if free_t is None else round(free_t, 2), 'slide_frames': None if free_t is None else round(free_t - r, 2),
            'exit_v_cm_f': round(float(np.linalg.norm(vel)) * 100, 2), 'exit_dir': [round(float(x), 3) for x in (vel / (np.linalg.norm(vel) or 1))],
            'spin_deg_f': round(math.degrees(float(np.linalg.norm(om))), 1), 'acc_guided': [[round(t, 4), [float(x) for x in a]] for t, a in accs],
            'pull_mean_g': {'gravity': round(float(comp[:, 0].mean() / G_ACC), 2), 'gun_linear': round(float(comp[:, 1].mean() / G_ACC), 2), 'gun_turning': round(float(comp[:, 2].mean() / G_ACC), 2)}}
    return {'gun': gid, 'clip': clip, 'plan': plan, 'release': r, 'free_from': ff if ff is not None else N, 'gone': gone, 'frames': out, 'phys': phys,
            'exit_gun_axes': [round(float(x), 3) for x in ex], 'enter_gun_axes': [round(float(x), 3) for x in v['enter']]}


def fresh_track(fp, GW, S, ex, cen, se, appear):
    """The fresh magazine before the seat, per frame {frame: (4x4, state)} (world, or gun-relative for 'carried').
    Frames not listed fall back to the rig: world-fixed at the gun's seat pose on the seated frame (state 'fresh').
      rig      nothing extra.
      pop      the rig pushes it up its own axis `rise` m (spring, eased) from `p0` to the seat frame: the gun is
               driven down onto a magazine still coming up to meet it ('presented').
      toss     the rig flips it up from `below` m under the catch point from frame `launch`: free flight under gravity,
               turning half a turn (end over end) into the pose of the seat, and caught on the seated frame by the
               upside-down gun, well up ('tossed'); before the launch it sits in the rig ('rig').
      slap     the gun picks it up at frame `pick` half in (`d0` m out of the well) from a rig and carries it
               ('carried', gun-relative); where the gun comes down to `d0` from the seat on the thigh its base meets
               the thigh and it stops there ('pressed'), the gun runs on over it to the seat."""
    k = fp.get('kind', 'rig'); F = GW[se] @ S; out = {}
    T = lambda d: np.block([[np.eye(3), np.asarray(d, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
    Ew = GW[se][:3, :3] @ (-ex)                                   # direction the magazine travels into the well, world
    if k == 'pop':
        p0, rise = int(fp.get('p0', se - 6)), fp.get('rise', 0.07)
        for f in range(appear, se):
            u = 0.0 if f <= p0 else (f - p0) / (se - p0); d = rise * (1 - (1 - u) ** 2)
            M = F.copy(); M[:3, 3] -= Ew * (rise - d); out[f] = (M, 'presented' if f > p0 else 'rig')
    elif k == 'toss':
        fl, below = int(fp['launch']), fp.get('below', 0.10); Tn = se - fl; u = (below + 0.5 * G_ACC * Tn * Tn) / Tn
        cF = (F @ cen)[:3]; RF = F[:3, :3]; Rr = rot_axis([0, 0, 1], math.pi) @ RF       # in the rig: base down
        def pose(R, c): M = np.eye(4); M[:3, :3] = R; M[:3, 3] = c - R @ cen[:3]; return M
        vy = u - G_ACC * Tn; ew = Ew / np.linalg.norm(Ew); hv = np.array([ew[0], 0.0, ew[2]]) / max(abs(ew[1]), 1e-6) * abs(vy)   # caught along a tilted well: the toss carries it sideways so it arrives along the axis
        for f in range(appear, se):
            if f <= fl: out[f] = (pose(Rr, cF - np.array([0, below, 0]) - hv * Tn), 'rig'); continue
            t = f - fl; y = -below + u * t - 0.5 * G_ACC * t * t; ang = math.pi * (1 - t / Tn)
            out[f] = (pose(rot_axis([0, 0, 1], ang) @ RF, cF + np.array([0, y, 0]) + hv * (f - se)), 'tossed')
        out['_u'] = u
    elif k == 'slap':
        pk, d0 = int(fp['pick']), fp.get('d0', 0.06); Rg = GW[pk] @ T(ex * d0) @ S
        a0 = (F @ cen)[:3]; ax = Ew / np.linalg.norm(Ew)
        fs = next((f for f in range(pk + 1, se) if float(((GW[f] @ S @ cen)[:3] - a0) @ -ax) <= d0 + 1e-4), se - 1)
        for f in range(appear, se):
            if f < pk: out[f] = (Rg, 'rig')
            elif f < fs: out[f] = (T(ex * d0) @ S, 'carried')
            else: out[f] = (F, 'pressed')
        out['_fs'] = fs
    return {f: v for f, v in out.items() if not isinstance(f, str)}


_mb = {}


def mag_body(gid, clip):
    """Contact points of the magazine (mesh vertices, every 25th, mag axes) and its inertia tensor per unit mass
    about the centre (from the vertices)."""
    if gid in _mb: return _mb[gid]
    import gungeo, common
    V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb'))[::25]; c = vanilla(gid, clip)['centre']; d = V - c
    I = (d ** 2).sum(1).mean() * np.eye(3) - (d.T @ d) / len(d); _mb[gid] = (V, I); return _mb[gid]


def mag_stats(gid, clip, track, G):
    """Exit speed (world, at the free moment) against the gun's speed at the magazine over the 3 frames up to the
    release; their ratio; the clearance of the free magazine from the gun over its first 6 free frames (cm, mesh
    points against gun points; negative = through the gun)."""
    import gungeo, common
    v = vanilla(gid, clip); cen = np.r_[v['centre'], 1]; S = v['seat']; r = track['release']
    C = [(m4(*G[f]) @ S @ cen)[:3] for f in range(max(r - 3, 0), r + 1)]
    gun = max(float(np.linalg.norm(C[i + 1] - C[i])) for i in range(len(C) - 1)) * 100
    ph = track['phys']; ex = ph['exit_v_cm_f']; ratio = ex / gun if gun > 0.5 else None
    Vm = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb'))[::7]; V1 = np.c_[Vm, np.ones(len(Vm))]
    PG = rchecks.gun_points(gid)[::4]; ff = track['free_from']; worst = 9e9
    tb = min([b['t'] for b in ph.get('bounces', []) if b['body'] == 'gun'] or [9e9])     # a bat is a planned contact
    for f in range(ff, min(ff + 6, len(G), int(math.floor(tb)))):
        row = track['frames'][f]
        if row['state'] != 'falling': break
        MP = (V1 @ np.array(row['m']).reshape(4, 4).T)[:, :3]          # gun axes
        d = np.sqrt(((MP[::2, None, :] - PG[None, :, :]) ** 2).sum(2)).min(); worst = min(worst, float(d))
    return {'exit_cm_f': ex, 'gun_cm_f': round(gun, 2), 'ratio': None if ratio is None else round(ratio, 2), 'slide_f': ph['slide_frames'], 'spin_deg_f': ph['spin_deg_f'],
            'pull_g': ph['pull_mean_g'], 'clear_cm': round(worst * 100, 2) if worst < 9e8 else None}
