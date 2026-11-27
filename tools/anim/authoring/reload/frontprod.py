"""Production of the owner's FRONT picks (PICKS.md, 2026-11-14): SF13 low chop (round 2, sf2.py), SF35 bat and
SF40 elbow check, slap home (round 4, sf4.py on the inertia model) on all six FRONT guns: Saratoga, Crusher,
Pozhar, Dian, Guillotine (take A, 72 frames) and Zhuo (take B, 81 frames); reload and empty reload, right and left
hand, male and female V; magazine track, gate numbers, layout.

What production adds to the reviewed generators (they ran on the Saratoga and the Zhuo, right hand, male V, empty
reload only):
  guns     each gun's own events (gun_events: cocking piece back, magazine out, seated, cocking home or the
           handle's frame, clamp) mapped onto the budget; the well axis from the magazine mesh in the gun's own
           plane (as round 2 did for the Saratoga; the Zhuo keeps its own clip's axis, as reviewed). Guillotine:
           no magazine anim set: the seat is the mesh bind pose on mag_slot and the timing is the Saratoga's (its
           gun anim matches within 0.04 cm, phase 1).
  clip     the empty reload as reviewed. The reload keeps the rack only where the gun's own reload clip works the
           cocking piece (Saratoga, Guillotine, Zhuo); elsewhere (Crusher, Pozhar, Dian) a round is chambered and
           nothing moves: up from the rig and settled into the idle, no hit.
  side     left: authored as a right hand in the mirror image (prod.Ctx), keys mirrored back (x, yaw, roll); the
           other gun's contact patches on its inner flank; the bat aim mirrored.
  body     pwa: stations from her hips, PWA_DROP where needed.
Checks added: end transition into the idle; the old magazine against the other gun (its seated magazine box: a
vertex inside it is a pass-through; the nearest distance to its body points).

usage: frontprod.py events | list | build [--guns a,b] [--picks ..] [--clips ..] [--sides ..] [--bodies ..]
       frontprod.py all [--jobs n] | layout | magsets | regress
"""
import os, sys, json, math, copy, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, manifest
import numpy as np
import nativelow as NL, author, prod, rgate, magtrack2, magtrack3, timing, gungeo, rchecks, rarmset, inertia, sf2, sf4, sf1
from rlib import K
from glb import Glb
from fk import Clip, qrot
from wclip import TClip

OUT = renv.OUT + '/clips'
GUNS = {'saratoga': 'A', 'crusher': 'A', 'pozhar': 'A', 'dian': 'A', 'guillotine': 'A', 'zhuo': 'B'}
SLOTS = ['SF13', 'SF35', 'SF40']
CLIPS = ('reload', 'empty_reload'); SIDES = ('right', 'left'); BODIES = ('pma', 'pwa')
COCK = {'saratoga': 'cocking', 'guillotine': 'cocking', 'zhuo': 'barrel_cocking', 'dian': 'charging_handle', 'crusher': 'reload_handle', 'pozhar': 'cocking_device'}
ARM_LEN = {'saratoga': (88, 88), 'guillotine': (88, 88), 'zhuo': (121, 121), 'dian': (81, 106), 'crusher': (86, 106), 'pozhar': (105, 129)}   # phase 1 (reload, empty)
PWA_DROP = {}
PARAMS = {            # (pick, gun) -> parameter changes in production
    # Dian: its idle is 16.8 cm from the eye and its stock reaches 37 cm behind the grip
    ('SF13', 'dian'): {'rise': (0.03, -0.12, -0.05), 'rise_rot': (4, 0, -3), 'rise_rlag': 0, 'rise_rprof': 'snap', 'ready_kick': (0.0, -0.004, -0.006)},   # the rise came to 15.6 cm (limit 15.8), 14.9 on female V; the reload's settle kick lifted the stock to 15.7
    ('SF40', 'dian'): {'p0': (0.16, -0.02, -0.05), 'r0': (-4, 0, -45), 'dist': 0.12, 'via': (0.10, -0.04, -0.06), 'post_seat': None,   # the Zhuo's long-gun path put the old magazine through the left gun's
                       'rise': (0.03, -0.13, -0.02), 'rise_rot': (4, 0, -3), 'rise_rlag': 0, 'ready_kick': (0.0, -0.004, -0.006), 'ready_extra': 5},   # magazine (f20); less roll, swing from further out; lower via (stock past her face at f26); no side step and a rise further back (shoulder 5.8 cm); the reload's settle 5 frames longer (it overshot to 15.5 cm)
    ('SF35', 'dian'): {'p0': (0.03, -0.10, -0.01), 'through': (0.0, 0.0, 0.02), 'roll': 50, 'bat_rot': (-4, 0, 45),
                       'bat_tries': ((2, (-0.03, 0.0, 0.08)), (2, (-0.02, -0.02, 0.06)), (3, (-0.03, 0.0, 0.08))),
                       'rise': (0.03, -0.13, -0.02), 'rise_rot': (4, 0, -3), 'rise_rlag': 0, 'ready_kick': (0.0, -0.004, -0.006), 'ready_extra': 5},
    # SF35: the bat swing's peak held to the reviewed Saratoga take (14.8 cm/f; owner: speeds must match across the family).
    # Dian: the stock came to 11.6 cm, the shoulder pulled 4 to 5 cm, the swing peaked at 22.4; met one frame later (2 after it
    # is free), from a lower pour: 16.9, the lowest that passes (searched in work/search: d1 to d23)
    ('SF35', 'crusher'): {'roll': 42, 'through': (0.01, -0.01, 0.0), 'bat_rot': (-4, 0, 36)},     # 17.5 -> 15.0 cm/f
    ('SF35', 'pozhar'): {'roll': 32, 'through': (0.01, -0.01, 0.0), 'bat_rot': (-4, 0, 30)},      # 17.8 -> 15.2 cm/f
    ('SF35', 'guillotine'): {'roll': 55},                                                         # 15.1 -> 14.7 cm/f
    ('SF13', 'zhuo', 'pwa'): {'rise': (0.03, -0.13, -0.06)},                          # female V: the rack's rise brought the Zhuo's stock to 19.4 cm (rule 20)
    # Guillotine: its 29 cm magazine hit the left gun on the release frame (velocity jump 2.5 cm/f), and the gun sat
    # 6.6 cm in the thigh block after the slap: swing from further out, slap station further out
    ('SF40', 'guillotine'): {'p0': (0.15, 0.02, -0.01), '_stations': {'slap_thigh': ((0.41, 0.06, -0.02), (-75, 0, -80))}},
    ('SF40', 'zhuo', 'left'): {'p0': (0.15, -0.05, -0.03)}}        # left hand: a double bounce on the right gun (velocity jump 1.53, rule 1.5; 0.135 still hung 1 f)
