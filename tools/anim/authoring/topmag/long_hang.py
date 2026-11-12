"""hang (hang and punch, pick L06) specs for long partner guns.
left : top-magazine gun in the LEFT hand, long gun in the right = data/picks/L06.json keys unchanged + elbow swivel
       (wrist bend fix).
right: top-magazine gun in the RIGHT hand, long gun in the left = L06 mirrored across V's centre plane, then
       re-aimed: the magazine exits back and to the gun's own left (toward the middle), so the punch comes from lower
       and further forward, driving up and back with a small outward part instead of the mirror's strong outward push.
Elbow swivel: the striking elbow lifts out during the punch (f12-f42) so the wrist bends less. The gun paths are
untouched by it.
Per gun a bump (smooth world translation of the long gun over f9-18-28-36, along the receiver top's normal at the
hit frame) so the contact is about 2 mm penetration. Guns whose bumps differ by <= 3 mm share one spec (the group's
mean bump). Female = same spec, other body, bumps refit.
Used through gen_long.py."""
import json, math
import numpy as np
from geo import load_spec, app, gunM, magJ, box_signed, tris, hand, M4, pick_spec, DATA, SIDES

HIT = 25
REF = 'carnage'          # the gun the pick was made with: its clip keeps the original path when the fit is small
P = json.load(open(DATA + 'picks/L06_params.json')); L06 = pick_spec('L06')
# swivel of the striking elbow (deg, Right arm sign; mirrored for the left arm). Negative lifts the right elbow up and out.
SWIVEL = [[0, [0]], [12, [0]], [21, [-22]], [26, [-38]], [31, [-38]], [37, [-18]], [44, [0]], [95, [0]]]
# re-aim of the 'rel' keys (strike point relative to the target, world m). Original, mirrored:
#   f18 [-0.14,-0.16,-0.06]  f21 [-0.13,-0.17,-0.05]  f25 0  f27 [-0.015,0.06,0]  f30 [-0.045,0.09,-0.05]  f34 [-0.07,0.03,-0.09]
REAIM = {18: [-0.10, -0.18, -0.10], 21: [-0.075, -0.19, -0.10], 23: [-0.036, -0.105, -0.055]}


def M(p): return [-p[0], p[1], p[2]]
def MR(r): return [r[0], -r[1], -r[2]]
def MK(keys): return [[k[0], M(k[1]), MR(k[2])] for k in keys]


def base_left():
    left = json.loads(json.dumps(L06))
    left['swivel'] = {'Right': SWIVEL}
    left['_note'] = 'L06.json keys + Right elbow swivel'
    return left


def base_right(reaim=REAIM):
    """reaim {} gives the pure mirror (for comparison)"""
    pure = not reaim
    # top-magazine gun (right hand): L06's left keys mirrored. Kick as the mirrored uppercut: up, back, a little outward.
    sh_keys = MK(L06['keys']['Left'])
    shakes = {"Right": [{"type": "kick", "f": HIT, "move": [0.008, 0.028, 0.022], "rot": [-7, -4, -9], "attack": 0.7, "release": 5.0, "lag": 0.7}],
              "Left": [{"type": "kick", "f": HIT, "move": M(P['rkick_move']), "rot": MR(P['rkick_rot']), "attack": 0.5, "release": 2.5}]}
    spec = {"body": 'pma', "template": "reload", "clip": "smack", "frames": 96,
            "keys": {"Right": sh_keys, "Left": [[0, [0, 0, 0], [0, 0, 0]]]}, "shakes": shakes}
    S_STRIKE = P['strike']; T_MAG = M(P['target'])          # inner (left) face of the magazine, lower half
    ns = load_spec(spec)
    gp, gq = ns['gun_pose']('Right', HIT); T = gp + ns['qrot'](gq, np.array(T_MAG))
    g0l, q0l = ns['rest'][ns['SIDES']['Left'][0][4]]; R0 = M4(g0l, q0l)[:3, :3]
    Mx = np.diag([-1., 1, 1])

    def euler_from(Rw):
        R = R0.T @ Rw
        y = math.asin(max(-1, min(1, R[0, 2]))); p = math.atan2(-R[1, 2], R[2, 2]); r = math.atan2(-R[0, 1], R[0, 0])
        return [round(math.degrees(v), 1) for v in (p, y, r)]

    def frame_rot(barrel, top):
        z = -np.array(barrel, float); z /= np.linalg.norm(z)
        y = np.array(top, float); y = y - z * (y @ z); y /= np.linalg.norm(y)
        return np.stack([np.cross(y, z), y, z], 1)

    def ear_m(el, az, ph):
        """L06's (barrel elevation, azimuth, top angle), mirrored: world rotation M R M, as euler on the LEFT gun rest"""
        e, a = math.radians(el), math.radians(az)
        b = np.array([math.cos(e) * math.sin(a), math.sin(e), -math.cos(e) * math.cos(a)])
        ref = np.array([-1., 0, 0]) + b * b[0]; ref /= np.linalg.norm(ref); o = np.cross(b, ref)
        if o[2] < 0: o = -o
        p = math.radians(ph)
        R = frame_rot(b, ref * math.cos(p) + o * math.sin(p))
        return euler_from(Mx @ R @ Mx)

    def off(rel, rot):
        q = ns['qmul'](q0l, ns['qeuler'](*rot))
        return [round(float(x), 4) for x in (T + np.array(rel) - ns['qrot'](q, np.array(S_STRIKE)) - g0l)]

    rot = {k: ear_m(*v) for k, v in P['rots'].items()}
    keys = [[0, [0, 0, 0], [0, 0, 0]]]
    for f, kind, v, rk in P['keys']:
        r = rot[rk] if isinstance(rk, str) else MR(rk)
        if kind == 'rel':
            v = reaim.get(f, M(v)); keys.append([f, off(v, r), r])
        else:
            keys.append([f, M(v), r])
        if f == 21 and not pure:   # extra drive key: the punch comes up from below, lateral motion dying out before contact
            r23 = [round((a + b) / 2, 1) for a, b in zip(rot['wind2'], rot['hit'])]
            keys.append([23, off(reaim[23], r23), r23])
    spec['keys']['Left'] = keys
    spec['swivel'] = {'Left': [[k[0], [-k[1][0]]] for k in SWIVEL]}
    spec['_strike'] = S_STRIKE; spec['_target'] = T_MAG; spec['_T_world'] = [round(float(x), 4) for x in T]
    spec['_note'] = 'L06 mirrored (top-magazine gun right), re-aimed rel keys f18-23, Left elbow swivel'
    return spec


