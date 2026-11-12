"""axe (overhead axe, pick L07) specs for long partner guns: top-magazine gun left (L07 original) and right (mirror,
re-aimed), six long guns, male and female. Each clip = the hand's base spec + one smooth translation bump of the long
gun so its mesh meets the magazine at the hit frame (target penetration TGT cm), plus a female correction of the
strike point. Fixes on every version vs L07: shoulder of the striking arm 6 cm forward f20-36 (wrist bend in the
bounce), and the contact pose turned a few degrees about the strike point so the two hands do not touch (DE_HIT).
Used through gen_long.py."""
import json
import numpy as np
from geo import load_spec, app, gunM, magJ, box_signed, tris, M4

HIT = 25
S = [0.0, -0.036, -0.09]          # strike point: receiver underside just ahead of the trigger guard (gun-local)
TM = [-0.026, 0.100, -0.035]      # target on the magazine (mag frame): top edge on the striker's side, 3 cm behind its front
SHOULDER = {'f': [10, 20, 36, 46], 'move': [0, 0, -0.06]}   # striking shoulder forward: wrist bend in the bounce
DE_HIT = [-4, 10, 4]              # euler delta on the strike keys (f23 x0.4, f24 x0.8, f25-26 x1, f30 x0.5; f23-26 turn
                                  # about the strike point): hands gap
BUMP_F = [14, 22, 28, 36]         # contact bump window (ramp in, full, full, ramp out)
TGT = 0.3                         # wanted gun-in-magazine depth at the hit frame, cm
# mirror re-aim: last 10 cm of the chop straight down and back with a slight pull toward V's middle (the magazine
# exits back and to V's left for either hand; a pure mirror would push it to the right)
MIRROR_U = [-0.10, -0.72, 0.65]
SHARE_MM = 3.0                    # guns whose bumps differ by less than this share one clip


def M(p): return [-p[0], p[1], p[2]]
def MR(r): return [r[0], -r[1], -r[2]]
def MK(keys): return [[k[0], M(k[1]), MR(k[2])] for k in keys]


def contact(ns, gun, sh, st, f=HIT):
    """max signed depth (cm) of the long gun's verts in the magazine box at f (+ = penetration, - = miss)"""
    P = tris(gun)[0]
    return box_signed(app(np.linalg.inv(magJ(ns, sh, f)) @ gunM(ns, st, f), P)).max() * 100


left = [[0, [0, 0, 0], [0, 0, 0]],
        [9, [0.001, 0.002, -0.002], [0.5, 1, 1.5]],
        [18, [0.008, 0.018, -0.008], [-1, 3, 5]],
        [HIT, [0.016, 0.040, -0.014], [-5, 6, 11]],
        [31, [0.012, 0.040, -0.012], [-4, 5, 9]],
        [36, [0.004, -0.06, -0.04], [-8, 3, 4]],
        [46, [-0.05, -0.62, -0.10], [-30, 0, 0]], [62, [-0.05, -0.62, -0.10], [-30, 0, 0]],
        [81, [0.004, 0.010, -0.006], [3, 0, -1]], [89, [0, -0.003, 0], [-1, 0, 0]], [95, [0, 0, 0], [0, 0, 0]]]
SH_KICK = {"type": "kick", "f": HIT, "move": [-0.018, -0.030, 0.014], "rot": [5, 3, 11], "attack": 0.7, "release": 5.0, "lag": 0.7}
ST_KICK = {"type": "kick", "f": HIT, "move": [0.030, 0.055, -0.020], "rot": [9, -10, 4], "attack": 0.5, "release": 4.0, "lag": 0.5}