MIR = np.array([-1.0, 1.0, 1.0])
STATE = {'rack': True}
REVIEWED = {('saratoga', 'SF13'): 'round2-front', ('zhuo', 'SF13'): 'round2-front', ('saratoga', 'SF35'): 'round4-front', ('zhuo', 'SF35'): 'round4-front',
            ('saratoga', 'SF40'): 'round4-front', ('zhuo', 'SF40'): 'round4-front'}


def stem(gid, side, pick, clip): return f'{gid}_{side}_{pick}{GUNS[gid]}_{clip}'


# ------------------------------------------------------------------------------------------------ gun data
def _guillotine():
    """Timing and magazine data of the Guillotine (no magazine anim set): the Saratoga's timing, its own mesh seated
    on mag_slot in the bind pose."""
    for clip in CLIPS:
        if ('guillotine', clip) not in timing._cache:
            T = copy.deepcopy(timing.table('saratoga', clip)); T['gun'] = 'guillotine'; timing._cache[('guillotine', clip)] = T
    if ('guillotine', 'empty_reload') not in magtrack2._van:
        gun = common.gun('guillotine'); gb = Glb(gungeo.wanim(gun, 'base1')); an = [a['name'] for a in gb.j['animations']]
        S = magtrack2.m4(*TClip(gb, 'empty_reload' if 'empty_reload' in an else an[0]).world(0)[gb.names.index('mag_slot')])
        mp = common.find('weapon_meshes', gun['mesh'] + '__mag_std_01.glb'); sk = Glb(mp); s = sk.j['skins'][0]
        ibm = np.asarray(sk.acc(s['inverseBindMatrices']), float).reshape(-1, 4, 4)[0].T; V = gungeo.verts(mp); cen = (V.min(0) + V.max(0)) / 2
        seat = S @ np.linalg.inv(ibm) @ ibm      # the joint at its bind: mesh model space on mag_slot
        magtrack2._van[('guillotine', 'empty_reload')] = {'M': [], 'seat': seat, 'centre': cen, 'exit': np.array([0, -1.0, 0]), 'enter': np.array([0, 1.0, 0]), 'dist': np.zeros(1), 'out': 0, 'seated': 0}


def gun_events(gid, clip):
    """The gun's own frames for one clip: frames (arm clip length), cock (cocking piece back), out, seated, home
    (cocking piece home, or a late handle's first frame), clamp_open / clamp_shut (Zhuo). None where a part does not move."""
    src = 'saratoga' if gid == 'guillotine' else gid; T = timing.table(src, clip); gun = common.gun(gid); b = gungeo.wanim(gun, 'base1')
    ev = {'frames': ARM_LEN[gid][CLIPS.index(clip)], 'out': T['out'], 'seated': T['seated'], 'cock': None, 'home': None, 'part': COCK[gid]}
    an = [a['name'] for a in Glb(b).j['animations']]
    if clip in an and COCK[gid] in Glb(b).names:
        d = sf1._curve(b, clip, COCK[gid]); pk = float(d.max())
        if pk > 0.5:
            first = int(np.argmax(d >= 0.1 * pk))
            if first < T['seated']:
                ev['cock'] = int(np.argmax(d >= 0.9 * pk)); ev['home'] = next((f for f in range(T['seated'], len(d)) if d[f] <= 0.5 * pk), None)
            else: ev['home'] = first
    if gid == 'zhuo':
        r = sf1._curve(gungeo.wanim(gun, 'rcv1'), clip, 'l_mag_holder_01'); m = r.max()
        ev['clamp_open'] = int(np.argmax(r >= 0.9 * m)); ev['clamp_shut'] = next(f for f in range(ev['clamp_open'] + 5, len(r)) if r[f] <= 0.5 * m)
    return ev


