"""Production rifle reload clips: every pick on every gun of its category, reload and empty reload, right and left
hand, male and female V, each with its magazine track and gate numbers. Everything comes from weapons.json:
guns[].reload (category, picks, weight, slots), guns[].raised (the idle the clip starts and ends in), paths.

usage: prod.py list                               the clip plan
       prod.py build [--guns id,id] [--picks F02,..] [--clips reload,empty_reload] [--sides right,left]
                     [--bodies pma,pwa] [--out dir] [--jobs n]
       prod.py layout [--out dir]                 layout table of the built clips -> layout.json, layout.md
Output: <out>/<body>/<gun>_<side>_<pick><take>_<clip>.glb, .json (spec), _track.json, _gate.json
(out default: paths.rreload_clips).

A take is a parameter set (TAKES): a light gun builds take A, a heavy gun take B of the same generator.
The left hand is the same motion mirrored (x, yaw, roll) and rebuilt on the left arm with the left idle; stations on
the body are mirrored with it, the magazine axes are the gun's own (the gun mesh is not mirrored).
Stations are placed from the hips joint, low enough that the gun, the hand and the forearm leave the first-person
view: the script may fast-forward that part (layout hide_start..hide_end).
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, manifest
import numpy as np
import author, rlib, rlib2, magtrack2, magtrack3, timing, rarmset
from rlib import K
from fk import qrot
from glb import Glb
from fk import Clip

TAKES = {'A': {'w': 1.0, 'drag': 0.8, 'lag': 1, 'k': 1.0, 'a': 0.05}, 'B': {'w': 1.15, 'drag': 1.3, 'lag': 2, 'k': 1.4, 'a': 0.09}}
WEIGHT_TAKE = {'light': 'A', 'heavy': 'B'}
PUNCH = (1.5, 1.5)
# elbow reference of the IK (author.py pole_tilt): without it the elbow flipped to the other side in one frame where
# the hand dives to a station (2026-11-12: up to 177 deg per frame, one broken key after the WolvenKit import).
# The station angles (Ctx.natural) are still searched with the old reference, so the gun paths stay as approved.
POLE_TILT = 0.6
# stations: offset of the grip from the hips joint (x to the gun hand's side, y up, z back), and the gun angles the
# search starts from (well toward the body)
STATION = {'belt': ((0.285, 0.145, -0.06), (-55, -8, 6)), 'stomach': ((0.185, 0.16, -0.115), (-52, 8, 0)), 'hip': ((0.31, 0.165, -0.04), (-64, -14, 14)),
           'belt_wide': ((0.30, 0.15, -0.05), (-55, -8, 6)),
           'stomach_m': ((0.20, 0.17, -0.19), (-45, 8, 0))}      # Masamune: stomach rig further forward, the long barrel clears the belt block


# female V: the forearm stayed on screen at the belt station (right hand), the barrel at the stomach_m station (M12); the station sits this much lower
PWA_DROP = {'belt': -0.025, 'stomach_m': -0.025}


class Ctx(rlib.Ctx):
    """rlib.Ctx for either hand. For the left hand everything is authored as a right hand in the mirror image
    (g0, q0 mirrored); keys are mirrored back when the spec is written."""
    def __init__(self, gun, body, clip, params, side):
        super().__init__(gun, gun, body, clip, params); self.side = side
        if side == 'Left':
            self.g0 = self.gl0 * np.array([-1, 1, 1]); x, y, z, w = self.ql0; self.q0 = np.array([x, -y, -z, w])
        self.v = magtrack2.vanilla(gun, clip)
        self.hips = self.joint('Hips') * (np.array([-1, 1, 1]) if side == 'Left' else 1)

    def ax(self, a):
        a = np.asarray(a, float)
        return a * np.array([-1, 1, 1]) if self.side == 'Left' else a

    def along(self, rot, axis, d):
        return qrot(author.qmul(self.q0, author.qeuler(*rot)), self.ax(axis)) * d

    def station(self, name):
        off, hint = STATION[name]; off = np.array(off) + (PWA_DROP.get(name, 0) if self.body == 'pwa' else 0) * np.array([0, 1, 0])
        pos = self.off(self.hips + np.array(off)); rot = self.natural(pos, self.P.get(name + '_rot', hint), span=14, twist_w=0.15)
        return np.array(pos), rot


def L(P, n): return int(round(n * P['w']))


def seat_block(c, tl, pos, rot, arrive, se, d=0.13, slam=5, reb=0.012, via=None):
    """via: the way down curves through this offset (arc) instead of going straight."""
    P = c.P; pre = np.array(pos) + c.along(rot, c.v['enter'], d)
    if via is None: tl.to(arrive, pre, rot, 'heavy', antic=P['a'])
    else: arc(tl, arrive, via, pre, rot, 'heavy')
    tl.kick(arrive, c.along(rot, c.v['enter'], -0.006), (-2, 0, 0), release=2.5)
    tl.hold(se - slam); tl.to(se, pos, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], reb * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=3.0)
    tl.mark('arrive', arrive)


def finish(c, tl, hit, fwd=0.08):
    """After the seat: up; with a handle, bolt or latch frame `hit`: cocked back, punch that lands on it, settle."""
    P = c.P; se = c.T['seated']; tl.hold(se + 3)
    n = max(L(P, 7), int(round(float(np.linalg.norm(tl.p)) * 100 / 4.5 * P['w'])))      # about 5 cm/frame mean: peak 9 to 10
    if hit is None:
        e = se + 3 + n + 3; tl.to(e - 3, (0.02, -0.07, -0.04), (-8, 0, -2), 'rise', antic=P['a'] * 0.6); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0.003, 0.008 * P['k'], -0.008), (-1.5, 0, 0), release=3.0); return
    cf = se + 3 + n + 2; tl.to(cf - 3, (0.03, -0.085, -0.04), (-10, 0, -4), 'rise', antic=P['a'] * 0.6); tl.to(cf, (0.012, -0.022, 0.035), (0, 0, -4), 'settle')   # up in front, then back: the stock stays off the face; tl.kick(cf, (0, 0.012 * P['k'], -0.004), (-2, 0, 0), release=3.0)
    a, b = hit
    tl.hold(a); tl.to(b, (0, 0.02, -fwd), (1, 0, 0), PUNCH, rlag=0); tl.kick(b, (0, 0.004, 0.018 * P['k']), (5 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.mark('hit', b if c.P.get('_hit_at_stop') else a + 1)
    tl.hold(b + 3 + (1 if P['w'] > 1 else 0)); e = b + 3 + L(P, 8); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.004), (-1.5, 0, 0), release=3.0)


def hit_frames(c):
    """(punch start, punch stop) for the gun's handle, bolt or latch after the seat, or None.
    A handle that goes back (Copperhead, Sidewinder, Ajax) is thrown by the punch starting: start one frame before
    it. A bolt that runs forward (Masamune) or a latch that shuts (Hercules) is thrown by the punch stopping dead."""
    T = c.T; g = T['parts'].get('magazine_grabber', {}).get('window')
    if g: c.P['_hit_at_stop'] = True; return (g[1] - 4, g[1])
    h = T.get('handle')
    if not h: return None
    stays = any(p['stays_moved'] for p in T['parts'].values() if p['window'][0] >= T['seated'])
    if stays: c.P['_hit_at_stop'] = True; return (h[0] - 4, h[0])
    return (h[0] - 1, h[0] + 3)


def belt_knock(c, tl, station):
    """Ajax, Kyubi empty reload: the gun's own magazine lock opens late (f38) and the game's left hand knocks the old
    magazine out forward with the new one at f49. One-handed: straight down to the rig, the old magazine catches on
    the rig hook and the rifle is yanked back off it on that frame; it drops. The rifle moves over the fresh
    magazine standing beside it and is driven onto it. Up, cocked, punch on the handle frame."""
    P = c.P; T = c.T; o, se = T['out'], T['seated']; pos, rot = c.station(station); r = o - 2
    ex = np.array(c.v['exit']) * np.array([0, 1, 1]); ex /= np.linalg.norm(ex)     # straight out of the well in the gun's own plane, the same for either hand
    hook = pos
    tl.hold(4 + L(P, 2)); tl.to(tl.f + 3, (0, 0.02, 0), (4, 0, 0), 'ease'); a = tl.f + L(P, 9); tl.to(a, hook, rot, 'heavy'); tl.kick(a, (0, -0.01 * P['k'], 0), (-3, 0, 0), attack=0.5, release=2.5)
    tl.hold(r); off = hook - c.along(rot, ex, 0.17); tl.to(r + 4, off, rot, PUNCH, rlag=0); tl.kick(r + 4, c.along(rot, ex, 0.01), (2, 0, 0), release=2.5)
    tl.mark('release', r); tl.hold(r + 7)
    seat_block(c, tl, pos, rot, r + 7 + L(P, 6), se, d=0.12)
    finish(c, tl, hit_frames(c))
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 4, 'tumble': 4, 'appear': r + 7 + L(P, 6) + 2, 'seated': se, 'exit': [float(x) for x in ex]}}


def f02(c, tl):
    """Side flick, punch rack. Counter roll, a hard outward wrist roll that stops dead throws the magazine out
    sideways; down to the belt rig, driven onto the fresh magazine; up, cocked back, forward punch on the handle."""
    P = c.P; T = c.T; se = T['seated']
    if common.gun(c.gun).get('reload', {}).get('empty') == 'belt_knock' and c.clip == 'empty_reload': return belt_knock(c, tl, 'belt')
    r = min(T['out'] - 1, se - 38); R = P.get('roll', 85)
    tl.hold(r - 5 - L(P, 4)); tl.to(r - 5, (-0.02, -0.012, 0.0), (0, 4, -14), 'ease')
    tl.to(r, (0.085, 0.03, -0.01), (4, -12, R), 'drive', rlag=0); tl.kick(r, (0.01, 0, 0), (0, -3, -10 * P['k']), attack=0.5, release=2.5); tl.mark('release', r)
    tl.hold(r + 5); pos, rot = c.station('belt'); arr = r + 5 + L(P, 8); seat_block(c, tl, pos, rot, arr, se)
    finish(c, tl, hit_frames(c))
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.16, 'tumble': 9, 'appear': arr + 2, 'seated': se}}


def f09(c, tl):
    """Chest tuck. A short dip, the rifle is snapped upward and canted, the magazine stays behind and drops; pulled
    back and down to the stomach rig, pressed onto the fresh magazine; pushed out, cocked, short punch."""
    P = c.P; T = c.T; se = T['seated']
    if common.gun(c.gun).get('reload', {}).get('empty') == 'belt_knock' and c.clip == 'empty_reload': return belt_knock(c, tl, 'stomach')
    r = min(T['out'] - 3, se - 40)
    tl.hold(r - 3 - L(P, 3)); tl.to(r, (0.0, -0.035, 0.012), (-4, 0, -10), 'ease'); tl.mark('release', r)
    tl.to(r + 3, (0.02, 0.05, 0.0), (7, 0, -34), PUNCH, rlag=1); tl.kick(r + 3, (0, -0.012 * P['k'], 0), (-3, 0, 5), attack=0.5, release=2.5)
    tl.hold(r + 8); pos, rot = c.station('stomach'); arr = r + 8 + L(P, 8); seat_block(c, tl, pos, rot, arr, se, d=0.11, reb=0.008)
    finish(c, tl, hit_frames(c), fwd=0.07)
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.15, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


def shakes(c, tl, f0, R, base=(0.05, 0.03, -0.01), amp=(0.05, 0.075)):
    P = c.P; b = np.array(base); s1 = f0 + 2; tl.to(s1, b + (amp[0], 0, 0), (3, -12, R + 6), PUNCH, rlag=0); tl.to(s1 + 2, b, (3, -8, R - 3), PUNCH, rlag=0)
    tl.hold(s1 + 4 + (1 if P['w'] > 1 else 0)); s2 = tl.f + 2
    tl.to(s2, b + (amp[1], 0.005, 0), (3, -14, R + 9), PUNCH, rlag=0); tl.kick(s2, (-0.008, 0, 0), (0, 2, -6 * P['k']), attack=0.5, release=2.0)
    tl.to(s2 + 3, b, (3, -8, R - 4), 'settle'); tl.mark('loosen', s1); tl.mark('release', s2)
    return s1, s2


def m02(c, tl):
    """Shake loose, punch. Counter roll, rolled onto its side and jerked outward twice: loose, then thrown; down to
    the belt rig and onto the fresh magazine; up, cocked back, a punch that stops dead on the bolt frame."""
    P = c.P; T = c.T; se = T['seated']; R = P.get('roll', 78); o = T['out']
    tl.hold(o - 11 - L(P, 2)); tl.to(o - 7, (-0.02, -0.012, 0), (0, 4, -14), 'ease'); tl.to(o - 2, (0.05, 0.03, -0.01), (3, -8, R), 'drive', rlag=0)
    tl.kick(o - 2, (0.008, 0, 0), (0, -2, -8 * P['k']), attack=0.5, release=2.5); tl.hold(o)
    s1, s2 = shakes(c, tl, o, R); tl.hold(s2 + 6); pos, rot = c.station('belt_wide'); arr = s2 + 6 + L(P, 8); seat_block(c, tl, pos, rot, arr, se)
    finish(c, tl, hit_frames(c))
    return {'mag': {'release': s2, 'loosen': [[s1, 0.03]], 'mode': 'throw', 'slide': 3, 'travel': 0.17, 'tumble': 8, 'appear': arr + 2, 'seated': se}}


def m03(c, tl):
    """Hip slam, hip bump. A short lift, the rifle swings down to the hip rig and its magazine catches there; the
    rifle is ripped off it and the magazine drops; held over the fresh magazine, slammed onto it; the butt is
    knocked on the hip on the bolt frame; up."""
    P = c.P; T = c.T; se = T['seated']; r = T['out']; h = T.get('handle'); b = h[0] if h else None
    th, rot = c.station('hip')
    tl.hold(r - 10 - L(P, 3)); tl.to(r - 10, (0, 0.025, 0.0), (5, 0, 0), 'ease'); tl.to(r, th, rot, 'heavy'); tl.kick(r, (0, -0.008 * P['k'], 0), (-3, 0, 0), attack=0.5, release=2.5)   # 0.01: the hooked magazine left the well 1.52 cm off its axis
    tl.mark('release', r)
    up = th - c.along(rot, c.v['exit'], 0.17); tl.to(r + 5, up, rot, PUNCH, rlag=0); tl.kick(r + 5, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=3.0)
    tl.hold(r + 13); pre = th + c.along(rot, c.v['enter'], P.get('windup', 0.20)); tl.to(r + 13 + L(P, 5), pre, rot, 'ease')
    tl.hold(se - 5); tl.to(se, th, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], 0.02 * P['k']), (-5 * P['k'], 0, 0), attack=0.5, release=3.5)
    tl.hold(se + 5)
    if b:
        hb = th + np.array((-0.02, 0.03, -0.02)); hrot = [rot[0] + 12, rot[1] + 2, rot[2] + 2]
        tl.to(b - 4, hb, hrot, 'heavy'); tl.to(b, hb + (0.0, 0.0, 0.05), [hrot[0] + 4, hrot[1], hrot[2]], 'slam', rlag=0); tl.kick(b, (0, 0.004, -0.02 * P['k']), (-4 * P['k'], 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', b); tl.hold(b + 3)
    # rise target z -0.045 (was -0.03: the stock came 19.8 cm from the eye, female, right hand)
    e = tl.f + L(P, 13); tl.to(e - 3, (0.004, -0.03, -0.045), (-3, 0, 0), 'rise', antic=P['a']); tl.to(e + 2, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0.004, 0.008, -0.024), (-1.5, 0, 1), release=3.5)
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 5, 'tumble': 3, 'appear': r + 13 + L(P, 5) + 2, 'seated': se}}


def h02(c, tl):
    """Flip and shake, punch. A wrist flick that stops dead on the latch frame pops the latch; counter roll, rolled
    onto its left side and jerked outward twice: the cassette comes loose, then flies out; down to the belt rig and
    onto the fresh cassette; up, cocked back, a punch that stops dead on the latch frame shuts it."""
    P = c.P; T = c.T; se = T['seated']; g = T['parts'].get('magazine_grabber', {}).get('window', [19, 140]); Lf = g[0]; R = P.get('roll', 78); o = T['out']
    tl.hold(Lf - 7 - L(P, 2)); tl.to(Lf - 4, (0, -0.004, 0), (0, 0, 8), 'ease'); tl.to(Lf, (0.02, 0.02, 0), (3, -3, -30), 'drive', rlag=0)
    tl.kick(Lf, (0.008, 0.004, 0), (0, -2, -7 * P['k']), attack=0.5, release=2.5); tl.hold(Lf + 4); tl.to(Lf + 4 + L(P, 6), (0, 0, 0), (0, 0, 0), 'settle'); tl.mark('latch', Lf)
    tl.hold(o - 9 - L(P, 2)); tl.to(o - 5, (-0.02, -0.012, 0), (0, 4, -14), 'ease'); tl.to(o, (0.05, 0.03, -0.01), (3, -8, R), 'drive', rlag=0)
    tl.kick(o, (0.008, 0, 0), (0, -2, -8 * P['k']), attack=0.5, release=2.5); tl.hold(o + 2)
    s1, s2 = shakes(c, tl, o + 2, R); tl.hold(s2 + 6); pos, rot = c.station('belt_wide'); arr = s2 + 6 + L(P, 8); seat_block(c, tl, pos, rot, arr, se)
    finish(c, tl, hit_frames(c))
    return {'mag': {'release': s2, 'loosen': [[s1, 0.03]], 'mode': 'throw', 'slide': 3, 'travel': 0.18, 'tumble': 6, 'appear': arr + 2, 'seated': se}}


def exw(c, rot):
    """World direction of the well's exit axis with the gun at angles rot (either hand)."""
    return c.along(rot, c.v['exit'], 1.0)


