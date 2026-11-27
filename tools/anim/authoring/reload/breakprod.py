"""Production of the owner's BREAK-OPEN picks (coordinator, 2026-11-14): BR17 chest roll-up, thrust; BR20 forward
roll-tip, side swing; BR18 shoulder snap, backhand (round3-break, break2.py on breakphys.py). Guns: Palica (take A),
Satara (take B), Igla (take A: light by bulk), Testera (take B: heavy); right and left hand, male and female V.

What production adds to the reviewed generator (right hand, male V, empty reload, Palica and Satara only):
  clip     empty reload: both barrels fired, both hulls eject, two fresh shells. reload: one barrel fired (phase 1:
           the game's reload loads the left barrel only): the left hull ejects and one fresh shell goes in; the
           right shell is live and stays in its chamber (lifted by the extractor while open, back in on the close).
           The motion and the barrel physics are the same clip (the swing has to break and shut the action either
           way); only the shells differ. Igla: the same clip serves both (no shells). Testera: empty reload only.
  side     left: authored in the mirror image (prod.Ctx), keys mirrored back; the barrel physics, the hulls and the
           holder run on the real gun path; the holder's strap is mirrored back.
  guns     Igla, Testera: no shell joints and no shell mesh. Their hinge (breakgeo.py) lies on the Palica's and
           Satara's pivot line and opens like the Satara (44.57 deg), so the chamber point the motion aims at the
           holder with is the Satara's (virtual, nothing drawn or tracked). Barrel mass from the barrel block's surface
           area against the Satara's (Igla 1.07 kg, Testera 1.28 kg), springs and friction the Satara's: estimates.
Checks: rgate, break2.break_gate (the swing cocks the action and reaches the trip with the lever thumbed, barrels not
before the lever, hulls eject and land, barrels open at the seat, the bolt latches on the close move, no hull on
screen in the hidden window), end transition into the idle, elbow step, hulls against the other gun.

usage: breakprod.py list | build [--guns a,b] [--picks ..] [--clips ..] [--sides ..] [--bodies ..] | layout | regress
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, prod, rgate, inertia, rarmset, rchecks, gungeo, magtrack2
import breakphys as bp
import break2 as B
from rlib import K
from glb import Glb
from fk import Clip

OUT = renv.OUT + '/clips'
TAKE = {'palica': 'A', 'satara': 'B', 'igla': 'A', 'testera': 'B'}
SLOTS = ['BR17', 'BR20', 'BR18']
CLIPS_OF = {'palica': ('reload', 'empty_reload'), 'satara': ('reload', 'empty_reload'), 'igla': ('empty_reload',), 'testera': ('empty_reload',)}
SERVES = {'igla': ['reload', 'empty_reload'], 'testera': ['empty_reload']}
SIDES = ('right', 'left'); BODIES = ('pma', 'pwa')
STRAP_OF = {'BR17': 'hip', 'BR20': 'hip', 'BR18': 'belt'}
NO_SHELLS = ('igla', 'testera')
MIR = np.array([-1.0, 1.0, 1.0])
PARAMS = {           # (pick, gun[, body][, side]) -> parameter changes in production (round 3 generator; round 2's are in tools_break)
    # end blend: the simulated gun still settling when the 3-frame end blend forced it in (end step over 0.5 cm)
    ('BR20', 'satara'): {'fade': 6}, ('BR20', 'testera'): {'fade': 6}, ('BR18', 'testera'): {'fade': 6},
    # hulls into the other gun (0.0 to 0.1 cm): more roll lifts them over it (wrist in view stays under 70)
    ('BR20', 'palica'): {'tip_yaw': -10, 'tip_roll': 52}, ('BR20', 'satara', 'left'): {'tip_roll': 52},
    # left hand: hulls in view 2 f (rule 4): the roll-up pitched 45 deg instead of 55
    ('BR17', 'palica', 'left'): {'face_pitch': 45},
    # female V: the backhand close ended 15.5 cm from her eye (as round 2): 4 cm lower, 2 cm further out
    ('BR18', 'palica', 'pwa'): {'bh_by': (-0.12, 0.20, -0.10)},
    # female V: the gun went 6 to 10 cm into her body block on the way to the holder (BR18B also back in view, opening 35 f): exit further out
    ('BR17', 'satara', 'pwa'): {'out_pos': (0.37, -0.24, 0.26)},
    ('BR18', 'satara', 'pwa'): {'out_pos': (0.40, -0.20, 0.26), 'via_pos': (0.24, -0.40, 0.32)},
    # Igla (93 cm): its barrels swung back into view on the way to the holder (opening 28 to 32 f, limit 23): a via point
    # with the muzzle pitched down; its heavier barrels latched early once the lever was let go: lever held to the holder
    ('BR17', 'igla'): {'lever_until': 34, 'via_f': 22, 'via_pos': (0.20, -0.40, 0.30), 'via_rot': (-50, -40, 0),
                       'cross_yaw': 15, 'face_yaw': 5},          # the cross and roll-up swept its muzzle into the left gun
    ('BR20', 'igla'): {'lever_until': 34, 'via_f': 22, 'via_pos': (0.20, -0.40, 0.30), 'via_rot': (-50, -40, 0)},
    ('BR18', 'igla'): {'lever_until': 34, 'via_f': 22, 'via_pos': (0.20, -0.40, 0.30), 'via_rot': (-50, -40, 0),
                       'load_rot': (-10, -15, 60), 'bh_prof': (2.8, 1.15)},   # loaded on its side the barrels hung 15 to 23 deg open (need 25): rolled 60 deg, a faster backhand to latch
    # female V: wrist in view 70.1 to 71.0 deg on the left hand (rule 70), and the Igla's barrels in view at her belt holder (opening 35 f)
    ('BR17', 'igla', 'pwa'): {'face_pitch': 50}, ('BR20', 'igla', 'pwa'): {'tip': -36}, ('BR20', 'palica', 'pwa', 'left'): {'tip_roll': 48},   # her right hand keeps 52 (48 put a hull on the other gun)
    ('BR18', 'igla', 'pwa'): {'rig_belt': (0.20, 0.165, -0.03)}}   # holder 2.5 cm lower (as the rifles' female drop)
#   (BR18 igla: loaded on its side the barrels hung 15 to 23 deg open (need 25): rolled 60 deg, a faster backhand to latch
# the script plays a pick only if its opening (clip start to hide_start) fits 1.15 x 0.75 x the reload time at base stats
# (round3-break/NOTES.md, gg-work/smg-wire/WIRING-NOTES.md): frames
OPEN_LIMIT = {'palica': 16, 'testera': 22, 'satara': 23, 'igla': 23}
NOTE_ONLY = {}
PWA_DROP = {}

# ---- guns: Igla and Testera into breakphys (hinge from breakgeo.py; virtual chambers and estimates as the docstring)
_S = bp.GEO['satara']
for g in ('igla', 'testera'):
    G = json.load(open(f'{renv.OUT}/ref/{g}_geometry.json')); G = dict(G, closed=_S['closed'], open_game=_S['open_game'], joints=_S['joints'], _virtual_chambers='satara')
    bp.GEO[g] = G
bp.MESH.update({'igla': 'w_shotgun_dual__rostovic_igla', 'testera': 'w_shotgun_dual__rostovic_testera'})
_AREA = {'satara': 0.2893, 'igla': 0.1991, 'testera': 0.2382}            # barrel block surface m2 (base1_01 minus the fixed 'barrel' joint)
for g in ('igla', 'testera'): bp.PAR[g] = dict(bp.PAR['satara'], mass=round(bp.PAR['satara']['mass'] * _AREA[g] / _AREA['satara'], 2))
B.take_of = lambda gid: TAKE[gid]
B.DRIVEN = True
# gun and hand inertia about the wrist for the barrel jolts (break2.I_GUN; Palica 0.045, Satara 0.16, both estimates):
# the Igla (93 cm, lighter barrels) and the Testera (72 cm) between them, unverified
B.I_GUN.update({'igla': 0.14, 'testera': 0.12})
# break2 reads the shell mesh through its own MESH table (shell centre, hulls on screen); breakphys reads the barrel
# mesh through bp.MESH. The Igla and Testera have no shell mesh: break2 uses the Satara's for the virtual chambers.
B.MESH = dict(bp.MESH, igla=bp.MESH['satara'], testera=bp.MESH['satara'])
_find = common.find
def _find_shell(kind, name):
    """common.find with the Igla's and Testera's missing shell mesh answered by the Satara's (rgate loads it for its
    hidden dummy track; nothing is drawn or measured with it)."""
    for g in NO_SHELLS:
        if name == f'{bp.MESH[g]}__mag_std_01.glb': return _find(kind, f"{bp.MESH['satara']}__mag_std_01.glb")
    return _find(kind, name)
common.find = _find_shell


def stem(gid, side, pick, clip): return f'{gid}_{side}_{pick}{TAKE[gid]}_{clip}'


def plan_list(guns=None, picks=None, clips=None, sides=None, bodies=None):
    return [(g, p, cl, s, b) for g in TAKE if not guns or g in guns for p in SLOTS if not picks or p in picks for cl in CLIPS_OF[g] if not clips or cl in clips
            for b in (bodies or BODIES) for s in (sides or SIDES)]


# ------------------------------------------------------------------------------------------------ loading
def load_press_js(js, strap):
    """break2.load_press for the given chamber joints only (the reload loads the left barrel)."""
    def fn(c, GW, th, ph, plan):
        se = plan['seat']; N = len(GW); fresh = {}; mats = {j: B.chamber_world(c, GW, th, se, j) for j in js}
        for j in js: fresh[j] = [mats[j] if f < se else B.chamber_world(c, GW, th, f, j) for f in range(N)]
        cen = np.r_[B.shell_centre(c.gun), 1]; u = mats[js[0]][:3, :3] @ np.array([0, 0, 1.0])
        a = [(B.chamber_world(c, GW, th, f, js[0]) @ cen)[:3] for f in (se - 2, se - 1, se)]; v = (a[2] - a[1]) * 100; lat = float(np.linalg.norm(v - (v @ u) * u))
        st = {'kind': 'press', 'joints': list(js), 'seat': se, 'insert_cm_f': round(float(-(v @ u)), 2), 'off_axis_cm_f': round(lat, 2), 'barrels_deg_at_seat': round(math.degrees(th[se]), 1)}
        return fresh, st, B.rig_holder(c, mats, N, strap)
    return fn


def live_shell(gid, GW, th, j):
    """The unfired shell of a reload: rides its chamber, lifted by the extractor while the barrels open (linear in the
    angle up to the trip), pushed back in as they close (breakphys.spent_shells' carried pose, never ejected)."""
    p = bp.PAR[gid]; trip = bp.tmax(gid) - math.radians(p['trip_before_stop_deg']); C0 = B.closed(gid, j); out = []
    for f in range(len(GW)):
        ext = p['extract_m'] * min(max(th[f], 0.0) / trip, 1.0); C = C0 @ np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, ext], [0, 0, 0, 1.0]])
        out.append(GW[f] @ bp.hinge_rot(gid, th[f]) @ C)
    return out


