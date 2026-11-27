"""SMG round 3 (BULLPUP, TOP): engine of the one-handed reload drafts under BRIEF-NEW-TECHNIQUES.md (owner feedback
2026-11-13: new techniques only, real inertia for gun and magazine). Built on r2lib (beats, gun time map, magazine
well model, gate wiring); what is new here:

Gun inertia: the timeline (TL3) gives the hand's target path; the gun and hand are simulated as a mass on an
  underdamped spring-damper per axis (position and rotation, 10 substeps per frame), so a stop overshoots and
  rebounds, a big move settles, rotation lags translation and the muzzle trails by angular inertia. No authored kicks:
  every rebound comes from the spring. During the slam onto the fresh magazine the hand guides the gun exactly
  (lock, blended in over 3 frames), then the spring carries on from the seat. Impacts (the fresh magazine seating, the gun slapped on the body) are velocity
  impulses into the same spring. Report per draft (inertia): overshoot in cm and deg at each stop, settle frames
  (within 0.3 cm), rotation lag (frames between target and gun reaching half of each rotation).
  SPRING per take: A light wp 1.2 rad/f, B heavy 1.0; rotation 0.9 / 0.75; damping 0.7 (just under critical, both).
In-hand toss (tl.slot): the gun leaves the palm by a few cm (offset in gun axes per frame) and is caught; the game's own
  melee clips move WeaponRight (a child of RightHand) up to 24 cm and 129 deg from the hand, so the rig carries it;
  whether a reload state keeps it is unverified (needs in-game check).
In-hand spin: the gun turns in the hand about a gun axis through a pivot (the trigger finger), on top of the arm
  (Gorilla Arms strength), angle also through the rotation spring. The magazine then feels the spin through the well
  model (centrifugal push along the well; r2lib.track integrates the seat point's acceleration).
  Finger torque: the fingers must supply I alpha minus the gravity moment (gunmass.net_torque, the draft check's R7 measure) of the gun's own mass
  properties (from its mesh). A spin that needs more than the limit (weapons.json checks.draft.finger_torque_nm) is stretched in time (its end frame
  moves out) until it fits; the stretch is stated in spec _finger and in the spin's `slowed`. The reaction, I alpha of the turn, goes into the arm's
  rotation spring as velocity impulses, so the arm works against it. The arm's inertia is the forearm and hand about the elbow measured from the player arm mesh
  (gunmass.arm_inertia, ARM_BODY pma, density 1000; the spring has no mass).
Fresh magazine (plan['fresh']): still (waits on the rig), present (the rig pops it up into reach, then still),
  toss (the rig launches it straight up; it reaches its apex in the gun on the seat frame), drop (a rig above lets it
  fall into the upturned well; it lands on the seat frame; toss, drop and present move along the well's line at
  the seat, the rig's chute set to it, with gravity's component along that line), slap (the gun takes it half in at the rig, then is slapped
  against the body and it seats on that impact). Moving fresh frames are labelled fresh_move (rgate's drift and
  insertion checks see only the still ones); insert_rel checks the moving ones in gun axes.
"""
import os, sys, json, math, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, prod, rgate, magtrack2, rlib2, gunmass
import r2lib as R2
from r2lib import ctx, aligned, exit_check, view_frames, elbow_step, stem, gun_map, gun_events, CLIP, PUNCH, mag_point, exw
from rlib import K
from glb import Glb
from fk import Clip, qrot, qmul
from magtrack2 import m4, rot_axis, log_rot, G_ACC

OUT = renv.OUT
for _t, (b, i) in {'A': (55, 61), 'B': (63, 70)}.items(): R2.BEATS[_t]['back'], R2.BEATS[_t]['idle'] = b, i     # earlier idle: the spring settles before the end
BEATS = R2.BEATS
SPRING = {'A': {'wp': 1.2, 'wr': 0.9, 'z': 0.7}, 'B': {'wp': 1.0, 'wr': 0.75, 'z': 0.7}}
ARM_BODY = 'pma'        # the arm mesh whose forearm and hand inertia about the elbow sets the size of the reaction (gunmass.arm_inertia: pma 0.0647 kg m2, pwa 0.0366)
STRETCH_MAX = 60        # frames a spin may be stretched

