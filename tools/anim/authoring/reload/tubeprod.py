"""Production of the owner's TUBE picks (PICKS.md, 2026-11-14): TU01 throw and meet, TU10 saddle flick, TU02 belt-row
sweep (round 1, tube1.py, take A, 76 frames) on the Carnage and the Tactician; right and left hand, male and female
V; shell objects, gate numbers, layout.

What production adds to the reviewed generator (Carnage, right hand, male V only):
  gun      the gun's own shell and pump geometry (<OUT>/ref/<gun>_geometry.json, tubegeo.py: the method that
           reproduces round 1's Carnage file exactly; Tactician: chamber = its empty reload's last shell pose f60,
           tube = reload f20, port = reload f14, fore-end `foreend`, 9.0 cm stroke)
  side     left: authored in the mirror image (prod.Ctx), keys mirrored back; the side saddle on the gun's outer
           side; rigs mirror; the ejector still throws to the gun's own right (mesh not mirrored)
  clip     one clip serves reload and empty reload (as the rifles' Hercules): every pick cycles the pump, and
           TU10 catches its shell in the open ejection port, which needs the pump open. Layout lists both slots.
Checks added: end transition into the idle; spent shell against the other gun (nearest distance).

usage: tubeprod.py list | build [--guns a,b] [--picks ..] [--sides ..] [--bodies ..] | layout | regress
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, prod, rgate, timing, magtrack2, phys, rarmset, rchecks, gungeo
import inertia_r1 as inertia      # the spring model (spring, report, END); inertia.py is the round 4 simulation
import tube1
from rlib import K
from glb import Glb
from fk import Clip

OUT = renv.OUT + '/clips'
GUNS = ['carnage', 'tactician']
SLOTS = ['TU01', 'TU10', 'TU02']
SIDES = ('right', 'left'); BODIES = ('pma', 'pwa'); CLIP = 'empty_reload'
MIR = np.array([-1.0, 1.0, 1.0])
SADDLE_OFF = np.array([0.045, -0.055, 0.03])
PARAMS = {          # (pick, gun[, body or side]) -> parameter changes
    ('TU02', 'tactician', 'left'): {'tipdown': 28}}      # left gun: the settle after the 36 deg tip-down brought the receiver to 19.3 cm (limit 19.3, idle 20.3)
STATE = {'real': False}


def stem(gid, side, pick): return f'{gid}_{side}_{pick}A_{CLIP}'


def use_gun(gid):
    """tube1's module geometry for this gun."""
    G = json.load(open(f'{renv.OUT}/ref/{gid}_geometry.json')); tube1.GID = gid; tube1.GEO = G
    tube1.CH, tube1.PORT, tube1.TUBEP = (np.array(G[k]) for k in ('chamber', 'port', 'tube')); tube1.SC = np.array(G['shell_centre'])
    tube1.PUMP_P = np.array(G['pump_point']); tube1.PUMP_MAX = float(G.get('pump_max', 0.085)); tube1.PUMP_CURVE = np.array(G['pump_curve'])
    tube1.SHELL_MESH = common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb')
    tube1.SADDLE = tube1.CH.copy(); tube1.SADDLE[:3, 3] += SADDLE_OFF


def saddle(side_real):
    S = tube1.CH.copy(); S[:3, 3] += SADDLE_OFF * (MIR if side_real == 'Left' else 1); return S


# female V: rig this much lower (y, m): her forearm stayed on screen at the belt and hip rigs (hidden window 11 f, rule 12); as the rifles' belt
PWA_DROP = {'belt': -0.05, 'hip': -0.025}      # belt: 2.5 cm still left TU01 (Carnage) hidden 11 f
_station = tube1.station
def _station_side(c, name):
    """tube1.station with the female drop; while the real-world shell tracks of a left-hand clip are computed,
    mirrored back."""
    p, h = _station(c, name); p = p + np.array([0, PWA_DROP.get(name, 0.0) if c.body == 'pwa' else 0.0, 0])
    return (p * MIR, h) if STATE['real'] and c.side == 'Left' else (p, h)
tube1.station = _station_side


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


