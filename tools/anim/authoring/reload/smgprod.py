"""Production of the owner-picked SMG one-handed reloads (PICKS.md, 2026-11-13/14), the way prod.py produced the
rifles: every pick, reload and empty reload, right and left hand, male and female V, each with its magazine track,
gate numbers and layout. The motion is the reviewed draft's own generator (grip1 SG08, grip2 SG13 SG12 on the
Senkoh LX, take A; bull3 SB43 SB39 SB38 on the Pulsar, take A; top3 ST38 ST40 ST32 on the Warden, take B), run on
its own engine (r1lib, r2lib, r3lib) unchanged except for what production needs:
  clip      reload: no rack (a round is chambered): up from the seat and settled into the idle, no hit; the gun's own
            reload events are time-mapped (gun_map). empty_reload: the draft as reviewed.
  side      left: authored as a right hand in the mirror image (prod.Ctx), keys mirrored back (x, yaw, roll); in-hand
            spins and offsets of WeaponLeft mirrored (axis M a, angle -a, pivot M p); stations mirror; the magazine
            axes stay the gun's own.
  body      pwa: stations from her hips joint, PWA_DROP below where her forearm or the gun stayed on screen.
One process per family (r3lib changes r2lib's back and idle beats on import; grip2 runs on the unchanged ones).

usage: smgprod.py list
       smgprod.py build <family> [--picks a,b] [--clips reload,empty_reload] [--sides right,left] [--bodies pma,pwa] [--lift <json>] [--lowered <json>]
       smgprod.py all [--jobs n]            every family, one process each (n at a time)
       smgprod.py layout                    layout.json, layout.md, gate tables, gate_fails.txt
Output: <OUT>/clips/<body>/<gun>_<side>_<pick>_<clip>.glb (padded to good_keys), .json (spec), _track.json, _gate.json
"""
import os, sys, json, importlib, subprocess, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np

OUT = renv.OUT + '/clips'
FAMILIES = {'grip1': ('senkoh', 'A', ['SG08'], 'r1lib'), 'grip2': ('senkoh', 'A', ['SG13', 'SG12'], 'r2lib'),
            'bull3': ('pulsar', 'A', ['SB43', 'SB39', 'SB38'], 'r3lib'), 'top3': ('warden', 'B', ['ST38', 'ST40', 'ST32'], 'r3lib'),
            'vtop': ('warden', 'B', ['SV%02d' % i for i in range(1, 17)], 'r3lib')}      # vtop: drafts from vanilla reloads (the family module sets its own beats: prepare(pick))
# slot order per gun (PICKS.md order): reload, reload_01, reload_02 and empty_reload, _01, _02
SLOTS = {'senkoh': ['SG08', 'SG13', 'SG12'], 'pulsar': ['SB43', 'SB39', 'SB38'], 'warden': ['ST38', 'ST40', 'ST32']}
if os.environ.get('SMG_GUN') and os.environ['SMG_GUN'] != 'warden':      # another gun of the top family (it plays the Warden's picks; pvar, from pborg)
    FAMILIES['top3'] = (os.environ['SMG_GUN'],) + FAMILIES['top3'][1:]; SLOTS[os.environ['SMG_GUN']] = SLOTS['warden']
IN_HAND = {'ST32': 'the gun turns half over in the fingers and back (WeaponLeft/Right animated relative to the hand): needs an in-game check before shipping'}
CLIPS = ('reload', 'empty_reload'); SIDES = ('right', 'left'); BODIES = ('pma', 'pwa')
# female V: station this much lower (y, m), filled in from the gate (her forearm or the gun stayed on screen)
PWA_DROP = {'rear_b': -0.05,      # SB43: the Pulsar's stock came 19.4 cm from her eye on the way to the rig behind the hip (rule 20; -0.025 gave 19.9)
            'belt_tl': -0.025}    # ST38: her forearm stayed on screen at the belt rig (hidden window 11 f, rule 12); as the rifles' belt