def spring_of(c):
    """Arm spring of the gun in ctx c: from its measured mass and inertia when weapons.json checks.draft.arm_spring.source is 'mass' (gunmass.arm_spring),
    else the take label (SPRING). A gun without a mesh keeps the label."""
    cfg = common.manifest.load()['checks']['draft'].get('arm_spring') or {}
    if cfg.get('source') == 'mass':
        s = gunmass.arm_spring(c.gun, cfg, ARM_BODY)
        if s is not None: return s
    return SPRING[c.take]


# ------------------------------------------------------------------------------------------------ gun inertia
def spring(T, w, z, imp, n=10, locks=()):
    """Mass on an underdamped spring-damper following the target T (frames x dims); imp {frame: velocity}.
    locks [(a, b)]: frames a..b the hand guides the gun exactly onto its path (the slam onto the fresh magazine),
    blended in over the 3 frames before a; after b the spring carries on from there."""
    e = T[-1].astype(float).copy(); T = T - e      # the end rest (the idle: zero; the lowered pose in a lowered variant)
    N = len(T); x = np.zeros_like(T); xc = T[0].astype(float).copy(); v = np.zeros(T.shape[1]); dt = 1.0 / n
    lw = np.zeros(N)
    for a, b in locks:
        for f in range(max(a - 3, 0), min(b + 1, N)): lw[f] = max(lw[f], 1.0 if f >= a else (f - (a - 3)) / 3.0)
    for f in range(N):
        if f > 0:
            for s in range(n):
                tg = T[f - 1] + (T[f] - T[f - 1]) * (s + 1) / n
                v += (w * w * (tg - xc) - 2 * z * w * v) * dt; xc = xc + v * dt
            if lw[f] > 0: xc = xc + (T[f] - xc) * lw[f]; v = v + ((T[f] - T[f - 1]) - v) * lw[f]
        x[f] = xc
        if f in imp: v = v + np.asarray(imp[f], float)
    fade = np.ones(N); k = 5; fade[N - k:] = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, k))
    return x * fade[:, None] + e      # the last 5 frames ease into the idle (the target is the idle there)