def part_frames(gid, clip, release):
    """Gun anim frame per budget frame, piecewise linear through the anchors this clip has (sf2.part_frames for
    any gun and either clip); after the last anchor at the gun's own pace."""
    B = sf2.BUDGET[GUNS[gid]]; G = gun_events(gid, clip); xs, ys = [0], [0]
    if G['cock'] is not None: xs.append(B['cock']); ys.append(G['cock'])
    xs += [release, B['seat']]; ys += [G['out'], G['seated']]
    if G['home'] is not None: xs.append(B['home']); ys.append(G['home'])
    xs.append(B['frames'] - 1); ys.append(min(ys[-1] + B['frames'] - 1 - xs[-1], G['frames'] - 1) if G['home'] is not None else min(G['seated'] + B['frames'] - 1 - B['seat'], G['frames'] - 1))
    return [round(float(np.interp(f, xs, ys)), 2) for f in range(B['frames'])], list(zip(xs, ys))


def setup(gid):
    """Budget frames into the timing table every tool reads, the well axis into the magazine data; both clips see
    the empty reload's seat (the reload clips of the Saratoga and Pozhar put the same magazine back)."""
    if gid == 'guillotine': _guillotine()
    T = timing.table(gid, 'empty_reload')
    if T.get('_fp'): return T
    take = GUNS[gid]; B = sf2.BUDGET[take]; T.update({'frames': B['frames'], 'seated': B['seat'], 'handle': [B['home'], B['home']], 'budget': B, 'gun_events': gun_events(gid, 'empty_reload'), '_sf2': True, '_fp': True})
    v = magtrack2.vanilla(gid, 'empty_reload')
    if gid == 'dian': v['seat'] = v['M'][-1]       # the Dian's magazine is 46 cm below the well on frame 0 of its own clip (phase 1); seated on the last frame
    if gid != 'zhuo':
        V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb')); P = (np.c_[V, np.ones(len(V))] @ v['seat'].T)[:, :3]
        ax = np.linalg.svd(P - P.mean(0), full_matrices=False)[2][0]; ax = ax * (-1 if ax[1] > 0 else 1); ax[0] = 0; ax /= np.linalg.norm(ax)
        v['exit'] = ax; v['enter'] = -ax
    magtrack2._van[(gid, 'reload')] = v
    return T


def half_width(gid):
    if gid == 'saratoga': return 0.019
    if gid == 'zhuo': return 0.04
    V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb')); return float(V[:, 0].max() - V[:, 0].min()) / 2


def bat_pad(gid):
    """The gun's underside 10 cm ahead of the magazine (gun axes): where the bat meets the magazine. The reviewed
    value on the Saratoga and the Zhuo."""
    if gid in ('saratoga', 'zhuo'): return (0.0, -0.05, -0.24)
    v = magtrack2.vanilla(gid, 'empty_reload'); zc = float((v['seat'] @ np.r_[v['centre'], 1])[2]) - 0.10; P = rchecks.gun_points(gid)
    near = P[np.abs(P[:, 2] - zc) < 0.02]; y = float(near[:, 1].min()) if len(near) else -0.05
    return (0.0, round(y, 3), round(zc, 3))


# ------------------------------------------------------------------------------------------------ racks
def ready(c, tl):
    """Reload with a round chambered and no cocking piece worked by the gun's own clip: no rack. Up from the rig
    through the rack's rise point and settled into the idle 3 frames before the home beat."""
    P = c.P; k = P['k']; se = sf2.bud(c)['seat']; h = sf2.bud(c)['home']; f = h - 4; L = prod.L
    rise = P.get('rise', (0.03, -0.10 if sf2.long_gun(c) else -0.085, -0.07 if sf2.long_gun(c) else -0.045))
    tl.hold(max(f - 3 - L(P, 8), tl.f)); tl.to(f - 3, rise, P.get('rise_rot', (-9, 0, -3)), 'rise', rlag=P.get('rise_rlag'), rprof=P.get('rise_rprof')); e = f + 1 + P.get('ready_extra', 0); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')
    tl.kick(e, P.get('ready_kick', (0.003, 0.008 * k, -0.008)), (-1.5, 0, 0), release=3.0); tl.mark('ready', e)


LONG = ('zhuo', 'dian')        # long guns: the round 2 / 4 long-gun handling (rack rise, rig lag, stations) of the Zhuo
sf2.long_gun = sf4.long_gun = lambda c: c.gun in LONG
_orig_rack = sf2.rack
def _rack(c, tl, kind):
    return _orig_rack(c, tl, kind) if STATE['rack'] else ready(c, tl)
sf2.rack = _rack; sf4.rack = _rack


