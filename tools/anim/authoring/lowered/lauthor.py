"""Lowered (safe) stance clips: friendly_idlepose (loop), safe_action, equip_safe, and the same clips under their _l names.
Gun paths are offsets from idlepose_shoulder of the game's dual-wield base set (the pose the graph blends from and to);
arms are solved with two-bone IK. Hand IK helpers follow the hand, pole vector helpers follow the forearm. The elbow
and the forearm roll keep the wrist as close to the rest pose as the reach allows.

Spec keys besides the gun paths:
  clavicle  {Right|Left: [pitch, yaw, roll]} degrees on the shoulder (clavicle) joint, local, applied in full with the
            lowered pose and blended in with it (keys that are not the lowered pose carry none of it)
  body      the base set glb decides the body (pma or pwa)
  usable as a module: setup(spec), solve(clip, f), build(spec)

usage: lauthor.py <spec.json>
spec: base, out, lowered {Right|Left: [[dx,dy,dz],[pitch,yaw,roll]]}, clavicle, idle {frames, sway}, safe_action and
equip_safe {frames, keys: {Right|Left: [[f, "L" | [dx,dy,dz], ...]]}} ("L" = the lowered pose, optionally followed
by an offset and angles added to it; templates/v1.json and v2.json are complete examples)
Offsets in metres, glTF axes (x = V's right, y = up, z = back toward the camera). Angles in degrees about the gun's
own axes: pitch + = muzzle up, yaw + = muzzle turns left, roll + = top tilts left."""
import sys, json, math
import numpy as np
from lpose import Rig, Glb, qmul, qinv, qrot, write_clips

_rigs = {}
spec = rig = idx = REST_L = rest = None
SIDES, LOW, CLAV = {}, {}, {}


def setup(sp):
    global spec, rig, idx, REST_L, rest
    spec = sp
    if sp['base'] not in _rigs:
        r = Rig(Glb(sp['base'])); RL = r.sample('idlepose_shoulder', 0.0); _rigs[sp['base']] = (r, RL, r.world(RL))
    rig, REST_L, rest = _rigs[sp['base']]; idx = rig.idx
    for S in ('Left', 'Right'):
        s = S.lower()
        ch = [idx[n] for n in (f'{S}Shoulder', f'{S}Arm', f'{S}ForeArm', f'{S}Hand', f'Weapon{S}')]
        hand_h = [idx[n] for n in (f'arm_{s}_ik', f'Torso_World_{S}Arm_Hand_IK_JNT', f'Torso_{S}Arm_Hand_IK_JNT') if n in idx]
        pole_h = [idx[n] for n in (f'Torso_World_{S}Arm_PoleVector_JNT', f'Torso_{S}Arm_PoleVector_JNT') if n in idx]
        SIDES[S] = (ch, hand_h, pole_h)
        LOW[S] = (np.array(sp['lowered'][S][0], float), np.array(sp['lowered'][S][1], float))
        CLAV[S] = np.array(sp.get('clavicle', {}).get(S, [0, 0, 0]), float)


def qaxis(ax, deg):
    h = math.radians(deg) / 2; v = np.zeros(3); v['xyz'.index(ax)] = 1
    return np.array([*(v * math.sin(h)), math.cos(h)])


def qeuler(p, y, r):
    return qmul(qaxis('x', p), qmul(qaxis('y', y), qaxis('z', r)))


def hermite(keys, f):
    fs = [k[0] for k in keys]; vs = [np.array(k[1], float) for k in keys]
    if f <= fs[0]: return vs[0]
    if f >= fs[-1]: return vs[-1]
    i = max(j for j in range(len(fs)) if fs[j] <= f)

    def tan(j):
        if j == 0 or j == len(vs) - 1: return np.zeros_like(vs[j])
        if np.allclose(vs[j], vs[j - 1]) or np.allclose(vs[j], vs[j + 1]): return np.zeros_like(vs[j])
        return (vs[j + 1] - vs[j - 1]) / (fs[j + 1] - fs[j - 1]) * (fs[i + 1] - fs[i])
    p1, p2, m1, m2 = vs[i], vs[i + 1], tan(i), tan(i + 1)
    t = (f - fs[i]) / (fs[i + 1] - fs[i]); t2, t3 = t * t, t * t * t
    return (2*t3 - 3*t2 + 1) * p1 + (t3 - 2*t2 + t) * m1 + (-2*t3 + 3*t2) * p2 + (t3 - t2) * m2


