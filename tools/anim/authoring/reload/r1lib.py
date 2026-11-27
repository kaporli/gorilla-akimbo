"""SMG round 1, GRIP / BULLPUP / TOP families: shared engine of the one-handed reload drafts (after sf1.py, FRONT).

Owner feedback on FRONT round 1, built in here:
  one timing budget per take: every draft of a family has the same length and beats (BEATS); take B is 13.2 %
  slower than take A; never the game clip's own length. The gun's own anims (moving parts) are time-mapped onto the
  beats (gun_map): its magazine-out frame lands on the release, its seat on the seat, its handle on the hit.
  magazine speed from the force: every draft releases on the dead stop of one chop along the well (SF09 wind-up
  chop); the magazine keeps the velocity and spin the gun had on that frame (magtrack3 'inertia'), then free fall
  at 9.81 m/s2; speed_check() compares its exit speed with the gun's speed over the 3 frames before the release.
  the old magazine falls to the ground even after the fresh one exists (two meshes: track rows m2, s2).

Beats (frames, 30 fps), take A (B in brackets):
  cue 6 (7)      opener: a short snap, stops dead (the thumb on the release; Warden: its latch opens here)
  wind 7-13 (8-15)  wind-up, then still
  chop 14-18 (16-21)  one chop along the well, dead stop on the release frame: the magazine flies on
  dep 21 (24)    leaves for the station; arr 30 (34) at the station, still; slam 33-38 (37-43): seated
  rise 39-50 (44-57)  up into a held pose; hit 53 (61): the rack's dead stop (or the yank's sharp start)
  back 57-65 (65-74)  settle into the idle; N 68 (77) frames, take B 13.2 % longer
"""
import os, sys, json, math, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, rlib2, magtrack2, prod, rgate, timing, gungeo
from rlib import K
from glb import Glb
from fk import Clip, qrot
from magtrack2 import m4, rot_axis, log_rot, G_ACC

OUT = renv.OUT
CLIP = 'empty_reload'
PUNCH = prod.PUNCH
BEATS = {'A': {'N': 68, 'cue': 6, 'wind': 7, 'top': 13, 'chop': 14, 'rel': 18, 'dep': 21, 'arr': 30, 'slam': 33, 'seat': 38, 'rise': 39, 'mid': 47, 'held': 50, 'hit': 53, 'back': 57, 'idle': 65},
         'B': {'N': 77, 'cue': 7, 'wind': 8, 'top': 15, 'chop': 16, 'rel': 21, 'dep': 24, 'arr': 34, 'slam': 37, 'seat': 43, 'rise': 44, 'mid': 53, 'held': 57, 'hit': 61, 'back': 65, 'idle': 74}}
SPEED_MIN, SPEED_MAX = 0.85, 1.15  # magazine exit speed / the gun's speed on the release frame (FRONT round 2 rule)


# ------------------------------------------------------------------------------------------------ gun events
def part_window(gid, part):
    T = timing.table(gid, CLIP); return T['parts'].get(part, {}).get('window')


def gun_events(gid):
    """The gun's own frames (its anim sets): out, seated, handle start, a part that opens before the release (latch)."""
    T = timing.table(gid, CLIP); ev = {'frames': T['frames'], 'out': T['out'], 'seated': T['seated'], 'handle': None, 'latch': None, 'handle_part': None}
    if gid == 'warden':
        ev['seated'] = 77            # magpath takes the reset old magazine; the fresh one (magazine_reload) is in at f64, rocked home f77 as the latch shuts (phase 1)
        w = part_window(gid, 'magazine_open'); ev['latch'] = w[0] if w else None      # production: the reload clip has no latch anim
    late = [(n, p['window']) for n, p in T['parts'].items() if p['window'][0] >= ev['seated']]
    if late: n, w = min(late, key=lambda x: x[1][0]); ev['handle'] = w[0]; ev['handle_part'] = n
    return ev


