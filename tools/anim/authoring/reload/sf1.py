"""SMG and shotgun FRONT family, round 1: ten one-handed reload drafts (SF01 to SF10), each in two takes:
A snappy on the Saratoga (light), B heavy on the Zhuo (heavy, wide clamped magazine). Right hand, male V,
empty reload. Built like the rifle production picks (prod.py context, takes, stations, seat block) with rlib2
timelines and an own magazine track (magtrack3: throw, hook, inertia).

usage: sf1.py list
       sf1.py events                          frames each gun gives the drafts (opener, release, seat, clamp, home)
       sf1.py build [ids csv] [--takes A,B] [--jobs n]
       sf1.py stats [ids csv]                 motionstats of every take beside the approved clips -> measure/
Output: <OUT>/clips/pma/<gun>_right_<id><take>_empty_reload.glb, .json (spec), _track.json, _gate.json

The gun's own frames (sf1.events, from its anim sets; 30 fps):
  cock     its cocking piece is pulled back (Saratoga cocking f6 to 8, Zhuo barrel_cocking f6 to 8): every draft
           opens with a small move that stops dead or starts sharply on this frame (the opener)
  out      the old magazine leaves (Saratoga f27, Zhuo f21): the release frame of the own magazine track
  seated   the fresh magazine is in (Saratoga f46, Zhuo f80); Zhuo's clamp closes f77 to 83 on the same slam
  home     the cocking piece runs home (Saratoga f69, Zhuo f90): the rack hit lands on this frame
  frames   the arm clip length (Saratoga 88, Zhuo 121: the Zhuo's arm set and base1 empty reload; its magazine
           anim is 86 and its receiver anim 96 frames long; phase 1 blocker, decided here as the arm length)
Well axis: Saratoga from the magazine mesh's long axis in the seat (the game's exit carries the left hand's pull
sideways); Zhuo the game's own (straight down).
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
ARM_LEN = {'saratoga': 88, 'zhuo': 121}          # arm set clip lengths (phase1 classify.md)
PUNCH = prod.PUNCH
L = prod.L
# stations (offset of the grip from the hips joint: x to the gun hand's side, y up, z back; search start angles):
# prod's plus the round 3 front ones
ST = {'thigh': ((0.29, 0.10, -0.035), (-78, -10, 10)), 'rear': ((0.31, 0.15, 0.07), (-100, -12, 10)),
      'belt_front': ((0.24, 0.15, -0.10), (-55, 0, 6))}
prod.STATION.update({k: v for k, v in ST.items() if k not in prod.STATION})


# ------------------------------------------------------------------------------------------------ gun events
def _curve(glb, clip, joint):
    g = Glb(glb); c = TClip(g, clip); i = g.names.index(joint); t0, r0 = c.local(i, 0.0); out = []
    for f in range(c.frames):
        t, r = c.local(i, f / FPS); out.append(max(float(np.linalg.norm(t - t0)) * 100, float(np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(r, r0)))))) / 10)))
    return np.array(out)


def events(gid):
    """The frames a draft has to fit, from the gun's own anim sets (see the module doc)."""
    T = timing.table(gid, CLIP); gun = common.gun(gid); b = gungeo.wanim(gun, 'base1')
    part = 'cocking' if gid == 'saratoga' else 'barrel_cocking'; d = _curve(b, CLIP, part); pk = d.max()
    cock = int(np.argmax(d >= 0.9 * pk)); home = next(f for f in range(T['seated'], len(d)) if d[f] <= 0.5 * pk)
    ev = {'frames': ARM_LEN[gid], 'cock': cock, 'out': T['out'], 'seated': T['seated'], 'home': home, 'part': part}
    if gid == 'zhuo':
        r = _curve(gungeo.wanim(gun, 'rcv1'), CLIP, 'l_mag_holder_01'); m = r.max()
        ev['clamp_open'] = int(np.argmax(r >= 0.9 * m)); ev['clamp_shut'] = next(f for f in range(ev['clamp_open'] + 5, len(r)) if r[f] <= 0.5 * m)
    return ev