# per pick and body: draft parameters changed in production (default: the reviewed draft)
BODY_PARAMS = {}
LOWERED = {}   # {'h', 'a', 'b', 'e', 's'} (--lowered <json>; s: scale of the post-seat gesture keys about the lowered pose, solved by plift3/bisect.py): the clip starts and ends in the gun's lowered idle (lowover.py); frames h to a raise, b to e return
LIFT = {}      # pick -> {'stop_m', 'pitch_deg', 'drop_m', 'frames'} (arm-driven stop, top3.LIFT2) or {'move_m': [x, y, z] (right hand, world metres), 'frames': [f0, f1, f2, f3]}: a minimum-jerk world offset of the gun and hand (--lift <json>, lift.py)
MIR = np.array([-1.0, 1.0, 1.0])


def family_of(pick):
    return next(f for f, v in FAMILIES.items() if pick in v[2])


def stem(gid, side, pick, take, clip): return f'{gid}_{side}_{pick}{take}_{clip}'


def plan(fams=None, picks=None, clips=None, sides=None, bodies=None):
    out = []
    for fam, (gid, take, pks, eng) in FAMILIES.items():
        if fams and fam not in fams: continue
        for p in pks:
            if picks and p not in picks: continue
            for clip in clips or CLIPS:
                for body in bodies or BODIES:
                    for side in sides or SIDES: out.append((fam, p, clip, side, body))
    return out


# ------------------------------------------------------------------------------------------------ engine wiring
def engine(fam):
    """(family module, engine module, r2lib) with the engine's names patched for production (rack on reload)."""
    F = importlib.import_module(fam); E = importlib.import_module(FAMILIES[fam][3]); import r2lib
    if os.environ.get('SMG_GUN') and fam == 'top3': F.GUN = os.environ['SMG_GUN']      # another gun of the family: the family's axes and stations stay
    orig = F.rack
    if not getattr(orig, '_prod', False):
        def rack(c, tl, kind):
            if c.clip == 'reload': return ready(c, tl, E)
            return orig(c, tl, kind)
        rack._prod = True; F.rack = rack
    return F, E, r2lib


def ready(c, tl, E):
    """Reload with a round chambered: no rack. Up from the seat through the rack's rise point, settled into the idle
    by the rack's held beat + 3 (the engine's spring, or a small kick, makes the stop); the idle holds to the end."""
    P = c.P; k = P['k']; B = c.B; e = B['held'] + 3
    tl.hold(B['rise']); tl.to(B['mid'], (0.03, -0.085, -0.045), (-9, 0, -3), 'rise'); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')
    tl.kick(e, (0.003, 0.008 * k, -0.008), (-1.5, 0, 0), release=3.0); tl.mark('ready', e)


def ctx(F, E, R2, P, ax, clip, side, body):
    import prod, magtrack2
    E.CLIP = clip; R2.CLIP = clip
    # seat and centre from the gun's empty reload for both clips, well axes the family's (the reload clip's own
    # magazine anim puts the same magazine back on the Pulsar); rgate and prod.Ctx read them through vanilla()
    v = dict(magtrack2.vanilla(F.GUN, 'empty_reload')); v.update({k: np.array(x, float) / np.linalg.norm(x) for k, x in ax.items()})
    magtrack2._van[(F.GUN, clip)] = v; magtrack2._van[(F.GUN, 'empty_reload')] = v
    c = prod.Ctx(F.GUN, body, clip, P, side.capitalize())
    c.T = (E.table if hasattr(E, 'table') else R2.table)(F.GUN, F.TAKE); c.N = c.T['frames']; c.B = c.T['beats']; c.take = F.TAKE
    c.v = v
    return c


def apply_spins_side(glb, clip, spins, slot, S):
    """r3lib.apply_spins on Weapon<S>. Left: authored in the mirror image, so a spin about gun axis a by d degrees
    becomes a spin about M a by -d through M p, an in-hand offset s becomes M s (M = diag(-1, 1, 1))."""
    import r3lib
    from glb import Glb
    from fk import Clip, qrot, qmul
    if S == 'Left':
        spins = [(dict(sp, axis=list(np.array(sp['axis'], float) * MIR), pivot=list(np.array(sp['pivot'], float) * MIR)), -np.asarray(a, float)) for sp, a in spins]
        slot = None if slot is None else slot * MIR
    if not spins and (slot is None or not np.any(slot)): return
    g = Glb(glb); i = g.names.index('Weapon' + S); a = g.anim(clip); c = Clip(g, clip); n = c.frames; T = []; Rr = []
    for f in range(n):
        t, r = c.local(i, f); t = np.array(t, float); r = np.array(r, float)
        for sp, ang in spins:
            q = r3lib.qaxis(sp['axis'], ang[f]); pv = np.array(sp['pivot'], float)
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