def shells_vs_other(gid, objs, GO):
    """Nearest distance (cm) of every shell to the other gun's surface points, over the frames it exists."""
    V = gungeo.verts(tube1.SHELL_MESH)[::3]; V1 = np.c_[V, np.ones(len(V))]; PG = rchecks.gun_points(gid, 4000); out = {}
    for name, W in objs:
        d = 9e9
        for f, M in enumerate(W):
            if M is None: continue
            P = (V1 @ M.T)[:, :3]; b = rchecks.place(GO[f], PG)[::3]; d = min(d, float(np.sqrt(((P[:, None] - b[None]) ** 2).sum(2)).min()) * 100)
        out[name] = round(d, 1)
    return out


def build(gid, pick, side, body, quiet=False, extra=None):
    use_gun(gid); T = tube1.setup(); S = side.capitalize(); O = 'Left' if S == 'Right' else 'Right'; d = f'{OUT}/{body}'; os.makedirs(d, exist_ok=True); name = stem(gid, side, pick)
    P = dict(prod.TAKES['A'], drag=0.0, lag=0); P.update(PARAMS.get((pick, gid), {})); P.update(PARAMS.get((pick, gid, body), {})); P.update(PARAMS.get((pick, gid, side), {})); P.update(extra or {})
    c = prod.Ctx(gid, body, CLIP, P, S); c.side = S; tl = tube1.TL(c, 0, 0.0); STATE['real'] = False; tube1.SADDLE = saddle('Right')     # authoring: right-hand image
    plan = tube1.PICKS[pick][1](c, tl)
    Pt, Rt = tl.P.copy(), tl.R.copy(); Pt[-1] = 0; Rt[-1] = 0; Ps, Rs = inertia.spring(Pt, Rt, 'A'); rep = inertia.report(Ps, Rs, Pt, Rt, tl.stops)
    if S == 'Left': Ps = Ps * prod.MIR_P; Rs = Rs * prod.MIR_R
    keys = [K(f, Ps[f], Rs[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    spec = {'_draft': name, '_name': f'{tube1.PICKS[pick][0]}, take A', '_doc': tube1.DOC[pick], '_gun': gid, '_left_gun': gid, '_body': body, '_side': S,
            '_gun_clip': CLIP, '_serves': ['reload', 'empty_reload'], '_pick': pick, '_take': 'A', '_timing': T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_two_arm': False,
            '_round': 'tube-production', '_geometry': f'{renv.OUT}/ref/{gid}_geometry.json', 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N,
            'keys': {S: keys, O: [K(0)]}, 'shakes': {S: []}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb', '_inertia': rep}
    spec['_loads'] = [{'kind': ld[0], 'frame': int(ld[1] if ld[0] == 'sweep' else ld[2]), 'into': 'chamber' if ld[0] == 'saddle' else 'tube'} for ld in plan['loads']]      # frame each fresh shell goes in
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); W = [cl.world(f) for f in range(c.N)]; i, io = g.names.index('Weapon' + S), g.names.index('Weapon' + O)
    G = [(np.array(W[f][i][0]), np.array(W[f][i][1])) for f in range(c.N)]; GO = [(np.array(W[f][io][0]), np.array(W[f][io][1])) for f in range(c.N)]; GW = phys.worlds(G)
    tube1.SADDLE = saddle(S); STATE['real'] = True                       # real world from here on
    sad = next((ld for ld in plan['loads'] if ld[0] == 'saddle'), None)
    if sad is not None and extra is None:      # catch where the built clip throws it (tube1.build's second pass), mirrored into the authoring image
        SD = tube1.SADDLE; SC = tube1.SC
        a0, a1, fc = getattr(tube1, 'SADDLE_WIN', (12, 21, 25))      # window searched for the saddle's fastest frame, catch frame
        cs = [(GW[f] @ SD @ np.r_[SC, 1])[:3] for f in range(a0, a1)]; sp = [np.linalg.norm(cs[k + 1] - cs[k]) for k in range(len(cs) - 1)]; fr = a0 + 1 + int(np.argmax(sp))
        p1 = (GW[fr] @ SD @ np.r_[SC, 1])[:3]; v = p1 - (GW[fr - 1] @ SD @ np.r_[SC, 1])[:3]; n = fc - fr; pc = p1 + v * n + np.array([0, -phys.G_ACC, 0]) * n * (n + 1) / 2
        if S == 'Left': pc = pc * MIR
        STATE['real'] = False; return build(gid, pick, side, body, quiet, {'catch_pc': [float(x) for x in pc], 'release_f': fr})
    drives = plan.get('pump', {}).get('drives', []); PU = tube1.PUMP_U; PM = tube1.PUMP_MAX
    s, hit = phys.slider(GW, tube1.PUMP_P, PU, PM, drives=drives, lock_home_after=tube1.BUDGET['seat'], rest=0.1)
    if hit is not None:
        rack0 = int(tl.marks.get('rack_start', tube1.BUDGET['seat'] + 6)); s, hit = phys.slider(GW, tube1.PUMP_P, PU, PM, drives=drives, locks=[(hit, rack0, PM)], lock_home_after=rack0, rest=0.1)      # round 2: the stop catches it on the hit frame (was hit + 1: a bounce, then set back to the stop)
    s = np.where(np.arange(c.N) > c.N - 4, 0.0, s)
    objs, info = tube1.shell_tracks(c, GW, plan, s, hit); STATE['real'] = False
    spec['_first_load'] = int(plan['loads'][0][2] if plan['loads'][0][0] not in ('sweep', 'saddle') else plan['loads'][0][1]); spec['_part_frames'] = tube1.pump_frames(s); spec['_pump_cm'] = [round(float(x) * 100, 2) for x in s]
    inv = [np.linalg.inv(M) for M in GW]; J = {'joints': {}, 'names': []}
    for nm, Wo in objs: J['names'].append(nm); J['joints'][nm] = [None if M is None else [round(float(x), 6) for x in (inv[f] @ M).ravel()] for f, M in enumerate(Wo)]
    spec['_objects'] = f'{d}/{name}_objects.json'; json.dump(J, open(spec['_objects'], 'w'))
    CH = tube1.CH; dummy = {'frames': [{'m': [round(float(x), 6) for x in CH.ravel()], 's': 0.0, 'state': 'seated'}] * c.N, 'release': 1, 'free_from': 2, 'gone': c.N, 'exit_gun_axes': [0, 1, 0], 'enter_gun_axes': [0, -1, 0], 'plan': {'mode': 'none'}, 'clip': CLIP}
    spec['_track'] = f'{d}/{name}_track.json'; json.dump(dummy, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, dummy); f2, seen = tube1.obj_checks(c, spec, GW, objs, o['layout']); o['fails'] += f2; o['shells_seen'] = seen; o['shells'] = info
    opened = next((f for f in range(c.N) if s[f] >= PM - 0.002), None); home = next((f for f in range(tube1.BUDGET['seat'], c.N) if s[f] <= 0.002), None)
    o['pump'] = {'open_frame': opened, 'home_frame': home, 'max_cm': round(float(s.max()) * 100, 2)}
    if opened is None: o['fails'].append('pump never opens')
    if home is None or home > c.N - 6: o['fails'].append('pump never closes')
    if info.get('spent_release') is None: o['fails'].append('spent shell never leaves')
    elif info.get('spent_land') is None: o['fails'].append('spent shell does not land')
    if 'saddle' in info and info['saddle']['catch_error_cm'] > 1.5: o['fails'].append(f"saddle shell caught {info['saddle']['catch_error_cm']} cm off the port")
    o['shells_to_other_gun_cm'] = so = shells_vs_other(gid, objs, GO)
    if min(so.values()) < 0.5: o['fails'].append(f'a shell touches the other gun ({so})')
    o['elbow_step_deg'] = prod_elbow(spec)
    if o['elbow_step_deg'] > 45: o['fails'].append(f"elbow swings {o['elbow_step_deg']} deg in one frame")
    o['end_transition'] = et = end_transition(spec)
    if et['last3_step_cm'] > 0.5 or et['last_vs_idle_cm'] > 0.02 or et['last_vs_idle_deg'] > 0.02: o['fails'].append(f'end transition {et}')
    o['inertia'] = rep; kn = rarmset.good_keys(c.N); o['layout']['keys'] = kn; pad(spec['out'], 'reload_draft', kn); spec['_keys'] = kn
    json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1); json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, side, name, '| fails', o['fails'], '| pump', o['pump'], '| spent', info.get('spent_release'), info.get('spent_land'), '| eye', o['eye_cm'], 'reach', o['reach'], 'sh', o['shoulder_pull_cm'],
                        'wrist', o['wrist'][0], o['wrist_view'], 'body', o['body_cm'], 'gap', o['guns_gap_cm'], 'hide', o['layout']['hide_start'], o['layout']['hide_end'], '| other', so, flush=True)
    return spec, o


def prod_elbow(spec):
    S = spec['_side']; g = Glb(spec['out']); c = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}; prev = None; worst = 0.0
    for f in range(spec['frames']):
        W = c.world(f); s, e, h = (np.array(W[ix[S + n]][0]) for n in ('Arm', 'ForeArm', 'Hand')); ax = (h - s) / np.linalg.norm(h - s)
        p = (e - s) - ((e - s) @ ax) * ax; p /= (np.linalg.norm(p) or 1)
        if prev is not None: worst = max(worst, float(np.degrees(np.arccos(np.clip(p @ prev, -1, 1)))))
        prev = p
    return round(worst, 1)