# ------------------------------------------------------------------------------------------------ build
def compose(gid, pick, side, body, extra=None):
    take = TAKE[gid]; B.setup(gid); S = side.capitalize(); magtrack2._van[(gid, 'reload')] = magtrack2._van[(gid, B.CLIP)]     # rgate reads the clip's name
    P = dict(B.TAKES_P[take]); P.update(B.PARAMS.get(pick + take, {}))
    for key in ((pick, gid), (pick, gid, body), (pick, gid, side), (pick, gid, body, side)): P.update(PARAMS.get(key, {}))
    P.update(extra or {})
    c = prod.Ctx(gid, body, B.CLIP, P, S); tl = B.TL(c, 0, 0.0); plan = B.PICKS[pick][1](c, tl)
    Pt, Rt = tl.P.copy(), tl.R.copy(); Pt[-1] = 0; Rt[-1] = 0
    return c, tl, plan, Pt, Rt


def gun_world(path, N, S):
    g = Glb(path); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); o = g.names.index('Weapon' + ('Left' if S == 'Right' else 'Right'))
    W = [cl.world(f) for f in range(N)]
    return [magtrack2.m4(np.array(W[f][i][0]), np.array(W[f][i][1])) for f in range(N)], [magtrack2.m4(np.array(W[f][o][0]), np.array(W[f][o][1])) for f in range(N)]


