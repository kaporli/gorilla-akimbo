"""Round 3, FRONT magazine rifles: drafts for the third reload slot (today F02, F09, F02). Built like the production
picks (prod.py: same context, takes, stations, seat block, mirror for the left hand), with rlib2 motion and an own
magazine track (magtrack3: magtrack2 plus 'inertia', a magazine that keeps flying when the gun stops dead).

usage: front3.py build [ids] [--guns copperhead] [--clips reload,empty_reload] [--sides right] [--bodies pma] [--take A] [--jobs n]
       front3.py list
Output: <OUT>/clips/<body>/<gun>_<side>_<id><take>_<clip>.glb, .json, _track.json, _gate.json (gate numbers, motion,
magazine exit check). OUT: anim-work/rifle-reloads/round3-front.

Every id is also registered in prod.PICKS, so prod.build / rrender3 work on it once weapons.json lists it.
Frames (Copperhead empty reload): magazine out f14 (the gun's own f15 less one, as F02), seated f57, lever f73.
Racks (empty reload, a lever that goes back at h0 and returns): the lever is thrown when the gun stops dead after
moving back (yank), stops dead after the muzzle went up (flick), starts to move forward (punch, uppercut) or starts
to tip down (nod), or is pushed against the belt edge out of view (rake).
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, manifest
import numpy as np
import author, rlib2, magtrack3, prod, rgate
from rlib import K
from glb import Glb
from fk import Clip, qrot

OUT = renv.OUT + '/round3-front'
PUNCH = prod.PUNCH
L = prod.L
# new stations: offset of the grip from the hips joint (x to the gun hand's side, y up, z back), search start angles
ST3 = {'thigh': ((0.29, 0.10, -0.035), (-78, -10, 10)), 'rear': ((0.31, 0.15, 0.07), (-100, -12, 10)), 'lhip': ((0.03, 0.17, -0.19), (-35, 60, 20)),
       'belt_front': ((0.24, 0.15, -0.10), (-55, 0, 6))}
prod.STATION.update({k: v for k, v in ST3.items() if k not in prod.STATION})


def rel(c):
    """Release frame: the gun's own magazine-out frame less one (Copperhead f14), early enough before the seat."""
    return min(c.T['out'] - 1, c.T['seated'] - 38)


def exw(c, rot):
    """World direction of the well's exit axis with the gun at angles rot."""
    return c.along(rot, c.v['exit'], 1.0)


def mag_point(c):
    """Centre of the seated magazine in gun axes."""
    return (c.v['seat'] @ np.r_[c.v['centre'], 1])[:3]


def aligned(c, p0, r0, re, lam):
    """End position of a move from (p0, r0) to angles re that ends with the magazine centre travelling along the
    well's exit axis: the translation cancels the sideways part of the rotation's arc at the end of the move
    (TL moves interpolate position and angles with one profile, so the end velocity is translation plus the
    tangent of the rotation). lam: metres of the move along the axis."""
    m = c.ax(mag_point(c)) if c.side == 'Left' else mag_point(c); r0, re = np.array(r0, float), np.array(re, float); dl = 0.02
    w = lambda r: qrot(author.qmul(c.q0, author.qeuler(*r)), m)
    tan = (w(re) - w(re - dl * (re - r0))) / dl
    return np.array(p0, float) + exw(c, re) * lam - tan


def knock(c, station):
    """Ajax and Kyubi empty reload: the belt knock of production (the gun's own magazine lock decides it)."""
    if common.gun(c.gun).get('reload', {}).get('empty') == 'belt_knock' and c.clip == 'empty_reload': return station
    return None


def handle(c):
    """First frame of a lever that goes back and returns (Copperhead f73), or None (no handle, or a bolt / latch
    type: those keep production's finish)."""
    T = c.T; h = T.get('handle')
    if not h or T['parts'].get('magazine_grabber'): return None
    if any(p['stays_moved'] for p in T['parts'].values() if p['window'][0] >= T['seated']): return None
    return h[0]