# ------------------------------------------------------------------------------------------------ checks
def through_other(gid, trk, G, GO):
    """Old magazine against the other gun: frames where a vertex of it is inside the other gun's seated magazine
    box (3 mm inside its faces), and the nearest distance (cm) to the other gun's body points."""
    v = magtrack2.vanilla(gid, 'empty_reload'); V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb'))
    lo, hi = V.min(0) + 0.003, V.max(0) - 0.003; Vs = np.c_[V[::4], np.ones(len(V[::4]))]; PG = rchecks.gun_points(gid, 4000)
    r = trk['release']; inside = []; dmin = 9e9
    for f in range(r + 1, len(trk['frames'])):
        row = trk['frames'][f]; M = row.get('m2') if 'm2' in row else (row['m'] if row['state'] in ('guided', 'falling', 'loose') else None)
        if M is None: continue
        W = (magtrack2.m4(*G[f]) @ np.array(M).reshape(4, 4) @ Vs.T).T
        L = (np.linalg.inv(magtrack2.m4(*GO[f]) @ v['seat']) @ W.T).T[:, :3]
        if np.any(np.all((L > lo) & (L < hi), axis=1)): inside.append(f)
        b = rchecks.place(GO[f], PG)[::3]; dmin = min(dmin, float(np.sqrt(((W[:, :3][::2, None] - b[None]) ** 2).sum(2)).min()) * 100)
    return {'inside_other_mag_frames': inside, 'other_gun_min_cm': round(dmin, 1)}


def end_transition(spec):
    from fk import qmul, qinv
    S = spec['_side']; N = spec['frames']; g = Glb(spec['out']); c = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}
    r = Glb(common.mp(spec.get('_idle') or spec['src'])); R0 = Clip(r, 'idle').world(0); rix = {n: i for i, n in enumerate(r.names)}      # a lowered clip ends in the lowered idle (rest_low)
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


# ------------------------------------------------------------------------------------------------ build
def mirror_keys(Pk, Rk, S):
    return (Pk * prod.MIR_P, Rk * prod.MIR_R) if S == 'Left' else (Pk, Rk)


def other_hits(c, rel, S):
    """sf4.left_hits for either hand: patches on the other gun's flank that faces this gun (its axes are its own:
    the left gun's right flank is +x, the right gun's left flank is -x)."""
    c0 = (c.v['seat'] @ np.r_[c.v['centre'], 1])[:3]; hw = half_width(c.gun); sg = 1.0 if S == 'Right' else -1.0
    return [{'body': 'left', 'f': [rel, rel + 20], 'p': [float(x) for x in c0 + np.array([sg * hw, 0, 0])], 'n': [sg, 0, 0], 'rad': 0.12, 'e': 0.35, 'mu': 0.3},
            {'body': 'left', 'f': [rel, rel + 20], 'p': [sg * 0.03, 0.0, -0.12], 'n': [sg, 0, 0], 'rad': 0.14, 'e': 0.35, 'mu': 0.3}]


def aim_bat(c, track, G, m, after, bias, S):
    """sf4.aim_bat for either hand (the left is authored in the mirror image: the magazine centre and the pad mirrored)."""
    P = c.P; v = c.v; cen = np.r_[v['centre'], 1]; ff = track['free_from']; fb = min(ff + after, len(G) - 1)
    mc = (magtrack2.m4(*G[fb]) @ np.array(track['frames'][fb]['m']).reshape(4, 4) @ cen)[:3]; pad_ = np.array(m['mag']['hits'][0]['p'], float)
    if S == 'Left': mc = mc * MIR; pad_ = pad_ * MIR
    rb = np.array(P.get('bat_rot', (-4, 0, 35)), float); q = author.qmul(c.q0, author.qeuler(*rb))
    pb = mc - qrot(q, pad_) - c.g0 + np.array(bias)
    return fb, [float(x) for x in pb], [float(x) for x in rb]


def base_spec(c, gid, pick, clip, S, body, name, d, keys, shakes, mg, marks, doc, rnd):
    O = 'Left' if S == 'Right' else 'Right'; pf, anchors = part_frames(gid, clip, mg['release'])
    return {'_draft': name, '_name': f"{(sf2.PICKS if pick == 'SF13' else sf4.PICKS)[pick][0]}, take {GUNS[gid]}", '_doc': doc, '_gun': gid, '_left_gun': gid, '_body': body, '_side': S,
            '_gun_clip': clip, '_pick': pick, '_take': GUNS[gid], '_timing': c.T, '_gun_events': gun_events(gid, clip), '_params': {k: v for k, v in c.P.items() if not k.startswith('_')},
            '_marks': marks, '_mag': mg, '_two_arm': False, '_round': rnd, '_part_frames': pf, '_gun_map': pf, '_gun_anchors': anchors, 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft',
            'frames': c.N, 'keys': {S: keys, O: [K(0)]}, 'shakes': shakes, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}


def world_paths(spec, N):
    S = spec['_side']; O = 'Left' if S == 'Right' else 'Right'; g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); W = [cl.world(f) for f in range(N)]
    i, io = g.names.index('Weapon' + S), g.names.index('Weapon' + O)
    return [(np.array(W[f][i][0]), np.array(W[f][i][1])) for f in range(N)], [(np.array(W[f][io][0]), np.array(W[f][io][1])) for f in range(N)]


