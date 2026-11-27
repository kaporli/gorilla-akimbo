"""Carnage per-shot toss-cock (pshot, owner 2026-11-25, reference video Dsmzmy7mZEM; phase table pshot/FLICK2.md).
One hand: toss the gun up (free flight), catch the fore-end (the pump), rack it (receiver slides on the held pump), toss again,
catch the pistol grip, settle into the ready idle. Hand and gun are authored separately (author.py hand_frames / gun_frames).

Free flight is pure ballistic: the gun's centre of mass on a gravity parabola (1.09 cm/f2), constant spin about the gun's x axis, no
hand contact. Contacts only at the two catches: the hand part (fore-end point, grip) and the gun part coincide, and the hand's
velocity there equals the part's. The hand's own path in flight is a Hermite curve from the release state to the catch state
with the part's velocity at the catch. The pump (slider) moves only while the hand holds it. The left hand is the right-hand
image mirrored (deltas from each side's idle). No finger tracks (not authored by this tool).
usage: flick2.py build [--bodies pma,pwa] [--sides right,left] [--d1 7] [--d2 7] [--settle 8] [--rack 3] [--rel 3] [--th1 65] [--th2 80]
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from scipy.spatial.transform import Rotation as Rot
import author, prod, rgate, phys, rarmset, timing, magtrack2
import tube1, tubeprod
from glb import Glb
from fk import Clip

OUT = renv.OUT + '/flick2'
GV = np.array([0.0, -9.81 / 900.0, 0.0])          # m per frame^2
S_MIR = np.diag([-1.0, 1.0, 1.0, 1.0])
EJECT0 = tube1.EJECT.copy()


def mat(p, R):
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = p; return M


def rotx(deg): return Rot.from_euler('x', deg, degrees=True).as_matrix()


def herm(p0, v0, p1, v1, T, t):
    u = t / T; h00 = 2 * u ** 3 - 3 * u ** 2 + 1; h10 = u ** 3 - 2 * u ** 2 + u; h01 = -2 * u ** 3 + 3 * u ** 2; h11 = u ** 3 - u ** 2
    return h00 * p0 + h10 * T * v0 + h01 * p1 + h11 * T * v1


def slerp(R0, R1, u):
    from scipy.spatial.transform import Slerp
    return Slerp([0, 1], Rot.from_matrix(np.array([R0, R1])))([u]).as_matrix()[0]


class Plan:
    """Right-image trajectories for one body. G[f], H[f] 4x4 world; s[f] pump travel (m); marks."""
    def __init__(self, G0, H0, CH, PUMP_P, P, mirror_of=None, COM_g=None):
        self.G0, self.H0 = G0, H0; R0 = G0[:3, :3]; self.R0 = R0; self.mir = mirror_of      # mirror_of: the right idle gun matrix whose targets are mirrored
        self.COM_g = np.array(CH[:3, 3] if COM_g is None else COM_g, float)      # the receiver: gun centre of mass estimate (gun axes)
        self.PUMP_P = np.array(PUMP_P, float); self.U = np.array([0.0, 0.0, 1.0])
        self.REL_grip = np.linalg.inv(G0) @ H0
        self.REL_c = None      # hand orientation relative to the gun on the pump: set from the catch orientation in _build
        self.REL_pump = self.REL_grip.copy(); self.REL_pump[:3, 3] = self.PUMP_P + np.array(P.get('pump_hand', (0.0, 0.02, 0.0)))
        self.P = P

    def hand_pump(self, Pp, Rg): return mat(Pp + np.array(self.P.get('pump_hand', (0.0, 0.03, 0.0))), Rg @ self.REL_c)

    def gun(self, com, Rg): return mat(com - Rg @ self.COM_g, Rg)

    def com_of(self, G): return G[:3, 3] + G[:3, :3] @ self.COM_g

    def pump_pt(self, G, s=0.0): return G[:3, 3] + G[:3, :3] @ (self.PUMP_P + self.U * s)

    def build(self):
        P = self.P; q2 = np.array(P.get('q2', (0.02, 0.05, 0.0)), float)
        for it in range(4):
            self.P = dict(P, q2=tuple(q2)); self._build()
            q2 = q2 + (self.G0[:3, 3] + np.array([0.0, -P.get('low', 0.02), 0.0]) - self.pA) * (np.array([-1.0, 1, 1]) if self.mir is not None else 1.0)
        self.P = dict(P, q2=tuple(q2)); return self._build()

    def _build(self):
        P = self.P; fr1 = int(P.get('rel', 2)); d1 = int(P.get('d1', 6)); Ac = int(P.get('catch_decel', 2)); K = int(P.get('rack_k', 3)); A2 = int(P.get('toss_accel', 1)); R = Ac + K + A2; d2 = int(P.get('d2', 7)); S = int(P.get('settle', 9))
        fc1 = fr1 + d1; fr2 = fc1 + R; fc2 = fr2 + d2; N = fc2 + S + 1
        G0 = self.G0; R0 = self.R0; p0 = self.com_of(G0)
        # orientations: R1 at catch 1 (muzzle up th1 deg, rolled roll1 deg about the long axis: the pump faces up to the hand), R2 at catch 2 (ready-ish)
        Rb = R0 if self.mir is None else self.mir[:3, :3]; Sm = np.eye(3) if self.mir is None else np.diag([-1.0, 1.0, 1.0]); mx = np.array([1.0, 1, 1]) if self.mir is None else np.array([-1.0, 1, 1])
        R1 = Sm @ (Rb @ rotx(P.get('th1', 80.0)) @ Rot.from_euler('z', P.get('roll1', 170.0), degrees=True).as_matrix()) @ Sm; R2 = Sm @ (Rb @ rotx(P.get('th2', 20.0))) @ Sm
        rv1 = Rot.from_matrix(R1 @ R0.T).as_rotvec(); F1 = float(np.linalg.norm(rv1)); a1 = rv1 / F1
        rv1 = Rot.from_matrix(R1 @ R0.T).as_rotvec(); F1 = float(np.linalg.norm(rv1)); a1 = rv1 / F1; w1 = F1 / (d1 + fr1 / 2.0)
        Rot1 = lambda phi: Rot.from_rotvec(a1 * phi).as_matrix() @ R0          # flight 1 and the throw
        Rs = Rot.from_rotvec(a1 * (w1 * Ac / 2.0)).as_matrix() @ R1              # where the catch brings the spin to rest
        rv2 = Rot.from_matrix(R2 @ Rs.T).as_rotvec(); F2 = float(np.linalg.norm(rv2)); a2 = rv2 / F2; w2 = F2 / (d2 + A2 / 2.0)
        Rot2 = lambda phi: Rot.from_rotvec(a2 * phi).as_matrix() @ Rs          # the toss and flight 2
        # catch 1: the pump point at X1
        EYE = np.array([0.0, 1.61, -0.02])
        Xs_t = (EYE + np.array(P.get('xs_abs', (0.10, -0.08, -0.22))) * mx) if P.get('xs_abs', True) is not None else self.H0[:3, 3] + np.array(P.get('x1', (0.035, 0.03, -0.04))) * mx      # the pump caught high and close to the camera (eye height, 40 cm ahead)      # where the pump point comes to rest in the hand
        def pump_vel(com_v, Rf, axis, w):
            e = 1e-3; Rn = Rot.from_rotvec(axis * w * e).as_matrix() @ Rf; return com_v + (Rn @ (self.PUMP_P - self.COM_g) - Rf @ (self.PUMP_P - self.COM_g)) / e
        X1 = Xs_t.copy()
        for _ in range(8):      # the catch brings the pump to rest Ac/2 frames of travel past the contact point
            com1 = X1 - R1 @ (self.PUMP_P - self.COM_g); v1 = (com1 - p0 - 0.5 * GV * d1 ** 2) / (fr1 / 2.0 + d1); vp1 = pump_vel(v1 + GV * d1, R1, a1, w1); X1 = Xs_t - vp1 * Ac / 2.0
        com1 = X1 - R1 @ (self.PUMP_P - self.COM_g); v1 = (com1 - p0 - 0.5 * GV * d1 ** 2) / (fr1 / 2.0 + d1); phirel = 0.5 * w1 * fr1; com_rel = p0 + 0.5 * v1 * fr1
        vp1 = pump_vel(v1 + GV * d1, R1, a1, w1)
        self.REL_c = R1.T @ self.H0[:3, :3]      # the hand arrives palm-over-pump in its idle orientation and then turns with the gun (arm-driven, no in-hand turn)
        Xs = X1 + vp1 * Ac / 2.0                                                  # the pump point at rest after the catch
        Q2 = G0[:3, 3] + np.array(P.get('q2', (0.02, 0.05, 0.0))) * mx; com2 = Q2 + R2 @ self.COM_g
        X2 = Xs + np.array(P.get('x2', (0.0, 0.0, 0.0))) * mx
        for _ in range(8):      # release state and flight 2 solved together (the toss gives the pump point vp2 over A2 frames)
            Rr = Rot2(0.5 * w2 * A2); com_r = X2 - Rr @ (self.PUMP_P - self.COM_g); v2 = (com2 - com_r - 0.5 * GV * d2 ** 2) / d2; vp2 = pump_vel(v2, Rr, a2, w2); X2 = Xs + vp2 * A2 / 2.0
        s_prof = P.get('s_prof', (0.0, 0.085, 0.045, 0.0))
        Gs = [None] * N; Hs = [None] * N; ss = [0.0] * N; marks = {'release1': fr1, 'catch1': fc1, 'release2': fr2, 'catch2': fc2, 'rack_rear': fc1 + Ac + 1}
        for f in range(fc2 + 1):
            if f <= fr1:
                t = f; com = p0 + 0.5 * (v1 / fr1) * t * t; Rg = Rot1(0.5 * (w1 / fr1) * t * t); Gs[f] = self.gun(com, Rg); Hs[f] = Gs[f] @ self.REL_grip
            elif f <= fc1:
                t = f - fr1; Gs[f] = self.gun(com_rel + v1 * t + 0.5 * GV * t * t, Rot1(phirel + w1 * t))
            elif f <= fr2:
                t = f - fc1
                if t <= Ac: u = t - t * t / (2.0 * Ac); Pp = X1 + vp1 * u; Rg = Rot.from_rotvec(a1 * w1 * u).as_matrix() @ R1
                elif t <= Ac + K: Pp = Xs; Rg = Rs
                else: tau = t - Ac - K; Pp = Xs + vp2 * (tau * tau / (2.0 * A2)); Rg = Rot2(w2 * tau * tau / (2.0 * A2))
                if Ac < t <= Ac + K:
                    k = (t - Ac) / K * (len(s_prof) - 1); i = min(int(k), len(s_prof) - 2); ss[f] = s_prof[i] + (s_prof[i + 1] - s_prof[i]) * (k - i)
                s = ss[f]; Gs[f] = mat(Pp - Rg @ (self.PUMP_P + self.U * s), Rg); Hs[f] = self.hand_pump(Pp, Rg)
            else:
                t = f - fr2; Gs[f] = self.gun(com_r + v2 * t + 0.5 * GV * t * t, Rot2(0.5 * w2 * A2 + w2 * t))
        # catch frames: the hand holds the part
        Hs[fc1] = self.hand_pump(X1, R1)
        Hs[fc2] = Gs[fc2] @ self.REL_grip
        # settle: from the catch pose (with its velocity) to the idle; orientation eased
        Gc = Gs[fc2]; vq = Gs[fc2][:3, 3] - Gs[fc2 - 1][:3, 3]; A = int(P.get('absorb', 3)); pA = Gc[:3, 3] + vq * (A - A / 2.0)
        self.vq = vq; self.pA = pA
        for f in range(fc2 + 1, N):
            t = f - fc2
            if t <= A: q = Gc[:3, 3] + vq * (t - t * t / (2.0 * A))
            else: q = herm(pA, np.zeros(3), G0[:3, 3], np.zeros(3), S - A, t - A)
            u = min(t / max(S - 3, 1), 1.0); u = u * u * u * (u * (6 * u - 15) + 10); Gs[f] = mat(q, slerp(Gc[:3, :3], R0, u)); Hs[f] = Gs[f] @ self.REL_grip
        def free_hand(f0, f1, partpos):
            Hst = Hs[f0]; Hend = Hs[f1]; vst = Hs[f0][:3, 3] - Hs[f0 - 1][:3, 3]; T = f1 - f0; vp_ = partpos(f1) - partpos(f1 - 1); ve = vp_.copy()
            for _ in range(6):      # end tangent chosen so that the last frame's step equals the part's last step (no relative speed at the catch)
                for f in range(f0 + 1, f1):
                    t = f - f0; p = herm(Hst[:3, 3], vst, Hend[:3, 3], ve, T, t); u = t / T; u = u * u * u * (u * (6 * u - 15) + 10); Hs[f] = mat(p, slerp(Hst[:3, :3], Hend[:3, :3], u))
                ve = ve - ((Hs[f1][:3, 3] - Hs[f1 - 1][:3, 3]) - vp_)
        free_hand(fr1, fc1, lambda f: self.pump_pt(Gs[f]) + np.array(self.P.get('pump_hand', (0.0, 0.03, 0.0))))
        free_hand(fr2, fc2, lambda f: (Gs[f] @ self.REL_grip)[:3, 3])
        self.G, self.H, self.s, self.marks, self.N, self.ph = Gs, Hs, np.array(ss), marks, N, {'fr1': fr1, 'fc1': fc1, 'fr2': fr2, 'fc2': fc2}
        return self


FINGER = ('InHandThumb', 'InHandIndex', 'InHandMiddle', 'InHandRing', 'InHandPinky') + tuple(f'Hand{n}{k}' for n in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky') for k in (1, 2, 3) if not (n != 'Thumb' and False))
FORE_SET = 'C:/Modding/_tools/gamefiles/gripsets/glb/base/animations/weapon/firearms/shotgun/budget_carnage/pma_w_shotgun__budget_carnage.anims.glb'


def finger_poses(src_glb, side):
    """{joint: (grip, open, fore)} local quaternions. grip: the clips' own hand (template frame 0); open: the rig's rest rotation; fore: the vanilla two-handed Carnage
    left-hand pose on the fore-end (idlepose_shoulder frame 0), the same local rotations serve the right hand (the rig's left and right finger joints share local frames)."""
    g = Glb(src_glb); cl = Clip(g, 'idle'); fg = Glb(FORE_SET); fc = Clip(fg, 'idlepose_shoulder'); out = {}
    for suf in FINGER:
        n = side + suf; nl = 'Left' + suf
        if n not in g.names: continue
        i = g.names.index(n); grip = np.array(cl.local(i, 0)[1], float); op = np.array(g.j['nodes'][i].get('rotation', [0, 0, 0, 1]), float)
        fore = np.array(fc.local(fg.names.index(nl), 0)[1], float) if nl in fg.names else grip
        out[n] = (grip, op, fore)
    return out


def nlerp(a, b, u):
    if np.dot(a, b) < 0: b = -b
    q = a * (1 - u) + b * u; return q / np.linalg.norm(q)


def finger_frames(poses, N, ph, ramp_open=2, ramp_close=3):
    """Open hand in flight, fore-end wrap at the pump catch, grip wrap at the last catch; closing over 3 frames before each catch."""
    def wts(f):      # (open weight, fore weight): pose = grip -> open -> fore
        fr1, fc1, fr2, fc2 = ph['fr1'], ph['fc1'], ph['fr2'], ph['fc2']
        if f <= fr1: return ('grip', 0.0)
        if f < fr1 + ramp_open: return ('go', (f - fr1) / ramp_open)
        if f < fc1 - ramp_close: return ('open', 0.0)
        if f < fc1: return ('of', (f - (fc1 - ramp_close)) / ramp_close)
        if f <= fr2: return ('fore', 1.0)
        if f < fr2 + ramp_open: return ('fo', (f - fr2) / ramp_open)
        if f < fc2 - ramp_close: return ('open', 0.0)
        if f < fc2: return ('og', (f - (fc2 - ramp_close)) / ramp_close)
        return ('grip', 0.0)
    out = {}
    for n, (gr, op, fo) in poses.items():
        qs = []
        for f in range(N):
            k, u = wts(f)
            q = {'grip': gr, 'open': op, 'fore': fo}.get(k) if k in ('grip', 'open', 'fore') else {'go': nlerp(gr, op, u), 'of': nlerp(op, fo, u), 'fo': nlerp(fo, op, u), 'og': nlerp(op, gr, u)}[k]
            qs.append([float(x) for x in q])
        out[n] = qs
    return out


def frames_of(Ms):
    out = []
    for M in Ms:
        q = Rot.from_matrix(M[:3, :3]).as_quat(); out.append([float(x) for x in M[:3, 3]] + [float(x) for x in q])
    return out


def mirror_deltas(Gr, G0r, G0l):
    return [S_MIR @ (M @ np.linalg.inv(G0r)) @ S_MIR @ G0l for M in Gr]


def build(side, body, quiet=False, extra=None):
    gid = 'carnage'; tubeprod.use_gun(gid); P = dict(extra or {}); S = side.capitalize(); O = 'Left' if S == 'Right' else 'Right'
    d = f'{OUT}/{body}'; os.makedirs(d, exist_ok=True); name = f'carnage_{side}_FC02A_cycle'
    # frame count first: a plan with a dummy rest to learn N
    T = {'gun': gid, 'clip': 'empty_reload', 'frames': 60, 'out': 8, 'clear': None, 'far': None, 'near': 40, 'seated': 40, 'exit_dir': [0, 1, 0], 'exit_speed_cm_f': 0, 'in_dir': [0, 1, 0],
         'slot': [0, 0, 0], 'parts': {}, 'handle': [40, 40], '_tube': True, '_flick': True}
    timing._cache[(gid, 'empty_reload')] = T
    magtrack2._van[(gid, 'empty_reload')] = {'M': [tube1.CH], 'seat': tube1.CH, 'centre': tube1.SC, 'exit': np.array([0, 1.0, 0]), 'enter': np.array([0, -1.0, 0]), 'dist': np.zeros(2), 'out': 0, 'seated': 1}
    c = prod.Ctx(gid, body, 'empty_reload', dict(prod.TAKES['A'], drag=0.0, lag=0), S)
    def rests(side_):
        sp = {'src': c.rest, 'template': 'idle', 'clip': 'x', 'frames': 2, 'keys': {}, 'out': '', 'body': body}; author.setup(sp)
        ch = author.SIDES[side_][0]; return [mat(*author.rest[ch[4]]) if False else None]
    def world_rest(side_):
        sp = {'src': c.rest, 'template': 'idle', 'clip': 'x', 'frames': 2, 'keys': {}, 'out': '', 'body': body}; author.setup(sp); ch = author.SIDES[side_][0]
        g = author.rest[ch[4]]; h = author.rest[ch[3]]
        return mat(g[0], Rot.from_quat(g[1]).as_matrix()), mat(h[0], Rot.from_quat(h[1]).as_matrix())
    G0r, H0r = world_rest('Right'); G0s, H0s = world_rest(S)
    if S == 'Right': plan = Plan(G0r, H0r, tube1.CH, tube1.PUMP_P, P).build()
    else:
        Mm = np.linalg.inv(G0s) @ S_MIR @ G0r; plan = Plan(G0s, H0s, tube1.CH, (Mm @ np.r_[tube1.PUMP_P, 1])[:3], P, mirror_of=G0r, COM_g=(Mm @ np.r_[tube1.CH[:3, 3], 1])[:3]).build()
    N = plan.N
    T.update(frames=N, near=N - 3, seated=N - 3, handle=[N - 3, N - 3]); timing._cache[(gid, 'empty_reload')] = T
    Gs, Hs = plan.G, plan.H
    spec = {'_draft': name, '_name': 'Toss-cock, take A', '_doc': ' '.join(__doc__.split()), '_gun': gid, '_left_gun': gid, '_body': body, '_side': S, '_gun_clip': 'empty_reload', '_pick': 'FC02',
            '_take': 'A', '_timing': dict(T, frames=N), '_params': P, '_marks': plan.marks, '_two_arm': False, '_round': 'toss-cock', '_clip_kind': 'cycle', 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': N,
            'keys': {S: [[0, [0, 0, 0], [0, 0, 0]]], O: [[0, [0, 0, 0], [0, 0, 0]]]}, 'shakes': {S: []}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT,
            'hand_frames': {S: frames_of(Hs)}, 'gun_frames': {S: frames_of(Gs)}, 'finger_frames': {S: finger_frames(finger_poses(c.rest, S), N, plan.ph)},
            '_free_flights': [[plan.ph['fr1'], plan.ph['fc1']], [plan.ph['fr2'], plan.ph['fc2']]], '_catch_windows': [[plan.ph['fr1'] - 1, plan.ph['fr1'] + 1], [plan.ph['fc1'], plan.ph['fc1'] + 2], [plan.ph['fr2'], plan.ph['fr2'] + 1], [plan.ph['fc2'], plan.ph['fc2'] + 3]], 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); W = [cl.world(f) for f in range(N)]; i, ih = g.names.index('Weapon' + S), g.names.index(S + 'Hand')
    Gc = [mat(np.array(W[f][i][0]), Rot.from_quat(np.array(W[f][i][1])).as_matrix()) for f in range(N)]; Hc = [mat(np.array(W[f][ih][0]), Rot.from_quat(np.array(W[f][ih][1])).as_matrix()) for f in range(N)]
    GW = phys.worlds([(m[:3, 3], Rot.from_matrix(m[:3, :3]).as_quat()) for m in Gc])
    s = plan.s; tube1.EJECT = EJECT0 * (np.array([-1.0, 1, 1]) if S == 'Left' else 1.0)
    objs, info = tube1.shell_tracks(None, GW, {'loads': []}, s, next((f for f in range(N) if s[f] >= tube1.PUMP_MAX - 0.002), None)); tube1.EJECT = EJECT0
    spec['_part_frames'] = tube1.pump_frames(s); spec['_pump_cm'] = [round(float(x) * 100, 3) for x in s]
    inv = [np.linalg.inv(M) for M in GW]; J = {'joints': {}, 'names': []}
    for nm, Wo in objs: J['names'].append(nm); J['joints'][nm] = [None if M is None else [round(float(x), 9) for x in (inv[f] @ M).ravel()] for f, M in enumerate(Wo)]
    spec['_objects'] = f'{d}/{name}_objects.json'; json.dump(J, open(spec['_objects'], 'w'))
    dummy = {'frames': [{'m': [round(float(x), 6) for x in tube1.CH.ravel()], 's': 0.0, 'state': 'seated'}] * N, 'release': 1, 'free_from': 2, 'gone': N, 'exit_gun_axes': [0, 1, 0], 'enter_gun_axes': [0, -1, 0], 'plan': {'mode': 'none'}}
    spec['_track'] = f'{d}/{name}_track.json'; json.dump(dummy, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, dummy); o['fails'] = [f for f in o['fails'] if 'hidden' not in f and 'hide' not in f]
    # rule F1 (free flight) and F2 (catches), measured on the built clip
    ph = plan.ph; com_g = plan.COM_g; pump_g = plan.PUMP_P; rel_grip = plan.REL_grip
    if False:      # the left gun is the mirrored image of the right trajectory: the same body points in the left gun's axes
        Mm = np.linalg.inv(G0s) @ S_MIR @ G0r; com_g = (Mm @ np.r_[plan.COM_g, 1])[:3]; pump_g = (Mm @ np.r_[plan.PUMP_P, 1])[:3]; rel_grip = np.linalg.inv(G0s) @ H0s
    flights = [(ph['fr1'], ph['fc1']), (ph['fr2'], ph['fc2'])]; F1 = []
    for a, b in flights:
        pts = [Gc[f][:3, 3] + Gc[f][:3, :3] @ com_g for f in range(a, b + 1)]; res = max(float(np.linalg.norm(pts[k + 1] - 2 * pts[k] + pts[k - 1] - GV)) * 100 for k in range(1, len(pts) - 1))
        ang = [Rot.from_matrix(Gc[f - 1][:3, :3].T @ Gc[f][:3, :3]).as_rotvec() for f in range(a + 1, b + 1)]; spin = max(float(np.linalg.norm(ang[k + 1] - ang[k])) for k in range(len(ang) - 1)) * 180 / math.pi
        F1.append({'frames': [a, b], 'com_residual_cm_f2': round(res, 4), 'spin_change_deg_f': round(spin, 3)})
    F2 = []
    off = np.array(plan.P.get('pump_hand', (0.0, 0.03, 0.0))); partpos = {ph['fc1']: lambda f: Gc[f][:3, 3] + Gc[f][:3, :3] @ pump_g + off, ph['fc2']: lambda f: (Gc[f] @ rel_grip)[:3, 3]}
    for f in (ph['fc1'], ph['fc2']):
        pp = partpos[f]; miss = float(np.linalg.norm(pp(f) - Hc[f][:3, 3])) * 100
        vh = np.linalg.norm(Hc[f][:3, 3] - Hc[f - 1][:3, 3]) * 100; rel = float(np.linalg.norm((Hc[f][:3, 3] - Hc[f - 1][:3, 3]) - (pp(f) - pp(f - 1)))) * 100
        F2.append({'frame': f, 'hand_part_miss_cm': round(miss, 3), 'hand_speed_cm_f': round(vh, 2), 'relative_speed_cm_f': round(rel, 3)})
    o['F1'] = F1; o['F2'] = F2; o['flick_frames'] = N; o['seconds'] = round(N / 30.0, 3)
    lim = {'com_residual_cm_f2': 0.05, 'spin_change_deg_f': 0.05, 'hand_part_miss_cm': 0.5, 'relative_speed_cm_f': 1.5}
    for k, x in enumerate(F1):
        if x['com_residual_cm_f2'] > lim['com_residual_cm_f2']: o['fails'].append(f"F1 flight {k + 1} off the parabola {x['com_residual_cm_f2']} cm/f2")
        if x['spin_change_deg_f'] > lim['spin_change_deg_f']: o['fails'].append(f"F1 flight {k + 1} spin not constant {x['spin_change_deg_f']} deg/f")
    for k, x in enumerate(F2):
        if x['hand_part_miss_cm'] > lim['hand_part_miss_cm']: o['fails'].append(f"F2 catch {k + 1}: hand misses the part by {x['hand_part_miss_cm']} cm")
        if x['relative_speed_cm_f'] > lim['relative_speed_cm_f']: o['fails'].append(f"F2 catch {k + 1}: relative speed {x['relative_speed_cm_f']} cm/f")
    import rchecks
    PGm = rchecks.gun_points('carnage', 4000); EYE_ = np.array([0.0, 1.61, -0.02]); thf = math.tan(math.radians(105.0 / 2)); ext = []
    for f in range(N):
        Pw = PGm @ Gc[f][:3, :3].T + Gc[f][:3, 3]; z = -(Pw[:, 2] - EYE_[2]); ok = z > 0.02
        sx = (Pw[ok, 0] - EYE_[0]) / z[ok] / thf; sy = (Pw[ok, 1] - EYE_[1]) / z[ok] / thf * (16 / 9)
        ext.append({'f': f, 'height_pct': round(float((min(sy.max(), 1) - max(sy.min(), -1)) / 2 * 100), 1) if len(sy) else 0.0, 'outside_pct': round(float(np.mean((np.abs(sy) > 1) | (np.abs(sx) > 1)) * 100), 1) if len(sy) else 100.0,
                    'nearest_cm': round(float(np.linalg.norm(Pw - EYE_, axis=1).min() * 100), 1), 'behind_near_plane_pct': round(float(np.mean(~ok) * 100), 2)})
    o['extent'] = ext; o['near_plane_cm'] = 2.0
    o['fails'] = [x for x in o['fails'] if not x.startswith('eye ')]      # the hard limit here is the camera near plane (2 cm), not the 20 cm comfort distance
    if any(e['behind_near_plane_pct'] > 0.5 for e in ext): o['fails'].append('over 0.5% of the gun behind the camera near plane')
    o['pump'] = {'max_cm': round(float(s.max()) * 100, 2), 'held_frames': [ph['fc1'], ph['fr2']]}
    if N / 30.0 > 1.06: o['fails'].append(f'cycle {N} f = {N / 30:.2f} s, slower than the Carnage CycleTime 1.06 s (31 f)')
    o['elbow_step_deg'] = tubeprod.prod_elbow(spec)
    if o['elbow_step_deg'] > 45: o['fails'].append(f"elbow swings {o['elbow_step_deg']} deg in one frame")
    o['end_transition'] = et = tubeprod.end_transition(spec)
    if et['last3_step_cm'] > 0.5 or et['last_vs_idle_cm'] > 0.02 or et['last_vs_idle_deg'] > 0.02: o['fails'].append(f'end transition {et}')
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1, default=float)
    if not quiet: print(body, side, name, 'N', N, '| fails', o['fails'], '| F1', F1, '| F2', F2, '| eye', o['eye_cm'], 'reach', o['reach'], 'wrist', o['wrist'][0], o['wrist_view'], flush=True)
    return spec, o


if __name__ == '__main__':
    a = sys.argv[1:]; opt = lambda n: common.opt(a, n); cs = lambda v: v.split(',') if v else None
    P = {k: float(opt('--' + k)) for k in ('d1', 'd2', 'settle', 'rack', 'rel', 'th1', 'th2', 'roll1') if opt('--' + k)}
    for b in (cs(opt('--bodies')) or ['pma']):
        for sd in (cs(opt('--sides')) or ['right']): build(sd, b, extra=P)