def quat_of(M):
    t = np.trace(M)
    if t > 0:
        s = math.sqrt(t + 1) * 2
        return np.array([(M[2, 1] - M[1, 2]) / s, (M[0, 2] - M[2, 0]) / s, (M[1, 0] - M[0, 1]) / s, s / 4])
    i = int(np.argmax([M[0, 0], M[1, 1], M[2, 2]])); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + M[i, i] - M[j, j] - M[k, k]) * 2; q = np.zeros(4)
    q[i] = s / 4; q[j] = (M[j, i] + M[i, j]) / s; q[k] = (M[k, i] + M[i, k]) / s; q[3] = (M[k, j] - M[j, k]) / s
    return q


def aim(d, up):
    x = d / np.linalg.norm(d); y = up - x * np.dot(up, x); y /= np.linalg.norm(y)
    return np.stack([x, y, np.cross(x, y)], 1)


def key_val(S, k):
    """[f, ...] -> (f, offset, euler, clavicle weight)"""
    f = k[0]
    if k[1] == 'L':
        d = np.array(k[2], float) if len(k) > 2 else np.zeros(3); e = np.array(k[3], float) if len(k) > 3 else np.zeros(3)
        return f, LOW[S][0] + d, LOW[S][1] + e, np.array([1.0])
    return f, np.array(k[1], float), np.array(k[2], float), np.array([0.0])


def offsets(clip, S, f):
    c = spec[clip]
    if clip == 'idle':
        N = c['frames']; sw = c.get('sway', {}).get(S, {}); a = 2 * math.pi * f / N
        dp = LOW[S][0] + np.array(sw.get('move', [0, 0, 0])) * math.sin(a) + np.array(sw.get('move2', [0, 0, 0])) * (1 - math.cos(a)) / 2
        de = LOW[S][1] + np.array(sw.get('rot', [0, 0, 0])) * math.sin(a) + np.array(sw.get('rot2', [0, 0, 0])) * (1 - math.cos(a)) / 2
        return dp, de, 1.0
    keys = [key_val(S, k) for k in c['keys'][S]]
    return (hermite([(k[0], k[1]) for k in keys], f), hermite([(k[0], k[2]) for k in keys], f),
            float(hermite([(k[0], k[3]) for k in keys], f)[0]))