def setup(gid):
    """Puts the events into the timing table every tool reads (timing.table cache) and the well axis into the
    magazine data (magtrack2.vanilla cache), so prod.Ctx, magtrack3 and rgate all see the same numbers."""
    T = timing.table(gid, CLIP)
    if T.get('_sf1'): return T
    ev = events(gid); T['frames'] = ev['frames']; T['handle'] = [ev['home'], ev['home']]; T['events'] = ev; T['_sf1'] = True
    v = magtrack2.vanilla(gid, CLIP)
    if gid == 'saratoga':
        V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb')); P = (np.c_[V, np.ones(len(V))] @ v['seat'].T)[:, :3]
        ax = np.linalg.svd(P - P.mean(0), full_matrices=False)[2][0]; ax = ax * (-1 if ax[1] > 0 else 1); ax[0] = 0; ax /= np.linalg.norm(ax)
        v['exit'] = ax; v['enter'] = -ax
    return T


# ------------------------------------------------------------------------------------------------ helpers
class TL(rlib2.TL):
    """rlib2.TL that refuses a move that does not move forward in time (it would jump)."""
    def to(self, f, *a, **k):
        if int(f) <= self.f: raise ValueError(f'move to f{f} from f{self.f}')
        return super().to(f, *a, **k)


def exw(c, rot): return c.along(rot, c.v['exit'], 1.0)


def mag_point(c): return (c.v['seat'] @ np.r_[c.v['centre'], 1])[:3]


def aligned(c, p0, r0, re, lam):
    """End position of a move from (p0, r0) to angles re such that the magazine centre travels along the well's
    exit axis on the stop frame (front3.aligned): the translation cancels the sideways part of the rotation's arc."""
    m = c.ax(mag_point(c)); r0, re = np.array(r0, float), np.array(re, float); dl = 0.02
    w = lambda r: qrot(author.qmul(c.q0, author.qeuler(*r)), m)
    return np.array(p0, float) + exw(c, re) * lam - (w(re) - w(re - dl * (re - r0))) / dl


def ev(c): return c.T['events']


def floor(c):
    """Height (m) at which the old magazine is gone (scale 0). Saratoga: 0.55, far below the first-person view (its
    lower edge is about 1.3 m high in front of the gun): the fresh magazine must exist 6 frames before the seat,
    19 frames after the release, and the preview draws one mesh for both. Zhuo: the ground (0.08)."""
    return c.P.get('floor', 0.08 if long_gun(c) else 0.55)


def long_gun(c): return c.gun == 'zhuo'


# openers on the cocking frame: (counter pose, pose on the frame, rebound kick). tug: pulled back and stopped dead,
# the cocking piece runs on back; tip: the muzzle snapped up and stopped (the top of the gun moves back);
# snap: both, small.
OPEN = {'tug': (((0, 0, -0.012), (1, 0, 0)), ((0, 0.004, 0.03), (-1, 0, 0)), ((0, 0, -0.008), (1.5, 0, 0))),
        'tip': (((0, -0.006, 0), (-4, 0, 0)), ((0, 0.01, 0.006), (12, 0, -2)), ((0, -0.004, 0), (-3, 0, 0))),
        'snap': (((0, -0.004, -0.006), (-2, 0, 0)), ((0, 0.006, 0.018), (7, 0, -1)), ((0, -0.002, -0.005), (-2, 0, 0)))}


def opener(c, tl, kind):
    P = c.P; k = P['k']; f = ev(c)['cock']; (cp, cr), (tp, tr), (kp, kr) = OPEN[kind]
    tl.hold(1); tl.to(f - 3, cp, cr, 'ease'); tl.to(f, tp, tr, 'drive', rlag=0)
    tl.kick(f, np.array(kp) * k, np.array(kr) * k, attack=0.5, release=2.5); tl.mark('cock', f)


def settle(c, tl, f):
    P = c.P; tl.hold(f + 3 + (1 if P['w'] > 1 else 0)); e = f + 3 + L(P, 9); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.004), (-1.5, 0, 0), release=3.0)


def seat(c, tl, station, arr, d=0.12, reb=0.012, via=None):
    pos, rot = c.station(stn(c, station)); seat_block(c, tl, pos, rot, arr, c.T['seated'], d=d, reb=reb, via=via)
    if 'clamp_shut' in ev(c): tl.mark('clamp', ev(c)['clamp_shut'])
    return pos, rot