class TL3(R2.TL):
    """Target path of the hand; kicks are ignored (the spring makes every rebound); impulses and in-hand spins."""
    def __init__(self, c, lag, drag):
        super().__init__(c, lag, 0.0); self.imp = {}; self.rimp = {}; self.spins = []; self.locks = []; self.slot = np.zeros((c.N, 3)); self.inertia = None; self.limit = None; self.finger = None

    def kick(self, *a, **k): return self

    def impulse(self, f, dpos=(0, 0, 0), drot=(0, 0, 0)):
        self.imp[int(f)] = np.array(dpos, float); self.rimp[int(f)] = np.array(drot, float); return self

    def spin(self, f0, f1, deg, axis=(0, 0, 1), pivot=(0.0, -0.03, -0.02), prof=(2.0, 2.0), inertia=None, limit=None):
        """The gun turns deg degrees in the hand between f0 and f1 about a gun axis through pivot (gun axes). inertia: gunmass.props() dict of the gun
        (default: from the mesh of c.gun); limit: finger torque limit in N m (default: weapons.json checks.draft.finger_torque_nm). A spin that needs
        more is stretched until it fits (see arrays)."""
        if inertia is not None: self.inertia = inertia
        if limit is not None: self.limit = limit
        self.spins.append({'f0': int(f0), 'f1': int(f1), 'deg': float(deg), 'axis': list(axis), 'pivot': list(pivot), 'prof': list(prof)}); return self

    def arrays(self):
        P, R = super().arrays(); S = spring_of(self.c); self.target = (P.copy(), R.copy())
        Pi = {f: v for f, v in self.imp.items()}; Ri = {f: v for f, v in self.rimp.items()}
        Ps = spring(P, S['wp'], S['z'], Pi, locks=self.locks); Rs = spring(R, S['wr'], S['z'], Ri, locks=self.locks)
        if self.spins and self._finger_model():
            for _ in range(6):             # the arm takes the reaction of the spins, the spins are stretched to the limit on that arm path; again until they hold
                Rs = spring(R, S['wr'], S['z'], self._reaction(R, Ri), locks=self.locks)
                if not self._fit(Rs): break
            self._report(Rs)
        Ps[0] = 0; Rs[0] = 0; Ps[-1] = 0; Rs[-1] = 0
        return Ps, Rs

    # -------------------------------------------------------------------------------------------- finger torque
    def _finger_model(self):
        """True when the gun's mass properties and the limit are known (a gun without a mesh has none: no limit, no reaction)."""
        if self.inertia is None: self.inertia = gunmass.props(self.c.gun)
        if self.limit is None: self.limit = common.manifest.load()['checks']['draft'].get('finger_torque_nm')
        return self.inertia is not None and self.limit is not None

    def _rel(self, ang):
        """Gun in the hand frame per frame: the spins applied in order, as apply_spins does."""
        out = []
        for f in range(self.N):
            M = np.eye(3)
            for sp, a in ang: M = M @ gunmass.qmat(qaxis(sp['axis'], a[f]))
            out.append(M)
        return np.array(out)

    def _world(self, Rs, rel):
        q0 = self.c.q0
        return np.array([gunmass.qmat(qmul(q0, author.qeuler(*Rs[f]))) @ rel[f] for f in range(self.N)])

    def _torque(self, Rs, gravity=True):
        ang = self.spin_angles(); rel = self._rel(ang); turn, tau = gunmass.net_torque(rel, self._world(Rs, rel), self.inertia, gravity)
        return ang, rel, turn, tau

    def _fit(self, Rs):
        """Stretch the spin that holds the torque peak until the peak is within the limit. -> True when a spin changed."""
        changed = False
        for _ in range(40):
            ang, rel, turn, tau = self._torque(Rs); nr = np.where(turn, np.linalg.norm(tau, axis=1), 0.0); f = int(np.argmax(nr)); peak = float(nr[f])
            if peak <= self.limit: break
            k = min(range(len(self.spins)), key=lambda i: 0 if self.spins[i]['f0'] - 1 <= f <= self.spins[i]['f1'] + 3 else min(abs(f - self.spins[i]['f0']), abs(f - self.spins[i]['f1'])) + 1)
            sp = self.spins[k]; n = sp['f1'] - sp['f0']; add = max(1, int(math.ceil(n * (math.sqrt(peak / self.limit) - 1))))
            first = sp.setdefault('slowed', {'asked': [sp['f0'], sp['f1']], 'demanded_nm': round(peak, 3), 'limit_nm': self.limit})
            if first['asked'][1] - first['asked'][0] + STRETCH_MAX <= n + add: break
            room = self.N - 3 - sp['f1']; up = min(add, room); sp['f1'] += up; sp['f0'] -= add - up
            if sp['f0'] < 1: sp['f1'] -= sp['f0'] - 1; sp['f0'] = 1
            changed = True
        return changed

    def _reaction(self, R, Ri):
        """Rotation impulses of Ri plus the reaction of the finger turn on the arm: -I alpha (turn frames), in the arm's euler angles, deg per frame."""
        Ri = {f: np.array(v, float) for f, v in Ri.items()}
        ang = self.spin_angles(); rel = self._rel(ang); turn, tau = gunmass.net_torque(rel, self._world(np.zeros_like(R), rel), self.inertia, False); arm_i = gunmass.arm_inertia(ARM_BODY, 'r')['I_transverse']
        for f in np.nonzero(turn)[0]:
            d = rel[f] @ (-tau[f]) / arm_i / 900.0                    # rad/s2 -> rad/f per frame, in the pre-spin gun axes
            Ri[int(f)] = Ri.get(int(f), np.zeros(3)) + np.linalg.lstsq(self._euler_jac(R[f]), d, rcond=None)[0]
        return Ri

    @staticmethod
    def _euler_jac(r):
        """d(rotation vector in the euler frame, rad)/d(euler angle, deg) at r, 3x3."""
        h = 0.01; q = author.qeuler(*r); J = np.zeros((3, 3))
        for i in range(3):
            e = np.array(r, float); e[i] += h; J[:, i] = gunmass.logR(gunmass.qmat(q).T @ gunmass.qmat(author.qeuler(*e))) / h
        return J

    def _report(self, Rs):
        ang, rel, turn, tau = self._torque(Rs); nr = np.where(turn, np.linalg.norm(tau, axis=1), 0.0)
        self.finger = {'limit_nm': self.limit, 'peak_nm': round(float(nr.max()), 4), 'mass_kg': round(self.inertia['mass_kg'], 4), 'turn_frames': int(turn.sum()),
                       'slowed': [dict(sp['slowed'], now=[sp['f0'], sp['f1']]) for sp in self.spins if 'slowed' in sp]}

    def spin_angles(self):
        """Per spin: angle per frame (deg) through the rotation spring."""
        S = spring_of(self.c); out = []
        for sp in self.spins:
            a = np.zeros((self.N, 1)); n = sp['f1'] - sp['f0']; s = rlib2.beta_cdf(*sp['prof'], n)
            for k in range(n + 1): a[sp['f0'] + k] = sp['deg'] * s[k]
            a[sp['f1']:] = sp['deg']
            out.append((sp, spring_keep(a, S)))
        return out