def aligned(c, p0, r0, re, lam):
    """End position of a move from (p0, r0) to angles re that ends with the magazine centre travelling along the
    well's exit axis: the translation cancels the sideways part of the rotation's arc at the end of the move (a TL
    move interpolates position and angles with one profile, so the end velocity is translation plus the tangent of
    the rotation). lam: metres of the move along the axis. Used where the gun stops dead and the magazine flies on
    (magtrack3 'inertia'): it must leave along the well, not through its side."""
    m = c.ax((c.v['seat'] @ np.r_[c.v['centre'], 1])[:3]); r0, re = np.array(r0, float), np.array(re, float); dl = 0.02
    w = lambda r: qrot(author.qmul(c.q0, author.qeuler(*r)), m)
    return np.array(p0, float) + exw(c, re) * lam - (w(re) - w(re - dl * (re - r0))) / dl


def yank_rack(c, tl, h0):
    """After the seat: up, low and forward first (the stock stays off the face), into a pose held out in front, then
    yanked back toward the body and stopped dead on the lever frame h0: the lever runs on (a lever that goes back
    and returns, Copperhead, Sidewinder)."""
    P = c.P; tl.hold(c.T['seated'] + 2); f = h0 - 3
    tl.to(f - 3, (0.03, -0.085, -0.045), (-9, 0, -3), 'rise'); tl.to(f, (0.01, -0.045, -0.06), (-5, 0, -3), 'settle'); tl.kick(f, (0, 0.005 * P['k'], -0.002), (-1.5, 0, 0), release=2.5)
    tl.to(h0, (0.0, -0.03, 0.012), (3, 0, -2), 'slam', rlag=0); tl.kick(h0, (0, 0.003, -0.014 * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.mark('hit', h0); tl.hold(h0 + 3 + (1 if P['w'] > 1 else 0)); e = h0 + 3 + L(P, 9); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.004), (-1.5, 0, 0), release=3.0)