def author_clip(c, tl, sim, name, d, gid, pick, clip, S, body):
    N = c.N; X, E = np.array(sim['X']), np.array(sim['E'])
    if S == 'Left': X = X * prod.MIR_P; E = E * prod.MIR_R
    O = 'Left' if S == 'Right' else 'Right'; keys = [K(f, X[f], E[f]) for f in range(N)]; keys[0] = K(0); keys[-1] = K(N - 1)
    spec = {'_draft': name, '_name': f'{B.PICKS[pick][0]}, take {TAKE[gid]}', '_doc': B.DOC[pick], '_gun': gid, '_left_gun': gid, '_body': body, '_side': S,
            '_gun_clip': clip, '_serves': SERVES.get(gid, [clip]), '_pick': pick, '_take': TAKE[gid], '_timing': c.T, '_params': {k: v for k, v in c.P.items() if not str(k).startswith('_')},
            '_marks': tl.marks, '_two_arm': False, '_round': 'break-production', 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': N,
            'keys': {S: keys, O: [K(0)]}, 'shakes': {S: [], O: []}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb',
            '_target': {'P': [[round(float(x), 5) for x in p] for p in tl.P], 'R': [[round(float(x), 3) for x in r] for r in tl.R]}}
    author.build(spec, spec['out']); GW, GO = gun_world(spec['out'], N, S)
    return spec, GW, GO