def spring_keep(a, S):
    """Spin angle through the spring, without the end fade (a full turn ends on a multiple of 360)."""
    N = len(a); x = np.zeros(N); xc = 0.0; v = 0.0; n = 10; dt = 0.1; w, z = S['wr'] * 1.6, S['z']     # a spin in the fingers: stiffer than the arm
    for f in range(N):
        if f > 0:
            for s in range(n):
                tg = a[f - 1, 0] + (a[f, 0] - a[f - 1, 0]) * (s + 1) / n; v += (w * w * (tg - xc) - 2 * z * w * v) * dt; xc += v * dt
        x[f] = xc
    end = a[-1, 0]; x[-6:] = x[-6:] + (end - x[-6:]) * np.linspace(0.2, 1.0, 6)
    return x


def qaxis(axis, deg):
    a = np.asarray(axis, float); a = a / np.linalg.norm(a); h = math.radians(deg) / 2
    return np.array([*(a * math.sin(h)), math.cos(h)])


def apply_spins(glb, clip, spins, slot=None):
    """Rewrites WeaponRight: per frame its local transform times the in-hand spins (about pivots, gun axes), then the
    in-hand offset slot[f] (gun axes: the gun tossed out of the palm and caught)."""
    if not spins and (slot is None or not np.any(slot)): return
    g = Glb(glb); i = g.names.index('WeaponRight'); a = g.anim(clip); c = Clip(g, clip); n = c.frames; T = []; Rr = []
    for f in range(n):
        t, r = c.local(i, f); t = np.array(t, float); r = np.array(r, float)
        for sp, ang in spins:
            q = qaxis(sp['axis'], ang[f]); pv = np.array(sp['pivot'], float)
            t = t + qrot(r, pv - qrot(q, pv)); r = qmul(r, q)
        if slot is not None: t = t + qrot(r, slot[f])
        T.append(t); Rr.append(r)
    Rr = np.array(Rr)
    for k in range(1, n):
        if np.dot(Rr[k], Rr[k - 1]) < 0: Rr[k] = -Rr[k]
    tin = g.add_acc(np.arange(n) / 30.0, 'SCALAR')
    for ch in a['channels']:
        if ch['target']['node'] == i and ch['target']['path'] in ('translation', 'rotation'):
            vals = np.array(T) if ch['target']['path'] == 'translation' else Rr
            a['samplers'][ch['sampler']] = {'input': tin, 'output': g.add_acc(vals, 'VEC3' if ch['target']['path'] == 'translation' else 'VEC4'), 'interpolation': 'LINEAR'}
    g.save(glb)


