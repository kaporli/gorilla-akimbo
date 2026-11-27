"""SMG and shotgun FRONT family, round 2: ten wind-up chop variations (SF11 to SF20), each in two takes: A snappy on
the Saratoga, B heavy on the Zhuo. Right hand, male V, empty reload. Owner feedback on round 1: SF09 wind-up chop by
far the best; magazine flight did not match the force; lengths ranged from SMG-quick to LMG-slow.

usage: sf2.py list | budget | build [ids csv] [--takes A,B] [--jobs n] | stats [ids] | round1
Output: <OUT>/clips/pma/<gun>_right_<id><take>_empty_reload.glb, .json (spec), _track.json, _gate.json

One timing budget per take, the same for all ten drafts (BUDGET): opener on the cocking frame, wind-up, one strike
along the well that stops dead, the magazine released on the strike's fastest frame, two still frames, dive to the
rig, slam onto the fresh magazine (seat), rise, rack on the home frame, settle. Take B is the same beat layout
13 % longer. The gun's own part frames (cocking back, magazine out, clamp, seat, cocking home) are mapped onto the
budget piecewise linearly (part_frames); the previews pose the gun parts from that map. In game the gun's own anim
would need the same remap (unverified, a production step).

Magazine: 'inertia' only. Seated up to the release frame, then free with the velocity and spin of its centre over
the last frame (no push, a 2 deg/frame tumble), gravity 9.81 m/s2 at 30 fps, no drag, gone at the ground (8 cm).
The release frame is the strike's fastest frame for the magazine (peak_mag): the gun brakes after it, so the
magazine leaves at the strike's full speed. Gate additions: mag_speed (exit speed against the gun's speed over the 3
frames up to the release, ratio 0.85 to 1.15) and gone height (the old magazine reaches the ground before the
fresh one exists).
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, rlib2, magtrack2, magtrack3, prod, rgate, timing, gungeo
from rlib import K
from glb import Glb
from fk import Clip, qrot
from wclip import TClip, FPS

OUT = renv.OUT
CLIP = 'empty_reload'
GUNS = {'A': 'saratoga', 'B': 'zhuo'}
# the timing budget (frames at 30 fps); 'stop' is the strike's dead stop, the release is its fastest frame (1 or 2 earlier)
BUDGET = {'A': {'cock': 6, 'stop': 20, 'seat': 38, 'home': 54, 'frames': 72},
          'B': {'cock': 7, 'stop': 23, 'seat': 43, 'home': 61, 'frames': 81}}
TAKES = {'A': dict(prod.TAKES['A']), 'B': dict(prod.TAKES['B'], w=1.13)}
GUN_EV = {'saratoga': {'cock': 7, 'out': 27, 'seated': 46, 'home': 69, 'frames': 88},     # sf1.events (round 1)
          'zhuo': {'cock': 8, 'clamp_open': 9, 'out': 21, 'clamp_shut': 77, 'seated': 80, 'home': 91, 'frames': 121}}
PUNCH = prod.PUNCH
L = prod.L
ST = {'thigh': ((0.29, 0.10, -0.035), (-78, -10, 10)), 'rear': ((0.31, 0.15, 0.07), (-100, -12, 10)),
      'belt_front': ((0.24, 0.15, -0.10), (-55, 0, 6))}
prod.STATION.update({k: v for k, v in ST.items() if k not in prod.STATION})
STN_LONG = {'stomach': 'stomach_m'}       # Zhuo: the long stock goes into the torso block at the stomach rig
MAG_RATIO = (0.85, 1.15)


def take_of(gid): return 'A' if gid == 'saratoga' else 'B'


def part_frames(take, release):
    """Gun anim frame per budget frame: piecewise linear through (0, 0), (cock), (release, magazine out), (seat,
    seated), (home, home), then the gun's own pace to the end."""
    gid = GUNS[take]; B = BUDGET[take]; G = GUN_EV[gid]
    xs = [0, B['cock'], release, B['seat'], B['home'], B['frames'] - 1]; ys = [0, G['cock'], G['out'], G['seated'], G['home'], G['home'] + B['frames'] - 1 - B['home']]
    return [round(float(np.interp(f, xs, ys)), 2) for f in range(B['frames'])]