def f16(c, tl):
    """Muzzle-up shove. The muzzle is tipped up high and the rifle drawn in; then shoved forward and down along the
    well and stopped dead: the magazine shoots out forward and falls in front. Down to the belt rig onto the fresh
    magazine. Up, held out in front and yanked back: the stop throws the lever."""
    P = c.P; T = c.T; se = T['seated']
    if common.gun(c.gun).get('reload', {}).get('empty') == 'belt_knock' and c.clip == 'empty_reload': return belt_knock(c, tl, 'belt_wide')
    r = min(T['out'] - 1, se - 38); ru = (P.get('tip', 38), -4, -4); pu = np.array(P.get('drawn', (0.0, 0.03, 0.08)))
    tl.hold(r - 14); tl.to(r - 5, pu, ru, 'heavy', rlag=1); tl.hold(r - 4)
    e = exw(c, ru); tl.to(r, pu + e * P.get('shove', 0.12), ru, 'slam', rlag=0); tl.kick(r, -e * 0.012 * P['k'], (-3 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.hold(r + 3); tl.to(r + 9, (0.05, -0.12, 0.06), (-20, -6, 4), 'heavy')
    pos, rot = c.station('belt_wide'); arr = r + 9 + L(P, 7); seat_block(c, tl, pos, rot, arr, se)
    h = T.get('handle'); lever = h and not T['parts'].get('magazine_grabber') and not any(p['stays_moved'] for p in T['parts'].values() if p['window'][0] >= se)
    if lever: yank_rack(c, tl, h[0])
    elif h: finish(c, tl, hit_frames(c))
    else:     # no lever (reload): as finish, the via point 1.5 cm lower and further out (Sidewinder, female: eye 20.1 cm)
        tl.hold(se + 3); n = max(L(P, 7), int(round(float(np.linalg.norm(tl.p)) * 100 / 4.5 * P['w']))); e = se + 3 + n + 3
        tl.to(e - 3, (0.02, -0.085, -0.055), (-8, 0, -2), 'rise', antic=P['a'] * 0.6); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0.003, 0.008 * P['k'], -0.008), (-1.5, 0, 0), release=3.0)
    return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.005, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