def pad(glb, clip, keys):
    """Hold the last frame up to `keys` keys (rarmset's padding, done here so the clip on disk has the count the
    WolvenKit import keeps)."""
    from glb import Glb
    g = Glb(glb); a = g.anim(clip); done = {}
    for ch in a['channels']:
        s = a['samplers'][ch['sampler']]
        if id(s) in done: continue
        t = np.asarray(g.acc(s['input']), float); v = np.asarray(g.acc(s['output']), float); n = len(t)
        if n >= keys or n < 2: continue
        v = v.reshape(n, -1); v2 = np.concatenate([v, np.repeat(v[-1:], keys - n, 0)]); t2 = np.arange(keys) / 30.0
        kind = {1: 'SCALAR', 3: 'VEC3', 4: 'VEC4'}[v.shape[1]]
        s['input'] = g.add_acc(t2, 'SCALAR'); s['output'] = g.add_acc(v2 if v.shape[1] > 1 else v2[:, 0], kind); done[id(s)] = True
    g.save(glb)


# ------------------------------------------------------------------------------------------------ extra checks
def flight(spec, trk, G, GO):
    """Old magazine after the release: nearest distance (cm) to the other gun and, once it is 3 frames past free,
    to its own gun (mesh points)."""
    import rchecks, gungeo, magtrack2
    gid = spec['_gun']; V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb'))[::7]; V1 = np.c_[V, np.ones(len(V))]
    PG = rchecks.gun_points(gid, 4000); r = trk['release']; ff = trk['free_from']; other = own = 9e9
    for f in range(r + 1, len(trk['frames'])):
        row = trk['frames'][f]; M = row.get('m2') if 'm2' in row else (row['m'] if row['state'] in ('guided', 'falling', 'loose') else None)
        if M is None: continue
        MP = rchecks.place(G[f], (V1 @ np.array(M).reshape(4, 4).T)[:, :3])
        b = rchecks.place(GO[f], PG)[::3]; other = min(other, float(np.sqrt(((MP[:, None] - b[None]) ** 2).sum(2)).min()) * 100)
        if f >= ff + 3:
            a = rchecks.place(G[f], PG)[::3]; own = min(own, float(np.sqrt(((MP[:, None] - a[None]) ** 2).sum(2)).min()) * 100)
    return {'other_gun_min_cm': round(other, 1), 'own_gun_min_cm_after_free': round(own, 1) if own < 9e8 else None}


def end_transition(spec):
    """The last frames against the idle the clip hands over to: every own arm joint and the gun, the largest step
    per frame over the last 3 frames (cm, deg) and the last frame against the idle (cm, deg)."""
    from glb import Glb
    from fk import Clip, qmul, qinv
    S = spec['_side']; N = spec['frames']; g = Glb(spec['out']); c = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}
    r = Glb(common.mp(spec.get('_idle') or spec['src'])); R0 = Clip(r, 'idle').world(0); rix = {n: i for i, n in enumerate(r.names)}
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