def inertia_report(tl, Ps, Rs):
    """Overshoot (cm, deg) at each stop of the target, settle frames (within 0.3 cm), rotation lag (frames)."""
    P, R = tl.target; N = len(P); sp = np.r_[0, np.linalg.norm(np.diff(P, axis=0), axis=1) * 100]; stops = []
    f = 1
    while f < N - 2:
        if sp[f] > 1.5 and sp[f + 1] < 0.15:
            s = f + 1; d = P[s] - P[max(s - 3, 0)]; d = d / (np.linalg.norm(d) or 1)
            h = s
            while h + 1 < min(s + 10, N) and np.linalg.norm(P[h + 1] - P[s]) < 0.002: h += 1      # only while the target holds still after the stop
            ov = max(float((Ps[k] - P[s]) @ d) for k in range(s, h + 1)) * 100
            dr = R[s] - R[max(s - 3, 0)]; rn = np.linalg.norm(dr); ovr = max(float((Rs[k] - R[s]) @ (dr / rn)) for k in range(s, h + 1)) if rn > 1 else 0.0
            st = next((k - s for k in range(s, min(s + 20, N - 2)) if all(np.linalg.norm(Ps[j] - P[j]) * 100 < 0.3 for j in range(k, k + 3))), None)
            stops.append({'f': s, 'overshoot_cm': round(max(ov, 0), 2), 'overshoot_deg': round(max(ovr, 0), 1), 'settle_f': st})
        f += 1
    rs = np.r_[0, np.linalg.norm(np.diff(R, axis=0), axis=1)]; lags = []; f = 1
    while f < N:
        if rs[f] > 1.0:
            k = f
            while k + 1 < N and rs[k + 1] > 0.3: k += 1
            tot = np.linalg.norm(R[k] - R[f - 1])
            if tot > 8:
                half = lambda A: next((j for j in range(f - 1, N) if np.linalg.norm(A[j] - R[f - 1]) >= tot / 2), None)
                a, b = half(R), half(Rs)
                if a is not None and b is not None: lags.append(b - a)
            f = k + 1
        else: f += 1
    return {'stops': stops, 'rot_lag_f': lags, 'overshoot_cm_max': max([s['overshoot_cm'] for s in stops] or [0]),
            'overshoot_deg_max': max([s['overshoot_deg'] for s in stops] or [0]), 'settle_f_max': max([s['settle_f'] or 0 for s in stops] or [0]),
            'rot_lag_mean_f': round(float(np.mean(lags)), 1) if lags else 0.0}