def gun_map(gid, take):
    """Gun anim frame for each draft frame: piecewise linear through the anchors (cue -> latch, rel -> out,
    seat -> seated, hit -> handle, end -> end)."""
    B = BEATS[take]; ev = gun_events(gid); A = [(0, 0)]
    if ev['latch']: A.append((B['cue'], ev['latch']))
    A += [(B['rel'], ev['out']), (B['seat'], ev['seated'])]
    if ev['handle']: A.append((B['hit'], ev['handle']))
    A.append((B['N'] - 1, ev['frames'] - 1))
    xs, ys = zip(*A)
    return [round(float(np.interp(f, xs, ys)), 3) for f in range(B['N'])], A


def table(gid, take):
    """timing.table of the gun with the beats in place of its own frames (what prod.Ctx, rgate read)."""
    B = BEATS[take]; T = copy.deepcopy(timing.table(gid, CLIP)); ev = gun_events(gid); mp, A = gun_map(gid, take)
    inv = lambda g: int(round(float(np.interp(g, [a[1] for a in A], [a[0] for a in A]))))
    T.update({'frames': B['N'], 'out': B['rel'], 'seated': B['seat'], 'handle': [B['hit'], B['hit']] if ev['handle'] else None, 'beats': B, 'gun_events': ev, 'gun_anchors': A})
    for p in T['parts'].values(): p['gun_window'] = p['window']; p['window'] = [inv(p['window'][0]), inv(p['window'][1])]
    return T


# ------------------------------------------------------------------------------------------------ context
class TL(rlib2.TL):
    """rlib2.TL that refuses a move that does not move forward in time (it would jump)."""
    def to(self, f, *a, **k):
        if int(f) <= self.f: raise ValueError(f'move to f{f} from f{self.f}')
        return super().to(f, *a, **k)


def ctx(gid, take, P, axes):
    c = prod.Ctx(gid, 'pma', CLIP, P, 'Right'); c.T = table(gid, take); c.N = c.T['frames']; c.B = c.T['beats']; c.take = take
    c.v = dict(c.v); c.v.update({k: np.array(v, float) / np.linalg.norm(v) for k, v in axes.items()})
    return c


def exw(c, rot): return c.along(rot, c.v['exit'], 1.0)


def mag_point(c): return (c.v['seat'] @ np.r_[c.v['centre'], 1])[:3]


def aligned(c, p0, r0, re, lam):
    """End position of a move from (p0, r0) to angles re such that the magazine centre travels along the well's
    exit axis on the stop frame (sf1.aligned)."""
    m = c.ax(mag_point(c)); r0, re = np.array(r0, float), np.array(re, float); dl = 0.02
    w = lambda r: qrot(author.qmul(c.q0, author.qeuler(*r)), m)
    return np.array(p0, float) + exw(c, re) * lam - (w(re) - w(re - dl * (re - r0))) / dl


# ------------------------------------------------------------------------------------------------ beats
# openers on the cue frame: (counter pose, pose on the frame, rebound kick)
OPEN = {'tug': (((0, 0, -0.012), (1, 0, 0)), ((0, 0.004, 0.03), (-1, 0, 0)), ((0, 0, -0.008), (1.5, 0, 0))),
        'tip': (((0, -0.006, 0), (-4, 0, 0)), ((0, 0.01, 0.006), (12, 0, -2)), ((0, -0.004, 0), (-3, 0, 0))),
        'snap': (((0, -0.004, -0.006), (-2, 0, 0)), ((0, 0.006, 0.018), (7, 0, -1)), ((0, -0.002, -0.005), (-2, 0, 0))),
        'press': (((0, 0.004, 0), (2, 0, 0)), ((0, -0.008, 0.004), (-6, 0, 2)), ((0, 0.003, 0), (2, 0, 0)))}


def opener(c, tl, kind):
    k = c.P['k']; f = c.B['cue']; (cp, cr), (tp, tr), (kp, kr) = OPEN[kind]
    tl.hold(1); tl.to(f - 3, cp, cr, 'ease'); tl.to(f, tp, tr, 'drive', rlag=0)
    tl.kick(f, np.array(kp) * k, np.array(kr) * k, attack=0.5, release=2.5); tl.mark('cue', f)