# ------------------------------------------------------------------------------------------------ build
def build(fam, pick, clip, side, body, quiet=False):
    import prod, rgate, magtrack2, author, rarmset
    from rlib import K
    from glb import Glb
    from fk import Clip
    F, E, R2 = engine(fam); r3 = E.__name__ == 'r3lib'
    if hasattr(F, 'prepare'): F.prepare(pick)
    prod.STATION.update(F.STATIONS); prod.PWA_DROP.update(PWA_DROP)
    S = side.capitalize(); O = 'Left' if S == 'Right' else 'Right'; d = f'{OUT}/{body}'; os.makedirs(d, exist_ok=True); name = stem(F.GUN, side, pick, F.TAKE, clip)
    P = dict(prod.TAKES[F.TAKE]); P.update(F.PARAMS.get(pick, {})); P.update(BODY_PARAMS.get((pick, body), {}))
    ax = dict(F.AXES); ax.update(P.get('axes', {}))
    c = ctx(F, E, R2, P, ax, clip, side, body)
    tl = E.TL3(c, P['lag'], 0.0) if r3 else E.TL(c, P['lag'], P['drag'])
    if hasattr(F, 'LIFT2'): F.LIFT2.clear(); F.LIFT2.update({k: LIFT[pick][k] for k in ('stop_m', 'pitch_deg', 'roll_deg', 'drop_m', 'lead') if k in LIFT[pick]} if 'stop_m' in LIFT.get(pick, {}) else {})
    if LOWERED:      # gun path from the lowered pose and back to it: start state, post-seat keys shifted by it, both ends exact (lowover.py)
        import lowover
        low_ = f"{common.path('low_clips')}/{body}/lowered_{common.gun(F.GUN)['lowered']['pose']}.glb"; Lp, Lr = lowover.gun_pose(c.rest, low_, 'Right'); seat_f = c.B['seat']; to0 = tl.to
        tl.P[:] = Lp; tl.R[:] = Lr; tl.p = Lp.copy(); tl.r = Lr.copy(); tl.end_p = Lp; tl.end_r = Lr
        sc = LOWERED.get('s', 1.0)
        def to_(f, pos, rot, *a, **k): return to0(f, np.array(pos, float) * (sc if f > seat_f else 1) + (Lp if f > seat_f else 0), np.array(rot, float) * (sc if f > seat_f else 1) + (Lr if f > seat_f else 0), *a, **k)
        tl.to = to_; arr0 = tl.arrays
        def arrays_():
            P_, R_ = arr0(); P_[0] = Lp; R_[0] = Lr; P_[-1] = Lp; R_[-1] = Lr; return P_, R_
        tl.arrays = arrays_
    fn = F.PICKS[pick][1]; m = fn(c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    rep = E.inertia_report(tl, Pk, Rk) if r3 else None
    spins = tl.spin_angles() if r3 else []
    if S == 'Left':
        Pk = Pk * prod.MIR_P; Rk = Rk * prod.MIR_R
        for k in kicks: k['move'] = list(np.array(k['move'], float) * prod.MIR_P); k['rot'] = list(np.array(k['rot'], float) * prod.MIR_R)
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0, Pk[0], Rk[0]) if LOWERED else K(0); keys[-1] = K(c.N - 1, Pk[-1], Rk[-1]) if LOWERED else K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    gm, anchors = R2.gun_map(F.GUN, F.TAKE) if r3 else E.gun_map(F.GUN, F.TAKE)
    spec = {'_draft': name, '_name': f'{F.PICKS[pick][0]}, take {F.TAKE}', '_doc': ' '.join((fn.__doc__ or '').split()), '_mechanism': getattr(F, 'MECH', {}).get(pick, ''),
            '_gun': F.GUN, '_left_gun': F.GUN, '_body': body, '_side': S, '_gun_clip': clip, '_pick': pick, '_take': F.TAKE, '_family': F.FAMILY, '_engine': E.__name__,
            '_timing': c.T, '_gun_map': gm, '_gun_anchors': anchors, '_axes': {k: [float(x) for x in v] for k, v in ax.items()}, '_params': {k: v for k, v in c.P.items()},
            '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False, '_round': 'smg-production', '_in_hand': IN_HAND.get(pick),
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, O: [K(0)]},
            'shakes': {S: kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}
    if r3: spec['_inertia'] = rep; spec['_spins'] = [[sp, [round(float(x), 2) for x in a]] for sp, a in spins]
    if r3 and tl.finger: spec['_finger'] = tl.finger
    if pick in LIFT and 'stop_m' in LIFT[pick]: spec['_lift'] = LIFT[pick]      # arm-driven stop at the raised position: the stop moved in top3.st38 (LIFT2), no bump
    if pick in LIFT and 'move_m' in LIFT[pick]:      # offset on the reloading gun: the hand follows, the arm is solved by the author's IK, the magazine track and the gate follow the lifted gun
        mv = np.array(LIFT[pick]['move_m'], float) * (prod.MIR_P if S == 'Left' else 1.0)
        spec['bumps'] = {S: [{'f': LIFT[pick]['frames'], 'move': [round(float(x), 5) for x in mv], 'profile': 'minjerk'}]}; spec['_lift'] = LIFT[pick]
    author.build(spec, spec['out'])
    if r3:
        apply_spins_side(spec['out'], 'reload_draft', spins, tl.slot if np.any(tl.slot) else None, S); spec['_slot_cm_max'] = round(float(np.abs(tl.slot).max()) * 100, 1)
    if LOWERED:
        import lowover
        low = f"{common.path('low_clips')}/{body}/lowered_{common.gun(F.GUN)['lowered']['pose']}.glb"; lr = f'{OUT}/../rest_low/{body}/rest_low_{F.GUN}.glb'; os.makedirs(os.path.dirname(lr), exist_ok=True)
        lowover.rest(c.rest, low, lr); L_ = LOWERED
        lowover.overlay(spec['out'], 'reload_draft', low, S, c.N, L_['h'], L_['a'], L_['b'], L_['e'], lowover.arm_joints(c.rest, low))
        spec['_idle'] = lr; spec['_lowered'] = dict(L_, low=low)
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); io = g.names.index('Weapon' + O)
    GG = [(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(c.N))]; GO = [cl.world(f)[io] for f in range(c.N)]
    trk = (E.track if r3 else E.track)(c, GG, m['mag']); trk['clip'] = clip; trk['side'] = S; trk['body'] = body
    spec['_track'] = f'{d}/{name}_track.json'
    json.dump(trk, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    magtrack2._van[(F.GUN, clip)] = c.v
    o = rgate.gate(spec, trk); o['elbow_step_deg'] = R2.elbow_step(spec) if r3 else E.elbow_step(spec)
    ex_fn = R2.exit_check if r3 else E.exit_check
    o['mag_exit'] = ex_fn(c, trk)
    if o['mag_exit']['off_axis_cm'] > rgate.LIM['off_axis_max_cm'] or o['mag_exit']['into_gun_cm'] > 0.5: o['fails'].append(f"magazine leaves the well {o['mag_exit']['off_axis_cm']} cm off its axis")
    o['mag_speed'] = E.speed_check(c, GG, trk); rs = o['mag_speed']['ratio']
    if not o['mag_speed']['ok']: o['fails'].append(f"magazine speed {o['mag_speed']['mag_cm_f']} cm/f vs gun {o['mag_speed']['gun_rel_cm_f']} on the release frame (ratio {rs})")
    o['mag_view_frames'] = (R2.view_frames if r3 else E.view_frames)(c, GG, trk)
    if r3:
        o['insert_rel_cm'] = E.insert_rel(c, trk); o['inertia'] = rep
        if o['insert_rel_cm'] > rgate.LIM['off_axis_max_cm']: o['fails'].append(f"fresh magazine meets the well {o['insert_rel_cm']} cm off its axis")
    if o['elbow_step_deg'] > 45: o['fails'].append(f"elbow swings {o['elbow_step_deg']} deg in one frame")
    o['flight'] = flight(spec, trk, GG, GO)
    if o['flight']['other_gun_min_cm'] < 5.0: o['fails'].append(f"old magazine {o['flight']['other_gun_min_cm']} cm from the other gun")
    o['end_transition'] = et = end_transition(spec)
    if et['last3_step_cm'] > 0.5 or et['last_vs_idle_cm'] > 0.02 or et['last_vs_idle_deg'] > 0.02: o['fails'].append(f"end transition {et}")
    keys_n = rarmset.good_keys(c.N); o['layout']['keys'] = keys_n
    pad(spec['out'], 'reload_draft', keys_n); spec['_keys'] = keys_n; json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o['in_hand'] = IN_HAND.get(pick)
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, side, rgate.line(o), '| elbow', o['elbow_step_deg'], '| exit', o['mag_exit'], '| speed', o['mag_speed'].get('na') or o['mag_speed']['ratio'], '| flight', o['flight'], flush=True)
    return spec, o