def setup(gid):
    """Budget frames into the timing table every tool reads (timing.table cache); Saratoga well axis from the
    magazine mesh (as round 1)."""
    T = timing.table(gid, CLIP)
    if T.get('_sf2'): return T
    B = BUDGET[take_of(gid)]; T['frames'] = B['frames']; T['seated'] = B['seat']; T['handle'] = [B['home'], B['home']]; T['budget'] = B; T['gun_events'] = GUN_EV[gid]; T['_sf2'] = True
    v = magtrack2.vanilla(gid, CLIP)
    if gid == 'saratoga':
        V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb')); P = (np.c_[V, np.ones(len(V))] @ v['seat'].T)[:, :3]
        ax = np.linalg.svd(P - P.mean(0), full_matrices=False)[2][0]; ax = ax * (-1 if ax[1] > 0 else 1); ax[0] = 0; ax /= np.linalg.norm(ax)
        v['exit'] = ax; v['enter'] = -ax
    return T


class TL(rlib2.TL):
    def to(self, f, *a, **k):
        if int(f) <= self.f: raise ValueError(f'move to f{f} from f{self.f}')
        return super().to(f, *a, **k)


def bud(c): return c.T['budget']
def long_gun(c): return c.gun == 'zhuo'
def exw(c, rot): return c.along(rot, c.v['exit'], 1.0)
def mag_point(c): return (c.v['seat'] @ np.r_[c.v['centre'], 1])[:3]


def aligned(c, p0, r0, re, lam):
    """End of a move from (p0, r0) to angles re so that the magazine centre travels along the well's exit axis at the
    end (the translation cancels the sideways part of the rotation's arc)."""
    m = mag_point(c); r0, re = np.array(r0, float), np.array(re, float); dl = 0.02
    w = lambda r: qrot(author.qmul(c.q0, author.qeuler(*r)), m)
    return np.array(p0, float) + exw(c, re) * lam - (w(re) - w(re - dl * (re - r0))) / dl


def mag_centres(c, tl, f0, f1):
    cen = mag_point(c)
    return np.array([c.g0 + tl.P[f] + qrot(author.qmul(c.q0, author.qeuler(*tl.R[f])), cen) for f in range(f0, f1 + 1)])


def peak_mag(c, tl, f0, f1):
    """Frame in f0..f1 at which the seated magazine's centre moves fastest: released there, it leaves at the
    strike's full speed while the gun brakes."""
    sp = np.linalg.norm(np.diff(mag_centres(c, tl, f0 - 1, f1), axis=0), axis=1)
    return f0 + int(np.argmax(sp))


OPEN = {'tug': (((0, 0, -0.012), (1, 0, 0)), ((0, 0.004, 0.03), (-1, 0, 0)), ((0, 0, -0.008), (1.5, 0, 0))),
        'tip': (((0, -0.006, 0), (-4, 0, 0)), ((0, 0.01, 0.006), (12, 0, -2)), ((0, -0.004, 0), (-3, 0, 0)))}


def opener(c, tl, kind):
    """On the cocking frame: pulled back and stopped dead (tug) or the muzzle snapped up and stopped (tip): the
    cocking piece runs on back."""
    P = c.P; k = P['k']; f = bud(c)['cock']; (cp, cr), (tp, tr), (kp, kr) = OPEN[kind]
    tl.hold(1); tl.to(f - 3, cp, cr, 'ease'); tl.to(f, tp, tr, 'drive', rlag=0)
    tl.kick(f, np.array(kp) * k, np.array(kr) * k, attack=0.5, release=2.5); tl.mark('cock', f)