def settle(c, tl, f):
    P = c.P; tl.hold(f + 3 + (1 if P['w'] > 1 else 0)); e = f + 3 + L(P, 9); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.004), (-1.5, 0, 0), release=3.0)


def rise_to(c, tl, f, pos, rot):
    """From the station up into view, low and forward first (as production's finish: the stock stays off the face),
    then into the rack pose, arriving on frame f."""
    P = c.P; tl.to(f - 3, (0.03, -0.085, -0.045), (-9, 0, -3), 'rise'); tl.to(f, pos, rot, 'settle')
    tl.kick(f, (0, 0.005 * P['k'], -0.002), (-1.5, 0, 0), release=2.5)


def rack(c, tl, kind, station=None):
    """After the seat. No handle: production's rise (prod.finish). With a lever at h0: one of the racks."""
    P = c.P; se = c.T['seated']; h0 = handle(c)
    if h0 is None:
        if c.T.get('handle'): return prod.finish(c, tl, prod.hit_frames(c))
        return prod.finish(c, tl, None)
    tl.hold(se + 2)
    if kind == 'yank':        # held out in front, yanked back toward the body and stopped dead: the lever runs on
        rise_to(c, tl, h0 - 3, (0.01, -0.045, -0.06), (-5, 0, -3))
        tl.to(h0, (0.0, -0.03, 0.012), (3, 0, -2), 'slam', rlag=0); tl.kick(h0, (0, 0.003, -0.014 * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', h0); settle(c, tl, h0)
    elif kind == 'flick':     # held low, the muzzle snapped up and stopped dead
        rise_to(c, tl, h0 - 3, (0.01, -0.055, -0.04), (-15, 0, -3))
        tl.to(h0, (0.002, -0.042, -0.032), (9, 0, -2), PUNCH, rlag=0); tl.kick(h0, (0, -0.004, 0.002), (-4 * P['k'], 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', h0); settle(c, tl, h0)
    elif kind == 'nod':       # held high with the muzzle up, the muzzle thrown down: the lever lags back on the start
        rise_to(c, tl, h0 - 2, (0.0, 0.0, -0.03), (10, 0, -2)); tl.hold(h0 - 1)
        tl.to(h0 + 2, (0.0, -0.03, -0.045), (-9, 0, -2), PUNCH, rlag=0); tl.kick(h0 + 2, (0, 0.006 * P['k'], 0), (4 * P['k'], 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', h0); settle(c, tl, h0 + 2)
    elif kind == 'upper':     # cocked low and back, a rising punch: the lever lags back on the start
        rise_to(c, tl, h0 - 2, (0.012, -0.065, 0.0), (-11, 0, -4)); tl.hold(h0 - 1)
        tl.to(h0 + 3, (0.0, 0.03, -0.05), (5, 0, 0), PUNCH, rlag=0); tl.kick(h0 + 3, (0, -0.006, 0.014 * P['k']), (4 * P['k'], 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', h0); settle(c, tl, h0 + 3)
    elif kind == 'rake':      # out of view: the lever is set against the belt edge and the gun shoved forward
        pos, rot = station; up = np.array(pos) + (0.0, 0.045, 0.035); fw = c.along(rot, (0, 0, -1), 0.075)
        tl.to(h0 - 3, up, rot, 'heavy', antic=P['a']); tl.hold(h0 - 1); tl.to(h0 + 3, up + fw, rot, PUNCH, rlag=0)
        tl.kick(h0 + 3, -fw * 0.15, (-2 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('hit', h0); tl.hold(h0 + 5)
        n = max(L(P, 9), int(round(float(np.linalg.norm(tl.p)) * 100 / 4.5 * P['w']))); e = h0 + 5 + n + 3
        tl.to(e - 3, (0.02, -0.07, -0.04), (-8, 0, -2), 'rise', antic=P['a'] * 0.6); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0.003, 0.008 * P['k'], -0.008), (-1.5, 0, 0), release=3.0)
    else: raise ValueError(kind)


def f11(c, tl):
    """Chop drop, thigh slam. A short lift, then the rifle is chopped straight down along its well and stops dead:
    the magazine keeps going and falls. Down beside the thigh, slammed onto the fresh magazine on the thigh rig. Up,
    held out in front and yanked back: the stop throws the lever."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'belt'): return prod.belt_knock(c, tl, 'belt')
    rc = (-8, 0, -3); top = np.array((0.004, 0.035, 0.008))
    tl.hold(r - 10); tl.to(r - 5, top, (7, 0, -2), 'ease')
    tl.to(r, aligned(c, top, (7, 0, -2), rc, 0.18), rc, 'slam', rlag=0); tl.kick(r, -exw(c, rc) * 0.012 * P['k'], (4 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('release', r)
    tl.hold(r + 3); pos, rot = c.station('thigh'); arr = r + 3 + L(P, 9); prod.seat_block(c, tl, pos, rot, arr, se, slam=4, reb=0.016)
    rack(c, tl, 'yank')
    return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.005, 'tumble': 4, 'appear': arr + 2, 'seated': se}}


def f12(c, tl):
    """Tip-up drop, hip seat. A small dip, the muzzle tips up a little and holds, the well pointing straight down: the
    magazine slides out under its own weight and drops in front of the hand. The rifle swings muzzle-down to the hip rig onto the fresh magazine. Up, held
    low, and the muzzle is snapped up: the stop throws the lever."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'hip'): return prod.belt_knock(c, tl, 'hip')
    tl.hold(r - 11); tl.to(r - 8, (0, -0.012, 0.004), (-4, 0, 1), 'ease')
    tl.to(r - 1, (0.0, 0.02, 0.01), (P.get('tip', 22), -3, -5), 'drive', rlag=1); tl.kick(r - 1, (0, -0.005, 0), (-2.5 * P['k'], 0, 0), attack=0.6, release=2.5); tl.mark('release', r)
    tl.hold(r + 6); pos, rot = c.station('hip'); arr = r + 6 + L(P, 9); prod.seat_block(c, tl, pos, rot, arr, se)
    rack(c, tl, 'flick')
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 4, 'travel': 0.09, 'tumble': 2, 'appear': arr + 2, 'seated': se}}


def f13(c, tl):
    """Belt hook strip. Straight down to the belt: the magazine catches on the rig's hook and the rifle is yanked
    back off it, out of view; it drops. Onto the fresh magazine beside it. The lever is raked on the belt edge, still
    out of view, and the rifle comes up loaded."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'belt'): return prod.belt_knock(c, tl, 'belt')
    ex = np.array(c.v['exit']) * np.array([0, 1, 1]); ex /= np.linalg.norm(ex)
    tl.hold(r - 11); tl.to(r - 8, (0, 0.02, 0), (4, 0, 0), 'ease')
    hook, rot = c.station('belt'); tl.to(r, hook, rot, 'heavy'); tl.kick(r, (0, -0.01 * P['k'], 0), (-3, 0, 0), attack=0.5, release=2.5)
    off = hook - c.along(rot, ex, 0.17); tl.to(r + 4, off, rot, PUNCH, rlag=0); tl.kick(r + 4, c.along(rot, ex, 0.01), (2, 0, 0), release=2.5); tl.mark('release', r)
    tl.hold(r + 7); pos, rot2 = c.station('belt_front'); arr = r + 7 + L(P, 7); prod.seat_block(c, tl, pos, rot2, arr, se, d=0.12)
    rack(c, tl, 'rake', (pos, rot2))
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 4, 'tumble': 4, 'appear': arr + 2, 'seated': se, 'exit': [float(x) for x in ex]}}


def f14(c, tl):
    """Backhand whip, cross-body seat. A counter move out, then the rifle is whipped down and in and rolled onto its
    left side, below the other rifle, and stopped dead: the magazine flies on, down and to the left. Down across the
    body to the left hip rig onto the fresh magazine. Swept back up, muzzle high, and thrown down: the lever racks."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'belt'): return prod.belt_knock(c, tl, 'belt')
    tl.hold(r - 11); tl.to(r - 6, (0.04, 0.015, -0.05), (2, -8, 14), 'ease')
    wr = P.get('whip_rot', (-12, 28, -62)); tl.to(r, aligned(c, (0.04, 0.015, -0.05), (2, -8, 14), wr, P.get('whip', 0.34)), wr, 'slam', rlag=0); tl.kick(r, (0.006, 0.002, 0), (0, -1, 3 * P['k']), attack=0.5, release=2.5); tl.mark('release', r)
    tl.hold(r + 3); pos, rot = c.station('lhip'); arr = r + 3 + L(P, 10); prod.seat_block(c, tl, pos, rot, arr, se)
    rack(c, tl, 'nod')
    return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.012, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


def f15(c, tl):
    """Pendulum, rear pouch. The rifle swings down and back beside the leg, muzzle down, and stops dead behind the
    hip: the magazine is flung out of the well, up and back. Onto the fresh magazine in the rear pouch. Swung forward and up, cocked low,
    a rising punch racks the lever."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'belt'): return prod.belt_knock(c, tl, 'belt')
    pos, rot = c.station('rear'); top = np.array(pos) + (0.0, 0.07, 0.03)
    tl.hold(r - 14); tl.to(r - 11, (0, 0.015, -0.025), (6, 0, 0), 'ease')
    tl.to(r, top, rot, 'drive', rlag=1); tl.kick(r, (0, 0.006, -0.012 * P['k']), (4 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('release', r)
    tl.hold(r + 4); arr = r + 4 + L(P, 6); prod.seat_block(c, tl, pos, rot, arr, se)
    rack(c, tl, 'upper')
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.10, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


def f16(c, tl):
    """Muzzle-up shove. The muzzle is tipped up high and the rifle drawn in; then shoved forward and down along the
    well and stopped dead: the magazine shoots out forward and falls in front. Down to the belt rig onto the fresh
    magazine. Up, held out in front and yanked back: the stop throws the lever."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'belt'): return prod.belt_knock(c, tl, 'belt_wide')
    ru = (P.get('tip', 42), -4, -4); pu = np.array((0.0, 0.03, 0.08))
    tl.hold(r - 14); tl.to(r - 5, pu, ru, 'heavy', rlag=1); tl.hold(r - 4)
    e = exw(c, ru); tl.to(r, pu + e * P.get('shove', 0.12), ru, 'slam', rlag=0); tl.kick(r, -e * 0.012 * P['k'], (-3 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.hold(r + 3); tl.to(r + 9, (0.05, -0.12, 0.06), (-20, -6, 4), 'heavy')
    pos, rot = c.station('belt_wide'); arr = r + 9 + L(P, 7); prod.seat_block(c, tl, pos, rot, arr, se)
    rack(c, tl, 'yank')
    return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.005, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


def f17(c, tl):
    """Thigh hook, uppercut. Down beside the thigh: the magazine catches on the thigh rig and the rifle is ripped off
    it and comes straight back up into view, empty, and stops. Down again to the hip rig onto the fresh magazine. Up,
    held low, and the muzzle is snapped up: the stop throws the lever."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'hip'): return prod.belt_knock(c, tl, 'hip')
    ex = np.array(c.v['exit']) * np.array([0, 1, 1]); ex /= np.linalg.norm(ex)
    tl.hold(r - 12); tl.to(r - 9, (0, 0.02, 0), (4, 0, 0), 'ease')
    hook, rot = c.station('thigh'); tl.to(r, hook, rot, 'heavy'); tl.kick(r, (0, -0.01 * P['k'], 0), (-3, 0, 0), attack=0.5, release=2.5)
    tl.to(r + 3, hook - c.along(rot, ex, 0.15), rot, PUNCH, rlag=0); tl.mark('release', r)
    up = r + 3 + L(P, 7); tl.to(up, P.get('show', (0.03, -0.06, -0.03)), (6, -2, -8), 'drive'); tl.kick(up, (0, -0.01 * P['k'], 0), (-3 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.hold(up + 4); pos, rot2 = c.station('hip'); arr = up + 4 + L(P, 8); prod.seat_block(c, tl, pos, rot2, arr, se, d=0.12)
    rack(c, tl, 'flick')
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 3, 'tumble': 3, 'appear': arr + 2, 'seated': se, 'exit': [float(x) for x in ex]}}


def f18(c, tl):
    """Nod drop. The rifle is dropped low with the muzzle lifted, then nodded down hard about the hand and stopped dead: the magazine, out in
    front of the hand, keeps going down and back out of the well. Down to the belt rig onto the fresh magazine. Up,
    muzzle high, and thrown down again: the lever racks."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'belt'): return prod.belt_knock(c, tl, 'belt')
    tl.hold(r - 10); tl.to(r - 5, (0.005, -0.07, -0.035), (8, 0, -2), 'ease')
    rn = (P.get('nod', -28), 0, -5); tl.to(r, aligned(c, (0.005, -0.07, -0.035), (8, 0, -2), rn, 0.08), rn, 'slam', rlag=0); tl.kick(r, (0, 0.006, 0), (5 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('release', r)
    tl.hold(r + 4); pos, rot = c.station('belt'); arr = r + 4 + L(P, 9); prod.seat_block(c, tl, pos, rot, arr, se)
    rack(c, tl, 'nod')
    return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.005, 'tumble': 4, 'appear': arr + 2, 'seated': se}}


def f19(c, tl):
    """Double chop. Two short chops down along the well: the first stops dead and the magazine drops a little in the
    well, the second stops dead and it flies out and falls. Down to the belt rig onto the fresh magazine. Up, cocked
    low, a rising punch racks the lever."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'belt'): return prod.belt_knock(c, tl, 'belt_wide')
    rc = (-6, 0, -3); top = np.array((0.003, 0.03, 0.006)); e = exw(c, rc)
    tl.hold(r - 13); tl.to(r - 10, top, (6, 0, -2), 'ease'); tl.to(r - 7, aligned(c, top, (6, 0, -2), rc, 0.08), rc, 'slam', rlag=0); tl.kick(r - 7, -e * 0.008 * P['k'], (3 * P['k'], 0, 0), attack=0.5, release=2.0)
    tl.hold(r - 6); tl.to(r - 3, top, (6, 0, -2), 'snap'); tl.to(r, aligned(c, top, (6, 0, -2), rc, 0.16), rc, 'slam', rlag=0); tl.kick(r, -e * 0.012 * P['k'], (4 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.mark('loosen', r - 7); tl.mark('release', r)
    tl.hold(r + 3); pos, rot = c.station('belt_wide'); arr = r + 3 + L(P, 9); prod.seat_block(c, tl, pos, rot, arr, se)
    rack(c, tl, 'upper')
    return {'mag': {'release': r, 'loosen': [[r - 7, 0.025]], 'mode': 'inertia', 'push': 0.005, 'tumble': 4, 'appear': arr + 2, 'seated': se}}


def f20(c, tl):
    """Cant-in drop. The rifle is raised a little and canted onto its left side, slowly: the magazine slides out
    sideways under its own weight and drops between the rifles. Down to the stomach rig onto the fresh magazine. Up,
    held out in front and yanked back: the stop throws the lever."""
    P = c.P; se = c.T['seated']; r = rel(c)
    if knock(c, 'stomach'): return prod.belt_knock(c, tl, 'stomach')
    tl.hold(r - 12); tl.to(r - 1, (0.025, 0.02, -0.015), (8, 4, P.get('cant', -58)), 'heavy', rlag=1); tl.kick(r - 1, (0.004, -0.004, 0), (0, 0, 4 * P['k']), attack=0.6, release=2.5)
    tl.mark('release', r); tl.hold(r + 6); pos, rot = c.station('stomach'); arr = r + 6 + L(P, 9); prod.seat_block(c, tl, pos, rot, arr, se, d=0.11, reb=0.008)
    rack(c, tl, 'yank')
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 5, 'travel': 0.08, 'tumble': 2, 'appear': arr + 2, 'seated': se}}


PICKS3 = {'F11': ('Chop drop, thigh slam', f11), 'F12': ('Tip-up drop, hip seat', f12), 'F13': ('Belt hook strip, belt rake', f13),
          'F14': ('Backhand whip, cross-body seat', f14), 'F15': ('Pendulum, rear pouch', f15), 'F16': ('Muzzle-up shove', f16),
          'F17': ('Thigh hook, uppercut', f17), 'F18': ('Nod drop', f18), 'F19': ('Double chop', f19), 'F20': ('Cant-in drop', f20)}
prod.PICKS.update(PICKS3)
MIR_P, MIR_R = prod.MIR_P, prod.MIR_R


def build(gid, pick, take, clip, side, body, out=None, params=None, quiet=False):
    """prod.build with magtrack3 (inertia) and the magazine exit check in the gate file."""
    out = out or OUT + '/clips'; d = f'{out}/{body}'; os.makedirs(d, exist_ok=True); name = prod.stem(gid, pick, take, clip, side)
    S = side.capitalize(); P = dict(prod.TAKES[take]); P.update(params or {}); c = prod.Ctx(gid, body, clip, P, S); tl = rlib2.TL(c, P['lag'], P['drag']); m = prod.PICKS[pick][1](c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    if S == 'Left':
        Pk = Pk * MIR_P; Rk = Rk * MIR_R
        for k in kicks: k['move'] = list(np.array(k['move'], float) * MIR_P); k['rot'] = list(np.array(k['rot'], float) * MIR_R)
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    spec = {'_draft': name, '_name': f'{prod.PICKS[pick][0]}, take {take}', '_doc': ' '.join((prod.PICKS[pick][1].__doc__ or '').split()), '_gun': gid, '_left_gun': gid, '_body': body,
            '_side': S, '_gun_clip': clip, '_pick': pick, '_take': take, '_timing': c.T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False,
            '_round': 3, 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, ('Left' if S == 'Right' else 'Right'): [K(0)]},
            'shakes': {S: kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); G = [cl.world(f)[i] for f in range(c.N)]
    track = magtrack3.build(gid, clip, [(np.array(t), np.array(q)) for t, q in G], m['mag']); spec['_track'] = f'{d}/{name}_track.json'
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); o['mag_exit'] = magtrack3.exit_check(track, gid, clip)
    if o['mag_exit']['off_axis_cm'] > 1.5 or o['mag_exit']['into_gun_cm'] > 0.5: o['fails'].append(f"magazine leaves the well {o['mag_exit']['off_axis_cm']} cm off its axis")
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, rgate.line(o), '| exit', o['mag_exit'], flush=True)
    return spec, o


def plan(ids=None, guns=None, clips=None, sides=None, bodies=None, take='A'):
    return [(g, p, take, cl, s, b) for p in (ids or list(PICKS3)) for g in (guns or ['copperhead']) for cl in (clips or ['reload', 'empty_reload'])
            for s in (sides or ['right']) for b in (bodies or ['pma'])]


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None
    cmd = argv[0] if argv else 'list'; ids = cs(argv[1]) if len(argv) > 1 and not argv[1].startswith('--') else None
    pl = plan(ids, cs(o('--guns')), cs(o('--clips')), cs(o('--sides')), cs(o('--bodies')), o('--take') or 'A'); jobs = int(o('--jobs') or 1); out = o('--out')
    if cmd == 'list':
        for p in pl: print(*p)
    elif cmd == 'build':
        if jobs > 1:
            procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), '_part', json.dumps(pl[k::jobs])] + (['--out', out] if out else [])) for k in range(jobs) if pl[k::jobs]]
            for p in procs: p.wait()
        else:
            for p in pl: build(*p, out=out)
    elif cmd == '_part':
        for p in json.loads(argv[1]): build(*p, out=out)
    else: raise SystemExit(__doc__)