def end_transition(spec):
    from fk import qmul, qinv
    S = spec['_side']; N = spec['frames']; g = Glb(spec['out']); c = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}
    r = Glb(common.mp(spec['src'])); R0 = Clip(r, 'idle').world(0); rix = {n: i for i, n in enumerate(r.names)}
    own = [n for n in g.names if n and n.startswith(S) and any(k in n for k in ('Shoulder', 'Arm', 'Hand')) and 'Leg' not in n] + ['Weapon' + S]
    ang = lambda q: math.degrees(2 * math.atan2(float(np.linalg.norm(q[:3])), abs(float(q[3]))))
    W = [c.world(f) for f in range(N - 4, N)]; st_cm = st_deg = 0.0
    for k in range(3):
        for n in own:
            (t0, q0), (t1, q1) = W[k][ix[n]], W[k + 1][ix[n]]; st_cm = max(st_cm, float(np.linalg.norm(t1 - t0)) * 100); st_deg = max(st_deg, ang(qmul(qinv(q0), q1)))
    e_cm = e_deg = 0.0
    for n in own:
        (t, q), (t0, q0) = W[-1][ix[n]], R0[rix[n]]; e_cm = max(e_cm, float(np.linalg.norm(t - t0)) * 100); e_deg = max(e_deg, ang(qmul(qinv(q0), q)))
    return {'last3_step_cm': round(st_cm, 3), 'last3_step_deg': round(st_deg, 2), 'last_vs_idle_cm': round(e_cm, 4), 'last_vs_idle_deg': round(e_deg, 4)}


def elbow_step(spec):
    S = spec['_side']; g = Glb(spec['out']); c = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}; prev = None; worst = 0.0
    for f in range(spec['frames']):
        W = c.world(f); s, e, h = (np.array(W[ix[S + n]][0]) for n in ('Arm', 'ForeArm', 'Hand')); ax = (h - s) / np.linalg.norm(h - s)
        p = (e - s) - ((e - s) @ ax) * ax; p /= (np.linalg.norm(p) or 1)
        if prev is not None: worst = max(worst, float(np.degrees(np.arccos(np.clip(p @ prev, -1, 1)))))
        prev = p
    return round(worst, 1)


def hulls_vs_other(gid, spent, GO):
    if not spent: return None
    V = gungeo.verts(common.find('weapon_meshes', bp.MESH[gid] + '__mag_std_01.glb'))[::4]; V1 = np.c_[V, np.ones(len(V))]; PG = rchecks.gun_points(gid, 4000); d = 9e9
    for W in spent.values():
        for f, M in enumerate(W):
            if M is None: continue
            P = (V1 @ M.T)[:, :3]; b = rchecks.place((GO[f][:3, 3], _quat(GO[f])), PG)[::3]; d = min(d, float(np.sqrt(((P[:, None] - b[None]) ** 2).sum(2)).min()) * 100)
    return round(d, 1)