def strike(c, tl, stop, srot, drop, wrot, ns=4, nw=7, wprof='rise'):
    """The reference move (round 1 SF09): wound up to the point `drop` metres back up the well from the stop (angles
    wrot), one beat at the top, then one decisive strike along the well onto the stop (angles srot) that stops dead
    on the budget's stop frame. Returns the release frame (fastest frame of the magazine)."""
    P = c.P; k = P['k']; s = bud(c)['stop']; ns = L(P, ns); nw = L(P, nw); a = s - ns - 1
    wpos = np.array(stop, float) - exw(c, srot) * drop
    tl.hold(a - nw); tl.to(a, wpos, wrot, wprof, antic=P['a'] * 0.5)
    tl.hold(a + 1); end = aligned(c, wpos, wrot, srot, drop); tl.to(s, end, srot, 'slam', rlag=0)
    tl.kick(s, -exw(c, srot) * 0.012 * k, (0.5 * k, 0, 0), attack=0.5, release=2.5); tl.nodrag.append((a, s + 1))
    r = peak_mag(c, tl, a + 2, s); tl.mark('release', r); tl.mark('stop', s); tl.mark('windup', a)
    return r


def seat_block(c, tl, pos, rot, arrive, se, d=0.12, slam=5, reb=0.012):
    P = c.P; pre = np.array(pos) + c.along(rot, c.v['enter'], d); rl = P['lag'] + (3 if long_gun(c) else 0)
    tl.to(arrive, pre, rot, 'drive', rlag=rl); tl.kick(arrive + (rl if long_gun(c) else 0), c.along(rot, c.v['enter'], -0.006), (-2, 0, 0), release=2.5)
    tl.hold(se - slam); tl.to(se, pos, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], reb * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=3.0)
    tl.mark('arrive', arrive)


def to_rig(c, tl, station, d=0.12):
    """Two still frames after the stop (the empty gun in view, the magazine flying), dive to the rig, slam onto the
    fresh magazine on the seat frame."""
    P = c.P; s = bud(c)['stop']; se = bud(c)['seat']; name = STN_LONG.get(station, station) if long_gun(c) else station
    pos, rot = c.station(name); tl.hold(s + 2); arr = min(s + 2 + L(P, 9), se - 6)
    seat_block(c, tl, pos, rot, arr, se, d=d)
    if long_gun(c): tl.mark('clamp', se)
    return arr


def rack(c, tl, kind):
    """Rise from the rig into a held pose, then the hit on the home frame h (the cocking piece runs home):
      punch  cocked back, punched forward, dead stop on h        yank   held out, a sharp start back on h
      nod    muzzle high, thrown down, dead stop on h             upper  cocked low, a rising punch, dead stop on h
      thumb  held ready; the thumb drops the cocking piece on h and the gun jolts"""
    P = c.P; k = P['k']; se = bud(c)['seat']; h = bud(c)['home']; tl.hold(se + 2)
    def rise_to(f, pos, rot):
        tl.hold(f - 3 - L(P, 8)); tl.to(f - 3, P.get('rise', (0.03, -0.10 if long_gun(c) else -0.085, -0.07 if long_gun(c) else -0.045)), P.get('rise_rot', (-9, 0, -3)), 'rise', rlag=P.get('rise_rlag'), rprof=P.get('rise_rprof'))   # production: rise_rot, rise_rlag, rise_rprof (Dian: the long stock rose past the face)
        if P.get('rack_held'): tl.to(f, pos, rot, 'settle'); tl.kick(f, (0, 0.005 * k, -0.002), (-1.5, 0, 0), release=2.5)   # production: the line below, active (NOTES.md: what the rack would look like); off by default, as reviewed
        # Zhuo: further forward, the long stock stays off the face; tl.to(f, pos, rot, 'settle'); tl.kick(f, (0, 0.005 * k, -0.002), (-1.5, 0, 0), release=2.5)
    if kind == 'punch':
        rise_to(h - 4, (0.012, -0.03, 0.035), (0, 0, -4)); tl.hold(h - 3)
        tl.to(h, (0, 0.01, -0.06), (1, 0, 0), PUNCH, rlag=0); tl.kick(h, (0, 0.004, 0.018 * k), (5 * k, 0, 0), attack=0.5, release=2.5); end = h
    elif kind == 'yank':
        rise_to(h - 2, (0.01, -0.045, -0.06), (-5, 0, -3)); tl.hold(h)
        tl.to(h + 3, (0.0, -0.03, 0.012), (3, 0, -2), (1.25, 2.6), rlag=0); tl.kick(h, (0, 0.002, 0.012 * k), (-2.5 * k, 0, 0), attack=0.5, release=2.0)
        tl.kick(h + 3, (0, -0.002, -0.006 * k), (1.5, 0, 0), attack=0.5, release=2.5); end = h + 3
    elif kind == 'nod':
        rise_to(h - 4, (0.0, 0.0, -0.03), (12, 0, -2)); tl.hold(h - 3)
        tl.to(h, (0.0, -0.03, -0.045), (-9, 0, -2), PUNCH, rlag=0); tl.kick(h, (0, 0.006 * k, 0), (4 * k, 0, 0), attack=0.5, release=2.5); end = h
    elif kind == 'upper':
        rise_to(h - 4, (0.012, -0.065, 0.0), (-11, 0, -4)); tl.hold(h - 3)
        tl.to(h, (0.0, 0.03, -0.05), (5, 0, 0), PUNCH, rlag=0); tl.kick(h, (0, -0.006, 0.014 * k), (4 * k, 0, 0), attack=0.5, release=2.5); end = h
    elif kind == 'thumb':
        rise_to(h - 2, (0.004, -0.012, -0.03), (2, 0, -3)); tl.hold(h)
        tl.kick(h, (0, 0.006 * k, 0.012 * k), (-3 * k, 0, 1), attack=0.5, release=2.5); end = h
    else: raise ValueError(kind)
    tl.mark('hit', h); tl.hold(end + 3 + (1 if P['w'] > 1 else 0)); e = min(end + 3 + L(P, 9), c.N - 5)   # the settle kick dies out before the last frame
    tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.004), (-1.5, 0, 0), release=3.0)