def base(hand, de_hit=None, shoulder=True, mirror_u=MIRROR_U):
    """hand 'left' = top-magazine gun in the left hand (L07), 'right' = mirror. Male body; returns the spec."""
    de_hit = DE_HIT if de_hit is None else de_hit
    mir = hand == 'right'
    sh, st = ('Right', 'Left') if mir else ('Left', 'Right')
    f = (lambda p: M(p)) if mir else (lambda p: list(p))
    fr = (lambda r: MR(r)) if mir else (lambda r: list(r))
    shk = dict(SH_KICK); stk = dict(ST_KICK)
    if mir:
        shk.update(move=M(SH_KICK['move']), rot=MR(SH_KICK['rot'])); stk.update(move=M(ST_KICK['move']), rot=MR(ST_KICK['rot']))
    spec = {"body": 'pma', "template": "reload", "clip": "smack", "frames": 96,
            "keys": {sh: MK(left) if mir else left, st: [[0, [0, 0, 0], [0, 0, 0]]]}, "shakes": {sh: [shk]}}
    ns = load_spec(spec)
    tm = M(TM) if mir else TM          # mag x axis ~ world -x for either hand: the striker-side edge flips
    T = app(magJ(ns, sh, HIT), np.array([tm]))[0]
    g0, q0 = ns['rest'][ns['SIDES'][st][0][4]]

    def place(X, e):
        R = M4([0, 0, 0], ns['qmul'](q0, ns['qeuler'](*e)))[:3, :3]
        return [round(float(v), 4) for v in (np.array(X) - R @ np.array(S) - g0)]
    def at(X, e): return [place(X, e), e]
    def dh(e, w=1.0): return [round(a + w * b, 2) for a, b in zip(e, fr(de_hit))]
    u = np.array([-0.45, -0.75, 0.48]) if not mir else np.array(mirror_u)
    u = u / np.linalg.norm(u)
    W = lambda p: f(p) if not mir else M(p)   # world point mirror (x -> -x)
    keys = [[0, [0, 0, 0], [0, 0, 0]],
            [6, f([0.006, -0.012, 0.004]), fr([-3, -1, 1])],
            [14, f([0.04, 0.15, 0.02]), fr([45, -4, -14])],
            [19, f([0.06, 0.215, 0.035]), fr([66, -6, -20])],
            [21, f([0.062, 0.225, 0.04]), fr([69, -5, -21])],
            [22, *at(W([0.15, 1.795, -0.42]), fr([68, 4, -21]))],
            [23, *at(W([0.03, 1.765, -0.44]), dh(fr([63, 16, -20]), 0.4))],
            [24, *at(T - u * 0.10, dh(fr([60, 28, -20]), 0.8))],
            [HIT, *at(T, dh(fr([57, 37, -20])))],
            [26, *at(T + u * 0.015, dh(fr([55, 40, -20])))],
            [30, f([-0.11, 0.17, 0.03]), dh(fr([66, 20, -18]), 0.5)],
            [34, f([-0.07, 0.06, 0.0]), fr([48, 10, -10])],
            [45, f([0.05, -0.62, -0.10]), fr([-30, 0, 0])], [62, f([0.05, -0.62, -0.10]), fr([-30, 0, 0])],
            [78, f([-0.004, 0.012, -0.006]), fr([3, 0, 1])], [86, f([0, -0.004, 0]), fr([-1, 0, 0])], [95, [0, 0, 0], [0, 0, 0]]]
    spec['keys'][st] = keys
    spec['shakes'][st] = [stk]
    if shoulder: spec['shoulder'] = {st: [dict(SHOULDER, move=f(SHOULDER['move']))]}
    spec['_sides'] = [sh, st]; spec['_strike'] = S; spec['_target_mag'] = tm
    spec['_target_world'] = [round(float(v), 4) for v in T]; spec['_u'] = u.round(3).tolist()
    return spec


def bump_for(spec, body, gun, ref_strike_mag=None):
    """body swap + bump: 3D move putting the strike point where it is (mag frame) in the male reference, then a
    move along the magazine's top normal so the gun mesh sinks TGT cm into the magazine box at the hit frame."""
    sh, st = spec['_sides']
    s = json.loads(json.dumps(spec)); s['body'] = body; s['bumps'] = {}
    move = np.zeros(3)
    if ref_strike_mag is not None:
        ns = load_spec(s); MJ = magJ(ns, sh, HIT)
        cur = app(gunM(ns, st, HIT), np.array([S]))[0]; want = app(MJ, np.array([ref_strike_mag]))[0]
        move = want - cur
    def depth(mv):
        s['bumps'] = {st: [{'f': BUMP_F, 'move': [round(float(x), 4) for x in mv]}]}
        return contact(load_spec(s), gun, sh, st)
    ns = load_spec(s); nrm = -magJ(ns, sh, HIT)[:3, 2]         # magazine top outward normal (mag -z), world
    lo, hi = -0.04, 0.10                                          # depth decreases as we move out along the normal
    for _ in range(18):
        mid = (lo + hi) / 2
        if depth(move + nrm * mid) > TGT: lo = mid
        else: hi = mid
    mv = move + nrm * (lo + hi) / 2
    if np.linalg.norm(mv) < 0.0015: mv = np.zeros(3)
    return mv


def strike_mag(spec):
    sh, st = spec['_sides']; ns = load_spec(spec)
    return app(np.linalg.inv(magJ(ns, sh, HIT)) @ gunM(ns, st, HIT), np.array([S]))[0]


_BASE = {}


def specs(side, body, guns):
    """{gun: spec} for one hand and body; guns in one sharing group get the same spec"""
    if side not in _BASE:
        b = base(side); _BASE[side] = (b, strike_mag(b))
    b, ref = _BASE[side]
    mv = {g: bump_for(b, body, g, None if body == 'pma' else ref) for g in guns}
    # share: greedy groups of guns whose bumps are within SHARE_MM of the group's first member
    grps = []
    for g in guns:
        for grp in grps:
            if np.linalg.norm(mv[g] - mv[grp[0]]) * 1000 < SHARE_MM: grp.append(g); break
        else: grps.append([g])
    out = {}
    for grp in grps:
        m = np.mean([mv[g] for g in grp], 0)
        s = json.loads(json.dumps(b)); s['body'] = body
        s['bumps'] = {s['_sides'][1]: [{'f': BUMP_F, 'move': [round(float(x), 4) for x in m]}]} if np.linalg.norm(m) >= 0.0015 else {}
        s['_guns'] = grp
        for g in grp:
            out[g] = dict(s, _bump={'own_bump_cm': (mv[g] * 100).round(2).tolist(), 'clip_bump_cm': (m * 100).round(2).tolist()})
    return out