def chop(c, tl, stop, srot, wrot, drop, via=None, wprof='rise', kick_rot=(0.5, 0, 0)):
    """Wind-up into (stop - exit * drop, wrot) by the top beat, still, then one chop that ends on the release frame in
    (stop', srot) with the magazine centre travelling along the exit axis (aligned): dead stop, the magazine flies on.
    Returns the wind-up position."""
    P = c.P; k = P['k']; B = c.B; r = B['rel']; stop = np.array(stop, float) + np.array(c.P.get('lift', (0, 0, 0)))   # lift: family offset of every stop (in view)
    wu = stop - c.along(srot, c.v['exit'], drop)
    if via is None: tl.hold(B['wind']); tl.to(B['top'], wu, wrot, wprof, antic=P['a'] * 0.5)
    else: tl.hold(B['wind']); prod.arc(tl, B['top'], via, wu, wrot, wprof)
    tl.hold(B['chop'])
    end = aligned(c, wu, wrot, srot, drop); tl.to(r, end, srot, 'slam', rlag=0)
    tl.kick(r, -c.along(srot, c.v['exit'], 0.012 * k), np.array(kick_rot) * k, attack=0.5, release=2.5)
    tl.mark('wind', B['top']); tl.mark('release', r); tl.nodrag.append((B['chop'], r + 1))
    return wu