def depart(c, tl, f0, n):
    """Leave for the station at f0 (or earlier, never before the timeline's current frame) and return the arrival
    frame: n frames (take-scaled) later, but at the latest 7 frames before the seat so the slam stays its own move
    (Saratoga: 19 frames from the release to the seat), and at least 8 frames of travel. A long hold at the rig
    follows on the Zhuo (hidden, fast-forwarded): stillness between decisive moves, not a slow glide."""
    cap = c.T['seated'] - 7; n = L(c.P, n); f0 = max(tl.f, min(f0, cap - n)); tl.hold(f0)
    return max(min(f0 + n, cap), f0 + 8)


STN_LONG = {'stomach': 'stomach_m'}     # Zhuo: the long stock went 7 cm into the torso block at the stomach rig


def stn(c, name): return STN_LONG.get(name, name) if long_gun(c) else name


def seat_block(c, tl, pos, rot, arrive, se, d=0.13, slam=5, reb=0.012, via=None):
    """prod.seat_block with the rotation trailing more on a long gun: the gun drops first and tips muzzle-down
    late, so the long stock does not swing up through the lower view on the way down (Zhuo: eye 17.5 cm before)."""
    P = c.P; pre = np.array(pos) + c.along(rot, c.v['enter'], d); rl = P['lag'] + (3 if long_gun(c) else 0)
    if via is None: tl.to(arrive, pre, rot, 'heavy', antic=P['a'], rlag=rl)
    else: prod.arc(tl, arrive, via, pre, rot, 'heavy', rlag=rl)
    tl.kick(arrive + (rl if long_gun(c) else 0), c.along(rot, c.v['enter'], -0.006), (-2, 0, 0), release=2.5)
    tl.hold(se - slam); tl.to(se, pos, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], reb * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=3.0)
    tl.mark('arrive', arrive)