def plan(guns=None, picks=None, sides=None, bodies=None):
    return [(g, p, s, b) for g in GUNS if not guns or g in guns for p in SLOTS if not picks or p in picks for b in (bodies or BODIES) for s in (sides or SIDES)]


def layout():
    lay = {}; fails = []; rows = []
    for gid, pick, side, body in plan():
        p = f'{OUT}/{body}/{stem(gid, side, pick)}_gate.json'
        if not os.path.exists(p): fails.append(f'missing {p}'); continue
        o = json.load(open(p)); Lr = dict(o['layout']); rows.append((gid, pick, side, body, o))
        e = lay.setdefault(gid, {}).setdefault(pick + 'A', {}).setdefault(CLIP, dict(Lr, per_clip={}))
        e['per_clip'][f'{body}_{side}'] = [Lr['hide_start'], Lr['hide_end']]
        ld = json.load(open(p[:-10] + '.json')).get('_loads', []); fr = [x['frame'] for x in ld]
        e.setdefault('loads', fr); e.setdefault('load_kinds', [x['kind'] for x in ld]); e['chamber'] = next((k for k, x in enumerate(ld) if x['into'] == 'chamber'), -1)
        if e['loads'] != fr: fails.append(f'{gid} {pick}: loads differ between clips ({e["loads"]} / {fr} {body} {side})')
        if Lr['hide_start'] is None or e['hide_start'] is None: e['hide_start'] = e['hide_end'] = None
        else: e['hide_start'] = max(e['hide_start'], Lr['hide_start']); e['hide_end'] = min(e['hide_end'], Lr['hide_end'])
        if o['fails']: fails.append(f"{body} {o['clip']}: {o['fails']}")
    for gid in lay:
        for pk in lay[gid]:
            i = SLOTS.index(pk[:-1]); e = lay[gid][pk][CLIP]; e['slot'] = CLIP if i == 0 else f'{CLIP}_0{i}'
            r = dict(e, slot='reload' if i == 0 else f'reload_0{i}', same_clip_as='empty_reload'); lay[gid][pk]['reload'] = r
            if e['hide_start'] is not None and e['hide_end'] - e['hide_start'] + 1 < 12: fails.append(f'{gid} {pk}: shared hidden window only {e["hide_end"] - e["hide_start"] + 1} f')
    json.dump(lay, open(f'{OUT}/layout_tube.json', 'w'), indent=1)
    Ls = ['| gun | pick | clip | slot | hide_start | hide_end | loads | chamber | first shell | seated | handle | length | keys |', '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for gid in lay:
        for pk in lay[gid]:
            for clip, e in lay[gid][pk].items(): Ls.append(f"| {gid} | {pk} | {clip} | {e['slot']} | {e['hide_start']} | {e['hide_end']} | {e.get('loads')} | {e.get('chamber')} | {e['mag_out']} | {e['seated']} | {e['handle']} | {e['length']} | {e['keys']} |")
    open(f'{OUT}/layout_tube.md', 'w').write('\n'.join(Ls) + '\n'); open(f'{OUT}/gate_fails_tube.txt', 'w').write('\n'.join(fails) + '\n')
    H = ['clip', 'body', 'side', 'hidden', 'eye cm', 'cover %', 'wrist / in view', 'reach', 'shoulder cm', 'body cm', 'guns gap cm', 'start / end cm', 'end step', 'end transition (cm, deg)',
         'pump open / home', 'spent shell out / lands', 'shells to other gun cm (min)', 'overshoot cm / deg', 'elbow step', 'peak / stop', 'fails']
    per = {}
    for gid, pick, side, body, o in rows:
        L = o['layout']; et = o['end_transition']; m = o['motion']; I = o['inertia']
        per.setdefault(gid, []).append('| ' + ' | '.join(str(x) for x in [f'{pick}A', body, side, f"f{L['hide_start']}-{L['hide_end']} ({o['hidden_frames']})", o['eye_cm'][0], o['cover_peak'][0],
            f"{o['wrist'][0]} / {o['wrist_view']}", o['reach'][0], o['shoulder_pull_cm'], o['body_cm'][0], o['guns_gap_cm'][0], f"{o['start_cm']:.3f} / {o['end_cm']:.3f}", o['end_step_cm'],
            f"{et['last3_step_cm']}, {et['last3_step_deg']}", f"f{o['pump']['open_frame']} / f{o['pump']['home_frame']}", f"f{o['shells'].get('spent_release')} / f{o['shells'].get('spent_land')}",
            min(o['shells_to_other_gun_cm'].values()), f"{I['max_overshoot_cm']} / {I['max_overshoot_deg']}", o['elbow_step_deg'], f"{m['peak_speed']} / {m['stop']}", '; '.join(o['fails']) or 'pass']) + ' |')
    os.makedirs(OUT + '/gates', exist_ok=True)
    for gid, Rw in per.items():
        npass = sum(1 for r in Rw if r.endswith('| pass |'))
        open(f'{OUT}/gates/gate_{gid}.md', 'w').write('\n'.join([f'# Gate, {common.gun(gid)["name"]}: {npass} of {len(Rw)} clips pass (each clip serves reload and empty reload)', '', '| ' + ' | '.join(H) + ' |', '|' + '---|' * len(H)] + Rw) + '\n')
        print(gid, npass, 'of', len(Rw), 'pass')
    print('\n'.join(Ls)); print(len(fails), 'failures or missing')


def regress():
    D = common.mp('C:/Modding/anim-work/smg-shotgun'); out = []
    for pick in SLOTS:
        a = f'{OUT}/pma/{stem("carnage", "right", pick)}'; b = f'{D}/round1-tube/clips/pma/carnage_right_{pick}A_empty_reload'
        if not os.path.exists(a + '.glb'): continue
        ga, gb = Glb(a + '.glb'), Glb(b + '.glb'); ca, cb = Clip(ga, 'reload_draft'), Clip(gb, 'reload_draft'); N = json.load(open(b + '.json'))['frames']
        names = [n for n in gb.names if n and (n.startswith('Right') or n == 'WeaponRight') and 'Leg' not in n]
        dj = max(float(np.linalg.norm(np.array(ca.world(f)[ga.names.index(n)][0]) - np.array(cb.world(f)[gb.names.index(n)][0]))) for f in range(N) for n in names) * 100
        oa, ob = json.load(open(a + '_objects.json')), json.load(open(b + '_objects.json')); dm = 0.0
        for nm in ob['names']:
            for x, y in zip(oa['joints'][nm], ob['joints'][nm]):
                if x is not None and y is not None: dm = max(dm, float(np.abs(np.array(x) - np.array(y)).max()))
        s = f'carnage {pick}: worst joint difference {dj:.4f} cm; worst shell matrix element difference {dm:.6f}'; print(s); out.append(s)
    open(renv.OUT + '/work/regress_tube.txt', 'w').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None; cmd = argv[0] if argv else 'list'
    if cmd == 'list':
        for p in plan(): print(*p)
    elif cmd == 'build':
        for p in plan(cs(o('--guns')), cs(o('--picks')), cs(o('--sides')), cs(o('--bodies'))): build(*p)
    elif cmd == 'layout': layout()
    elif cmd == 'regress': regress()
    else: raise SystemExit(__doc__)
