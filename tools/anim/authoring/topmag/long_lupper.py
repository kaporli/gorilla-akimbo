"""lupper (upright uppercut, pick L01) specs for long partner guns.
left  = top-magazine gun in the LEFT hand, long gun in the right: data/picks/L01.json unchanged (fitted on the Carnage).
right = top-magazine gun in the RIGHT hand, long gun in the left: L01 mirrored across V's centre plane (x -> -x,
        yaw/roll negated, Left <-> Right), then re-aimed: the magazine exits back and to the gun's own left (toward
        the middle), so the wind-up sits further under the magazine and further forward and the drive pushes up and
        back instead of up and outward (REAIM, T_MAG_M).
Per gun: one smooth world translation bump of the long gun (window BWIN), the shortest move that makes it touch the
magazine at the hit frame by TOUCH. Female: same specs, other body, bumps refit.
Used through gen_long.py."""
import json
import numpy as np
from geo import load_spec, gunM, magJ, app, box_signed, contact_mt, dense, pick_spec, SIDES

HIT = 25
REF = 'carnage'          # the gun the pick was made with
TOUCH = 0.001            # target overlap at the hit frame (L01 Carnage: 1.1 mm)
BWIN = [9, 18, 28, 36]   # bump: ramp in f9..18, full f18..28, ramp out f28..36
SHARE_MM = 3.0           # guns whose fitted bumps differ by less than this share one clip (mean bump)
OKRANGE = (0.0, 0.0025)  # no bump when the base clip already touches by 0..2.5 mm
L01 = pick_spec('L01')


def contact(ns, sh, st, gun, f=HIT):
    """signed depth (m) of the long gun into the magazine box at frame f, and the deepest sample (gun-local)"""
    D = dense(gun)
    d = box_signed(app(np.linalg.inv(magJ(ns, sh, f)), app(gunM(ns, st, f), D)))
    k = int(np.argmax(d)); return float(d[k]), D[k]


def M(p): return [-p[0], p[1], p[2]]
def MR(r): return [r[0], -r[1], -r[2]]
def MK(keys): return [[k[0], M(k[1]), MR(k[2])] for k in keys]
def MS(sh): return dict(sh, move=M(sh['move']), rot=MR(sh['rot']))


# ---- mirror --------------------------------------------------------------------------------------------------------
T_MAG_M = [-0.023, 0.026, 0.135]       # L01 target (edge underside, 0.12 from the gun origin) on the left edge, 1.5 cm
                                       # further back so the drive from underneath clears the right hand on the grip
S_STRIKE_M = [0.020, 0.079, -0.005]    # top-RIGHT edge of the receiver just ahead of the (left) hand
# L01 path (strike point offset from the target, world m; rotation) mirrored. REAIM: the wind-up keys move in under
# the magazine and forward, so the drive f22..25 comes more from underneath and pushes more backward along the exit
# (pure mirror f22 [-0.065,-0.13,-0.075], f18 [-0.08,-0.11,-0.07]). Further in (x > -0.04) hits the right hand.
REAIM = {18: [-0.055, -0.10, -0.095], 22: [-0.04, -0.12, -0.10]}


def path_m(reaim=REAIM):
    P = [(12, [0.16, -0.08, -0.05], [12, -8, 10]), (18, [0.08, -0.11, -0.07], [32, -8, 18]),
         (22, [0.065, -0.13, -0.075], [42, -6, 22]), (HIT, [0, 0, 0], [58, -4, 26]),
         (27, [0.02, 0.05, 0.02], [66, -8, 20]), (30, [0.08, 0.06, 0.01], [80, -10, 10]), (34, [0.11, -0.02, -0.03], [52, -6, 4])]
    out = []
    for f, rel, rot in P:
        rel = M(rel)
        rot = MR(rot)
        if f in reaim:
            v = reaim[f]
            if isinstance(v, dict): rel = v.get('rel', rel); rot = v.get('rot', rot)
            elif isinstance(v, list): rel = v
            else: rel[0] = v
        out.append((f, rel, rot))
    for f, v in reaim.items():          # extra keys not in the L01 path
        if f not in [p[0] for p in P]: out.append((f, v['rel'], v['rot']))
    return sorted(out, key=lambda p: p[0])