def rack(c, tl, kind):
    """After the seat: up into view and the hit on the home frame h (the cocking piece runs home). Long enough
    (Saratoga: 23 frames) the gun rises into a held pose and the rack is its own move:
      punch  cocked back, punched forward, dead stop on h: the cocking piece runs on forward
      yank   held out in front, a sharp start back on h: the piece lags and runs home; stop 3 frames later
      nod    held muzzle-high, the muzzle thrown down and stopped dead on h (the top of the gun goes forward)
      upper  cocked low and back, a rising punch forward that stops dead on h
    Short (Zhuo: 10 frames) the rise is the rack: it ends in a dead stop on h moving forward (punch, upper,
    yank) or with the muzzle thrown down (nod)."""
    P = c.P; k = P['k']; se = c.T['seated']; h = ev(c)['home']
    if h - se < 16:
        tl.hold(se + 1)
        if kind == 'nod':
            tl.to(h - 3, (0.01, -0.01, -0.02), (12, 0, -3), 'rise', rlag=0, rprof='snap')
            tl.to(h, (0.0, -0.03, -0.04), (-6, 0, -2), PUNCH, rlag=0); tl.kick(h, (0, 0.006 * k, 0), (4 * k, 0, 0), attack=0.5, release=2.5)
        else:
            tl.to(h, (0.006, 0.012, -0.05), (4, 0, -2), 'rise', rlag=0, rprof='snap'); tl.kick(h, (0, -0.004, 0.016 * k), (3 * k, 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', h); settle(c, tl, h); return
    tl.hold(se + 2)
    def rise_to(f, pos, rot):
        tl.hold(f - 3 - L(P, 8)); tl.to(f - 3, (0.03, -0.085, -0.045), (-9, 0, -3), 'rise'); tl.to(f, pos, rot, 'settle'); tl.kick(f, (0, 0.005 * k, -0.002), (-1.5, 0, 0), release=2.5)
    if kind == 'punch':
        rise_to(h - 4, (0.012, -0.03, 0.035), (0, 0, -4)); tl.hold(h - 3)
        tl.to(h, (0, 0.01, -0.06), (1, 0, 0), PUNCH, rlag=0); tl.kick(h, (0, 0.004, 0.018 * k), (5 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', h); settle(c, tl, h)
    elif kind == 'yank':
        rise_to(h - 2, (0.01, -0.045, -0.06), (-5, 0, -3)); tl.hold(h)
        tl.to(h + 3, (0.0, -0.03, 0.012), (3, 0, -2), (1.25, 2.6), rlag=0); tl.kick(h, (0, 0.002, 0.012 * k), (-2.5 * k, 0, 0), attack=0.5, release=2.0)
        tl.kick(h + 3, (0, -0.002, -0.006 * k), (1.5, 0, 0), attack=0.5, release=2.5); tl.mark('hit', h); settle(c, tl, h + 3)
    elif kind == 'nod':
        rise_to(h - 4, (0.0, 0.0, -0.03), (12, 0, -2)); tl.hold(h - 3)
        tl.to(h, (0.0, -0.03, -0.045), (-9, 0, -2), PUNCH, rlag=0); tl.kick(h, (0, 0.006 * k, 0), (4 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', h); settle(c, tl, h)
    elif kind == 'upper':
        rise_to(h - 4, (0.012, -0.065, 0.0), (-11, 0, -4)); tl.hold(h - 3)
        tl.to(h, (0.0, 0.03, -0.05), (5, 0, 0), PUNCH, rlag=0); tl.kick(h, (0, -0.006, 0.014 * k), (4 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', h); settle(c, tl, h)
    else: raise ValueError(kind)


# ------------------------------------------------------------------------------------------------ drafts
def sf01(c, tl):
    """Nod throw. A small muzzle-up snap stops dead on the cocking frame. The muzzle is cocked up, then the wrist
    nods it down hard and stops dead: the magazine, out in front of the hand, keeps going down its well and falls in
    front. Down to the belt rig, driven onto the fresh magazine. Up, cocked back, a forward punch stops dead on the
    home frame."""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'tip')
    p0, r0 = np.array(P.get('p0', (0.0, 0.025, 0.015))), tuple(P.get('r0', (16, 0, -4))); tl.hold(r - 4 - L(P, 5)); tl.to(r - 4, p0, r0, 'ease')
    rn = (P.get('nod', -26), 0, 3); tl.to(r, aligned(c, p0, r0, rn, P.get('lam', 0.05)), rn, 'slam', rlag=0); tl.kick(r, -exw(c, rn) * 0.01 * k, (5 * k, 0, 0), attack=0.5, release=2.5); tl.mark('release', r)
    arr = depart(c, tl, r + 3, 11); seat(c, tl, 'belt', arr)
    rack(c, tl, 'punch')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'inertia', 'push': 0.004, 'tumble': 4, 'appear': arr + 2, 'seated': c.T['seated']}}


def sf02(c, tl):
    """Shake loose. A tug back stops dead on the cocking frame. The gun is rolled onto its left side (the well faces
    out) and jerked outward twice along the well: the first jerk works the magazine loose, the second stops dead and
    it flies out to the right and falls. Down beside the thigh onto the fresh magazine on the thigh rig. Up, held out
    in front and yanked back on the home frame."""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'tug')
    R = P.get('roll', 72); b0, rb = np.array((0.02, 0.02, -0.01)), (2, -6, R)
    tl.hold(r - 8 - L(P, 6)); tl.to(r - 8, b0, rb, 'drive', rlag=1); tl.kick(r - 8, (0.004, 0, 0), (0, 0, -4 * k), attack=0.5, release=2.0)
    e = exw(c, rb); s1 = r - 5; tl.hold(s1 - 2); tl.to(s1, b0 + e * 0.045, rb, PUNCH, rlag=0); tl.kick(s1, -e * 0.006 * k, (0, 0, -3 * k), attack=0.5, release=1.5)
    tl.to(r - 2, b0, rb, 'snap', rlag=0); tl.to(r, b0 + e * P.get('jerk', 0.08), rb, 'slam', rlag=0); tl.kick(r, -e * 0.01 * k, (0, 2, -5 * k), attack=0.5, release=2.5)
    tl.mark('loosen', s1); tl.mark('release', r); tl.nodrag.append((s1 - 3, r + 1))
    arr = depart(c, tl, r + 3, 11); seat(c, tl, 'thigh', arr)
    rack(c, tl, 'yank')
    return {'mag': {'floor': floor(c), 'release': r, 'loosen': [[s1, 0.02]], 'mode': 'inertia', 'push': 0.006, 'tumble': 5, 'appear': arr + 2, 'seated': c.T['seated']}}


def sf03(c, tl):
    """Tip-up drop. A small snap back stops dead on the cocking frame. A dip, then the muzzle tips up and stops,
    the well pointing straight down: the magazine slides out under its own weight and drops past the hand. The gun
    swings muzzle-down to the hip rig onto the fresh magazine. Up, held muzzle-high, and the muzzle is thrown down
    on the home frame."""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'snap')
    tl.hold(r - 8 - L(P, 4)); tl.to(r - 8, (0, -0.014, 0.004), (-4, 0, 1), 'ease')
    tl.to(r - 1, (0.0, 0.02, 0.01), (P.get('tip', 22), -3, -4), 'drive', rlag=1); tl.kick(r - 1, (0, -0.005, 0), (-2.5 * k, 0, 0), attack=0.6, release=2.5); tl.mark('release', r)
    arr = depart(c, tl, r + 5, 11); seat(c, tl, 'hip', arr)
    rack(c, tl, 'nod')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'throw', 'slide': 4, 'travel': 0.08, 'tumble': 2, 'appear': arr + 2, 'seated': c.T['seated']}}


def sf04(c, tl):
    """Thigh hook. A tug back stops dead on the cocking frame. The gun swings down beside the thigh: the magazine
    catches on the thigh rig's hook and the gun is ripped up off it along the well; the magazine drops. Wound up
    over the fresh magazine on the same rig and slammed down onto it. Up, cocked back, punched forward: stop dead on
    the home frame."""
    P = c.P; k = P['k']; r = ev(c)['out']; se = c.T['seated']; opener(c, tl, 'tug')
    ex = np.array(c.v['exit']) * np.array([0, 1, 1]); ex /= np.linalg.norm(ex)
    hook, rot = c.station('thigh'); tl.to(r - 3, hook, rot, 'heavy', antic=P['a'] * 0.6, rlag=0); tl.kick(r - 3, (0, -0.01 * k, 0), (-3, 0, 0), attack=0.5, release=2.0); tl.hold(r)
    po = r + L(P, 4); tl.to(po, hook - c.along(rot, ex, 0.16), rot, PUNCH, rlag=0); tl.kick(po, c.along(rot, ex, 0.01), (2, 0, 0), release=2.5); tl.mark('release', r); tl.nodrag.append((r - 2, r + 6))
    w = max(r + 10, se - 14); tl.hold(r + 7); pre = hook + c.along(rot, c.v['enter'], P.get('windup', 0.20)); tl.to(w, pre, rot, 'ease')
    tl.hold(se - 5); tl.to(se, hook, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], 0.02 * k), (-5 * k, 0, 0), attack=0.5, release=3.5)
    if 'clamp_shut' in ev(c): tl.mark('clamp', ev(c)['clamp_shut'])
    rack(c, tl, 'punch')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'hook', 'slide': 4, 'tumble': 3, 'appear': w + 2, 'seated': se, 'exit': [float(x) for x in ex]}}