def _quat(M):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_matrix(M[:3, :3]).as_quat()


def pad(glb, clip, keys):
    g = Glb(glb); a = g.anim(clip); done = set()
    for ch in a['channels']:
        s = a['samplers'][ch['sampler']]
        if id(s) in done: continue
        t = np.asarray(g.acc(s['input']), float); v = np.asarray(g.acc(s['output']), float); n = len(t)
        if n >= keys or n < 2: continue
        v = v.reshape(n, -1); v2 = np.concatenate([v, np.repeat(v[-1:], keys - n, 0)]); kind = {1: 'SCALAR', 3: 'VEC3', 4: 'VEC4'}[v.shape[1]]
        s['input'] = g.add_acc(np.arange(keys) / 30.0, 'SCALAR'); s['output'] = g.add_acc(v2 if v.shape[1] > 1 else v2[:, 0], kind); done.add(id(s))
    g.save(glb)


def build(gid, pick, clip, side, body, quiet=False):
    S = side.capitalize(); d = f'{OUT}/{body}'; os.makedirs(d, exist_ok=True); name = stem(gid, side, pick, clip)
    c, tl, plan, Pt, Rt = compose(gid, pick, side, body)
    if 'close' in tl.marks:
        f = tl.marks['close']
        while f > 1 and (np.abs(tl.P[f] - tl.P[f - 1]).max() > 2e-4 or np.abs(tl.R[f] - tl.R[f - 1]).max() > 0.05): f -= 1
        plan.setdefault('close_from', f)
    take = TAKE[gid]; base_imp = B.impulses_from(tl); react = []; hist = []
    for it in range(3):
        sim = inertia.simulate_gun(c, take, Pt, Rt, base_imp + react, plan.get('gun_contacts', []), tl.guides, fade=c.P.get('fade', 3))   # fade: frames the simulated gun blends into the idle at the end (break2: 3)
        spec, GW, GO = author_clip(c, tl, sim, name, d, gid, pick, clip, S, body)
        ph = B.run_phys(c, plan, GW); hist.append({k: ph['events'].get(k) for k in ('trip', 'open', 'shut')})
        new = B.reactions(c, ph)
        if it > 0 and [x[0] for x in new] == [x[0] for x in react]: react = new; break
        react = new
    spec['_reactions'] = [(int(f), [round(float(x), 4) for x in dw]) for f, _, dw in react]; spec['_passes'] = hist
    ph['theta_sim'] = ph['theta']; ph['theta'] = bp.drive_hinge(ph['theta']); ph['w'] = np.gradient(ph['theta']) * B.FPS      # rule S1: one open, one close
    th = ph['theta']; spec['_hinge_deg'] = [round(float(math.degrees(x)), 2) for x in th]; spec['_hinge_sim_deg'] = [round(float(math.degrees(x)), 2) for x in ph['theta_sim']]; spec['_part_frames'] = B.hinge_frames(gid, th)
    js = B.joints(gid); sc = B.shell_centre(gid); cl = {j: B.closed(gid, j) for j in js}
    strap = B.strap_x(c, STRAP_OF[pick]) * (MIR if S == 'Left' else 1)
    if gid in NO_SHELLS: spent, sst, fresh, fst, prims, live = {}, [], {}, {}, [], {}
    else:
        fired = js if clip == 'empty_reload' else js[:1]
        spent, sst = bp.spent_shells(gid, GW, th, ph['events'], fired, cl, sc)
        fresh, fst, prims = load_press_js(fired, strap)(c, GW, th, ph, plan)
        live = {j: live_shell(gid, GW, th, j) for j in js if j not in fired}
    inv = [np.linalg.inv(M) for M in GW]; J = {'names': [], 'joints': {}, 'gun_axes': True, 'clip': clip}
    for nm, per in (('spent', spent), ('fresh', fresh), ('live', live)):
        if not per: continue
        J['names'].append(nm); J['joints'][nm] = {j: [None if M is None else [round(float(x), 6) for x in (inv[f] @ M).ravel()] for f, M in enumerate(W)] for j, W in per.items()}
    spec['_objects'] = f'{d}/{name}_objects.json'; json.dump(J, open(spec['_objects'], 'w'))
    spec['_prims'] = f'{d}/{name}_prims.json'; json.dump(prims, open(spec['_prims'], 'w'))
    C0 = B.closed(gid, js[0])
    dummy = {'frames': [{'m': [round(float(x), 6) for x in C0.ravel()], 's': 0.0, 'state': 'seated'}] * c.N, 'release': 1, 'free_from': 2, 'gone': c.N, 'exit_gun_axes': [0, 1, 0], 'enter_gun_axes': [0, -1, 0], 'plan': {'mode': 'none'}, 'clip': clip}
    spec['_track'] = f'{d}/{name}_track.json'; json.dump(dummy, open(spec['_track'], 'w'))
    if plan.get('seat') is not None: spec['_timing'] = dict(c.T, seated=int(plan['seat']))
    spec['_plan'] = {k: v for k, v in plan.items() if k not in ('load', 'hinge_contacts', 'gun_contacts')}
    json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, dummy); gs = inertia.gun_stats(sim, tl.marks)
    o['phys'] = B.phys_stats(c, plan, GW, ph, sst, fst, spec); o['inertia'] = {'gun': gs, 'model': sim['model']}
    B.break_gate(c, o, plan, ph, sst, fst, spent, fresh, GW)
    for k, txt in NOTE_ONLY.items():
        if pick == k:
            keep = [x for x in o['fails'] if x.startswith(txt)]; o['fails'] = [x for x in o['fails'] if not x.startswith(txt)]
            if keep: o.setdefault('notes', []).extend(f'{x} (kept as reviewed: 2 frames is the best reachable without changing the pick)' for x in keep)
    o['opening_f'] = o['layout']['hide_start']; o['opening_limit_f'] = OPEN_LIMIT[gid]
    if o['opening_f'] is None or o['opening_f'] > OPEN_LIMIT[gid]: o['fails'].append(f"opening {o['opening_f']} f over the fallback limit {OPEN_LIMIT[gid]} f")
    o['elbow_step_deg'] = elbow_step(spec)
    if o['elbow_step_deg'] > 45: o['fails'].append(f"elbow swings {o['elbow_step_deg']} deg in one frame")
    o['hulls_to_other_gun_cm'] = ho = hulls_vs_other(gid, spent, GO)
    if ho is not None and ho < 0.5: o['fails'].append(f'a hull touches the other gun ({ho} cm)')
    o['end_transition'] = et = end_transition(spec)
    if et['last3_step_cm'] > 0.5 or et['last_vs_idle_cm'] > 0.02 or et['last_vs_idle_deg'] > 0.02: o['fails'].append(f'end transition {et}')
    o['shells'] = 'none in the game files (virtual Satara chambers for the holder)' if gid in NO_SHELLS else {'fired': list(spent), 'live': list(live)}
    kn = rarmset.good_keys(c.N); o['layout']['keys'] = kn
    pad(spec['out'], 'reload_draft', kn); spec['_keys'] = kn; json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    json.dump({'events': ph['events'], 'hinge_deg': spec['_hinge_deg'], 'w_deg_f': [round(math.degrees(x) / B.FPS, 2) for x in ph['w']], 'log': ph['log'], 'spent': sst, 'fresh': fst,
               'model': bp.summary(gid), 'stats': o['phys']}, open(f'{d}/{name}_phys.json', 'w'), indent=1, default=float)
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1, default=float)
    if not quiet:
        p = o['phys']; print(body, side, name, '| fails', o['fails'], '| open', p['open_swing_deg_f'], '->', p['barrel_at_trip_deg_f'], 'trip', p['trip_f'], '| close', p['close_swing_deg_f'], '->', p['latch_w_deg_f'], p['latch'],
                              '| eye', o['eye_cm'], 'reach', o['reach'], 'sh', o['shoulder_pull_cm'], 'body', o['body_cm'], 'wrist', o['wrist'][0], o['wrist_view'], 'gap', o['guns_gap_cm'], 'hide', o['layout']['hide_start'], o['layout']['hide_end'], '| hulls-other', ho, flush=True)
    return spec, o