def seat(c, tl, station, d=0.12, reb=0.012, via=None):
    """Hold after the chop, leave on dep, at the station (pre-position along the well) on arr, still, slam onto the
    fresh magazine on the seat beat."""
    P = c.P; B = c.B; pos, rot = c.station(station); pre = np.array(pos) + c.along(rot, c.v['enter'], d); rl = P['lag'] + 1
    tl.hold(B['dep'])
    if via is None: tl.to(B['arr'], pre, rot, 'snap', rlag=rl)      # no anticipation: the chop's rebound is the start, 9 frames of travel
    else: prod.arc(tl, B['arr'], via, pre, rot, 'heavy', rlag=rl)
    tl.kick(B['arr'] + rl, c.along(rot, c.v['enter'], -0.006), (-2, 0, 0), release=2.5)
    tl.hold(B['slam']); tl.to(B['seat'], pos, rot, 'slam', rlag=0)
    tl.kick(B['seat'], c.along(rot, c.v['enter'], reb * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=3.0)
    tl.mark('arrive', B['arr']); tl.mark('seat', B['seat'])
    return pos, rot


def rack(c, tl, kind):
    """After the seat: up into a held pose (rise .. held), then the rack on the hit beat, settle into the idle.
      punch  cocked back, punched forward, dead stop on hit
      yank   held out in front, a sharp start back on hit, stop 3 frames later
      nod    held muzzle-high, the muzzle thrown down and stopped dead on hit
      upper  cocked low and back, a rising punch forward that stops dead on hit"""
    P = c.P; k = P['k']; B = c.B; h = B['hit']
    held = {'punch': ((0.012, -0.03, 0.035), (0, 0, -4)), 'yank': ((0.01, -0.045, -0.06), (-5, 0, -3)), 'nod': ((0.0, 0.0, -0.03), (12, 0, -2)),
            'upper': ((0.012, -0.065, 0.0), (-11, 0, -4))}[kind]
    tl.hold(B['rise']); mid = B['mid']
    tl.to(mid, (0.03, -0.085, -0.045), (-9, 0, -3), 'rise'); tl.to(B['held'], held[0], held[1], 'settle'); tl.kick(B['held'], (0, 0.005 * k, -0.002), (-1.5, 0, 0), release=2.5)
    if kind == 'yank':
        tl.hold(h); tl.to(h + 3, (0.0, -0.03, 0.012), (3, 0, -2), (1.25, 2.6), rlag=0); tl.kick(h, (0, 0.002, 0.012 * k), (-2.5 * k, 0, 0), attack=0.5, release=2.0)
        tl.kick(h + 3, (0, -0.002, -0.006 * k), (1.5, 0, 0), attack=0.5, release=2.5)
    else:
        tl.hold(h - 3)
        end = {'punch': ((0, 0.01, -0.06), (1, 0, 0), (0, 0.004, 0.018), (5, 0, 0)), 'nod': ((0.0, -0.03, -0.045), (-9, 0, -2), (0, 0.006, 0), (4, 0, 0)),
               'upper': ((0.0, 0.03, -0.05), (5, 0, 0), (0, -0.006, 0.014), (4, 0, 0))}[kind]
        tl.to(h, end[0], end[1], PUNCH, rlag=0); tl.kick(h, np.array(end[2]) * np.array([1, 1, k]), np.array(end[3]) * k, attack=0.5, release=2.5)
    tl.mark('hit', h); tl.hold(B['back']); tl.to(B['idle'], (0, 0, 0), (0, 0, 0), 'settle')


# ------------------------------------------------------------------------------------------------ magazine
def track(c, G, plan):
    """Own magazine track (magtrack3 'inertia' with two meshes). Seated up to the release frame, free from the next
    with the world velocity of its centre and the gun's spin over the last frame (plus push along the well and a
    little tumble), free fall to the ground (floor); the fresh one exists, world-fixed, from appear (the gun's seat
    there on the seated frame). Rows: m, s, state of the main mesh (old, then fresh, then seated); m2, s2 the old
    magazine while it still falls after the fresh one exists."""
    v = c.v; S = v['seat']; cen = np.r_[v['centre'], 1]; N = len(G); ex = np.array(v['exit'], float)
    GW = [m4(t, q) for t, q in G]; r = int(plan['release']); appear = int(plan['appear']); seated = int(plan['seated']); floor = plan.get('floor', 0.08)
    loosen = sorted(plan.get('loosen', [])); pre = lambda f: max([0.0] + [d for lf, d in loosen if f >= lf])
    T = lambda d: np.block([[np.eye(3), np.asarray(d, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
    Wm = {f: GW[f] @ T(ex * pre(f)) @ S for f in range(0, r + 1)}
    a, b = Wm[r - 1], Wm[r]
    vel = (b @ cen)[:3] - (a @ cen)[:3] + GW[r][:3, :3] @ ex * plan.get('push', 0.004)
    om = log_rot(b[:3, :3] @ a[:3, :3].T) + GW[r][:3, :3] @ np.array([math.radians(plan.get('tumble', 3)), 0, 0])
    p = (b @ cen)[:3]; R = b[:3, :3]; gone = None; f = r
    while f < N - 1:
        f += 1; vel = vel + np.array([0, -G_ACC, 0]); p = p + vel; R = rot_axis(om, np.linalg.norm(om)) @ R
        if p[1] < floor: gone = f; break
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = p - R @ cen[:3]; Wm[f] = M
    gone = gone or N; appear = min(appear, seated - 6); fresh = GW[seated] @ S; out = []
    rnd = lambda M: [round(float(x), 6) for x in M.ravel()]
    for f in range(N):
        old = f in Wm and f < gone
        if f < appear:
            row = {'m': rnd(np.linalg.inv(GW[f]) @ Wm[f]), 's': 1.0, 'state': ('seated' if pre(f) == 0 else 'loose') if f <= r else 'falling'} if old else {'m': rnd(S), 's': 0.0, 'state': 'gone'}
        else:
            row = {'m': rnd(np.linalg.inv(GW[f]) @ fresh if f < seated else S), 's': 1.0, 'state': 'fresh' if f < seated else 'seated'}
            if old and f > r: row.update({'m2': rnd(np.linalg.inv(GW[f]) @ Wm[f]), 's2': 1.0})
        out.append(row)
    return {'gun': c.gun, 'clip': CLIP, 'plan': plan, 'release': r, 'free_from': r + 1, 'gone': gone, 'frames': out,
            'exit_gun_axes': [round(float(x), 3) for x in ex], 'enter_gun_axes': [round(float(x), 3) for x in v['enter']]}


def exit_check(c, trk):
    """magtrack3.exit_check with this draft's axes: sideways offset from the well axis while the leaving magazine is
    within 10 cm of its seat, and how far it went back into the gun."""
    v = c.v; cen = np.r_[v['centre'], 1]; S = v['seat']; ex = np.array(trk['exit_gun_axes'], float); r = trk['release']; worst = 0.0; n = 0; back = 0.0
    for f in range(r + 1, len(trk['frames'])):
        row = trk['frames'][f]; M = row.get('m2') if row['state'] in ('fresh', 'seated') else row['m']
        if M is None or row['state'] == 'gone': break
        dv = (np.array(M).reshape(4, 4) @ cen)[:3] - (S @ cen)[:3]; al = float(dv @ ex); d = float(np.linalg.norm(dv))
        if d > 0.10:
            if n == 0: worst = max(worst, float(np.linalg.norm(dv - al * ex)) / d * 0.10); back = min(back, al / d * 0.10)
            break
        worst = max(worst, float(np.linalg.norm(dv - al * ex))); back = min(back, al); n += 1
    return {'off_axis_cm': round(worst * 100, 2), 'frames_to_10cm': n, 'into_gun_cm': round(-back * 100, 2)}


def speed_check(c, G, trk):
    """Magazine exit speed against the gun. FRONT round 2 metric (the rule): the magazine's velocity on leaving
    (first free frame, gravity's first frame taken off) against the gun's speed at the magazine on the release frame
    (r-1 to r); ratio 0.85 to 1.15. Also the gun's mean speed over the 3 frames before the release (information:
    a chop accelerates, so that mean is lower than the release-frame speed)."""
    v = c.v; cen = np.r_[v['centre'], 1]; r = trk['release']; GW = [m4(t, q) for t, q in G]
    Cg = lambda f: (GW[f] @ np.array(trk['frames'][f]['m']).reshape(4, 4) @ cen)[:3]     # attached (seated or loosened) up to the release
    row = trk['frames'][r + 1]; M = np.array(row.get('m2') if 'm2' in row else row['m']).reshape(4, 4)
    vm = (GW[r + 1] @ M @ cen)[:3] - Cg(r) - np.array([0, -G_ACC, 0]); mag = float(np.linalg.norm(vm)) * 100
    rel = float(np.linalg.norm(Cg(r) - Cg(r - 1))) * 100; gun3 = float(np.linalg.norm(Cg(r) - Cg(r - 3))) / 3 * 100
    ratio = mag / max(rel, 1e-6)
    return {'mag_cm_f': round(mag, 1), 'gun_rel_cm_f': round(rel, 1), 'ratio': round(ratio, 2), 'gun3_cm_f': round(gun3, 1), 'mag_m_s': round(mag * 0.3, 2),
            'ok': bool(SPEED_MIN <= ratio <= SPEED_MAX)}


def view_frames(c, G, trk):
    """Frames after the release in which the old magazine is still on the first-person screen (SF09A: 3)."""
    import rchecks
    V = gungeo.verts(common.find('weapon_meshes', common.gun(c.gun)['mesh'] + '__mag_std_01.glb'))[::5]; V1 = np.c_[V, np.ones(len(V))]; r = trk['release']; seen = 0
    for f in range(r + 1, len(trk['frames'])):
        row = trk['frames'][f]; M = row.get('m2') if 'm2' in row else (row['m'] if row['state'] == 'falling' else None)
        if M is None: break
        if rchecks.screen(rchecks.place(G[f], (V1 @ np.array(M).reshape(4, 4).T)[:, :3]))[2].any(): seen = f - r
    return seen


# ------------------------------------------------------------------------------------------------ build
def elbow_step(spec):
    S = spec['_side']; g = Glb(spec['out']); cl = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}; prev = None; worst = 0.0
    for f in range(spec['frames']):
        W = cl.world(f); s, e, h = (np.array(W[ix[S + n]][0]) for n in ('Arm', 'ForeArm', 'Hand')); ax = (h - s) / np.linalg.norm(h - s)
        p = (e - s) - ((e - s) @ ax) * ax; p /= (np.linalg.norm(p) or 1)
        if prev is not None: worst = max(worst, float(np.degrees(np.arccos(np.clip(p @ prev, -1, 1)))))
        prev = p
    return round(worst, 1)


def stem(F, pick): return f"{F.GUN}_right_{pick}{F.TAKE}_{CLIP}"


def build(F, pick, quiet=False):
    """F: the family module (GUN, TAKE, AXES, PICKS, PARAMS, STATIONS)."""
    prod.STATION.update(F.STATIONS); d = f'{OUT}/clips/pma'; os.makedirs(d, exist_ok=True); name = stem(F, pick)
    P = dict(prod.TAKES[F.TAKE]); P.update(F.PARAMS.get(pick, {})); ax = dict(F.AXES); ax.update(P.get('axes', {}))      # axes: a draft's own enter direction (TOP)
    c = ctx(F.GUN, F.TAKE, P, ax); tl = TL(c, P['lag'], P['drag'])
    fn = F.PICKS[pick][1]; m = fn(c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    gm, _ = gun_map(F.GUN, F.TAKE)
    spec = {'_draft': name, '_name': f'{F.PICKS[pick][0]}, take {F.TAKE}', '_doc': ' '.join((fn.__doc__ or '').split()), '_gun': F.GUN, '_left_gun': F.GUN, '_body': 'pma', '_side': 'Right',
            '_gun_clip': CLIP, '_pick': pick, '_take': F.TAKE, '_family': F.FAMILY, '_timing': c.T, '_gun_map': gm, '_axes': {k: [float(x) for x in v] for k, v in ax.items()},
            '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False, '_round': 'smg-' + F.FAMILY.lower() + '-1',
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {'Right': keys, 'Left': [K(0)]},
            'shakes': {'Right': kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('WeaponRight'); G = [cl.world(f)[i] for f in range(c.N)]
    GG = [(np.array(t), np.array(q)) for t, q in G]; trk = track(c, GG, m['mag'])
    spec['_track'] = f'{d}/{name}_track.json'
    json.dump(trk, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    magtrack2._van[(F.GUN, CLIP)] = c.v           # rgate reads the well axes of this family through magtrack2.vanilla
    o = rgate.gate(spec, trk); o['elbow_step_deg'] = elbow_step(spec)
    o['mag_exit'] = exit_check(c, trk)
    if o['mag_exit']['off_axis_cm'] > rgate.LIM['off_axis_max_cm'] or o['mag_exit']['into_gun_cm'] > 0.5: o['fails'].append(f"magazine leaves the well {o['mag_exit']['off_axis_cm']} cm off its axis")
    o['mag_speed'] = speed_check(c, GG, trk); rs = o['mag_speed']['ratio']
    if not o['mag_speed']['ok']: o['fails'].append(f"magazine speed {o['mag_speed']['mag_cm_f']} cm/f vs gun {o['mag_speed']['gun_rel_cm_f']} on the release frame (ratio {rs})")
    o['mag_view_frames'] = view_frames(c, GG, trk)
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(rgate.line(o), '| elbow', o['elbow_step_deg'], '| exit', o['mag_exit'], '| speed', o['mag_speed'], flush=True)
    return spec, o


def regate(F, pick):
    """Gate of a built draft again (glb and track as they are, no rebuild: the renders stay valid)."""
    prod.STATION.update(F.STATIONS); d = f'{OUT}/clips/pma'; name = stem(F, pick); spec = json.load(open(f'{d}/{name}.json')); trk = json.load(open(spec['_track']))
    P = dict(prod.TAKES[F.TAKE]); P.update(F.PARAMS.get(pick, {})); ax = dict(F.AXES); ax.update(P.get('axes', {})); c = ctx(F.GUN, F.TAKE, P, ax)
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('WeaponRight'); GG = [(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(c.N))]
    magtrack2._van[(F.GUN, CLIP)] = c.v
    o = rgate.gate(spec, trk); o['elbow_step_deg'] = elbow_step(spec); o['mag_exit'] = exit_check(c, trk)
    if o['mag_exit']['off_axis_cm'] > rgate.LIM['off_axis_max_cm'] or o['mag_exit']['into_gun_cm'] > 0.5: o['fails'].append(f"magazine leaves the well {o['mag_exit']['off_axis_cm']} cm off its axis")
    o['mag_speed'] = speed_check(c, GG, trk); rs = o['mag_speed']['ratio']
    if not o['mag_speed']['ok']: o['fails'].append(f"magazine speed {o['mag_speed']['mag_cm_f']} cm/f vs gun {o['mag_speed']['gun_rel_cm_f']} on the release frame (ratio {rs})")
    o['mag_view_frames'] = view_frames(c, GG, trk); json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    print(pick, 'speed', o['mag_speed'], 'seen', o['mag_view_frames'], 'fails', o['fails'], flush=True)


APPROVED = common.mp('C:/Modding/anim-work/smg-shotgun/round1-front/ref/motion_all.json')      # approved shipped clips (NAS round2/measure)


def stats(F, ids):
    import motionstats
    J = json.load(open(APPROVED)); rows = [(k, v) for k, v in J.items() if k.startswith('APPROVED')]
    sf = common.mp('C:/Modding/anim-work/smg-shotgun/round1-front/measure/motion_round1.json')
    if os.path.exists(sf): rows += [(k, v) for k, v in json.load(open(sf)).items() if k.startswith('SF09')]
    for p in ids:
        gp = f'{OUT}/clips/pma/{stem(F, p)}.glb'
        if os.path.exists(gp): rows.append((f'{p}{F.TAKE} {F.PICKS[p][0]} ({F.GUN})', motionstats.stats(gp, 'reload_draft', 'Right', 0.55 if F.TAKE == 'A' else 0.6)))
    Tb = ['| clip | peak cm/f | peak at | stop | jerks | still | whip | muzzle peak | big moves |', '|---|---|---|---|---|---|---|---|---|']
    for lab, s in rows: Tb.append(f"| {lab} | {s['peak_speed']} | {s['peak_at']} | {s['stop']} | {s['jerk_events']} | {int(s['hold_share'] * 100)} % | {s['whip']} | {s['peak_muzzle_speed']} | {s['big_moves']} |")
    os.makedirs(OUT + '/measure', exist_ok=True); open(OUT + '/measure/motion_round1.md', 'w').write('\n'.join(Tb) + '\n'); print('\n'.join(Tb))
    json.dump({l: s for l, s in rows}, open(OUT + '/measure/motion_round1.json', 'w')); motionstats.plot(rows, OUT + '/measure/motion_round1.png')


def gate_table(F, ids):
    Tb = ['| take | len | release | seat | hit | hidden | eye cm | cover % | wrist / in view | reach | shoulder | body | guns gap | end cm | end step | hang | dv | free exit off axis | into gun | mag / gun on release cm/f (ratio) | gun 3-frame mean | elbow step | magazine in view after release (f) | fails |',
          '|' + '---|' * 24]
    for p in ids:
        o = json.load(open(f'{OUT}/clips/pma/{stem(F, p)}_gate.json')); L = o['layout']; ms = o['mag_speed']; me = o['mag_exit']
        Tb.append(f"| {p}{F.TAKE} | {L['length']} | {L['mag_out']} | {L['seated']} | {L['handle']} | f{L['hide_start']}-{L['hide_end']} ({o['hidden_frames']}) | {o['eye_cm'][0]} | {o['cover_peak'][0]} | {o['wrist'][0]} / {o['wrist_view']} | {o['reach'][0]} | {o['shoulder_pull_cm']} | {o['body_cm'][0]} | {o['guns_gap_cm'][0]} | "
                  f"{max(o['start_cm'], o['end_cm']):.3f} | {o['end_step_cm']} | {o['mag_hang']} | {o['release_dv_cm_f']} | {me['off_axis_cm']} | {me['into_gun_cm']} | {ms['mag_cm_f']} / {ms['gun_rel_cm_f']} ({ms['ratio']}) | {ms['gun3_cm_f']} | {o['elbow_step_deg']} | {o['mag_view_frames']} | {'; '.join(o['fails']) or 'none'} |")
    open(OUT + '/measure/gate_round1.md', 'w').write('\n'.join(Tb) + '\n'); print('\n'.join(Tb))


def main(F, argv):
    import subprocess
    o = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'; jobs = int(o('--jobs') or 1)
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(F.PICKS)
    if cmd == 'list':
        for p, (n, fn) in F.PICKS.items(): print(p, n, '|', ' '.join((fn.__doc__ or '').split()))
    elif cmd == 'events': print(gun_events(F.GUN), gun_map(F.GUN, F.TAKE)[1], BEATS[F.TAKE])
    elif cmd == 'build':
        if jobs > 1:
            procs = [subprocess.Popen([sys.executable, '-B', F.__file__, '_part', ','.join(ids[k::jobs])]) for k in range(jobs) if ids[k::jobs]]
            for p in procs: p.wait()
        else:
            for p in ids: build(F, p)
    elif cmd == '_part':
        for p in argv[1].split(','): build(F, p)
    elif cmd == 'regate':
        for p in ids: regate(F, p)
    elif cmd == 'stats': stats(F, ids)
    elif cmd == 'gates': gate_table(F, ids)
    else: raise SystemExit(__doc__)
