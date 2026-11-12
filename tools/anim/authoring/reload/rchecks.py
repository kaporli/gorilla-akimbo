"""Numeric checks of a one-handed reload draft; no Blender.

usage: rchecks.py <spec.json> [--json out.json]
check(spec dict or path) -> dict. Camera: the raised-pose fit (eye [0, 1.61, -0.02], 105 deg horizontal, 16:9).

  end_cm, end_deg        first and last frame against the raised idle (rest glb), worst arm joint, both arms
  eye_cm (frame)         nearest point of the right gun to the eye over the clip          rule: >= 20
  cover_peak (frame)     largest share of the screen the right gun covers (percent)       rule: <= 18 (L01 long pick)
  cover_idle             the same in the raised idle
  left_eye_cm, left_cover_peak   the same for the left gun (rules apply in two-arm drafts)
  hidden                 [first, last] frame of the longest run with the gun fully out of view
  mag_float              frames between far and near in which the detached magazine is on screen (it hangs in the
                         air there: the hand that carries it does not exist)               rule: 0
  mag_insert_seen        frames between near and seated with the magazine on screen        rule: 0
  mag_exit               world velocity of the magazine over out..clear (cm/frame), its angle from straight down,
                         and whether it comes nearer than 30 cm to the eye
  handle_seen            frames of the handle window with the gun on screen (informational: a visible handle
                         action needs a motivating hit or jerk in the clip)
  wrist_swing (frame)    largest wrist bend against the idle, all frames; wrist_view: while the gun is on screen
                         rule: <= 113 (manifest topmag.wrist_deg), aim <= 70
  wrist_twist            largest hand twist about the forearm against the idle (deg)
  reach (frame)          shoulder to wrist over arm length, largest                        rule: <= 0.985
  shoulder_pull_cm       how far the shoulder joint had to move                            rule: <= 3
  hands_gap_cm (frame)   smallest distance between the two wrists                          rule: >= 8 (no clip)
  guns_gap_cm (frame)    smallest distance between the two guns (surfaces)                 rule: > 0 (two-arm contact: about 0)
  gun_forearm_cm         smallest distance right gun to left forearm line
  body_cm (frame)        smallest distance right gun to the torso, belt and thigh blocks (negative: inside; the blocks
                         are rough, so the rule is >= -5)
  speed_cm_f             fastest grip move per frame
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import Clip, qmul, qinv, qrot
from wclip import TClip
import gungeo, timing

EYE = np.array([0, 1.61, -0.02]); HH = math.radians(105.0 / 2); HV = math.atan(math.tan(HH) * 9 / 16)
GRID = (160, 90)
RULES = {'end_cm': 0.01, 'end_deg': 0.01, 'eye_cm': 20.0, 'cover_peak': 18.0, 'mag_float': 0, 'mag_insert_seen': 0, 'wrist_swing': 113.0,
         'wrist_view_aim': 70.0, 'reach': 0.985, 'shoulder_pull_cm': 3.0, 'hands_gap_cm': 8.0, 'guns_gap_cm': 0.0, 'body_cm': -5.0}
_pts = {}


def tris(path):
    g = Glb(path); out = []
    for m in g.j['meshes']:
        for pr in m['primitives']:
            P = np.asarray(g.acc(pr['attributes']['POSITION']), float); I = np.ravel(g.acc(pr['indices'])).astype(int).reshape(-1, 3)
            out.append(P[I])
    return np.concatenate(out)


def sample(T, n, seed=7):
    ar = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    rng = np.random.default_rng(seed); k = rng.choice(len(T), n, p=ar / ar.sum())
    u, v = rng.random(n), rng.random(n); f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    return T[k, 0] + (T[k, 1] - T[k, 0]) * u[:, None] + (T[k, 2] - T[k, 0]) * v[:, None]


def gun_points(gid, n=12000):
    """Surface points of the gun body (no magazine), gun axes."""
    if gid not in _pts:
        G = common.gun(gid)['mesh']; T = []
        for p in gungeo.BODY_PARTS:
            f = common.find('weapon_meshes', f'{G}__{p}.glb')
            if f: T.append(tris(f))
        _pts[gid] = sample(np.concatenate(T), n)
    return _pts[gid]


def mag_points(gid, n=1500):
    k = gid + ':mag'
    if k not in _pts:
        f = common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb')
        _pts[k] = sample(tris(f), n) if f else None
    return _pts[k]


_mag = {}


def mag_track(gid, clip):
    """Per frame: (translation, rotation) of the visible magazine in gun axes, and its distance from the seat (m).
    The visible magazine is the joint nearer its seat (the leaving one, then the incoming one)."""
    if (gid, clip) in _mag: return _mag[(gid, clip)]
    gun = common.gun(gid); b = gungeo.wanim(gun, 'base1'); m = gungeo.wanim(gun, 'mag_std')
    bs = b if 'mag_slot' in Glb(b).names else gungeo.wanim(gun, 'rcv1')
    gb = Glb(bs); an = [a['name'] for a in gb.j['animations']]
    st, sq = TClip(gb, clip if clip in an else ('reload' if 'reload' in an else an[0])).world(0)[gb.names.index('mag_slot')]
    mg = Glb(m); c = TClip(mg, clip); W0 = c.wf(0); out = []
    pair = [('magazine', 'mag_std' if 'mag_std' in mg.names else 'magazine')]
    if 'magazine_reload' in mg.names and 'mag_stdr' in mg.names and 'magazine_reload' in c.moved(): pair.append(('magazine_reload', 'mag_stdr'))
    skin = Glb(common.find('weapon_meshes', gun['mesh'] + '__mag_std_01.glb')); sj = [skin.names[j] for j in skin.j['skins'][0]['joints']]
    use_parent = 'mag_std' not in sj   # Hercules: the mesh hangs on the magazine joint
    for f in range(c.frames):
        W = c.wf(f); best = None
        for j, leaf in pair:
            d = float(np.linalg.norm(W[mg.names.index(j)][0] - W0[mg.names.index(j)][0]))
            if best is None or d < best[0]: best = (d, W[mg.names.index(j if use_parent else leaf)])
        d, (t, q) = best
        out.append((st + qrot(sq, t), qmul(sq, q), d))
    _mag[(gid, clip)] = out
    return out


def place(tq, V):
    t, (x, y, z, w) = tq
    R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                  [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    return np.asarray(t) + V @ R.T


def screen(P):
    Q = P - EYE; fwd = -Q[:, 2]; ok = fwd > 0.02
    sx = Q[:, 0] / np.maximum(fwd, 1e-6) / math.tan(HH); sy = Q[:, 1] / np.maximum(fwd, 1e-6) / math.tan(HV)
    return sx, sy, ok & (np.abs(sx) < 1) & (np.abs(sy) < 1)


def cover(P):
    sx, sy, on = screen(P)
    if not on.any(): return 0.0
    g = np.zeros((GRID[1], GRID[0]), bool)
    ix = np.clip(((sx[on] + 1) / 2 * GRID[0]).astype(int), 0, GRID[0] - 1); iy = np.clip(((1 - sy[on]) / 2 * GRID[1]).astype(int), 0, GRID[1] - 1)
    g[iy, ix] = True
    return 100.0 * float(g.mean())


def seg_dist(P, a, b):
    """Distance of points P to segment a-b."""
    ab = b - a; t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def check(spec):
    if isinstance(spec, str): spec = json.load(open(spec))
    gid, lid, clip = spec['_gun'], spec['_left_gun'], spec['_gun_clip']; T = spec['_timing']; N = spec['frames']
    g = Glb(spec['out']); c = Clip(g, spec['clip']); nm = g.names; ix = {n: i for i, n in enumerate(nm)}
    r = Glb(spec['src']); R0 = Clip(r, 'idle').world(0)
    PR, PL, PM = gun_points(gid), gun_points(lid, 5000), mag_points(gid); MT = mag_track(gid, clip)
    arm = [n for n in nm if (n.startswith('Right') or n.startswith('Left')) and any(k in n for k in ('Shoulder', 'Arm', 'ForeArm', 'Hand')) and 'Leg' not in n] + ['WeaponRight', 'WeaponLeft']
    out = {'draft': spec['_draft'], 'gun': gid, 'frames': N, 'two_arm': spec.get('_two_arm', False)}
    W = [c.world(f) for f in range(N)]

    def endpose(f):
        dc = dd = 0.0
        for n in arm:
            t, q = W[f][ix[n]]; t0, q0 = R0[r.names.index(n)]
            dc = max(dc, float(np.linalg.norm(t - t0)) * 100); dd = max(dd, math.degrees(2 * math.acos(min(1.0, abs(float(np.dot(q, q0)))))))
        return dc, dd
    e0, e1 = endpose(0), endpose(N - 1)
    out['end_cm'] = round(max(e0[0], e1[0]), 4); out['end_deg'] = round(max(e0[1], e1[1]), 4)
    covL = []; eyeL = []; cov = []; eye = []; gap = []; body = []; gfa = []; hands = []; magon = []; speed = [0.0]; wr = []; tw = []; reach = []; sh = []
    hip, sp3 = W[0][ix['Hips']][0], W[0][ix['Spine3']][0] + np.array([0, 0.12, 0])
    legs = [(W[0][ix[f'{s}UpLeg']][0], W[0][ix[f'{s}Leg']][0]) for s in ('Left', 'Right')]
    belt = (hip + np.array([-0.17, -0.02, 0]), hip + np.array([0.17, -0.02, 0]))
    S0 = {}
    for S in ('Right', 'Left'):
        hq0, fq0 = R0[r.names.index(f'{S}Hand')][1], R0[r.names.index(f'{S}ForeArm')][1]; S0[S] = (hq0, fq0, R0[r.names.index(f'{S}Arm')][0])
    for f in range(N):
        Wf = W[f]; GR = place(Wf[ix['WeaponRight']], PR); GL = place(Wf[ix['WeaponLeft']], PL)
        cov.append(cover(GR)); eye.append(float(np.linalg.norm(GR - EYE, axis=1).min()) * 100)
        covL.append(cover(GL)); eyeL.append(float(np.linalg.norm(GL - EYE, axis=1).min()) * 100)
        a, b = GR[::6], GL[::4]; gap.append(float(np.sqrt(((a[:, None] - b[None]) ** 2).sum(2)).min()) * 100)
        d = np.minimum.reduce([seg_dist(GR, hip, sp3) - 0.15, seg_dist(GR, *belt) - 0.12] + [seg_dist(GR, *l) - 0.085 for l in legs]); body.append(float(d.min()) * 100)
        gfa.append(float(seg_dist(GR, Wf[ix['LeftForeArm']][0], Wf[ix['LeftHand']][0]).min()) * 100)
        hands.append(float(np.linalg.norm(Wf[ix['RightHand']][0] - Wf[ix['LeftHand']][0])) * 100)
        if f: speed.append(float(np.linalg.norm(Wf[ix['WeaponRight']][0] - W[f - 1][ix['WeaponRight']][0])) * 100)
        if PM is not None:
            mt, mq, md = MT[min(f, len(MT) - 1)]; gt, gq = Wf[ix['WeaponRight']]
            MW = place((gt + qrot(gq, mt), qmul(gq, mq)), PM); magon.append((bool(screen(MW)[2].any()), md, MW.mean(0)))
        row_w = 0.0; row_t = 0.0; row_r = 0.0; row_s = 0.0
        for S in ('Right', 'Left'):
            hq0, fq0, s0 = S0[S]; hp, hq = Wf[ix[f'{S}Hand']]; ep, fq = Wf[ix[f'{S}ForeArm']]; sp = Wf[ix[f'{S}Arm']][0]
            uf = (hp - ep) / np.linalg.norm(hp - ep); rel = qmul(hq, qinv(qmul(fq, qmul(qinv(fq0), hq0))))
            if rel[3] < 0: rel = -rel
            row_w = max(row_w, 2 * math.degrees(math.acos(min(1.0, math.sqrt(rel[3] ** 2 + np.dot(rel[:3], uf) ** 2)))))
            row_t = max(row_t, abs(math.degrees(2 * math.atan2(np.dot(rel[:3], uf), rel[3]))))
            row_r = max(row_r, float(np.linalg.norm(hp - sp) / (np.linalg.norm(ep - sp) + np.linalg.norm(hp - ep))))
            row_s = max(row_s, float(np.linalg.norm(sp - s0)) * 100)
        wr.append(row_w); tw.append(row_t); reach.append(row_r); sh.append(row_s)
    am = lambda a: int(np.argmax(a)); an = lambda a: int(np.argmin(a))
    out['eye_cm'] = [round(min(eye), 1), an(eye)]; out['cover_peak'] = [round(max(cov), 1), am(cov)]; out['cover_idle'] = round(cov[0], 1)
    out['cover_mean'] = round(float(np.mean(cov)), 1)
    out['left_eye_cm'] = [round(min(eyeL), 1), an(eyeL)]; out['left_cover_peak'] = [round(max(covL), 1), am(covL)]; out['left_cover_idle'] = round(covL[0], 1)
    best = (0, 0, -1); f = 0
    while f < N:
        if cov[f] == 0:
            k = f
            while k + 1 < N and cov[k + 1] == 0: k += 1
            if k - f + 1 > best[0]: best = (k - f + 1, f, k)
            f = k + 1
        else: f += 1
    out['hidden'] = [best[1], best[2]] if best[0] else None
    if magon:
        far = T.get('far') or T['out'] + 5; near, seated, mo, cl = T['near'], T['seated'], T['out'], T.get('clear') or T['out'] + 3
        out['mag_float'] = int(sum(1 for f in range(far, near) if magon[f][0]))
        out['mag_float_frames'] = [f for f in range(far, near) if magon[f][0]][:40]
        out['mag_insert_seen'] = int(sum(1 for f in range(near, seated) if magon[f][0]))
        v = (magon[cl][2] - magon[mo - 1][2]) / max(cl - mo + 1, 1) * 100; sp = float(np.linalg.norm(v))
        out['mag_exit'] = {'v_cm_f': [round(float(x), 1) for x in v], 'speed': round(sp, 1), 'from_down_deg': round(math.degrees(math.acos(np.clip(-v[1] / max(sp, 1e-9), -1, 1)))),
                           'seen_at_out': bool(magon[mo][0]), 'seen_at_clear': bool(magon[cl][0]),
                           'eye_cm': round(min(float(np.linalg.norm(magon[f][2] - EYE)) for f in range(mo, far + 1)) * 100, 1)}
    if T.get('handle'):
        h0, h1 = T['handle']; out['handle_seen'] = int(sum(1 for f in range(h0, min(h1, N - 1) + 1) if cov[f] > 0)); out['handle_window'] = [h0, h1]
    view = [f for f in range(N) if cov[f] > 0]
    out['wrist_swing'] = [round(max(wr), 1), am(wr)]; out['wrist_view'] = round(max([wr[f] for f in view] or [0]), 1); out['wrist_twist'] = [round(max(tw), 1), am(tw)]
    out['reach'] = [round(max(reach), 3), am(reach)]; out['shoulder_pull_cm'] = round(max(sh), 1)
    out['hands_gap_cm'] = [round(min(hands), 1), an(hands)]; out['guns_gap_cm'] = [round(min(gap), 1), an(gap)]
    out['gun_forearm_cm'] = [round(min(gfa), 1), an(gfa)]; out['body_cm'] = [round(min(body), 1), an(body)]; out['speed_cm_f'] = [round(max(speed), 1), am(speed)]
    out['cover_per_4f'] = [round(x, 1) for x in cov[::4]]
    fails = []
    v = lambda k: out[k][0] if isinstance(out[k], list) else out[k]
    if v('end_cm') > RULES['end_cm'] or v('end_deg') > RULES['end_deg']: fails.append('end pose')
    if v('eye_cm') < RULES['eye_cm']: fails.append(f"eye {v('eye_cm')} cm")
    if v('cover_peak') > RULES['cover_peak']: fails.append(f"cover {v('cover_peak')} %")
    if out['two_arm'] and v('left_eye_cm') < RULES['eye_cm']: fails.append(f"left gun eye {v('left_eye_cm')} cm")
    if out['two_arm'] and v('left_cover_peak') > RULES['cover_peak']: fails.append(f"left gun cover {v('left_cover_peak')} %")
    if out.get('mag_float', 0) > 0: fails.append(f"magazine floats in view {out['mag_float']} f")
    if out.get('mag_insert_seen', 0) > 0: fails.append(f"insert in view {out['mag_insert_seen']} f")
    if v('wrist_swing') > RULES['wrist_swing']: fails.append(f"wrist {v('wrist_swing')} deg")
    if v('reach') > RULES['reach']: fails.append(f"reach {v('reach')}")
    if v('shoulder_pull_cm') > RULES['shoulder_pull_cm']: fails.append(f"shoulder pulled {v('shoulder_pull_cm')} cm")
    if v('hands_gap_cm') < RULES['hands_gap_cm']: fails.append(f"hands {v('hands_gap_cm')} cm apart")
    if v('guns_gap_cm') <= RULES['guns_gap_cm'] and not out['two_arm']: fails.append('guns cross')
    if v('body_cm') < RULES['body_cm']: fails.append(f"gun {-v('body_cm')} cm inside the body")
    out['fails'] = fails
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]; jo = common.opt(argv, '--json')
    o = check(argv[0])
    for k, v in o.items(): print(f'{k:18s} {v}')
    if jo: json.dump(o, open(jo, 'w'), indent=1)