# ------------------------------------------------------------------------------------------------ layout, regress
def layout():
    lay = {}; fails = []; rows = []
    for gid, pick, clip, side, body in plan_list():
        p = f'{OUT}/{body}/{stem(gid, side, pick, clip)}_gate.json'
        if not os.path.exists(p): fails.append(f'missing {p}'); continue
        o = json.load(open(p)); s = json.load(open(p[:-10] + '.json')); Lr = dict(o['layout']); rows.append((gid, pick, clip, side, body, o))
        ph = o['phys']; e = lay.setdefault(gid, {}).setdefault(pick + TAKE[gid], {}).setdefault(clip, dict(Lr, per_clip={}, shells={}))
        e['per_clip'][f'{body}_{side}'] = [Lr['hide_start'], Lr['hide_end']]
        e['shells'][f'{body}_{side}'] = {'lever': ph['lever_f'], 'trip_eject': ph['trip_f'], 'hulls_land': [x.get('land') for x in ph.get('spent', [])], 'seat': s['_timing'].get('seated'),
                                          'shut': ph['shut_f'], 'objects': os.path.basename(s['_objects']), 'barrel_part_frames': 'spec _part_frames'}
        if Lr['hide_start'] is None or e['hide_start'] is None: e['hide_start'] = e['hide_end'] = None
        else: e['hide_start'] = max(e['hide_start'], Lr['hide_start']); e['hide_end'] = min(e['hide_end'], Lr['hide_end'])
        if o['fails']: fails.append(f"{body} {o['clip']}: {o['fails']}")
    for gid in lay:
        for pk in lay[gid]:
            i = SLOTS.index(pk[:-1])
            for clip, e in list(lay[gid][pk].items()):
                e['slot'] = clip if i == 0 else f'{clip}_0{i}'
                if e['hide_start'] is not None and e['hide_end'] - e['hide_start'] + 1 < 12: fails.append(f'{gid} {pk} {clip}: shared hidden window only {e["hide_end"] - e["hide_start"] + 1} f')
                e['opening_limit'] = OPEN_LIMIT[gid]
                if e['hide_start'] is None or e['hide_start'] > OPEN_LIMIT[gid]: fails.append(f'{gid} {pk} {clip}: shared opening {e["hide_start"]} f over the fallback limit {OPEN_LIMIT[gid]}')
            if gid == 'igla' and 'empty_reload' in lay[gid][pk]:
                lay[gid][pk]['reload'] = dict(lay[gid][pk]['empty_reload'], slot='reload' if i == 0 else f'reload_0{i}', same_clip_as='empty_reload')
    json.dump(lay, open(f'{OUT}/layout_break.json', 'w'), indent=1, default=float)
    Ls = ['| gun | pick | clip | slot | hide_start (opening) | limit | hide_end | seated | length | keys |', '|---|---|---|---|---|---|---|---|---|---|']
    for gid in lay:
        for pk in lay[gid]:
            for clip, e in lay[gid][pk].items(): Ls.append(f"| {gid} | {pk} | {clip} | {e['slot']} | {e['hide_start']} | {OPEN_LIMIT[gid]} | {e['hide_end']} | {e['seated']} | {e['length']} | {e['keys']} |")
    open(f'{OUT}/layout_break.md', 'w').write('\n'.join(Ls) + '\n'); open(f'{OUT}/gate_fails_break.txt', 'w').write('\n'.join(fails) + '\n')
    H = ['clip', 'body', 'side', 'opening f (limit)', 'hidden', 'eye cm', 'cover %', 'wrist / in view', 'reach', 'shoulder cm', 'body cm', 'guns gap cm', 'start / end cm', 'end transition (cm, deg)',
         'lever, cocked, trip f', 'gun swing at break deg/f', 'barrels at trip deg/f', 'close swing deg/f', 'latch (w / need)', 'shut f', 'barrels at seat deg', 'hulls land f', 'hulls to other gun cm', 'elbow', 'fails']
    per = {}
    for gid, pk, clip, side, body, o in rows:
        L = o['layout']; et = o['end_transition']; p = o['phys']; fr = p.get('fresh') or {}
        per.setdefault(gid, []).append('| ' + ' | '.join(str(x) for x in [f'{pk}{TAKE[gid]} {clip}', body, side, f"{L['hide_start']} ({OPEN_LIMIT[gid]})", f"f{L['hide_start']}-{L['hide_end']} ({o['hidden_frames']})", o['eye_cm'][0], o['cover_peak'][0],
            f"{o['wrist'][0]} / {o['wrist_view']}", o['reach'][0], o['shoulder_pull_cm'], o['body_cm'][0], o['guns_gap_cm'][0], f"{o['start_cm']:.3f} / {o['end_cm']:.3f}", f"{et['last3_step_cm']}, {et['last3_step_deg']}",
            f"{p['lever_f']}, {p['cocked_f']}, {p['trip_f']}", p['open_swing_deg_f'], p['barrel_at_trip_deg_f'], p['close_swing_deg_f'], f"{p['latch']} ({p['latch_w_deg_f']} / {p['latch_need_deg_f']})",
            p['shut_f'], fr.get('barrels_deg_at_seat', '-'), [x.get('land') for x in p.get('spent', [])] or '-', o['hulls_to_other_gun_cm'], o['elbow_step_deg'], '; '.join(o['fails']) or 'pass']) + ' |')
    os.makedirs(OUT + '/gates', exist_ok=True)
    for gid, Rw in per.items():
        npass = sum(1 for r in Rw if r.endswith('| pass |'))
        open(f'{OUT}/gates/gate_{gid}.md', 'w').write('\n'.join([f'# Gate, {common.gun(gid)["name"]}: {npass} of {len(Rw)} clips pass', '', '| ' + ' | '.join(H) + ' |', '|' + '---|' * len(H)] + Rw) + '\n')
        print(gid, npass, 'of', len(Rw), 'pass')
    print('\n'.join(Ls)); print(len(fails), 'failures or missing')