def build_sf13(gid, clip, S, body, name, d):
    take = GUNS[gid]; P = dict(sf2.TAKES[take]); P.update(sf2.PARAMS.get('SF13' + take, {})); P.update(PARAMS.get(('SF13', gid), {})); P.update(PARAMS.get(('SF13', gid, body), {}))
    c = prod.Ctx(gid, body, 'empty_reload', P, S); tl = sf2.TL(c, P['lag'], P['drag'])
    if NL.NATIVE: Lp, Lr, note = NL.prepare(tl, c, gid, body, c.T['seated'], lambda: m)      # native lowered mode (nativelow.py)
    m = sf2.PICKS['SF13'][1](c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]; Pk, Rk = mirror_keys(Pk, Rk, S)
    if S == 'Left':
        for k in kicks: k['move'] = list(np.array(k['move'], float) * prod.MIR_P); k['rot'] = list(np.array(k['rot'], float) * prod.MIR_R)
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0, Pk[0], Rk[0]) if NL.NATIVE else K(0); keys[-1] = K(c.N - 1, Pk[-1], Rk[-1]) if NL.NATIVE else K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    spec = base_spec(c, gid, 'SF13', clip, S, body, name, d, keys, {S: kicks}, m['mag'], tl.marks, sf2.DOC['SF13'], 'smg-front-production (round 2 generator)')
    author.build(spec, spec['out'])
    if NL.NATIVE: NL.finish(spec, c, m, gid, body, S, name, OUT, manifest.path('smg_reload_clips')); spec['_clearance'] = note
    G, GO = world_paths(spec, c.N)
    track = magtrack3.build(gid, 'empty_reload', G, m['mag']); o_extra = {}
    return c, spec, track, G, GO, {'kind': 'sf2', 'm': m}


def compose4(gid, pick, S, body, extra=None):
    take = GUNS[gid]; P = dict(sf4.TAKES[take]); P.update(sf4.DEF.get(pick, {})); P.update(sf4.PARAMS.get(pick + take, {})); P.update(PARAMS.get((pick, gid), {})); P.update(PARAMS.get((pick, gid, body), {})); P.update(PARAMS.get((pick, gid, S.lower()), {}))
    if pick == 'SF35': P.setdefault('pad', bat_pad(gid))
    P.update(extra or {})
    keep = {k: prod.STATION.get(k) for k in P.get('_stations', {})}; prod.STATION.update(P.get('_stations', {}))
    try:
        c = prod.Ctx(gid, body, 'empty_reload', P, S); tl = sf4.TL(c, 0, 0.0); m = sf4.PICKS[pick][1](c, tl)
    finally:
        for k, v in keep.items(): prod.STATION[k] = v
    Pt, Rt = tl.P.copy(), tl.R.copy(); Pt[-1] = 0; Rt[-1] = 0
    sim = inertia.simulate_gun(c, take, Pt, Rt, sf4.impulses_from(tl), m.get('contacts', []), tl.guides, model=m.get('model'))
    return c, tl, m, sim, Pt, Rt