def solve_offsets(off):
    """off: {S: (dp, de, clavicle weight)} -> (local pose, stats)"""
    W = list(rest); L = list(REST_L); stats = {}
    for S, (ch, hand_h, pole_h) in SIDES.items():
        sh, ua, fa, hd, gn = ch
        dp, de, cw = off[S]
        g0, q0 = rest[gn]; hp0, hq0 = rest[hd]
        gp, gq = g0 + dp, qmul(q0, qeuler(*de))
        hq = qmul(gq, qmul(qinv(q0), hq0)); hp = gp + qrot(gq, qrot(qinv(q0), hp0 - g0))
        # clavicle: rotate the shoulder joint (local), carrying the upper arm root with it
        shq = qmul(rest[sh][1], qeuler(*(CLAV[S] * cw)))
        S0 = rest[sh][0] + qrot(shq, qrot(qinv(rest[sh][1]), rest[ua][0] - rest[sh][0]))
        uq0 = qmul(shq, qmul(qinv(rest[sh][1]), rest[ua][1]))
        E0r = rest[fa][0]; Ec = rest[sh][0] + qrot(shq, qrot(qinv(rest[sh][1]), E0r - rest[sh][0]))
        a = np.linalg.norm(E0r - rest[ua][0]); b = np.linalg.norm(hp0 - E0r)
        Sp = S0.copy(); shift = np.zeros(3); d = np.linalg.norm(hp - Sp)
        if d > (a + b) * 0.995:
            u = (hp - Sp) / d; shift = u * (d - (a + b) * 0.995); Sp = Sp + shift; d = (a + b) * 0.995
        u = (hp - Sp) / d
        x = (a * a - b * b + d * d) / (2 * d); h = math.sqrt(max(a * a - x * x, 0))
        fq0 = rest[fa][1]; rel0 = qmul(qinv(fq0), hq0); qstar = qmul(hq, qinv(rel0))
        Estar = hp - qrot(qstar, qrot(qinv(fq0), hp0 - E0r))
        C = Sp + u * x; vv = Estar - C; vv = vv - u * np.dot(vv, u)
        if np.linalg.norm(vv) < 1e-6:
            vv = Ec - S0; vv = vv - u * np.dot(vv, u)
        Ep = C + vv / np.linalg.norm(vv) * h
        # upper arm: rest frame carried by the clavicle, then aimed at the new elbow in the arm plane
        E0c, H0c = Ec, rest[sh][0] + qrot(shq, qrot(qinv(rest[sh][1]), hp0 - rest[sh][0]))
        pr = np.cross(E0c - S0, H0c - E0c); pn = np.cross(Ep - Sp, hp - Ep)
        Rua = aim(Ep - Sp, pn) @ aim(E0c - S0, pr).T
        ax0 = qrot(qinv(fq0), hp0 - E0r); ax0 /= np.linalg.norm(ax0)
        a1 = qrot(qstar, ax0); d1 = (hp - Ep) / np.linalg.norm(hp - Ep)
        cr = np.cross(a1, d1); sn = np.linalg.norm(cr); cs = float(np.dot(a1, d1))
        qs = np.array([0, 0, 0, 1.0]) if sn < 1e-9 else np.array([*(cr / sn * math.sin(math.atan2(sn, cs) / 2)), math.cos(math.atan2(sn, cs) / 2)])
        fq = qmul(qs, qstar)
        world = {sh: (rest[sh][0] + shift, shq), ua: (Sp, qmul(quat_of(Rua), uq0)), fa: (Ep, fq), hd: (hp, hq)}
        for hj in hand_h:
            jp, jq = rest[hj]
            world[hj] = (hp + qrot(hq, qrot(qinv(hq0), jp - hp0)), qmul(hq, qmul(qinv(hq0), jq)))
        for hj in pole_h:
            jp, jq = rest[hj]
            world[hj] = (Ep + qrot(fq, qrot(qinv(fq0), jp - E0r)), qmul(fq, qmul(qinv(fq0), jq)))
        for n in [sh, ua, fa, hd] + hand_h + pole_h:
            pw = W[rig.par[n]]; t, q = world[n]
            L[n] = (qrot(qinv(pw[1]), t - pw[0]), qmul(qinv(pw[1]), q))
            W[n] = world[n]
        rel = qmul(qinv(fq), hq)
        stats[S] = {'wrist': math.degrees(2 * math.acos(min(1, abs(float(np.dot(rel, rel0)))))), 'shift': float(np.linalg.norm(shift))}
    return L, stats


def solve(clip, f):
    return solve_offsets({S: offsets(clip, S, f) for S in SIDES})


NAMES = {'idle': 'friendly_idlepose', 'safe_action': 'safe_action', 'equip_safe': 'equip_safe'}


def build(sp, write=True):
    setup(sp)
    clips = {}; report = {}
    for clip, name in NAMES.items():
        N = spec[clip]['frames'] + 1
        frames, st = [], []
        for f in range(N):
            L, s = solve(clip, f); frames.append(L); st.append(s)
        clips[name] = frames; clips[name + '_l'] = frames
        report[name] = {S: {'max_wrist_deg': round(max(x[S]['wrist'] for x in st), 1),
                            'max_shoulder_shift_cm': round(100 * max(x[S]['shift'] for x in st), 1)} for S in SIDES}
    if write:
        write_clips(rig, spec['base'], clips, spec['out'])
        json.dump(report, open(spec['out'].replace('.glb', '_ik.json'), 'w'), indent=1)
    return clips, report


if __name__ == '__main__':
    c, r = build(json.load(open(sys.argv[1])))
    print('saved', spec['out'], json.dumps(r))