# ------------------------------------------------------------------------------------------------ drafts
# Each draft: opener, strike(stop, strike angles, drop along the well, wind-up angles), rig, rack. Angles (pitch,
# yaw, roll): roll + puts the gun on its left side (the well faces right, out), roll - on its right side (in).
def gen(opn, stop, srot, drop, wrot, rig, rk, ns=4, nw=7):
    def f(c, tl):
        P = c.P; S = P.get('strike', {})
        opener(c, tl, opn)
        r = strike(c, tl, S.get('stop', stop), S.get('srot', srot), S.get('drop', drop), S.get('wrot', wrot), S.get('ns', ns), S.get('nw', nw))
        arr = to_rig(c, tl, P.get('rig', rig)); rack(c, tl, rk)
        return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.0, 'tumble': 2, 'appear': arr + 2, 'seated': bud(c)['seat'], 'floor': 0.08}}
    return f


DRAFTS = {
    'SF11': ('Wind-up chop', 'tug', (0.0, -0.03, 0.02), (-6, 0, 0), 0.22, (18, 0, -3), 'belt', 'upper',
             'Round 1 SF09 rebuilt to the budget. The gun is lifted with the muzzle up, one beat, then chopped down along the well and stopped dead in front of the chest: the magazine flies on straight down at the chop\'s speed. Belt rig; a rising punch stops dead on the home frame.'),
    'SF12': ('High chop', 'tip', (0.12, 0.07, 0.0), (-4, -8, 6), 0.16, (24, -6, 2), 'hip', 'nod',
             'Wound up high beside the head, muzzle up, and chopped down to shoulder height out to the right, dead stop: the magazine falls through the whole right side of the view. Hip rig; held muzzle-high, the muzzle is thrown down on the home frame.'),
    'SF13': ('Low chop', 'tug', (0.02, -0.17, 0.04), (-8, 0, 2), 0.24, (14, 0, -2), 'thigh', 'punch',
             'A short wind-up at chest height, then a long chop down to the bottom edge of the view, dead stop: the magazine is driven out fast and drops past the thigh. Thigh rig; cocked back and punched forward on the home frame.'),
    'SF14': ('Cant-out chop', 'tip', (0.12, -0.06, 0.0), (-4, -4, 36), 0.18, (16, -4, 28), 'belt_wide', 'yank',
             'Wound up canted onto its left side so the well faces down and out, then chopped diagonally down and out to arm\'s length, dead stop: the magazine flies out to the right and falls outside the leg. Wide belt rig; held out in front and yanked back on the home frame.'),
    'SF15': ('Cant-in chop', 'tug', (-0.05, -0.08, 0.02), (-4, 4, -30), 0.15, (14, 4, -24), 'stomach', 'thumb',
             'Wound up canted onto its right side so the well faces down and in, then chopped diagonally down toward the belly, dead stop: the magazine is driven out between the guns. Stomach rig; held ready, the thumb drops the cocking piece and the gun jolts on the home frame.'),
    'SF16': ('Cross-body slash', 'tip', (0.10, -0.07, 0.0), (-6, -10, 40), 0.28, (18, 16, 18), 'hip', 'punch',
             'Drawn across the chest toward the left shoulder, muzzle up, then slashed down and out to the right along the well like drawing a blade, dead stop: the magazine flies off down and out. Hip rig; punched forward on the home frame.'),
    'SF17': ('Out-front chop', 'tug', (0.0, -0.08, -0.03), (-10, 0, 0), 0.16, (16, 0, -2), 'belt_front', 'nod',
             'The arm pushed out in front with the muzzle up, then chopped down at arm\'s length, dead stop: the magazine leaves ahead of the gun and falls in front. Front belt rig; the muzzle is thrown down on the home frame.'),
    'SF18': ('Wrist chop', 'tip', (0.0, -0.02, 0.0), (-14, 0, 0), 0.08, (26, 0, -2), 'belt', 'yank',
             'No arm wind-up: the wrist cocks the muzzle up and snaps it down with a short forearm chop, dead stop. Less force, so the magazine leaves slower and drops close in front of the hand. Belt rig; yanked back on the home frame.'),
    'SF19': ('Twist chop', 'tug', (0.0, -0.04, 0.01), (-6, 0, 0), 0.17, (16, -4, 42), 'belt_wide', 'thumb',
             'Wound up canted out on its left side, then chopped down while rolling back upright, dead stop: the magazine leaves with the roll\'s spin and tumbles as it falls. Wide belt rig; the thumb drops the cocking piece on the home frame.'),
    'SF20': ('Hip-back chop', 'tip', (0.10, -0.15, 0.08), (-22, -6, 16), 0.18, (8, -4, 10), 'rear', 'upper',
             'Wound up at chest height, then chopped down and back toward the hip with the muzzle dipped, dead stop: the magazine flies down and back past the outside of the leg. Rear pouch; a rising punch from low on the home frame.'),
}
PICKS = {k: (v[0], gen(*v[1:8])) for k, v in DRAFTS.items()}
DOC = {k: v[8] for k, v in DRAFTS.items()}
PARAMS = {'SF11B': {'strike': {'wrot': (8, 0, -3), 'drop': 0.22, 'stop': (0.0, -0.12, -0.05)}},
          # Zhuo: the long stock came within 17.6 to 19.3 cm of the eye at the wind-up or after the stop: lower and further forward
          'SF15B': {'strike': {'stop': (-0.04, -0.12, -0.05)}}, 'SF16B': {'strike': {'drop': 0.22, 'wrot': (12, 14, 18), 'stop': (0.10, -0.10, -0.03)}},
          'SF18B': {'strike': {'stop': (0.0, -0.06, -0.03), 'drop': 0.09, 'wrot': (20, 0, -2)}}, 'SF19B': {'strike': {'stop': (0.0, -0.10, -0.04), 'wrot': (8, -4, 42)}},
          'SF20B': {'rig': 'hip'}}   # SF20B: the rear pouch brought the long stock up past the face on the rise (eye 18.2 to 19.4 cm)