def sf05(c, tl):
    """Chest snap. A muzzle-up snap stops dead on the cocking frame. A short dip, then the gun is snapped up and
    canted inward: the magazine stays where it was and drops out of the well. Pulled back and down to the stomach
    rig, pressed onto the fresh magazine. Up, held out in front and yanked back on the home frame."""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'tip')
    tl.hold(r - L(P, 5)); tl.to(r, (0.0, -0.035, 0.012), (-4, 0, -8), 'ease'); tl.mark('release', r)
    tl.to(r + 3, (0.02, 0.05, 0.0), (7, 0, -30), PUNCH, rlag=1); tl.kick(r + 3, (0, -0.012 * k, 0), (-3, 0, 5), attack=0.5, release=2.5)
    arr = depart(c, tl, r + 7, 10); seat(c, tl, 'stomach', arr, d=0.11, reb=0.008)
    rack(c, tl, 'yank')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.14, 'tumble': 5, 'appear': arr + 2, 'seated': c.T['seated']}}


def sf06(c, tl):
    """Backswing. A small snap back stops dead on the cocking frame. The gun swings down and back past the hip,
    muzzle down, and stops dead behind it: the magazine flies on out of the well, back and down. Onto the fresh
    magazine in the pouch behind the hip. Swung forward and up, cocked low, and a rising punch stops dead on the
    home frame."""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'snap')
    pos, rot = c.station('rear'); top = np.array(pos) + (0.0, 0.06, 0.03)
    tl.hold(r - 12 - L(P, 4)); tl.to(r - 12, (0, 0.015, -0.025), (6, 0, 0), 'ease')
    tl.to(r, top, rot, 'drive', rlag=1); tl.kick(r, (0, 0.006, -0.012 * k), (4 * k, 0, 0), attack=0.5, release=2.5); tl.mark('release', r)
    arr = depart(c, tl, r + 4, 8); seat_block(c, tl, pos, rot, arr, c.T['seated'])
    if 'clamp_shut' in ev(c): tl.mark('clamp', ev(c)['clamp_shut'])
    rack(c, tl, 'upper')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.08, 'tumble': 4, 'appear': arr + 2, 'seated': c.T['seated']}}