def regress(picks=('BR17', 'BR20', 'BR18')):
    D = common.mp('C:/Modding/anim-work/smg-shotgun/round3-break/clips/pma'); out = []
    for gid in ('palica', 'satara'):
        for pick in picks:
            a = f'{OUT}/pma/{stem(gid, "right", pick, "empty_reload")}'; b = f'{D}/{gid}_right_{pick}{TAKE[gid]}_empty_reload'
            if not os.path.exists(a + '.glb'): continue
            ga, gb = Glb(a + '.glb'), Glb(b + '.glb'); ca, cb = Clip(ga, 'reload_draft'), Clip(gb, 'reload_draft'); N = json.load(open(b + '.json'))['frames']
            names = [n for n in gb.names if n and (n.startswith('Right') or n == 'WeaponRight') and 'Leg' not in n]
            dj = max(float(np.linalg.norm(np.array(ca.world(f)[ga.names.index(n)][0]) - np.array(cb.world(f)[gb.names.index(n)][0]))) for f in range(N) for n in names) * 100
            ha, hb = json.load(open(a + '.json'))['_hinge_deg'], json.load(open(b + '.json'))['_hinge_deg']
            dh = max(abs(x - y) for x, y in zip(ha, hb))
            oa, ob = json.load(open(a + '_objects.json')), json.load(open(b + '_objects.json')); dm = 0.0
            for nm in ob['names']:
                for j in ob['joints'][nm]:
                    for x, y in zip(oa['joints'][nm][j], ob['joints'][nm][j]):
                        if x is not None and y is not None: dm = max(dm, float(np.abs(np.array(x) - np.array(y)).max()))
            s = f'{gid} {pick}: worst joint difference {dj:.4f} cm; barrel angle {dh:.3f} deg; shell matrix element {dm:.6f}'; print(s); out.append(s)
    open(renv.OUT + '/work/regress_break.txt', 'w').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None; cmd = argv[0] if argv else 'list'
    if cmd == 'list':
        for p in plan_list(): print(*p)
        print(len(plan_list()), 'clips')
    elif cmd == 'build':
        for p in plan_list(cs(o('--guns')), cs(o('--picks')), cs(o('--clips')), cs(o('--sides')), cs(o('--bodies'))): build(*p)
    elif cmd == 'layout': layout()
    elif cmd == 'regress': regress()
    else: raise SystemExit(__doc__)