def stem(pick, take, side='right'): return prod.stem(GUNS[take], pick, take, CLIP, side)


def elbow_step(spec):
    S = spec['_side']; g = Glb(spec['out']); c = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}; prev = None; worst = 0.0
    for f in range(spec['frames']):
        W = c.world(f); s, e, h = (np.array(W[ix[S + n]][0]) for n in ('Arm', 'ForeArm', 'Hand')); ax = (h - s) / np.linalg.norm(h - s)
        p = (e - s) - ((e - s) @ ax) * ax; p /= (np.linalg.norm(p) or 1)
        if prev is not None: worst = max(worst, float(np.degrees(np.arccos(np.clip(p @ prev, -1, 1)))))
        prev = p
    return round(worst, 1)


def mag_speed(gid, track, G):
    """Exit speed of the released magazine (world, cm/f, gravity's share of the first free step taken off) against
    the gun's speed at the magazine seat over the 3 frames up to the release; their ratio."""
    v = magtrack2.vanilla(gid, CLIP); cen = np.r_[v['centre'], 1]; S = v['seat']; r = track['release']
    C = [(magtrack2.m4(*G[f]) @ S @ cen)[:3] for f in range(r - 3, r + 1)]
    gun = max(float(np.linalg.norm(C[i + 1] - C[i])) for i in range(3)) * 100
    M0 = magtrack2.m4(*G[r]) @ np.array(track['frames'][r]['m']).reshape(4, 4) @ cen; M1 = magtrack2.m4(*G[r + 1]) @ np.array(track['frames'][r + 1]['m']).reshape(4, 4) @ cen
    ex = float(np.linalg.norm(M1[:3] - M0[:3] - np.array([0, -magtrack2.G_ACC, 0]))) * 100
    ratio = ex / gun if gun > 1e-6 else 0.0
    return {'exit_cm_f': round(ex, 2), 'gun_cm_f': round(gun, 2), 'ratio': round(ratio, 2), 'ok': MAG_RATIO[0] <= ratio <= MAG_RATIO[1]}