def sf07(c, tl):
    """Muzzle-up shove. A tug back stops dead on the cocking frame. The muzzle is tipped up high and the gun drawn
    in, then shoved forward and down along the well and stopped dead: the magazine shoots out in front and falls.
    Down to the belt rig onto the fresh magazine. Up, held out in front and yanked back on the home frame. (The
    rifles' F16 for the short guns.)"""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'tug')
    ru = (P.get('tip', 40), -4, -4); pu = np.array(P.get('drawn', (0.0, 0.03, 0.07)))
    tl.hold(r - 5 - L(P, 8)); tl.to(r - 5, pu, ru, 'heavy', rlag=1); tl.hold(r - 4)
    e = exw(c, ru); tl.to(r, pu + e * P.get('shove', 0.11), ru, 'slam', rlag=0); tl.kick(r, -e * 0.012 * k, (-3 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); arr = depart(c, tl, r + 3, 12); seat(c, tl, 'belt_wide', arr, via=(0.07, -0.16, 0.08))
    rack(c, tl, 'yank')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'inertia', 'push': 0.005, 'tumble': 5, 'appear': arr + 2, 'seated': c.T['seated']}}


def sf08(c, tl):
    """Cant-in drop. A muzzle-up snap stops dead on the cocking frame. The gun is raised a little and canted onto
    its right side: the magazine slides out sideways under its own weight and drops between the guns. Down to the
    stomach rig onto the fresh magazine. Up, held muzzle-high, and the muzzle is thrown down on the home frame."""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'tip')
    tl.hold(r - 1 - L(P, 10)); tl.to(r - 1, (0.025, 0.02, -0.015), (8, 4, P.get('cant', -58)), 'heavy', rlag=0); tl.kick(r - 1, (0.004, -0.004, 0), (0, 0, 4 * k), attack=0.6, release=2.5)
    tl.mark('release', r); arr = depart(c, tl, r + 5, 8); seat(c, tl, 'stomach', arr, d=0.11, reb=0.008, via=P.get('via'))
    rack(c, tl, 'nod')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'throw', 'slide': 5, 'travel': 0.08, 'tumble': 2, 'appear': arr + 2, 'seated': c.T['seated']}}


def sf09(c, tl):
    """Wind-up chop. A tug back stops dead on the cocking frame. The gun is lifted with the muzzle up, then chopped
    down along the well and stopped dead in front of the chest: the magazine flies on straight down. Down to the
    belt rig onto the fresh magazine. Up, cocked low, a rising punch stops dead on the home frame."""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'tug')
    hrot = (-6, 0, 0); stop = np.array(P.get('stop', (0.0, -0.03, 0.02))); wu = stop - c.along(hrot, c.v['exit'], P.get('drop', 0.17))
    tl.hold(r - 5 - L(P, 8)); tl.to(r - 5, wu, (P.get('wind', 18), 0, -3), 'rise', antic=P['a'] * 0.5); tl.hold(r - 4)
    tl.to(r, aligned(c, wu, (P.get('wind', 18), 0, -3), hrot, P.get('drop', 0.17)), hrot, 'slam', rlag=0); tl.kick(r, -c.along(hrot, c.v['exit'], 0.012 * k), (0.5, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 4, r + 1))
    arr = depart(c, tl, r + 4, 10); seat(c, tl, 'belt', arr)
    rack(c, tl, 'upper')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'inertia', 'push': 0.003, 'tumble': 4, 'appear': arr + 2, 'seated': c.T['seated']}}