def author4(gid, pick, clip, S, body, name, d, c, tl, m, sim, Pt, Rt, other_shakes=None):
    O = 'Left' if S == 'Right' else 'Right'; X, E = mirror_keys(np.array(sim['X']), np.array(sim['E']), S)
    keys = [K(f, X[f], E[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1); mg = m['mag']
    spec = base_spec(c, gid, pick, clip, S, body, name, d, keys, {S: [], O: other_shakes or []}, mg, tl.marks, sf4.DOC[pick], 'smg-front-production (round 4 generator, inertia)')
    spec['_why'] = sf4.WHY.get(pick, ''); spec['twist_share'] = m.get('twist_share', 0.6)
    spec['_target'] = {'P': [[round(float(x), 5) for x in p] for p in Pt], 'R': [[round(float(x), 3) for x in r] for r in Rt]}
    author.build(spec, spec['out']); G, GO = world_paths(spec, c.N)
    mg = dict(mg, hits=mg.get('hits', []) + other_hits(c, mg['release'], S)); spec['_mag'] = mg
    track = inertia.simulate_mag(gid, 'empty_reload', G, mg, {'left': inertia.GunPath(GO)})
    return spec, track, G, GO


def build_sf4(gid, pick, clip, S, body, name, d, quiet=False):
    c, tl, m, sim, Pt, Rt = compose4(gid, pick, S, body)
    spec, track, G, GO = author4(gid, pick, clip, S, body, name, d, c, tl, m, sim, Pt, Rt)
    if m.get('bat'):
        fs = track['free_from']; best = None
        tries = c.P.get('bat_tries') or ((1, (-0.03, 0.0, 0.06)), (1, (-0.02, -0.02, 0.06)), (2, (-0.03, 0.0, 0.08)), (2, (-0.02, -0.02, 0.06)), (1, (0.0, -0.04, 0.04)))   # sf4's order; bat_tries: per gun
        for after, bias in tries:
            fb, pb, rb = aim_bat(c, track, G, m, after, bias, S)
            c2, tl2, m2, sim2, Pt2, Rt2 = compose4(gid, pick, S, body, {'_bat': (fb, pb, rb, fs)})
            r2 = author4(gid, pick, clip, S, body, name, d, c2, tl2, m2, sim2, Pt2, Rt2)
            hit = any(b['body'] == 'gun' for b in r2[1]['phys']['bounces'])
            if not quiet: print('   bat try', after, bias, 'hit', hit, flush=True)
            if hit or best is None: best = (c2, tl2, m2, sim2, Pt2, Rt2) + tuple(r2)
            if hit: break
        c, tl, m, sim, Pt, Rt, spec, track, G, GO = best
    lb = [b for b in track['phys']['bounces'] if b['body'] == 'left']
    if lb:     # the other gun takes the knock (magazine about 0.5 kg against gun and forearm about 4 kg)
        J = np.array(lb[0]['impulse']) * -0.125; f = int(round(lb[0]['t'])); sg = 1.0 if S == 'Right' else -1.0
        sh = [{'type': 'kick', 'f': f, 'move': [float(x) for x in J * 0.7], 'rot': [float(-J[1] * 300), 0.0, float(sg * J[0] * 300)], 'attack': 0.5, 'release': 2.5, 'lag': 0.6}]
        spec, track, G, GO = author4(gid, pick, clip, S, body, name, d, c, tl, m, sim, Pt, Rt, other_shakes=sh)
    return c, spec, track, G, GO, {'kind': 'sf4', 'm': m, 'sim': sim, 'tl': tl}


def build(gid, pick, clip, side, body, quiet=False):
    setup(gid); ev = gun_events(gid, clip); STATE['rack'] = ev['home'] is not None
    prod.PWA_DROP.update(PWA_DROP); S = side.capitalize(); d = f'{OUT}/{body}'; os.makedirs(d, exist_ok=True); name = stem(gid, side, pick, clip)
    if pick == 'SF13': c, spec, track, G, GO, X = build_sf13(gid, clip, S, body, name, d)
    else: c, spec, track, G, GO, X = build_sf4(gid, pick, clip, S, body, name, d, quiet)
    track['clip'] = clip; track['side'] = S; track['body'] = body; spec['_track'] = f'{d}/{name}_track.json'
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); o['elbow_step_deg'] = sf2.elbow_step(spec); o['mag_gone_height_m'] = sf2.gone_height(gid, track, G)
    if X['kind'] == 'sf2':
        o['mag_speed'] = sf2.mag_speed(gid, track, G)
        if not o['mag_speed']['ok']: o['fails'].append(f"magazine speed {o['mag_speed']['exit_cm_f']} cm/f against the gun's {o['mag_speed']['gun_cm_f']} (ratio {o['mag_speed']['ratio']})")
    else:
        m, sim, tl = X['m'], X['sim'], X['tl']; gs = inertia.gun_stats(sim, tl.marks); ms = inertia.mag_stats(gid, 'empty_reload', track, G)
        hit = [e for e in gs['impacts'] if e['name'] != 'seat' and e['f'] >= m['mag']['release'] - 1]
        if m.get('thrown') and hit: ms['gun_cm_f'] = round(max(ms['gun_cm_f'], hit[0]['impact_cm_f']), 2); ms['ratio'] = round(ms['exit_cm_f'] / ms['gun_cm_f'], 2); ms['gun_from'] = 'contact'
        o['mag_speed'] = ms; sf4.release_dv(o, track, G); sf4.bounce_hang(o, track, G)
        if m.get('thrown') and (ms['ratio'] is None or not sf4.MAG_RATIO[0] <= ms['ratio'] <= sf4.MAG_RATIO[1]): o['fails'].append(f"thrown magazine {ms['exit_cm_f']} cm/f against the gun's {ms['gun_cm_f']} (ratio {ms['ratio']})")
        if ms['clear_cm'] is not None and ms['clear_cm'] < 0.3: o['fails'].append(f"free magazine {ms['clear_cm']} cm from the gun (through it)")
        if track['phys']['free_t'] is None: o['fails'].append('magazine never leaves the well')
        if m.get('bat') and not any(b['body'] == 'gun' for b in track['phys']['bounces']): o['fails'].append('bat misses the magazine')
        o['inertia'] = {'gun': gs, 'mag': ms, 'bounces': track['phys']['bounces']}
        json.dump({'gun': gs, 'mag': ms, 'bounces': track['phys']['bounces'], 'model': sim['model']}, open(f'{d}/{name}_inertia.json', 'w'), indent=1)
    if o['mag_gone_height_m'] is not None and o['mag_gone_height_m'] > 0.09: o['fails'].append(f"old magazine removed {o['mag_gone_height_m']} m above the ground")
    if o['elbow_step_deg'] > 45: o['fails'].append(f"elbow swings {o['elbow_step_deg']} deg in one frame")
    o['other_gun'] = th = through_other(gid, track, G, GO)
    if th['inside_other_mag_frames']: o['fails'].append(f"old magazine passes through the other gun's magazine (f{th['inside_other_mag_frames'][:5]})")
    o['end_transition'] = et = end_transition(spec)
    if et['last3_step_cm'] > 0.5 or et['last_vs_idle_cm'] > 0.02 or et['last_vs_idle_deg'] > 0.02: o['fails'].append(f'end transition {et}')
    kn = rarmset.good_keys(c.N); o['layout']['keys'] = kn; pad(spec['out'], 'reload_draft', kn); spec['_keys'] = kn
    json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1); json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, side, rgate.line(o), '| elbow', o['elbow_step_deg'], '| speed', o['mag_speed'].get('ratio'), '| other', th, flush=True)
    return spec, o