def gone_height(gid, track, G):
    """Height (m) the old magazine would have on the frame after its last drawn one (its fall continued): at or
    below the ground (0.08) when it was removed because it landed, above it when it was cut off in mid-air."""
    v = magtrack2.vanilla(gid, CLIP); cen = np.r_[v['centre'], 1]
    fr = [f for f, row in enumerate(track['frames']) if row['state'] in ('falling', 'guided', 'loose') and row['s'] > 0.5]
    if len(fr) < 2: return None
    y = [float((magtrack2.m4(*G[f]) @ np.array(track['frames'][f]['m']).reshape(4, 4) @ cen)[1]) for f in fr[-2:]]
    return round(y[1] + (y[1] - y[0]) - magtrack2.G_ACC, 3)


def build(pick, take, side='right', body='pma', out=None, quiet=False):
    gid = GUNS[take]; setup(gid); out = out or OUT + '/clips'; d = f'{out}/{body}'; os.makedirs(d, exist_ok=True); name = stem(pick, take, side)
    S = side.capitalize(); P = dict(TAKES[take]); P.update(PARAMS.get(pick + take, {})); c = prod.Ctx(gid, body, CLIP, P, S); tl = TL(c, P['lag'], P['drag'])
    m = PICKS[pick][1](c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    pf = part_frames(take, m['mag']['release'])
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {take}', '_doc': DOC[pick], '_gun': gid, '_left_gun': gid, '_body': body, '_side': S,
            '_gun_clip': CLIP, '_pick': pick, '_take': take, '_timing': c.T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False, '_round': 'smg-front-2',
            '_part_frames': pf, 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, ('Left' if S == 'Right' else 'Right'): [K(0)]},
            'shakes': {S: kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); G = [(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(c.N))]
    track = magtrack3.build(gid, CLIP, G, m['mag']); spec['_track'] = f'{d}/{name}_track.json'
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); o['elbow_step_deg'] = elbow_step(spec)
    o['mag_speed'] = mag_speed(gid, track, G); o['mag_gone_height_m'] = gone_height(gid, track, G)
    if not o['mag_speed']['ok']: o['fails'].append(f"magazine speed {o['mag_speed']['exit_cm_f']} cm/f against the gun's {o['mag_speed']['gun_cm_f']} (ratio {o['mag_speed']['ratio']})")
    if o['mag_gone_height_m'] is not None and o['mag_gone_height_m'] > 0.09: o['fails'].append(f"old magazine removed {o['mag_gone_height_m']} m above the ground")
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, rgate.line(o), '| elbow', o['elbow_step_deg'], '| magv', o['mag_speed'], 'gone', o['mag_gone_height_m'], '| exit', o.get('mag_exit'), flush=True)
    return spec, o


