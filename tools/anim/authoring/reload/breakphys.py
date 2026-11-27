"""Break-action physics for BREAK-OPEN round 2 (RESEARCH.md, section 2). Units m, rad, frames (30 fps) unless a name
says otherwise; gravity 9.81 m/s2. The barrels are a rigid body on the hinge pin of the game's own hinge (pin and
axis from the game's open pose, ref/<gun>_geometry.json); they never move by themselves:

  I theta'' = sum_i m_i (r_i x (g - a_i)) . h      inertia about the pin of the gun's motion and gravity
                                                    (a_i: acceleration the barrel point i would have if it were
                                                    fixed in the gun at the current angle: linear, Euler and
                                                    centrifugal terms of the gun's motion; Coriolis left out)
             - tau_cock    0 < theta < cock_deg, first opening only: the barrels cock both hammers (Anson and
                           Deeley cocking levers); once past cock_deg the sears hold the hammers
             + tau_ej      0 < theta < ej_deg, after the ejectors fired: closing compresses both ejector springs
                           again (Southgate type), they push the barrels open
             - friction    Coulomb torque on the pin and the forend iron (static and sliding)
  stops      open stop (the lump on the knuckle) with restitution e_stop; closed: the barrels come home on the
             bolt cam; the bolt springs into the bite only if the barrels arrive with at least w_latch, else the
             cam throws them back (restitution e_cam): latch energy E_latch = 1/2 I w_latch^2
  lever      the barrels are held shut until the thumb pushes the top lever (release frame); the lever comes back
             onto the lump once the barrels are 3 deg open (snap closing)
  contacts   a body surface (thigh, belt, hip, palm of the other forearm is not used) as a world plane: a barrel
             point cannot pass it, the plane turns the barrels (plastic contact, it moves with the gun's motion
             into it); listed per draft
  shells     spent: ride the chambers, the extractors lift them 7 mm over the opening; at the trip angle (while
             opening) the ejector springs throw them out along the chamber axis at v_eject on top of the barrels'
             velocity at the chamber; free flight with gravity and spin.
All spring and friction numbers are estimates (RESEARCH.md: unverified), chosen so that the barrels cannot fall open
or swing shut under gravity alone from the idle and do from a hard wrist snap.
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from magtrack2 import rot_axis

FPS = 30.0
G = 9.81
GV = np.array([0.0, -G, 0.0])           # m/s2 world (y up)
SUB = 24
GEO = {g: json.load(open(f'{renv.OUT}/ref/{g}_geometry.json')) for g in ('palica', 'satara')}
MESH = {'palica': 'w_shotgun_dual__rostovic_palica', 'satara': 'w_shotgun_dual__rostovic_satara'}

# per gun: barrel mass (kg), springs (J), zones (deg), friction (N m), restitutions, trip angle, ejection speed
PAR = {
    'palica': {'mass': 0.75, 'E_cock': 0.22, 'cock_deg': 14.0, 'E_ej': 0.16, 'ej_deg': 16.0, 'E_latch': 0.035, 'fric': 0.12,
               'e_stop': 0.22, 'e_cam': 0.3, 'trip_before_stop_deg': 4.0, 'v_eject': 3.2, 'extract_m': 0.007},
    'satara': {'mass': 1.55, 'E_cock': 0.70, 'cock_deg': 9.0, 'E_ej': 0.70, 'ej_deg': 11.0, 'E_latch': 0.05, 'fric': 0.45,
               'e_stop': 0.18, 'e_cam': 0.3, 'trip_before_stop_deg': 4.0, 'v_eject': 3.2, 'extract_m': 0.007},
}
_bar = {}


def gun_geo(gid): return GEO[gid]
def pivot(gid): return np.array(GEO[gid]['hinge_pivot'], float)
def axis(gid): h = np.array(GEO[gid]['hinge_axis'], float); return h / np.linalg.norm(h)
def tmax(gid): return math.radians(GEO[gid]['open_deg'])


def hinge_rot(gid, th):
    """4x4 in gun axes: the barrels turned th (rad, opening positive) about the pin."""
    q = pivot(gid); R = rot_axis(axis(gid), th); M = np.eye(4); M[:3, :3] = R; M[:3, 3] = q - R @ q; return M


def barrel(gid):
    """Points of the barrel block (mesh part skinned to 'barrel_hinge' and the parts riding on it), area-weighted
    surface samples treated as a thin shell; returns (points gun axes, closed), centre, k2 (radius of gyration about
    the pin squared), lever arm of the centre, inertia I (kg m2), latch speed (rad/s)."""
    if gid in _bar: return _bar[gid]
    from glb import Glb
    g = Glb(common.find('weapon_meshes', MESH[gid] + '__base1_01.glb')); sk = g.j['skins'][0]; names = [g.names[j] for j in sk['joints']]
    keep = {k for k, n in enumerate(names) if n not in ('barrel',)}       # 'barrel' is the fixed action block in this rig
    pts, wts = [], []
    for pr in g.j['meshes'][0]['primitives']:
        P = g.acc(pr['attributes']['POSITION']); J = g.acc(pr['attributes']['JOINTS_0']); W = g.acc(pr['attributes']['WEIGHTS_0'])
        idx = np.asarray(g.acc(pr["indices"])).astype(int).reshape(-1, 3); dom = np.asarray(J)[np.arange(len(J)), np.asarray(W).argmax(1)].astype(int)
        for t in idx:
            if not all(int(dom[v]) in keep for v in t): continue
            a, b, c = P[t[0]], P[t[1]], P[t[2]]; ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a))
            if ar > 0: pts.append((a + b + c) / 3); wts.append(ar)
    pts = np.array(pts); wts = np.array(wts); wts = wts / wts.sum()
    rng = np.random.default_rng(1); sel = rng.choice(len(pts), 400, p=wts, replace=True); S = pts[sel]
    q = pivot(gid); h = axis(gid); d = S - q; dp = d - np.outer(d @ h, h); k2 = float((dp ** 2).sum(1).mean())
    cen = S.mean(0); rc = float(np.linalg.norm((cen - q) - ((cen - q) @ h) * h)); m = PAR[gid]['mass']; I = m * k2
    wl = math.sqrt(2 * PAR[gid]['E_latch'] / I)
    _bar[gid] = {'pts': S, 'centre': cen, 'k2': k2, 'rc': rc, 'I': I, 'w_latch': wl, 'mass': m}
    return _bar[gid]


def summary(gid):
    """Numbers of the model for the page and RESEARCH.md."""
    b = barrel(gid); p = PAR[gid]; I = b['I']; tc = p['E_cock'] / math.radians(p['cock_deg']); te = p['E_ej'] / math.radians(p['ej_deg'])
    grav = b['mass'] * G * b['rc']
    def w_needed(E): return math.sqrt(2 * E / I)
    return {'mass_kg': p['mass'], 'centre_from_pin_cm': round(b['rc'] * 100, 1), 'k_cm': round(math.sqrt(b['k2']) * 100, 1), 'I_kgm2': round(I, 5),
            'gravity_torque_Nm': round(grav, 3), 'cock_torque_Nm': round(tc, 3), 'ej_torque_Nm': round(te, 3),
            'open_min_w_deg_f': round(math.degrees(w_needed(p['E_cock'] + p['fric'] * math.radians(p['cock_deg']))) / FPS, 1),
            'close_min_w_deg_f': round(math.degrees(w_needed(p['E_ej'] + p['E_latch'] + p['fric'] * math.radians(p['ej_deg']))) / FPS, 1),
            'latch_w_deg_f': round(math.degrees(b['w_latch']) / FPS, 1), 'open_deg': round(GEO[gid]['open_deg'], 1),
            'trip_deg': round(GEO[gid]['open_deg'] - p['trip_before_stop_deg'], 1), 'v_eject_m_s': p['v_eject'], 'cock_deg': p['cock_deg'], 'ej_deg': p['ej_deg'],
            'E_cock_J': p['E_cock'], 'E_ej_J': p['E_ej'], 'E_latch_J': p['E_latch'], 'fric_Nm': p['fric'], 'e_stop': p['e_stop'], 'e_cam': p['e_cam']}


class GunMotion:
    """The gun's world pose per frame (4x4 list GW, from the built clip) at fractional time: position Catmull-Rom,
    rotation slerp; affine acceleration field (world, m/s2) a(p) = A p + a0 from second differences."""
    def __init__(self, GW):
        self.GW = [np.asarray(M, float) for M in GW]; self.N = len(GW)

    def mat(self, t):
        t = min(max(t, 0.0), self.N - 1.0); i = min(int(math.floor(t)), self.N - 2); u = t - i
        M0, M1 = self.GW[i], self.GW[i + 1]; Ma, Mb = self.GW[max(i - 1, 0)], self.GW[min(i + 2, self.N - 1)]
        T =[Ma[:3, 3], M0[:3, 3], M1[:3, 3], Mb[:3, 3]]
        p = 0.5 * ((2 * T[1]) + (-T[0] + T[2]) * u + (2 * T[0] - 5 * T[1] + 4 * T[2] - T[3]) * u * u + (-T[0] + 3 * T[1] - 3 * T[2] + T[3]) * u ** 3)
        R = slerp_m(M0[:3, :3], M1[:3, :3], u); M = np.eye(4); M[:3, :3] = R; M[:3, 3] = p; return M

    def acc_mat(self, t, d=0.25):
        """D with a(world point of gun-axes x) = D @ [x, 1] (m/s2)."""
        return (self.mat(t - d) - 2 * self.mat(t) + self.mat(t + d))[:3, :] / (d * d) * FPS * FPS

    def vel_mat(self, t, d=0.25):
        return (self.mat(t + d) - self.mat(t - d))[:3, :] / (2 * d) * FPS


def slerp_m(A, B, u):
    Rr = B @ A.T; ang = math.acos(max(-1.0, min(1.0, (np.trace(Rr) - 1) / 2)))
    if ang < 1e-9: return A.copy()
    ax = np.array([Rr[2, 1] - Rr[1, 2], Rr[0, 2] - Rr[2, 0], Rr[1, 0] - Rr[0, 1]]) / (2 * math.sin(ang))
    return rot_axis(ax, ang * u) @ A


def simulate(gid, GW, release, contacts=(), lever_until=None, hold_open=()):
    """Barrel angle per frame. release: frame the thumb pushes the top lever; lever_until: frame the thumb lets it
    go (default release + 3: the lever then rests on the lump and springs into the bite when the barrels come home).
    contacts: [{'f': [f0, f1], 'p': world point on the surface, 'n': world normal out of the surface, 'pt': barrel
    point (gun axes, closed) that touches, 'name'}]. hold_open: [(f0, f1)] frames the barrels are held at the open
    stop by a contact the model does not draw (none used). Returns dict theta (rad per frame), w (rad/s per frame),
    events, log (per frame torques)."""
    b = barrel(gid); p = PAR[gid]; gm = GunMotion(GW); N = len(GW); q = pivot(gid); h0 = axis(gid); I = b['I']; m = b['mass']; S0 = b['pts']
    tc = p['E_cock'] / math.radians(p['cock_deg']); te = p['E_ej'] / math.radians(p['ej_deg']); tm = tmax(gid); trip = tm - math.radians(p['trip_before_stop_deg'])
    lever_until = release + 3 if lever_until is None else lever_until
    for ct in contacts: ct.pop('_prev', None); ct.pop('_on', None)
    th, w = 0.0, 0.0; latched = True; cocked = False; fired = False; out = [0.0]; W = [0.0]; ev = {'release': release, 'closes': [], 'stops': [], 'contacts': []}; log = [{}]
    dt = 1.0 / (FPS * SUB)
    for f in range(1, N):
        lg = {'tau_in': 0.0, 'tau_spring': 0.0, 'n': 0}
        for k in range(SUB):
            t = f - 1 + (k + 1) / SUB
            if latched:
                if t >= release and f - 1 >= release - 1 and t <= lever_until + 1e-9: latched = False; ev.setdefault('unlatch', round(t, 2))
                else: continue
            M = gm.mat(t); D = gm.acc_mat(t); R = M[:3, :3]; H = hinge_rot(gid, th)
            X = (H[:3, :3] @ S0.T).T + H[:3, 3]                       # barrel points, gun axes, current angle
            Xw = (R @ X.T).T + M[:3, 3]; qw = R @ q + M[:3, 3]; hw = R @ h0
            A = (D[:, :3] @ X.T).T + D[:, 3]                           # their carried acceleration, world
            tau_in = m * float(np.mean(np.cross(Xw - qw, GV - A) @ hw))
            sp = 0.0
            if not cocked and th < math.radians(p['cock_deg']): sp -= tc
            if fired and th < math.radians(p['ej_deg']): sp += te
            net = tau_in + sp
            if abs(w) < 1e-6 and abs(net) <= p['fric']: a = 0.0; w = 0.0
            else: a = (net - p['fric'] * (np.sign(w) if abs(w) > 1e-6 else np.sign(net))) / I
            w_old = w; w = w + a * dt
            if w_old != 0 and np.sign(w) != np.sign(w_old) and abs(net) <= p['fric']: w = 0.0      # friction stops it, it does not reverse it
            th = th + w * dt
            lg['tau_in'] += tau_in; lg['tau_spring'] += sp; lg['n'] += 1
            # contacts: a barrel point may not pass a body surface; the surface turns the barrels
            for ct in contacts:
                if not (ct['f'][0] <= t <= ct['f'][1]): continue
                n = np.asarray(ct['n'], float); n = n / np.linalg.norm(n); P0 = np.asarray(ct['p'], float)
                def depth(a_):
                    Hh = hinge_rot(gid, a_); x = Hh[:3, :3] @ np.asarray(ct['pt'], float) + Hh[:3, 3]; return float(((R @ x + M[:3, 3]) - P0) @ n)
                d0 = depth(th)
                if ct.get('rad') is not None:         # a body patch, not an endless plane: the point must be within rad of p sideways
                    Hh = hinge_rot(gid, th); xw = R @ (Hh[:3, :3] @ np.asarray(ct['pt'], float) + Hh[:3, 3]) + M[:3, 3]; lat = (xw - P0) - ((xw - P0) @ n) * n
                    if np.linalg.norm(lat) > ct['rad']: ct['_prev'] = d0; ct['_on'] = False; continue
                prev = ct.get('_prev'); ct['_prev'] = d0
                if d0 < -0.01 and (prev is None or prev < -0.01) and not ct.get('_on'): continue      # came into the patch from the side, already deep: not a contact
                ct['_on'] = d0 < 0
                if d0 < 0:
                    lo, hi = th, th; step = math.radians(0.5); dirn = 1 if depth(th + step) > d0 else -1; k2 = 0
                    while depth(hi) < 0 and k2 < 400: hi += dirn * step; k2 += 1
                    a_, b_ = sorted((lo, hi))
                    for _ in range(30):
                        mid = 0.5 * (a_ + b_)
                        if (depth(mid) < 0) == (depth(a_) < 0): a_ = mid
                        else: b_ = mid
                    tn = b_ if dirn > 0 else a_; tn = min(max(tn, 0.0), tm); vn = (tn - th) / dt
                    if abs(tn - th) > 1e-6: ev['contacts'].append({'t': round(t, 2), 'name': ct.get('name', 'body'), 'deg': round(math.degrees(tn), 1)})
                    w = vn if abs(vn) > abs(w) or np.sign(vn) != np.sign(w) else w; th = tn
            if th >= math.radians(p['cock_deg']) and not cocked: cocked = True; ev['cocked'] = round(t, 2)
            if th >= tm:
                if w > 0: ev['stops'].append({'t': round(t, 2), 'w_deg_f': round(math.degrees(w) / FPS, 1)}); ev.setdefault('open', round(t, 2))
                th = tm; w = -w * p['e_stop'] if w > 0 else w
            if not fired and th >= trip and w > 0: fired = True; ev['trip'] = round(t, 2); ev['trip_w_deg_f'] = round(math.degrees(w) / FPS, 1)
            if th <= 0.0:
                if w < 0 and ev.get('unlatch') is not None and t > lever_until and max(out) > math.radians(5):
                    wv = -w
                    if wv >= b['w_latch']:
                        ev['closes'].append({'t': round(t, 2), 'w_deg_f': round(math.degrees(wv) / FPS, 1), 'result': 'latched'}); th = 0.0; w = 0.0; latched = True; ev['shut'] = round(t, 2); release = 1e9
                        break
                    ev['closes'].append({'t': round(t, 2), 'w_deg_f': round(math.degrees(wv) / FPS, 1), 'result': 'bounced'}); th = 0.0; w = wv * p['e_cam']
                else:
                    th = 0.0; w = max(w, 0.0)
        out.append(th); W.append(w); log.append({k: (v / lg['n'] if lg['n'] else 0.0) if k != 'n' else v for k, v in lg.items()})
    return {'theta': np.array(out), 'w': np.array(W), 'events': ev, 'log': log, 'w_latch_deg_f': round(math.degrees(b['w_latch']) / FPS, 1)}


def chamber_mats(gid, joints, closed):
    return {j: np.array(closed[j]) for j in joints}


def spent_shells(gid, GW, theta, ev, joints, closed, centre, floor=0.08):
    """Spent shell world matrices per frame (mesh vertex -> world) for each chamber joint, and stats. Before the
    trip: in the chamber, lifted by the extractors (linear in the angle up to the trip); at the trip: free, with the
    velocity of its centre in the moving barrels plus v_eject along the chamber axis outward; then free flight."""
    p = PAR[gid]; N = len(GW); tm = tmax(gid); trip = tm - math.radians(p['trip_before_stop_deg']); cen = np.r_[centre, 1]
    ft = ev.get('trip'); out = {}; st = []
    def carried(f, j, s=None):
        th = theta[f]; ext = p['extract_m'] * min(th / trip, 1.0) if s is None else s
        C = closed[j].copy(); C = C @ np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, ext], [0, 0, 0, 1.0]])
        return GW[f] @ hinge_rot(gid, th) @ C
    for j in joints:
        Wj = [carried(f, j) for f in range(N)]
        if ft is not None:
            f0 = int(math.floor(ft)); f1 = min(f0 + 1, N - 1)
            M1 = carried(f1, j, p['extract_m']); M0 = carried(f0, j, p['extract_m'])
            v = ((M1 @ cen)[:3] - (M0 @ cen)[:3]) * FPS; u = M1[:3, :3] @ np.array([0, 0, 1.0]); v = v + u * p['v_eject']
            Rr = M1[:3, :3] @ M0[:3, :3].T; ang = math.acos(max(-1, min(1, (np.trace(Rr) - 1) / 2)))
            om = (np.array([Rr[2, 1] - Rr[1, 2], Rr[0, 2] - Rr[2, 0], Rr[1, 0] - Rr[0, 1]]) / (2 * math.sin(ang)) * ang * FPS) if ang > 1e-6 else np.zeros(3)
            om = om + M1[:3, :3] @ np.array([1.0, 0, 0]) * (8.0 if j == joints[0] else -8.0)     # the ejector strikes the rim off centre: a tumble (rad/s), unverified
            c = (M1 @ cen)[:3]; R = M1[:3, :3]; land = None; pos = {}
            Wj[f1] = M1       # the release frame is the flight's own start (it was carried(f1) at the angle's own lift: 0.03 mm off, a second difference of 0.003 cm/f2 at the first flight frame)
            for f in range(f1 + 1, N):
                dt = 1.0 / FPS; c = c + v * dt + 0.5 * GV * dt * dt; v = v + GV * dt; R = rot_axis(om, np.linalg.norm(om) * dt) @ R
                if c[1] < floor: land = f; break
                M = np.eye(4); M[:3, :3] = R; M[:3, 3] = c - R @ cen[:3]; Wj[f] = M; pos[f] = c.copy()
            for f in range(land or N, N): Wj[f] = None
            v0 = ((M1 @ cen)[:3] - (M0 @ cen)[:3]) * FPS
            st.append({'joint': j, 'free': f1, 'land': land, 'carry_m_s': round(float(np.linalg.norm(v0)), 2), 'exit_m_s': round(float(np.linalg.norm(v0 + u * p['v_eject'])), 2),
                       'path': {f: [round(float(x), 4) for x in c_] for f, c_ in pos.items()}})
        out[j] = Wj
    return out, st


def drive_hinge(theta, open_deg=5.0):
    """The hinge as the owner's rule has it (S1): the barrels open once, stay open while the shells change, close once.
    The simulated angle bounces (ejector springs, gravity, the gun's stops: Palica BR17 0, 54, 0, 54, 19, 68 ...); in the
    game that reads as flapping. Opening: running maximum of the simulated angle up to the start of the final closing
    descent (the last run of frames whose angle only falls, ending where the angle last drops below open_deg).
    Closing: the simulated descent, unchanged. A close that never latches (no final descent) leaves the angle as it is.
    Returns the angle per frame (rad)."""
    th = np.asarray(theta, float).copy(); o = math.radians(open_deg)
    if th.max() <= o: return th
    F = int(np.nonzero(th > o)[0][-1]) + 1                      # first frame back below open_deg after the last open stretch
    F = min(F, len(th) - 1)
    c = F
    while c > 0 and th[c - 1] >= th[c]: c -= 1                  # start of the monotone final descent
    out = th.copy(); out[:c + 1] = np.maximum.accumulate(th[:c + 1])
    out[c:F + 1] = np.minimum(out[c], np.minimum.accumulate(th[c:F + 1]))
    return out


def hinge_stats(theta_deg, open_deg=20.0, shut_deg=10.0):
    """Rule S1 numbers of an angle track (deg per frame): opens (up-crossings of open_deg after being under shut_deg),
    closes (down-crossings of shut_deg after being open) and the largest dip below the running maximum before the
    final close starts (the flap)."""
    h = [float(x) for x in theta_deg]; state = False; opens = closes = 0
    for v in h:
        if not state and v > open_deg: state = True; opens += 1
        elif state and v < shut_deg: state = False; closes += 1
    F = max([i for i, v in enumerate(h) if v > shut_deg], default=0); c = F
    while c > 0 and h[c - 1] >= h[c]: c -= 1
    run = 0.0; dip = 0.0
    for i in range(c + 1): run = max(run, h[i]); dip = max(dip, run - h[i]) if h[i] > shut_deg else dip
    return {'opens': opens, 'closes': closes, 'dip_deg': round(dip, 2), 'max_deg': round(max(h), 1)}


if __name__ == '__main__':
    for g in ('palica', 'satara'):
        print(g, json.dumps(summary(g)))