# ---- per gun bump --------------------------------------------------------------------------------------------------
def contact(ns, sh, st, Pts, f=HIT):
    """signed contact (+ penetration / - gap, m) of points (striker gun-local) with the magazine box at frame f"""
    Pm = app(np.linalg.inv(magJ(ns, sh, f)), app(gunM(ns, st, f), Pts))
    return box_signed(Pm).max()


def bumped(spec, st, move, win=(9, 18, 28, 36)):
    s = json.loads(json.dumps(spec))
    if any(abs(x) > 1e-5 for x in move): s['bumps'] = {st: [{'f': list(win), 'move': [round(float(x), 4) for x in move]}]}
    else: s.pop('bumps', None)
    return s


def bump_axis(spec, st):
    """striking feature's outward normal at the hit frame (receiver top, gun-local +y), world"""
    ns = load_spec(spec)
    return gunM(ns, st, HIT)[:3, :3] @ np.array([0, 1., 0])


def solve_bump(spec, sh, st, gun, target=0.002, tol=0.0005):
    """shift s (m) along -axis (+ = away from the magazine) so the contact at the hit frame is `target` penetration"""
    ax = bump_axis(spec, st)
    V, _ = tris(gun); Pts = np.vstack([V[::2], hand(spec['body'], st)])
    def c(s):
        return contact(load_spec(bumped(spec, st, -s * ax)), sh, st, Pts)
    s0, c0 = 0.0, c(0.0)
    s = s0 + (c0 - target)
    for _ in range(8):
        cs = c(s)
        if abs(cs - target) < tol: break
        d = (cs - c0) / (s - s0) if abs(s - s0) > 1e-6 else -1
        if abs(d) < 0.2: d = -1 if d <= 0 else d
        s0, c0 = s, cs; s = s - (cs - target) / d
    return round(s, 4), cs


_BASE = {}


def specs(side, body, guns):
    """{gun: spec} for one hand and body; guns in one sharing group get the same spec"""
    if side not in _BASE:
        _BASE[side] = base_left() if side == 'left' else base_right()
    sh, st = SIDES[side]
    b = json.loads(json.dumps(_BASE[side])); b['body'] = body
    shifts = {}; hit = {}
    for g in guns:
        shifts[g], hit[g] = solve_bump(b, sh, st, g)
    # group: sort by shift, start a new group when the spread would exceed 3 mm
    order = sorted(guns, key=lambda g: shifts[g]); grps = [[order[0]]]
    for g in order[1:]:
        if shifts[g] - shifts[grps[-1][0]] <= 0.003: grps[-1].append(g)
        else: grps.append([g])
    ax = bump_axis(b, st)
    out = {}
    for grp in grps:
        s = round(float(np.mean([shifts[g] for g in grp])), 4)
        if abs(s) < 0.0015 and REF in grp: s = 0.0          # the reference gun's version stays the original
        sp = bumped(b, st, -s * ax)
        sp['_shared_by'] = grp; sp['_shift_mm'] = round(s * 1000, 1)
        for g in grp:
            out[g] = dict(sp, _bump={'own_shift_mm': round(float(shifts[g]) * 1000, 1), 'own_contact_mm': round(float(hit[g]) * 1000, 1)})
    return out