def stats(ids):
    import motionstats
    rows = []; J = json.load(open(OUT + '/ref/motion_all.json')); rows += [(k, v) for k, v in J.items() if k.startswith('APPROVED')]
    for p in ids:
        for t in ('A', 'B'):
            g = f'{OUT}/clips/pma/{stem(p, t)}.glb'
            if os.path.exists(g): rows.append((f'{p}{t} {PICKS[p][0]} ({GUNS[t]})', motionstats.stats(g, 'reload_draft', 'Right', 0.55 if t == 'A' else 0.6)))
    Tb = ['| clip | frames | peak cm/f | peak at | stop | jerks | still | whip | muzzle peak | big moves |', '|---|---|---|---|---|---|---|---|---|---|']
    for lab, s in rows: Tb.append(f"| {lab} | {s['frames']} | {s['peak_speed']} | {s['peak_at']} | {s['stop']} | {s['jerk_events']} | {int(s['hold_share'] * 100)} % | {s['whip']} | {s['peak_muzzle_speed']} | {s['big_moves']} |")
    os.makedirs(OUT + '/measure', exist_ok=True); open(OUT + '/measure/motion_round2.md', 'w').write('\n'.join(Tb) + '\n'); print('\n'.join(Tb))
    json.dump({l: s for l, s in rows}, open(OUT + '/measure/motion_round2.json', 'w')); motionstats.plot(rows, OUT + '/measure/motion_round2.png')


def round1():
    """Why round 1's magazines looked slow: per take the magazine mode, the exit speed against the gun's speed over
    the 3 frames up to the release (same measure as the round 2 gate), the removal height, the clip length."""
    R1 = common.mp('C:/Modding/anim-work/smg-shotgun/round1-front/clips/pma'); rows = ['| take | frames | mode | release | magazine exit cm/f | gun cm/f (3 f before) | ratio | removed at m |', '|---|---|---|---|---|---|---|---|']
    import glob
    for p in sorted(glob.glob(R1 + '/*_empty_reload.json')):
        s = json.load(open(p)); tr = json.load(open(s['_track'])); gid = s['_gun']
        g = Glb(s['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('WeaponRight'); G = [(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(s['frames']))]
        r = tr['release']; mode = tr['plan']['mode']
        if mode == 'throw': tr = dict(tr, release=tr['free_from'] - 1)      # speed where the guided slide hands over to free flight
        ms = mag_speed(gid, tr, G) if mode != 'hook' else {'exit_cm_f': '-', 'gun_cm_f': '-', 'ratio': '-'}
        rows.append(f"| {s['_pick']}{s['_take']} | {s['frames']} | {mode} | f{r} | {ms['exit_cm_f']} | {ms['gun_cm_f']} | {ms['ratio']} | {gone_height(gid, tr, G)} |")
    os.makedirs(OUT + '/measure', exist_ok=True); open(OUT + '/measure/round1_magazine_speed.md', 'w').write('\n'.join(rows) + '\n'); print('\n'.join(rows))


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'
    takes = (o('--takes') or 'A,B').split(','); jobs = int(o('--jobs') or 1)
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(PICKS)
    if cmd == 'list':
        for p, (n, fn) in PICKS.items(): print(p, n, '|', DOC[p])
    elif cmd == 'budget':
        for t in 'AB': print(t, GUNS[t], BUDGET[t])
    elif cmd == 'build':
        todo = [(p, t) for p in ids for t in takes]
        if jobs > 1:
            procs = [subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), '_part', json.dumps(todo[k::jobs])]) for k in range(jobs) if todo[k::jobs]]
            for p in procs: p.wait()
        else:
            for t in todo: build(*t)
    elif cmd == '_part':
        for t in json.loads(argv[1]): build(*t)
    elif cmd == 'stats': stats(ids)
    elif cmd == 'round1':
        for gid in GUNS.values(): setup(gid)
        round1()
    else: raise SystemExit(__doc__)