def sf10(c, tl):
    """Drop stop. A muzzle-up snap stops dead on the cocking frame. The arm drops the gun straight down, level, out
    of view and stops it dead beside the hip: the magazine keeps falling out of the well. The gun tips onto the fresh
    magazine on the belt rig. One decisive rise; the punch forward stops dead on the home frame. (Today's generic
    drop, with the magazine falling by itself.)"""
    P = c.P; k = P['k']; r = ev(c)['out']; opener(c, tl, 'tip')
    rl = (P.get('pitch', -6), 0, 3); low = np.array(P.get('low', (0.08, -0.30, 0.12))); top = low - exw(c, rl) * P.get('drop', 0.30)
    tl.hold(r - 8 - L(P, 5)); tl.to(r - 8, top, rl, 'ease', rlag=0); tl.hold(r - 6); tl.to(r, low, rl, 'slam', rlag=0); tl.nodrag.append((r - 6, r + 1))
    tl.kick(r, -exw(c, rl) * 0.012 * k, (0, 0, 0), attack=0.5, release=2.5); tl.mark('release', r)
    arr = depart(c, tl, r + 4, 8); seat(c, tl, 'belt', arr, d=0.12)
    rack(c, tl, 'punch')
    return {'mag': {'floor': floor(c), 'release': r, 'mode': 'inertia', 'push': 0.006, 'tumble': 3, 'appear': arr + 2, 'seated': c.T['seated']}}


PICKS = {'SF01': ('Nod throw', sf01), 'SF02': ('Shake loose', sf02), 'SF03': ('Tip-up drop', sf03), 'SF04': ('Thigh hook', sf04),
         'SF05': ('Chest snap', sf05), 'SF06': ('Backswing', sf06), 'SF07': ('Muzzle-up shove', sf07), 'SF08': ('Cant-in drop', sf08),
         'SF09': ('Wind-up chop', sf09), 'SF10': ('Drop stop', sf10)}
PARAMS = {'SF08B': {'via': (0.14, -0.14, -0.08)}, 'SF01B': {'nod': -16, 'lam': 0.2, 'p0': (0.0, -0.01, -0.02), 'r0': (8, 0, -3)}, 'SF09B': {'wind': 10, 'drop': 0.13, 'stop': (0.0, -0.06, -0.04)}}          # per draft and take overrides


def stem(pick, take, side='right'): return prod.stem(GUNS[take], pick, take, CLIP, side)


def elbow_step(spec):
    S = spec['_side']; g = Glb(spec['out']); c = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}; prev = None; worst = 0.0
    for f in range(spec['frames']):
        W = c.world(f); s, e, h = (np.array(W[ix[S + n]][0]) for n in ('Arm', 'ForeArm', 'Hand')); ax = (h - s) / np.linalg.norm(h - s)
        p = (e - s) - ((e - s) @ ax) * ax; p /= (np.linalg.norm(p) or 1)
        if prev is not None: worst = max(worst, float(np.degrees(np.arccos(np.clip(p @ prev, -1, 1)))))
        prev = p
    return round(worst, 1)