# ---------------------------------------------------------------- Masamune, round 3 picks (from masa3.py)
READY = {'yank': ((0.004, -0.008, -0.045), (2, 0, -2)), 'nod': ((0.004, 0.006, 0.0), (9, 0, -2)), 'thumb': ((0.0, -0.006, 0.006), (-1, 0, 4)), None: ((0, 0, 0), (0, 0, 0))}


def bolt(c):
    """The bolt frame of this clip, or None (reload clip: no bolt)."""
    h = c.T.get('handle')
    return h[0] if h else None


def rise_time(c, tl):
    P = c.P; return max(L(P, 7), int(round(float(np.linalg.norm(tl.p)) * 100 / 4.6 * P['w'])))


def finish3(c, tl, kind):
    """After the seated frame: one decisive rise from the station into a ready pose (the muzzle comes up first, so
    the long stock swings away from the torso), dead stop with a rebound; on the empty reload the bolt hit of `kind`
    lands on the bolt frame; settle into the idle."""
    P = c.P; se = c.T['seated']; b = bolt(c); tl.hold(se + 2); n = rise_time(c, tl)
    if b is None: kind = None
    end = se + 2 + n if b is None else min(se + 2 + n, b - 6); pos, rot = READY[kind]
    tl.to(end, pos, rot, 'drive', antic=P['a'] * 0.8, rprof='settle'); tl.kick(end, (0, 0.010 * P['k'], -0.004), (-2, 0, 0), attack=0.5, release=3.0)
    if kind is None: return
    if kind == 'yank':
        tl.hold(b); tl.to(b + 3, (0.0, 0.006, 0.035), (-3, 0, 1), (1.25, 2.6), rlag=0)            # sharp start on the bolt frame: the bolt lags, runs home
        tl.kick(b, (0, 0.002, 0.012 * P['k']), (-2.5 * P['k'], 0, 0), attack=0.5, release=2.0); tl.kick(b + 3, (0, -0.002, -0.006 * P['k']), (1.5, 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', b); tl.hold(b + 4 + (1 if P['w'] > 1 else 0)); e = b + 4 + L(P, 8); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.003), (-1, 0, 0), release=3.0)
    elif kind == 'nod':
        tl.hold(b - 4); tl.to(b, (0.0, -0.012, -0.012), (-16, 0, 0), PUNCH, rlag=0)                 # muzzle snapped down, dead stop on the bolt frame
        tl.kick(b, (0, 0.004, 0.004), (5 * P['k'], 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', b); tl.hold(b + 4 + (1 if P['w'] > 1 else 0)); e = b + 4 + L(P, 8); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.003, 0.003), (-1, 0, 0), release=3.0)
    elif kind == 'thumb':
        tl.hold(b); tl.kick(b, (0, 0.006 * P['k'], -0.012 * P['k']), (-3 * P['k'], 0, 1), attack=0.5, release=2.5)   # the bolt slams home: the rifle jumps
        tl.mark('hit', b); e = b + 3 + L(P, 8); tl.hold(b + 3); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')
    else: raise ValueError(kind)


def m11(c, tl):
    """Nod throw, yank. The muzzle is cocked up a little, then snapped down and stopped dead: the magazine is thrown
    out of the well along its own axis and falls. Down to the belt rig and onto the fresh magazine. Up, held a
    little forward, and jerked back toward the body on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 20
    tl.hold(r - 5 - L(P, 4)); tl.to(r - 5, (0.0, 0.018, 0.012), (10, 0, -4), 'ease')
    tl.to(r, (0.01, -0.11, 0.02), (-40, -4, 6), 'drive', rlag=0); tl.kick(r, (0, 0.012 * P['k'], 0), (6 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('release', r - 1)   # tips over a point near the butt: the grip drops, the stock stays low
    tl.hold(r + 5); pos, rot = c.station('belt'); arr = r + 5 + L(P, 7); seat_block(c, tl, pos, rot, arr, se)
    finish3(c, tl, 'yank')
    return {'mag': {'release': r - 1, 'mode': 'throw', 'slide': 3, 'travel': 0.17, 'tumble': 7, 'appear': arr + 2, 'seated': se}}


def m12(c, tl):
    """Heave, nod. A short dip, then the rifle is heaved up and forward and stops dead: the heavy magazine stays
    behind and drops out. Pulled back to the stomach rig and pressed onto the fresh one. Up, and the muzzle is
    snapped down on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 19
    tl.hold(r - 4 - L(P, 3)); tl.to(r, (0.0, -0.045, 0.015), (-6, 0, -6), 'ease'); tl.mark('release', r)
    tl.to(r + 4, (0.015, 0.06, -0.05), (10, 0, -22), PUNCH, rlag=1); tl.kick(r + 4, (0, -0.016 * P['k'], 0), (-3, 0, 5), attack=0.5, release=2.5)
    tl.hold(r + 9); pos, rot = c.station('stomach_m'); arr = r + 9 + L(P, 8); seat_block(c, tl, pos, rot, arr, se, d=0.12, reb=0.009)
    finish3(c, tl, 'nod')
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.15, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


def m20(c, tl):
    """Corkscrew. A counter roll, then one heavy move down and out that rolls the rifle onto its side and stops dead:
    the magazine is flung out and down. Straight on to the belt rig and onto the fresh one. Up; the thumb drops the
    bolt and the rifle jolts on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 21
    tl.hold(r - 4 - L(P, 4)); tl.to(r - 4, (-0.015, 0.015, 0.0), (4, 4, -16), 'ease')
    tl.to(r, (0.07, -0.08, 0.03), (-12, -10, 80), 'slam', rlag=1); tl.kick(r, (0.01, 0.006, 0), (0, 0, -7 * P['k']), attack=0.5, release=2.5); tl.mark('release', r - 1)
    tl.hold(r + 5); pos, rot = c.station('belt'); arr = r + 5 + L(P, 7); seat_block(c, tl, pos, rot, arr, se)
    finish3(c, tl, 'thumb')
    return {'mag': {'release': r - 1, 'mode': 'throw', 'slide': 3, 'travel': 0.17, 'tumble': 8, 'appear': arr + 2, 'seated': se}}


# ---- Hercules round 3 picks (side cassette: latch opens f19 and shuts f140, seated f116; one clip for reload and
# empty reload). Every pick stops dead on the latch frames. Drafts, frames and review: anim-work/rifle-reloads/round3-hercules.

def arc(tl, f, via, pos, rot, prof='drive', rlag=None, rprof=None):
    """tl.to along a curve: a quadratic Bezier from the current pose through the pull of `via` to `pos`."""
    f = int(f); pos = np.array(pos, float); rot = np.array(rot, float); via = np.array(via, float); f0 = tl.f; p0, r0 = tl.p.copy(), tl.r.copy()
    a, b = rlib2.PROFILES[prof] if isinstance(prof, str) else prof; n = f - f0; s = rlib2.beta_cdf(a, b, n)
    for k in range(n + 1): u = s[k]; tl.P[f0 + k] = (1 - u) ** 2 * p0 + 2 * u * (1 - u) * via + u * u * pos
    tl.P[f:] = pos; rl = int(round(tl.lag if rlag is None else rlag))
    tl._fill(tl.R, max(f0 + rl // 2, tl.rf if tl.rf > f0 else f0), f + rl, r0, rot, rprof or prof)
    tl.f = f; tl.p = pos; tl.r = rot; tl.rf = f + rl
    return tl


def hframes(c):
    """(latch opens, latch shuts, seated) of the gun's own clip."""
    g = c.T['parts'].get('magazine_grabber', {}).get('window', [19, 140])
    return g[0], g[1], c.T['seated']


# latch openers: (counter pose, pose on the latch frame, rebound kick); each stops dead on the latch frame
HOPEN = {'jolt': (((0, 0.012, 0.004), (3, 0, 0)), ((0, -0.035, 0), (-5, 0, 0)), ((0, 0.008, 0), (2, 0, 0))),
         'thrust': (((0, 0, 0.012), (1, 0, 0)), ((0, 0.006, -0.04), (-2, 0, 0)), ((0, 0, 0.01), (2, 0, 0))),
         'cant': (((0, 0, 0), (0, 0, 6)), ((0.01, -0.006, 0), (0, 0, -24)), ((0, 0, 0), (0, 0, 4)))}


def open_latch(c, tl, kind):
    P = c.P; Lf = hframes(c)[0]; k = P['k']; (cp, cr), (tp, tr), (kp, kr) = HOPEN[kind]
    tl.hold(Lf - 6 - L(P, 3)); tl.to(Lf - 4, cp, cr, 'ease'); tl.to(Lf, tp, tr, 'drive', rlag=0)
    tl.kick(Lf, np.array(kp) * k, np.array(kr) * k, attack=0.5, release=2.5); tl.mark('latch', Lf)
    tl.hold(Lf + 4); tl.to(Lf + 4 + L(P, 7), (0, 0, 0), (0, 0, 0), 'settle')


def peak_mag(c, tl, f0, f1):
    """Frame in f0..f1 at which the seated magazine's centre moves fastest (timeline without the muzzle drag): the gun
    brakes after it, so a loose magazine released there flies on (magtrack3 'inertia')."""
    cen = c.ax((c.v['seat'] @ np.r_[c.v['centre'], 1])[:3]); pts = []
    for f in range(f0 - 1, f1 + 1): pts.append(tl.P[f] + qrot(author.qmul(c.q0, author.qeuler(*tl.R[f])), cen))
    return f0 + int(np.argmax(np.linalg.norm(np.diff(np.array(pts), axis=0), axis=1)))


def settle_in(c, tl, f):
    P = c.P; tl.hold(f); e = f + L(P, 9); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.004), (-1.5, 0, 0), release=3.0)


def rise_to(c, tl, f, pos, rot):
    """From a muzzle-down station back into view, arriving at f. The muzzle comes up a little ahead of the hand (no
    rotation lag, earlier profile peak): with the rotation trailing, the stock swung up through the lower view."""
    P = c.P; tl.to(f, pos, rot, 'rise', antic=P['a'] * 0.6, rlag=0, rprof='snap'); tl.kick(f, (0, 0.006 * P['k'], -0.003), (-1.5, 0, 0), release=2.5)


def h13(c, tl):
    """Hammer drop, uppercut. A short downward jolt pops the latch. The rifle is wound up (muzzle up) and hammered
    down along the cassette's own axis, stopping dead in mid-air: the loose cassette flies on out of the bottom and
    falls. Down to the belt rig and onto the fresh cassette. From the belt an uppercut that stops dead above the idle
    on the latch frame shuts it; it settles."""
    P = c.P; Lf, C, se = hframes(c); k = P['k']; ex = c.v['exit']
    open_latch(c, tl, 'jolt')
    hrot = (-6, 0, 0); drop = np.array(P.get('stop', (0.0, -0.02, 0.02))); wu = drop - c.along(hrot, ex, P.get('drop', 0.15))   # hammered along the well axis
    w = 41; tl.hold(w - L(P, 9)); tl.to(w, wu, (14, 0, -3), 'rise', antic=P['a'] * 0.5); tl.hold(w + 2); s = w + 2 + L(P, 5)
    tl.to(s, drop, hrot, 'slam', rlag=0); tl.kick(s, -c.along(hrot, ex, 0.012 * k), (3 * k, 0, 0), attack=0.5, release=2.5)
    r = peak_mag(c, tl, w + 3, s); tl.mark('release', r)
    tl.hold(s + 7); bp, rot = c.station('belt_wide'); arr = s + 7 + L(P, 6); seat_block(c, tl, bp, rot, arr, se)
    tl.hold(C - L(P, 9)); tl.to(C, (0.006, 0.04, -0.014), (8, 0, -2), 'slam', rlag=0); tl.kick(C, (0, -0.008 * k, 0.002), (-3 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', C)
    settle_in(c, tl, C + 3 + (1 if P['w'] > 1 else 0))
    return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.0, 'tumble': 4, 'appear': arr + 2, 'seated': se}}


def h14(c, tl):
    """Up-snap, cant snap. A short forward thrust pops the latch. Counter dip with the muzzle tipped up, then the
    rifle is ripped straight up off the cassette: the cassette stays where it was and drops. Down to the stomach rig
    and pressed onto the fresh cassette. Up into view canted outward, then snapped upright, dead stop on the latch
    frame: it shuts. The muzzle tilt makes the snap run straight up (the rear stays lower) and lines gravity up with
    the well; the way down curves down first: going straight back to the rig, the rear of the rifle filled the lower
    right of the view for 8 frames (cover 9.3 %, now 7.1 % for 4 frames)."""
    P = c.P; Lf, C, se = hframes(c); k = P['k']; ex = c.v['exit']; tilt = P.get('tilt', 14); n = P.get('snap_f', 3)
    open_latch(c, tl, 'thrust')
    r = 46; tl.hold(r - 5 - L(P, 2)); d0 = np.array(P.get('dip', (0, -0.03, 0.006))); r0 = (tilt, 0, 0); tl.to(r, d0, r0, 'ease'); tl.mark('release', r)
    up = d0 - c.along(r0, ex, P.get('snap', 0.10)); tl.to(r + n, up, r0, PUNCH, rlag=0); tl.kick(r + n, (0, -0.008 * k, 0), (-2 * k, 0, 0), attack=0.5, release=2.5); tl.nodrag.append((r - 1, r + n + 2))
    tl.hold(r + n + P.get('top_hold', 1)); sp, rot = c.station('stomach'); arr = tl.f + L(P, 7)
    seat_block(c, tl, sp, rot, arr, se, d=0.11, reb=0.008, via=P.get('dive_via', (0.03, -0.18, -0.01)))   # down first, away from the camera
    tl.hold(C - 6 - L(P, 8)); rise_to(c, tl, C - 6, (0.016, -0.01, -0.004), (2, 0, -28)); tl.hold(C - 4)
    tl.to(C, (0, 0.004, 0), (0, 0, 5), PUNCH, rlag=0); tl.kick(C, (0, 0.002, 0), (0, 0, -3 * k), attack=0.5, release=2.5); tl.mark('hit', C)
    settle_in(c, tl, C + 3 + (1 if P['w'] > 1 else 0))
    return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.0, 'tumble': 2, 'appear': arr + 2, 'seated': se}}