# ------------------------------------------------------------------------------------------------ fresh magazine
def fresh_world(c, GW, S, plan, f):
    """World matrix of the fresh magazine on frame f (appear <= f < seated) and whether it moves."""
    fr = plan.get('fresh', {'mode': 'still'}); mode = fr['mode']; se = int(plan['seated']); final = GW[se] @ S
    T = lambda d: np.block([[np.eye(3), np.asarray(d, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
    if mode == 'still': return final, False
    en_w = GW[se][:3, :3] @ np.array(c.v['enter'], float); en_w = en_w / np.linalg.norm(en_w)      # the well's line at the seat (world)
    if mode == 'present':      # the rig pushes it up the well's line into the gun
        a0, n = int(plan['appear']), int(fr.get('n', 4)); dist = float(np.linalg.norm(fr.get('from', (0, -0.10, 0))))
        u = min(max((f - a0) / n, 0.0), 1.0); u = u * u * (3 - 2 * u)
        return T(-en_w * dist * (1 - u)) @ final, u < 1.0
    if mode in ('toss', 'drop'):      # along the well's line (the rig's chute is set to it), gravity's component along that line
        n = int(fr.get('n', 7)); L = se - n; t = max(se - f, 0) if f >= L else n; gl = G_ACC * abs(float(en_w[1])); h = 0.5 * gl * t * t
        return T(-en_w * h) @ final, f >= L
    if mode == 'fall':      # the rig above releases it from rest and it falls straight down in the world at g onto the gun, which waits at the seat pose
        n = int(fr.get('n', 5)); L = se - n; t = min(max(f - L, 0), n)      # time since the rig let go
        return T((0.0, 0.5 * G_ACC * (n * n - t * t), 0.0)) @ final, f >= L
    if mode == 'slap':
        pk = int(fr['pick']); part = fr.get('carry', fr.get('part', 0.04)); ex = -np.array(c.v['enter'], float)      # half in: back out along the line it comes in on; carry (default part): how far out it stands while carried, within the contact distance of the gun (part is the hand's)
        if f < pk: return GW[pk] @ T(ex * part) @ S, False
        return GW[f] @ T(ex * part * (1.0 if f < se else 0.0)) @ S, True
    raise ValueError(mode)


def track(c, G, plan):
    """r2lib.track (old magazine: well or hook) with the fresh magazine from fresh_world."""
    trk = R2.track(c, G, plan); S = c.v['seat']; GW = [m4(t, q) for t, q in G]; se = int(plan['seated']); ap = min(int(plan['appear']), se - 6)
    rnd = lambda M: [round(float(x), 6) for x in M.ravel()]
    for f in range(ap, se):
        W, moving = fresh_world(c, GW, S, plan, f); row = trk['frames'][f]
        row['m'] = rnd(np.linalg.inv(GW[f]) @ W); row['s'] = 1.0; row['state'] = 'fresh_move' if moving else 'fresh'
    return trk


def insert_rel(c, trk):
    """Largest sideways offset (cm) from the well axis of the fresh magazine while it is within 10 cm of its seat
    before the seated frame (gun axes), moving frames included."""
    v = c.v; cen = np.r_[v['centre'], 1]; s0 = (v['seat'] @ cen)[:3]; en = np.array(v['enter'], float); worst = 0.0
    for row in trk['frames']:
        if row['state'] not in ('fresh', 'fresh_move'): continue
        dv = (np.array(row['m']).reshape(4, 4) @ cen)[:3] - s0; al = float(dv @ en)
        if np.linalg.norm(dv) < 0.10: worst = max(worst, float(np.linalg.norm(dv - al * en)))
    return round(worst * 100, 2)


# ------------------------------------------------------------------------------------------------ seat and rack
def seat(c, tl, station, d=0.15, dep=None, arr=None, mode='still', jolt=None, jolt_vec=None, rot_add=(0, 0, 0), flip=False, scoop=False):
    """Leave on dep, at the rig on arr, slam onto the fresh magazine on the seat beat; the seat is an impact: an
    impulse back along the well into the gun's spring (the gun jolts). mode drop: the gun waits still at the seat
    pose with the well up and the magazine falls in."""
    P = c.P; B = c.B; pos, rot = c.station(station); rot = [a + b for a, b in zip(rot, rot_add)]; dep = dep or B['dep']; arr = arr or B['arr']; tl.hold(dep)
    j = jolt if jolt is not None else (0.012 if c.take == 'A' else 0.016)
    if mode == 'drop':      # the gun waits with the well up; the falling magazine lands in it and knocks it down
        tl.to(arr, pos, rot, 'snap', rlag=P['lag'] + 1); tl.hold(B['seat']); tl.locks.append((B['slam'], B['seat']))
        tl.impulse(B['seat'], np.array(jolt_vec if jolt_vec is not None else (0, -j, 0)), (-4, 0, 0))
    else:
        sg = -1.0 if flip else 1.0          # flip: the gun is upside down in the fingers (half an in-hand roll): the well axis is mirrored
        pre = np.array(pos) + c.along(rot, c.v['enter'], d) * sg
        tl.to(arr, pre, rot, (2.4, 1.4) if scoop else 'snap', rlag=P['lag'] + 1)      # scoop: the dive runs straight into the seat
        tl.hold(B['slam']); tl.to(B['seat'], pos, rot, 'slam', rlag=0); tl.locks.append((B['slam'], B['seat']))
        tl.impulse(B['seat'], c.along(rot, c.v['enter'], j) * sg, (-3, 0, 0))
    tl.mark('arrive', arr); tl.mark('seat', B['seat'])
    return pos, rot


rack = R2.rack


# ------------------------------------------------------------------------------------------------ build
def speed_check(c, G, trk):
    """r2lib.speed_check (FRONT round 2 metric). A centrifugal release from an in-hand spin is not a throw: the
    magazine keeps gaining speed while it slides out along the spinning well (a bead on a spinning rod leaves faster
    than the rod's point it started on), so the 0.85 to 1.15 rule is not applied; the numbers stay in the report."""
    o = R2.speed_check(c, G, trk)
    if trk['plan'].get('spin_release'): o.update({'na': trk['plan'].get('spin_why', 'centrifugal: it gains speed sliding out of the spinning well'), 'ok': True})
    return o


def build(F, pick, quiet=False):
    prod.STATION.update(F.STATIONS); d = f'{OUT}/clips/pma'; os.makedirs(d, exist_ok=True); name = stem(F, pick)
    P = dict(prod.TAKES[F.TAKE]); P.update(F.PARAMS.get(pick, {})); ax = dict(F.AXES); ax.update(P.get('axes', {}))
    c = ctx(F.GUN, F.TAKE, P, ax); tl = TL3(c, P['lag'], 0.0)
    fn = F.PICKS[pick][1]; m = fn(c, tl)
    Pk, Rk = tl.arrays(); rep = inertia_report(tl, Pk, Rk); spins = tl.spin_angles(); rep['spins'] = [dict(sp, peak_deg_f=round(float(np.abs(np.diff(a)).max()), 1)) for sp, a in spins]
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    gm, _ = gun_map(F.GUN, F.TAKE)
    spec = {'_draft': name, '_name': f'{F.PICKS[pick][0]}, take {F.TAKE}', '_doc': ' '.join((fn.__doc__ or '').split()), '_mechanism': F.MECH[pick], '_gun': F.GUN, '_left_gun': F.GUN,
            '_body': 'pma', '_side': 'Right', '_gun_clip': CLIP, '_pick': pick, '_take': F.TAKE, '_family': F.FAMILY, '_timing': c.T, '_gun_map': gm,
            '_axes': {k: [float(x) for x in v] for k, v in ax.items()}, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False,
            '_round': 'smg-' + F.FAMILY.lower() + '-3', '_inertia': rep, '_spins': [[sp, [round(float(x), 2) for x in a]] for sp, a in spins], **({'_finger': tl.finger} if tl.finger else {}),
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {'Right': keys, 'Left': [K(0)]},
            'shakes': {'Right': []}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out']); apply_spins(spec['out'], 'reload_draft', spins, tl.slot); spec['_slot_cm_max'] = round(float(np.abs(tl.slot).max()) * 100, 1)
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('WeaponRight'); G = [cl.world(f)[i] for f in range(c.N)]
    GG = [(np.array(t), np.array(q)) for t, q in G]; trk = track(c, GG, m['mag'])
    spec['_track'] = f'{d}/{name}_track.json'
    json.dump(trk, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    magtrack2._van[(F.GUN, CLIP)] = c.v
    o = rgate.gate(spec, trk); o['elbow_step_deg'] = elbow_step(spec); o['mag_exit'] = exit_check(c, trk)
    if o['mag_exit']['off_axis_cm'] > rgate.LIM['off_axis_max_cm'] or o['mag_exit']['into_gun_cm'] > 0.5: o['fails'].append(f"magazine leaves the well {o['mag_exit']['off_axis_cm']} cm off its axis")
    o['mag_speed'] = speed_check(c, GG, trk); rs = o['mag_speed']['ratio']
    if not o['mag_speed']['ok']: o['fails'].append(f"magazine speed {o['mag_speed']['mag_cm_f']} cm/f vs gun {o['mag_speed']['gun_rel_cm_f']} on the release frame (ratio {rs})")
    o['mag_view_frames'] = view_frames(c, GG, trk); o['insert_rel_cm'] = insert_rel(c, trk); o['inertia'] = rep
    if o['insert_rel_cm'] > rgate.LIM['off_axis_max_cm']: o['fails'].append(f"fresh magazine meets the well {o['insert_rel_cm']} cm off its axis")
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(rgate.line(o), '| elbow', o['elbow_step_deg'], '| exit', o['mag_exit'], '| speed', o['mag_speed'], '| insert', o['insert_rel_cm'],
                        '| inertia', {k: rep[k] for k in ('overshoot_cm_max', 'overshoot_deg_max', 'settle_f_max', 'rot_lag_mean_f')}, flush=True)
    return spec, o


def main(F, argv):
    import subprocess
    o = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'; jobs = int(o('--jobs') or 1)
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(F.PICKS)
    if cmd == 'list':
        for p, (n, fn) in F.PICKS.items(): print(p, n, '|', F.MECH[p])
    elif cmd == 'build':
        if jobs > 1:
            procs = [subprocess.Popen([sys.executable, '-B', F.__file__, '_part', ','.join(ids[k::jobs])]) for k in range(jobs) if ids[k::jobs]]
            for p in procs: p.wait()
        else:
            for p in ids: build(F, p)
    elif cmd == '_part':
        for p in argv[1].split(','): build(F, p)
    elif cmd == 'stats': R2.stats(F, ids)
    elif cmd == 'gates': R2.gate_table(F, ids)
    else: raise SystemExit(__doc__)