def build(pick, take, side='right', body='pma', out=None, quiet=False):
    gid = GUNS[take]; setup(gid); out = out or OUT + '/clips'; d = f'{out}/{body}'; os.makedirs(d, exist_ok=True); name = stem(pick, take, side)
    S = side.capitalize(); P = dict(prod.TAKES[take]); P.update(PARAMS.get(pick + take, PARAMS.get(pick, {}))); c = prod.Ctx(gid, body, CLIP, P, S); tl = TL(c, P['lag'], P['drag'])
    fn = PICKS[pick][1]; m = fn(c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    if S == 'Left':
        Pk = Pk * prod.MIR_P; Rk = Rk * prod.MIR_R
        for k in kicks: k['move'] = list(np.array(k['move'], float) * prod.MIR_P); k['rot'] = list(np.array(k['rot'], float) * prod.MIR_R)
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {take}', '_doc': ' '.join((fn.__doc__ or '').split()), '_gun': gid, '_left_gun': gid, '_body': body, '_side': S,
            '_gun_clip': CLIP, '_pick': pick, '_take': take, '_timing': c.T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False, '_round': 'smg-front-1',
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, ('Left' if S == 'Right' else 'Right'): [K(0)]},
            'shakes': {S: kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); G = [cl.world(f)[i] for f in range(c.N)]
    GG = [(np.array(t), np.array(q)) for t, q in G]; track = magtrack3.build(gid, CLIP, GG, m['mag']); cap = c.T['seated'] - 6
    if not long_gun(c) and track['gone'] > cap:
        # the fresh magazine must exist 6 frames before the seat and one mesh carries both: the old one is gone at the
        # height it has reached by then (below the first-person view; checked by rgate's magazine-on-screen rule)
        t2 = magtrack3.build(gid, CLIP, GG, dict(m['mag'], floor=-9.0)); cen = np.r_[magtrack2.vanilla(gid, CLIP)['centre'], 1]
        y = float((magtrack2.m4(*GG[cap - 1]) @ np.array(t2['frames'][cap - 1]['m']).reshape(4, 4) @ cen)[1])
        m['mag']['floor'] = round(y + 0.002, 3); track = magtrack3.build(gid, CLIP, GG, m['mag'])
    spec['_track'] = f'{d}/{name}_track.json'; spec['_mag'] = m['mag']
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); o['elbow_step_deg'] = elbow_step(spec)
    if m['mag']['mode'] == 'inertia' and 'mag_exit' not in o: o['mag_exit'] = magtrack3.exit_check(track, gid, CLIP)
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, rgate.line(o), '| elbow', o['elbow_step_deg'], '| exit', o.get('mag_exit'), flush=True)
    return spec, o


APPROVED = OUT + '/ref/motion_all.json'          # round 2 measure: the approved shipped clips (rifle-reloads/round2/measure on the NAS)


def stats(ids):
    import motionstats
    rows = []; J = json.load(open(APPROVED)); rows += [(k, v) for k, v in J.items() if k.startswith('APPROVED')]
    for p in ids:
        for t in ('A', 'B'):
            g = f'{OUT}/clips/pma/{stem(p, t)}.glb'
            if os.path.exists(g): rows.append((f'{p}{t} {PICKS[p][0]} ({GUNS[t]})', motionstats.stats(g, 'reload_draft', 'Right', 0.55 if t == 'A' else 0.6)))
    Tb = ['| clip | peak cm/f | peak at | stop | jerks | still | whip | muzzle peak | big moves |', '|---|---|---|---|---|---|---|---|---|']
    for lab, s in rows: Tb.append(f"| {lab} | {s['peak_speed']} | {s['peak_at']} | {s['stop']} | {s['jerk_events']} | {int(s['hold_share'] * 100)} % | {s['whip']} | {s['peak_muzzle_speed']} | {s['big_moves']} |")
    os.makedirs(OUT + '/measure', exist_ok=True); open(OUT + '/measure/motion_round1.md', 'w').write('\n'.join(Tb) + '\n'); print('\n'.join(Tb))
    json.dump({l: s for l, s in rows}, open(OUT + '/measure/motion_round1.json', 'w')); motionstats.plot(rows, OUT + '/measure/motion_round1.png')


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'
    takes = (o('--takes') or 'A,B').split(','); jobs = int(o('--jobs') or 1)
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(PICKS)
    if cmd == 'list':
        for p, (n, fn) in PICKS.items(): print(p, n, '|', ' '.join((fn.__doc__ or '').split()))
    elif cmd == 'events':
        for gid in GUNS.values(): print(gid, events(gid))
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
    else: raise SystemExit(__doc__)