def mirror_spec(reaim=REAIM, lift=0.0, body='pma', kick=None, tmag=None):
    spec = {k: L01[k] for k in ('template', 'clip', 'frames')}
    spec['body'] = body
    shingen = MK(L01['keys']['Left'])
    k = MS(L01['shakes']['Left'][0])
    # the top-magazine gun's kick follows the new push: up and back, less outward than the pure mirror
    k['move'] = kick or [0.010, 0.030, 0.020]
    spec['shakes'] = {'Right': [k], 'Left': [MS(L01['shakes']['Right'][0])]}
    spec['keys'] = {'Right': shingen, 'Left': [[0, [0, 0, 0], [0, 0, 0]]]}
    ns = load_spec(spec)
    tm = tmag or T_MAG_M
    T = app(gunM(ns, 'Right', HIT), np.array([tm]))[0] + np.array([0, lift, 0])
    g0, q0 = ns['rest'][ns['SIDES']['Left'][0][4]]
    qmul, qeuler, qrot = ns['qmul'], ns['qeuler'], ns['qrot']
    def off(rel, rot):
        q = qmul(q0, qeuler(*rot))
        return [round(float(x), 4) for x in (T + np.array(rel) - qrot(q, np.array(S_STRIKE_M)) - g0)]
    Rk = L01['keys']['Right']
    left = [[0, [0, 0, 0], [0, 0, 0]], [5, M(Rk[1][1]), MR(Rk[1][2])]]
    left += [[f, off(rel, rot), rot] for f, rel, rot in path_m(reaim)]
    left += [[k[0], M(k[1]), MR(k[2])] for k in Rk if k[0] >= 45]
    spec['keys']['Left'] = left
    spec['_strike'] = S_STRIKE_M; spec['_target'] = tm; spec['_reaim'] = {str(k): v for k, v in reaim.items()}
    return spec


def fit_mirror(reaim=REAIM, touch=TOUCH, body='pma', tmag=None):
    """lift the target in world y until the reference gun touches the magazine by `touch` at the hit frame"""
    lift = 0.0
    for _ in range(5):
        sp = mirror_spec(reaim, lift, body, tmag=tmag); d, _ = contact(load_spec(sp), 'Right', 'Left', REF)
        lift += touch - d
    sp = mirror_spec(reaim, lift, body, tmag=tmag); d, pt = contact(load_spec(sp), 'Right', 'Left', REF)
    sp['_lift'] = round(lift, 4); sp['_contact_local'] = pt.round(4).tolist(); sp['_contact_depth_mm'] = round(d * 1000, 1)
    return sp


# ---- per gun bump --------------------------------------------------------------------------------------------------
def with_bump(base, st, move):
    sp = json.loads(json.dumps(base))
    if np.linalg.norm(move) > 1e-5:
        sp.setdefault('bumps', {})[st] = [{'f': BWIN, 'move': [round(float(x), 4) for x in move]}]
    return sp


def fit_bump(base, sh, st, gun, touch=TOUCH):
    """smallest translation of the long gun (world, applied as one bump) that makes its overlap with the magazine
    box at the hit frame = touch: repeatedly move along the shortest gap (or exit) vector between gun and box"""
    mv = np.zeros(3); D = dense(gun)
    for _ in range(8):
        ns = load_spec(with_bump(base, st, mv)); Mj = magJ(ns, sh, HIT)
        val, v = contact_mt(app(np.linalg.inv(Mj), app(gunM(ns, st, HIT), D)))
        vw = Mj[:3, :3] @ v; n = np.linalg.norm(vw)
        if abs(val - touch) < 2e-4 or n < 1e-6: break
        mv = mv + (vw + touch * vw / n if val < 0 else vw * (val - touch) / val)
    return with_bump(base, st, mv)


def fit_or_keep(base, sh, st, gun):
    d, pt = contact(load_spec(base), sh, st, gun)
    if OKRANGE[0] <= d <= OKRANGE[1]:
        sp = json.loads(json.dumps(base)); sp.pop('bumps', None)
        return sp
    return fit_bump(base, sh, st, gun)


_MIRROR = []


def base_spec(side, body):
    """the hand's spec before the per gun bump. The mirror is fitted once, on the male body, and used for both."""
    if side == 'left':
        sp = json.loads(json.dumps(L01))
    else:
        if not _MIRROR:
            _MIRROR.append(fit_mirror())
        sp = json.loads(json.dumps(_MIRROR[0]))
    sp['body'] = body
    return sp


def groups(moves):
    """complete-linkage groups of guns whose bump vectors are all within SHARE_MM of each other"""
    out = []
    for g in moves:
        for grp in out:
            if all(np.linalg.norm(moves[g] - moves[h]) * 1000 < SHARE_MM for h in grp): grp.append(g); break
        else: out.append([g])
    return out


def specs(side, body, guns):
    """{gun: spec} for one hand and body; guns in one sharing group get the same spec"""
    base = base_spec(side, body); sh, st = SIDES[side]
    fits = {gun: fit_or_keep(base, sh, st, gun) for gun in guns}
    mv = {g: np.array(sp.get('bumps', {}).get(st, [{'move': [0, 0, 0]}])[0]['move']) for g, sp in fits.items()}
    out = {}
    for grp in groups(mv):
        m = np.mean([mv[g] for g in grp], 0)
        shared = with_bump(base, st, m) if len(grp) > 1 else fits[grp[0]]
        for g in grp:
            sp = json.loads(json.dumps(shared)); d, pt = contact(load_spec(sp), sh, st, g)
            sp['_bump'] = {'gun': g, 'shared_with': grp, 'own_fit_mm': (mv[g] * 1000).round(1).tolist(),
                           'move_mm': (m * 1000).round(1).tolist(), 'contact_mm': round(d * 1000, 1),
                           'contact_pt': pt.round(4).tolist()}
            out[g] = sp
    return out