# ------------------------------------------------------------------------------------------------ plan, layout, magsets
def plan(guns=None, picks=None, clips=None, sides=None, bodies=None):
    return [(g, p, cl, s, b) for g in GUNS if not guns or g in guns for p in SLOTS if not picks or p in picks for cl in (clips or CLIPS) for b in (bodies or BODIES) for s in (sides or SIDES)]


def layout():
    lay = {}; fails = []; rows = []
    for gid, pick, clip, side, body in plan():
        p = f'{OUT}/{body}/{stem(gid, side, pick, clip)}_gate.json'
        if not os.path.exists(p): fails.append(f'missing {p}'); continue
        o = json.load(open(p)); Lr = dict(o['layout']); rows.append((gid, pick + GUNS[gid], clip, side, body, o))
        e = lay.setdefault(gid, {}).setdefault(pick + GUNS[gid], {}).setdefault(clip, dict(Lr, per_clip={}))
        e['per_clip'][f'{body}_{side}'] = [Lr['hide_start'], Lr['hide_end']]
        if Lr['hide_start'] is None or e['hide_start'] is None: e['hide_start'] = e['hide_end'] = None
        else: e['hide_start'] = max(e['hide_start'], Lr['hide_start']); e['hide_end'] = min(e['hide_end'], Lr['hide_end'])
        if o['fails']: fails.append(f"{body} {o['clip']}: {o['fails']}")
    for gid in lay:
        for pk in lay[gid]:
            for clip, e in lay[gid][pk].items():
                i = SLOTS.index(pk[:-1]); e['slot'] = clip if i == 0 else f'{clip}_0{i}'
                if e['hide_start'] is not None and e['hide_end'] - e['hide_start'] + 1 < 12: fails.append(f'{gid} {pk} {clip}: shared hidden window only {e["hide_end"] - e["hide_start"] + 1} f')
    json.dump(lay, open(f'{OUT}/layout_front.json', 'w'), indent=1)
    Ls = ['| gun | pick | clip | slot | hide_start | hide_end | mag_out | seated | handle | length | keys |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for gid in lay:
        for pk in lay[gid]:
            for clip, e in lay[gid][pk].items(): Ls.append(f"| {gid} | {pk} | {clip} | {e['slot']} | {e['hide_start']} | {e['hide_end']} | {e['mag_out']} | {e['seated']} | {e['handle']} | {e['length']} | {e['keys']} |")
    open(f'{OUT}/layout_front.md', 'w').write('\n'.join(Ls) + '\n'); open(f'{OUT}/gate_fails_front.txt', 'w').write('\n'.join(fails) + '\n')
    tables(rows); print('\n'.join(Ls)); print(len(fails), 'failures or missing')


def tables(rows):
    H = ['clip', 'body', 'side', 'hidden', 'eye cm', 'cover %', 'wrist / in view', 'reach', 'shoulder cm', 'body cm', 'guns gap cm', 'start / end cm', 'end step cm', 'end transition (cm, deg)',
         'hang', 'dv cm/f', 'exit off axis (guided / at out)', 'insert off axis', 'speed ratio', 'lands m', 'other gun (min cm, through its magazine)', 'elbow step', 'peak / stop', 'fails']
    per = {}
    for gid, pk, clip, side, body, o in rows:
        L = o['layout']; et = o['end_transition']; m = o['motion']; ms = o['mag_speed']; th = o['other_gun']
        per.setdefault(gid, []).append('| ' + ' | '.join(str(x) for x in [f'{pk} {clip}', body, side, f"f{L['hide_start']}-{L['hide_end']} ({o['hidden_frames']})", o['eye_cm'][0], o['cover_peak'][0],
            f"{o['wrist'][0]} / {o['wrist_view']}", o['reach'][0], o['shoulder_pull_cm'], o['body_cm'][0], o['guns_gap_cm'][0], f"{o['start_cm']:.3f} / {o['end_cm']:.3f}", o['end_step_cm'],
            f"{et['last3_step_cm']}, {et['last3_step_deg']}", o['mag_hang'], o['release_dv_cm_f'], f"{o['exit_off_axis_cm']} / {o['exit_at_10cm']}", o['insert_off_axis_cm'], ms.get('ratio'),
            o['mag_gone_height_m'], f"{th['other_gun_min_cm']}, {len(th['inside_other_mag_frames'])} f", o['elbow_step_deg'], f"{m['peak_speed']} / {m['stop']}", '; '.join(o['fails']) or 'pass']) + ' |')
    os.makedirs(OUT + '/gates', exist_ok=True)
    for gid, Rw in per.items():
        npass = sum(1 for r in Rw if r.endswith('| pass |'))
        open(f'{OUT}/gates/gate_{gid}.md', 'w').write('\n'.join([f'# Gate, {common.gun(gid)["name"]}: {npass} of {len(Rw)} clips pass', '', '| ' + ' | '.join(H) + ' |', '|' + '---|' * len(H)] + Rw) + '\n')
        print(gid, npass, 'of', len(Rw), 'pass')


def magsets():
    sys.path.insert(0, common.mp('C:/Modding/anim-work/smg-shotgun/production/tools/anim')); import rmagset2
    dd = renv.OUT + '/magsets'; os.makedirs(dd, exist_ok=True); rp = f'{dd}/magsets_front.json'; rep = json.load(open(rp)) if os.path.exists(rp) else {}
    for gid in GUNS:
        if gid == 'guillotine': continue        # no magazine anim set in the game files
        gun = common.gun(gid); van, wpn, mesh = gungeo.wanim(gun, 'mag_std'), gungeo.wanim(gun, 'base1'), common.find('weapon_meshes', gun['mesh'] + '__mag_std_01.glb')
        if 'mag_slot' not in Glb(wpn).names: wpn = gungeo.wanim(gun, 'rcv1')
        for body in BODIES:
            for side in SIDES:
                items = []
                for clip in CLIPS:
                    for k, p in enumerate(SLOTS):
                        base = f'{OUT}/{body}/{stem(gid, side, p, clip)}'; spec = json.load(open(base + '.json'))
                        items.append((base + '_track.json', clip if k == 0 else f'{clip}_0{k}', spec['_keys'], spec['_part_frames']))
                out = f'{dd}/{gid}__smgmag_{body}_{side}.glb'; r, _ = rmagset2.build(van, wpn, mesh, out, items); chk = rmagset2.check(out, wpn, mesh, items)
                rep[os.path.basename(out)] = {'slots': r, 'check': chk}; print(out, 'worst rebuilt mesh error', max(x['worst_cm'] for x in chk), 'cm', flush=True)
    json.dump(rep, open(rp, 'w'), indent=1)


def regress():
    """Right hand, male V, empty reload of the Saratoga and the Zhuo against the reviewed drafts."""
    D = common.mp('C:/Modding/anim-work/smg-shotgun'); out = []
    for (gid, pick), rnd in REVIEWED.items():
        a = f'{OUT}/pma/{stem(gid, "right", pick, "empty_reload")}'; b = f'{D}/{rnd}/clips/pma/{gid}_right_{pick}{GUNS[gid]}_empty_reload'
        if not (os.path.exists(a + '.glb') and os.path.exists(b + '.glb')): continue
        ga, gb = Glb(a + '.glb'), Glb(b + '.glb'); ca, cb = Clip(ga, 'reload_draft'), Clip(gb, 'reload_draft'); N = json.load(open(b + '.json'))['frames']
        names = [n for n in gb.names if n and (n.startswith('Right') or n.startswith('Left') or n.startswith('Weapon')) and 'Leg' not in n]
        dj = max(float(np.linalg.norm(np.array(ca.world(f)[ga.names.index(n)][0]) - np.array(cb.world(f)[gb.names.index(n)][0]))) for f in range(N) for n in names) * 100
        ta, tb = json.load(open(a + '_track.json')), json.load(open(b + '_track.json'))
        dm = max(float(np.abs(np.array(ra['m']) - np.array(rb['m'])).max()) for ra, rb in zip(ta['frames'], tb['frames']))
        s = f'{gid} {pick}: worst joint difference {dj:.4f} cm; worst track matrix element difference {dm:.6f}'; print(s); out.append(s)
    open(renv.OUT + '/work/regress_front.txt', 'w').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None; cmd = argv[0] if argv else 'list'
    if cmd == 'events':
        for g in GUNS:
            for cl in CLIPS: print(g, cl, gun_events(g, cl))
    elif cmd == 'list':
        for p in plan(): print(*p)
    elif cmd == 'build':
        for p in plan(cs(o('--guns')), cs(o('--picks')), cs(o('--clips')), cs(o('--sides')), cs(o('--bodies'))): build(*p)
    elif cmd == 'all':
        import time
        jobs = int(o('--jobs') or 3); todo = list(GUNS); procs = []
        while todo or procs:
            while todo and len(procs) < jobs:
                g = todo.pop(0); lg = open(f'{renv.OUT}/work/build_front_{g}.log', 'w'); procs.append((g, subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), 'build', '--guns', g], stdout=lg, stderr=subprocess.STDOUT)))
            for g, p in list(procs):
                if p.poll() is not None: print(g, 'exit', p.returncode, flush=True); procs.remove((g, p))
            time.sleep(2)
    elif cmd == 'layout': layout()
    elif cmd == 'magsets': magsets()
    elif cmd == 'regress': regress()
    else: raise SystemExit(__doc__)