def h16(c, tl):
    """Two chops. A short outward cant pops the latch. The muzzle is raised, then chopped down and back and stopped
    dead: the loose cassette flies on out of the bottom, along the well. Down to the hip rig and onto the fresh
    cassette. Up into view muzzle high, a second chop stops dead on the latch frame: it shuts."""
    P = c.P; Lf, C, se = hframes(c); k = P['k']
    open_latch(c, tl, 'cant')
    w = 42; tl.hold(w - L(P, 9)); tl.to(w, P.get('chop_from', (0.0, 0.07, -0.05)), (22, 0, -3), 'rise', antic=P['a'] * 0.5); tl.hold(w + 2)
    s = w + 2 + L(P, 4); tl.to(s, P.get('chop_pos', (0.0, 0.01, 0.065)), (-20, 0, 0), 'slam', rlag=0); tl.kick(s, (0, 0.006 * k, 0), (4 * k, 0, 0), attack=0.5, release=2.5)
    r = peak_mag(c, tl, w + 3, s); tl.mark('release', r); tl.nodrag.append((w + 1, s + 2))   # the chop also moves back: the cassette leaves along the well
    tl.hold(s + 7); hp, rot = c.station('hip'); arr = s + 7 + L(P, 6); seat_block(c, tl, hp, rot, arr, se)
    tl.hold(C - 6 - L(P, 8)); rise_to(c, tl, C - 6, (0.0, 0.025, 0.01), (20, 0, -3)); tl.hold(C - 4)
    tl.to(C, (0, -0.012, 0.0), (-5, 0, 0), PUNCH, rlag=0); tl.kick(C, (0, 0.006 * k, 0), (3 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', C)
    settle_in(c, tl, C + 3 + (1 if P['w'] > 1 else 0))
    return {'mag': {'release': r, 'mode': 'inertia', 'push': 0.0, 'tumble': 4, 'appear': arr + 2, 'seated': se}}


PICKS = {'F02': ('Side flick, punch rack', f02), 'F09': ('Chest tuck', f09), 'F16': ('Muzzle-up shove', f16), 'M02': ('Shake loose, punch', m02), 'M03': ('Hip slam, hip bump', m03), 'H02': ('Flip and shake, punch', h02),
         'M11': ('Nod throw, yank', m11), 'M12': ('Heave, nod', m12), 'M20': ('Corkscrew', m20)}
PICKS.update({'H13': ('Hammer drop, uppercut', h13), 'H14': ('Up-snap, cant snap', h14), 'H16': ('Two chops', h16)})   # Hercules round 3
MIR_P = np.array([-1, 1, 1]); MIR_R = np.array([1, -1, -1])


def owners():
    """Guns that own a model variable and have reload slots: [(gun id, reload entry)]."""
    return [(g['id'], g['reload']) for g in manifest.guns(all_=True) if g.get('reload', {}).get('slots')]


def clips_of(gid):
    """Gun clips to build: reload and empty_reload; one when the gun's own clips are the same (Hercules)."""
    a, b = timing.table(gid, 'reload'), timing.table(gid, 'empty_reload')
    same = a['frames'] == b['frames'] and a['out'] == b['out'] and a['seated'] == b['seated'] and a.get('handle') == b.get('handle')
    return ['reload'] if same else ['reload', 'empty_reload']


def plan(guns=None, picks=None, clips=None, sides=None, bodies=None):
    out = []
    for gid, r in owners():
        if guns and gid not in guns: continue
        for pick in r['picks']:
            if picks and pick not in picks: continue
            for clip in clips_of(gid):
                if clips and clip not in clips: continue
                for body in (bodies or manifest.bodies()):
                    for side in (sides or ('right', 'left')): out.append((gid, pick, WEIGHT_TAKE[r['weight']], clip, side, body))
    return out


def stem(gid, pick, take, clip, side): return f'{gid}_{side}_{pick}{take}_{clip}'


def build(gid, pick, take, clip, side, body, out=None, quiet=False):
    import rgate
    out = out or manifest.path('rreload_clips'); d = f'{out}/{body}'; os.makedirs(d, exist_ok=True); name = stem(gid, pick, take, clip, side)
    S = side.capitalize(); P = dict(TAKES[take]); c = Ctx(gid, body, clip, P, S); tl = rlib2.TL(c, P['lag'], P['drag']); m = PICKS[pick][1](c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    if S == 'Left':
        Pk = Pk * MIR_P; Rk = Rk * MIR_R
        for k in kicks: k['move'] = list(np.array(k['move'], float) * MIR_P); k['rot'] = list(np.array(k['rot'], float) * MIR_R)
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {take}', '_doc': ' '.join((PICKS[pick][1].__doc__ or '').split()), '_gun': gid, '_left_gun': gid, '_body': body, '_side': S,
            '_gun_clip': clip, '_pick': pick, '_take': take, '_timing': c.T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False, '_round': 3,
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, ('Left' if S == 'Right' else 'Right'): [K(0)]},
            'shakes': {S: kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': POLE_TILT, 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); G = [cl.world(f)[i] for f in range(c.N)]
    track = magtrack3.build(gid, clip, [(np.array(t), np.array(q)) for t, q in G], m['mag']); spec['_track'] = f'{d}/{name}_track.json'
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, rgate.line(o), flush=True)
    return spec, o


def layout(out=None):
    """Layout per gun, pick and clip: the window every hand and body shares (latest hide_start, earliest hide_end)."""
    out = out or manifest.path('rreload_clips'); lay = {}; rows = []; fails = []
    for gid, pick, take, clip, side, body in plan():
        p = f'{out}/{body}/{stem(gid, pick, take, clip, side)}_gate.json'
        if not os.path.exists(p): fails.append(f'missing {p}'); continue
        o = json.load(open(p)); Lr = o['layout']; Lr['keys'] = rarmset.good_keys(Lr['length']); e = lay.setdefault(gid, {}).setdefault(pick + take, {}).setdefault(clip, dict(Lr))
        if Lr['hide_start'] is None or e['hide_start'] is None: e['hide_start'] = e['hide_end'] = None
        else: e['hide_start'] = max(e['hide_start'], Lr['hide_start']); e['hide_end'] = min(e['hide_end'], Lr['hide_end'])
        if o['fails']: fails.append(f"{body} {o['clip']}: {o['fails']}")
    for gid, r in owners():
        for pick in r['picks']:
            if len(clips_of(gid)) == 1 and gid in lay: lay[gid][pick + WEIGHT_TAKE[r['weight']]]['empty_reload'] = lay[gid][pick + WEIGHT_TAKE[r['weight']]]['reload']
    json.dump(lay, open(f'{out}/layout.json', 'w'), indent=1)
    Ls = ['| gun | pick | clip | hide_start | hide_end | mag_out | seated | handle | length | keys |', '|---|---|---|---|---|---|---|---|---|---|']
    for gid in lay:
        for pk in lay[gid]:
            for clip, e in lay[gid][pk].items(): Ls.append(f"| {gid} | {pk} | {clip} | {e['hide_start']} | {e['hide_end']} | {e['mag_out']} | {e['seated']} | {e['handle']} | {e['length']} | {e['keys']} |")
    open(f'{out}/layout.md', 'w').write('\n'.join(Ls) + '\n'); open(f'{out}/gate_fails.txt', 'w').write('\n'.join(fails) + '\n')
    print('\n'.join(Ls)); print(len(fails), 'clips with failures or missing')
    return lay


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None
    guns, picks, clips, sides, bodies, out, jobs = cs(o('--guns')), cs(o('--picks')), cs(o('--clips')), cs(o('--sides')), cs(o('--bodies')), o('--out'), int(o('--jobs') or 1)
    cmd = argv[0] if argv else 'list'; pl = plan(guns, picks, clips, sides, bodies)
    if cmd == 'list':
        for p in pl: print(*p)
        print(len(pl), 'clips')
    elif cmd == 'regate':
        import rgate
        for gid, pick, take, clip, side, body in pl:
            p = f"{out or manifest.path('rreload_clips')}/{body}/{stem(gid, pick, take, clip, side)}"
            o = rgate.gate(p + '.json'); json.dump(o, open(p + '_gate.json', 'w'), indent=1); print(body, rgate.line(o), flush=True)
    elif cmd == 'layout': layout(out)
    elif cmd == 'build':
        if jobs > 1:
            procs = []
            for k in range(jobs):
                part = pl[k::jobs]
                if not part: continue
                a = [sys.executable, os.path.abspath(__file__), '_part', json.dumps(part)] + (['--out', out] if out else [])
                procs.append(subprocess.Popen(a))
            for p in procs: p.wait()
        else:
            for p in pl: build(*p, out=out)
    elif cmd == '_part':
        for p in json.loads(argv[1]): build(*p, out=out)