# ------------------------------------------------------------------------------------------------ layout
def layout():
    """Per gun, pick and clip: the hidden window every hand and body shares (latest hide_start, earliest hide_end)."""
    lay = {}; fails = []; rows = []
    for fam, pick, clip, side, body in plan():
        gid, take = FAMILIES[fam][0], FAMILIES[fam][1]; p = f'{OUT}/{body}/{stem(gid, side, pick, take, clip)}_gate.json'
        if not os.path.exists(p): fails.append(f'missing {p}'); continue
        o = json.load(open(p)); Lr = dict(o['layout']); rows.append((gid, pick + take, clip, side, body, o))
        e = lay.setdefault(gid, {}).setdefault(pick + take, {}).setdefault(clip, dict(Lr, per_clip={}))
        e['per_clip'][f'{body}_{side}'] = [Lr['hide_start'], Lr['hide_end']]
        if Lr['hide_start'] is None or e['hide_start'] is None: e['hide_start'] = e['hide_end'] = None
        else: e['hide_start'] = max(e['hide_start'], Lr['hide_start']); e['hide_end'] = min(e['hide_end'], Lr['hide_end'])
        if o['fails']: fails.append(f"{body} {o['clip']}: {o['fails']}")
    for gid in lay:
        for pk in lay[gid]:
            for clip, e in lay[gid][pk].items():
                e['slot'] = (clip if SLOTS[gid].index(pk[:-1]) == 0 else f"{clip}_0{SLOTS[gid].index(pk[:-1])}")
                if e['hide_start'] is not None and e['hide_end'] - e['hide_start'] + 1 < 12: fails.append(f'{gid} {pk} {clip}: shared hidden window only {e["hide_end"] - e["hide_start"] + 1} f')
    json.dump(lay, open(f'{OUT}/layout.json', 'w'), indent=1)
    Ls = ['| gun | pick | clip | slot | hide_start | hide_end | mag_out | seated | handle | length | keys |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for gid in lay:
        for pk in lay[gid]:
            for clip, e in lay[gid][pk].items(): Ls.append(f"| {gid} | {pk} | {clip} | {e['slot']} | {e['hide_start']} | {e['hide_end']} | {e['mag_out']} | {e['seated']} | {e['handle']} | {e['length']} | {e['keys']} |")
    open(f'{OUT}/layout.md', 'w').write('\n'.join(Ls) + '\n'); open(f'{OUT}/gate_fails.txt', 'w').write('\n'.join(fails) + '\n')
    gate_tables(rows); print('\n'.join(Ls)); print(len(fails), 'failures or missing')
    return lay


def gate_tables(rows):
    H = ['clip', 'body', 'side', 'hidden', 'eye cm', 'cover %', 'wrist / in view', 'reach', 'shoulder cm', 'body cm', 'guns gap cm', 'start / end cm', 'end step cm',
         'end transition (step cm, deg)', 'hang', 'dv cm/f', 'exit off axis (guided / free / at out)', 'insert off axis', 'speed (mag / gun, ratio)', 'mag in view after release',
         'old mag to other gun cm', 'elbow step deg', 'peak / stop cm/f', 'fails']
    per = {}
    for gid, pk, clip, side, body, o in rows:
        L = o['layout']; me = o['mag_exit']; ms = o['mag_speed']; et = o['end_transition']; m = o['motion']
        per.setdefault(gid, []).append('| ' + ' | '.join(str(x) for x in [
            f'{pk} {clip}', body, side, f"f{L['hide_start']}-{L['hide_end']} ({o['hidden_frames']})", o['eye_cm'][0], o['cover_peak'][0], f"{o['wrist'][0]} / {o['wrist_view']}", o['reach'][0],
            o['shoulder_pull_cm'], o['body_cm'][0], o['guns_gap_cm'][0], f"{o['start_cm']:.3f} / {o['end_cm']:.3f}", o['end_step_cm'], f"{et['last3_step_cm']}, {et['last3_step_deg']}",
            o['mag_hang'], o['release_dv_cm_f'], f"{o['exit_off_axis_cm']} / {me['off_axis_cm']} / {o['exit_at_10cm']}", o.get('insert_rel_cm', o['insert_off_axis_cm']),
            f"{ms['mag_cm_f']} / {ms['gun_rel_cm_f']} ({ms.get('na') or ms['ratio']})", o['mag_view_frames'], o['flight']['other_gun_min_cm'], o['elbow_step_deg'],
            f"{m['peak_speed']} / {m['stop']}", '; '.join(o['fails']) or 'pass']) + ' |')
    os.makedirs(OUT + '/gates', exist_ok=True)
    for gid, Rw in per.items():
        npass = sum(1 for r in Rw if r.endswith('| pass |'))
        txt = [f'# Gate, {common.gun(gid)["name"]}: {npass} of {len(Rw)} clips pass', '', '| ' + ' | '.join(H) + ' |', '|' + '---|' * len(H)] + Rw
        open(f'{OUT}/gates/gate_{gid}.md', 'w').write('\n'.join(txt) + '\n')
        print(gid, npass, 'of', len(Rw), 'pass')


def magsets():
    """One magazine set per gun, body and hand (tools/anim/rmagset2.py): the six slots carry the tracks of the three
    picks (SLOTS order), padded to the arm clip's key count, gun parts time-mapped; then rmagset2.check rebuilds every
    mesh matrix from the written keys. Output <OUT>/magsets/<gun>__smgmag_<body>_<side>.glb, magsets.json."""
    import gungeo
    sys.path.insert(0, renv.TOOLS); import rmagset2
    d = renv.OUT + '/magsets'; os.makedirs(d, exist_ok=True); rep = {}
    for gid, picks in SLOTS.items():
        fam = family_of(picks[0]); take = FAMILIES[fam][1]; gun = common.gun(gid)
        van, wpn, mesh = gungeo.wanim(gun, 'mag_std'), gungeo.wanim(gun, 'base1'), common.find('weapon_meshes', gun['mesh'] + '__mag_std_01.glb')
        for body in BODIES:
            for side in SIDES:
                items = []
                for clip in CLIPS:
                    for k, p in enumerate(picks):
                        base = f'{OUT}/{body}/{stem(gid, side, p, take, clip)}'; spec = json.load(open(base + '.json'))
                        items.append((base + '_track.json', clip if k == 0 else f'{clip}_0{k}', spec['_keys'], spec['_gun_map']))
                out = f'{d}/{gid}__smgmag_{body}_{side}.glb'; r, _ = rmagset2.build(van, wpn, mesh, out, items)
                chk = rmagset2.check(out, wpn, mesh, items); rep[os.path.basename(out)] = {'slots': r, 'check': chk}
                print(out, 'worst rebuilt mesh error', max(c['worst_cm'] for c in chk), 'cm', flush=True)
    json.dump(rep, open(f'{d}/magsets.json', 'w'), indent=1)


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None
    cmd = argv[0] if argv else 'list'
    if cmd == 'list':
        for p in plan(): print(*p)
        print(len(plan()), 'clips')
    elif cmd == 'build':
        lf = o('--lift')
        if lf: LIFT.update(json.load(open(lf)))
        lw = o('--lowered')
        if lw: LOWERED.update(json.load(open(lw)))
        fam = argv[1]; pl = plan([fam], cs(o('--picks')), cs(o('--clips')), cs(o('--sides')), cs(o('--bodies')))
        for p in pl: build(*p)
    elif cmd == 'all':
        jobs = int(o('--jobs') or 2); fams = list(FAMILIES); procs = []
        while fams or procs:
            while fams and len(procs) < jobs:
                f = fams.pop(0); lg = open(f'{renv.OUT}/work/build_{f}.log', 'w'); procs.append((f, subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), 'build', f], stdout=lg, stderr=subprocess.STDOUT)))
            for f, p in list(procs):
                if p.poll() is not None: print(f, 'exit', p.returncode, flush=True); procs.remove((f, p))
            import time; time.sleep(2)
    elif cmd == 'layout': layout()
    elif cmd == 'magsets': magsets()
    else: raise SystemExit(__doc__)
