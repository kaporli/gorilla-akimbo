"""Round 3: more one-handed reloads for the Hercules 3AX (side cassette, latch opens f19 and shuts f140, cassette
seated f116, 186 frames, one clip for reload and empty reload). Heavy gun: take B (prod.TAKES['B']).

Every draft is a prod-style generator gen(c, tl) -> {'mag': plan} on rlib2 timelines (Beta-profile moves, counter
moves, dead stops with rebound kicks, rotation trailing translation) with an own magazine track (magtrack3: the
magtrack2 modes plus 'inertia', a loose cassette that keeps the velocity and spin the gun gave it). Each draft is
different from H02 (latch flick, two shakes throw the cassette, belt slam, punch shuts the latch) in how the latch
opens, how the cassette leaves, where the fresh one stands and how the latch shuts.

usage: herc3.py list
       herc3.py build [ids csv] [--sides right] [--bodies pma] [--out dir] [--jobs n]
       herc3.py stats [ids csv] [--out dir]        motionstats of each draft beside the approved clips -> stats.json, .txt, .png
Output: <out>/<body>/hercules_<side>_<id>B_reload.glb, .json, _track.json, _gate.json (out default
<OUT>/clips, OUT = renv.OUT). File names as prod.py, so a pick can be copied into production unchanged.

To merge a pick: put its generator (and the helpers it uses: frames, stn, HST, open_latch, arc, peak_mag) into
prod.py, add it to prod.PICKS, and make prod.build call magtrack3.build instead of magtrack2.build (same result
for the old picks: magtrack3 hands every mode but 'inertia' to magtrack2).
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, rlib2, prod, magtrack3
from rlib import K
from prod import L, PUNCH, seat_block
from fk import qrot
from glb import Glb
from fk import Clip

OUT = renv.OUT + '/clips'
GUN = 'hercules'; TAKE = 'B'; CLIP = 'reload'
# stations: offset of the grip from the hips joint (x to the gun hand's side, y up, z back), the angles the wrist
# search starts from (prod.STATION plus a thigh station)
HST = dict(prod.STATION)
HST.update({'thigh': ((0.30, 0.13, -0.07), (-78, -8, 10))})


def frames(c):
    """(latch opens, latch shuts, seated) of the gun's own clip."""
    g = c.T['parts'].get('magazine_grabber', {}).get('window', [19, 140])
    return g[0], g[1], c.T['seated']


def stn(c, name):
    off, hint = HST[name]; off = np.array(off) + (prod.PWA_DROP.get(name, 0) if c.body == 'pwa' else 0) * np.array([0, 1, 0])
    pos = c.off(c.hips + off); rot = c.natural(pos, c.P.get(name + '_rot', hint), span=14, twist_w=0.15)
    return np.array(pos), rot


class TL(rlib2.TL):
    """rlib2.TL with windows without muzzle drag: while the gun is pulled off a hooked cassette the well must stay on
    the cassette's axis, so the drag (a rotation from the speed) is left out there."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.nodrag = []

    def arrays(self):
        P, R = super().arrays(); R0 = self.R.copy(); R0[-1] = 0
        for f0, f1 in self.nodrag: R[max(f0, 0):min(f1 + 1, self.N)] = R0[max(f0, 0):min(f1 + 1, self.N)]
        return P, R


def hook_off(c, tl, r, pos, rot, d=0.17, n=5):
    """The cassette is caught at frame r; the gun is pulled off it straight along the well over n frames."""
    P = c.P; ex = c.v['exit']; tl.kick(r, (0, -0.008 * P['k'], 0), (0, 0, 0), attack=0.5, release=2.5); tl.mark('release', r)
    up = pos - c.along(rot, ex, d); tl.to(r + n, up, rot, PUNCH, rlag=0); tl.kick(r + n, c.along(rot, ex, 0.01), (2, 0, 0), release=3.0); tl.nodrag.append((r - 2, r + n + 1))


def arc(tl, f, via, pos, rot, prof='drive', rlag=None, rprof=None):
    """tl.to along a curve: quadratic Bezier from the current pose through the pull of `via` to `pos`."""
    f = int(f); pos = np.array(pos, float); rot = np.array(rot, float); via = np.array(via, float); f0 = tl.f; p0, r0 = tl.p.copy(), tl.r.copy()
    a, b = rlib2.PROFILES[prof] if isinstance(prof, str) else prof; n = f - f0; s = rlib2.beta_cdf(a, b, n)
    for k in range(n + 1): u = s[k]; tl.P[f0 + k] = (1 - u) ** 2 * p0 + 2 * u * (1 - u) * via + u * u * pos
    tl.P[f:] = pos; rl = int(round(tl.lag if rlag is None else rlag))
    tl._fill(tl.R, max(f0 + rl // 2, tl.rf if tl.rf > f0 else f0), f + rl, r0, rot, rprof or prof)
    tl.f = f; tl.p = pos; tl.r = rot; tl.rf = f + rl
    return tl


def peak_mag(c, tl, f0, f1):
    """Frame in f0..f1 at which the seated cassette's centre moves fastest (timeline without the muzzle drag): the
    frame after it the gun brakes, so a loose cassette released there flies on."""
    v = c.v; cen = (v['seat'] @ np.r_[v['centre'], 1])[:3]; pts = []
    for f in range(f0 - 1, f1 + 1):
        q = author.qmul(c.q0, author.qeuler(*tl.R[f])); pts.append(c.g0 + tl.P[f] + qrot(q, cen))
    sp = np.linalg.norm(np.diff(np.array(pts), axis=0), axis=1)
    return f0 + int(np.argmax(sp))


# latch openers: (counter pose, pose at the latch frame, rebound kick); every one stops dead on the latch frame
OPEN = {'tug': (((0, -0.004, -0.012), (-2, 0, 0)), ((0, 0.006, 0.035), (4, 0, 0)), ((0, 0, -0.008), (-2, 0, 0))),
        'tip': (((0, -0.006, 0), (-4, 0, 0)), ((0, 0.012, 0.006), (14, 0, -2)), ((0, -0.004, 0), (-4, 0, 0))),
        'jolt': (((0, 0.012, 0.004), (3, 0, 0)), ((0, -0.035, 0), (-5, 0, 0)), ((0, 0.008, 0), (2, 0, 0))),
        'thrust': (((0, 0, 0.012), (1, 0, 0)), ((0, 0.006, -0.04), (-2, 0, 0)), ((0, 0, 0.01), (2, 0, 0))),
        'whip': (((-0.01, 0, 0), (0, 5, 0)), ((0.035, 0.004, 0), (0, -14, -4)), ((-0.008, 0, 0), (0, 3, 0))),
        'cant': (((0, 0, 0), (0, 0, 6)), ((0.01, -0.006, 0), (0, 0, -24)), ((0, 0, 0), (0, 0, 4))),
        'thumb': (((0, 0.003, 0), (1, 0, 2)), ((0, -0.008, 0.004), (-3, 0, -6)), ((0, 0.003, 0), (1, 0, 2)))}


def open_latch(c, tl, kind):
    P = c.P; Lf = frames(c)[0]; k = P['k']; (cp, cr), (tp, tr), (kp, kr) = OPEN[kind]
    tl.hold(Lf - 6 - L(P, 3)); tl.to(Lf - 4, cp, cr, 'ease'); tl.to(Lf, tp, tr, 'drive', rlag=0)
    tl.kick(Lf, np.array(kp) * k, np.array(kr) * k, attack=0.5, release=2.5); tl.mark('latch', Lf)
    tl.hold(Lf + 4); tl.to(Lf + 4 + L(P, 7), (0, 0, 0), (0, 0, 0), 'settle')


def settle(c, tl, f):
    P = c.P; tl.hold(f); e = f + L(P, 9); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.004), (-1.5, 0, 0), release=3.0)


def rise_to(c, tl, f, pos, rot):
    """From a station back into view, arriving at f (a 'rise' with a little anticipation). The muzzle comes up a
    little ahead of the hand (rotation profile peaks earlier, no lag): with the rotation trailing, the stock of a gun
    coming up from a muzzle-down station swung up through the lower view, large."""
    P = c.P; tl.to(f, pos, rot, 'rise', antic=P['a'] * 0.6, rlag=0, rprof='snap'); tl.kick(f, (0, 0.006 * P['k'], -0.003), (-1.5, 0, 0), release=2.5)


def end_rise(c, tl, n=11, via=None):
    """From a low station back into the idle: a driven rise that peaks past its middle, stops just short of the idle
    (gun a little forward, so the stock stays off the face) and settles in."""
    P = c.P; k = P['k']; e = tl.f + L(P, n); tgt, rot = (0.004, -0.014, -0.03), (-2, 0, 0)
    if via is not None: arc(tl, e, via, tgt, rot, 'drive', rlag=0, rprof='snap')
    else: tl.to(e, tgt, rot, 'drive', antic=P['a'] * 0.6, rlag=0, rprof='snap')
    tl.kick(e, (0, 0.006 * k, -0.006), (-1.5, 0, 0), attack=0.6, release=2.5); tl.hold(e + 1); f = e + 1 + L(P, 6); tl.to(f, (0, 0, 0), (0, 0, 0), 'settle')
    tl.kick(f, (0, -0.003, 0.003), (-1, 0, 0), release=3.0)


def hip_bump_close(c, tl, th, rot):
    """The rifle's butt is knocked back on the hip on the latch frame (out of view); then up."""
    P = c.P; C = frames(c)[1]; hb = th + np.array((-0.02, 0.03, -0.02)); hrot = [rot[0] + 12, rot[1] + 2, rot[2] + 2]
    tl.to(C - 4, hb, hrot, 'heavy'); tl.to(C, hb + (0.0, 0.0, 0.05), [hrot[0] + 4, hrot[1], hrot[2]], 'slam', rlag=0)
    tl.kick(C, (0, 0.004, -0.02 * P['k']), (-4 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('hit', C); tl.hold(C + 3); end_rise(c, tl)


# ---------------------------------------------------------------------------------------------------------------- drafts

def h11(c, tl):
    """Belt dip. Quick and plain: the rifle goes straight down to the belt rig and stops dead there on the latch
    frame (the rig knocks the latch open), the cassette catches on the rig and the rifle is pulled up off it, then
    driven onto the fresh cassette; knocked down on the rig edge on the latch frame (shuts it), up. All of it below
    the view: in game a dip and a rise."""
    P = c.P; Lf, C, se = frames(c); ex = c.v['exit']; bp, rot = stn(c, 'belt_wide')
    tl.hold(8); tl.to(12, (0, 0.02, 0.0), (4, 0, 0), 'ease'); tl.to(Lf, bp, rot, 'heavy'); tl.kick(Lf, (0, -0.01 * P['k'], 0), (-3, 0, 0), attack=0.5, release=2.5); tl.mark('latch', Lf)
    r = 34; tl.hold(r); hook_off(c, tl, r, bp, rot, 0.16, 4)
    tl.hold(r + 12); seat_block(c, tl, bp, rot, r + 12 + L(P, 6), se, d=0.13)
    tl.hold(se + 6); kn = bp + c.along(rot, c.v['enter'], 0.07); tl.to(C - 5, kn, [rot[0] + 4, rot[1], rot[2]], 'ease'); tl.to(C, bp + c.along(rot, c.v['enter'], 0.01), rot, 'slam', rlag=0)
    tl.kick(C, c.along(rot, c.v['enter'], 0.012 * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('hit', C); tl.hold(C + 3); end_rise(c, tl, 9)
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 4, 'tumble': 3, 'appear': r + 12 + L(P, 6) + 2, 'seated': se}}


def h12(c, tl):
    """Tip-up drop, whip shut. A small muzzle-up flick pops the latch. Counter dip, the muzzle is tipped up and
    stops dead: the loose cassette slides out of the bottom by its own weight and drops. A pendulum swing down
    beside the leg, the rifle is slammed back onto the fresh cassette on the thigh rig. Up, and an outward wrist whip
    that stops dead on the latch frame shuts it."""
    P = c.P; Lf, C, se = frames(c); k = P['k']; tip = P.get('tip', 22)
    open_latch(c, tl, 'tip')
    t = 46; tl.hold(t - 8 - L(P, 2)); tl.to(t - 5, (0, -0.012, 0.0), (-4, 0, 1), 'ease'); tl.to(t, (0.008, 0.03, 0.02), (tip, -3, -3), 'drive', rlag=1)
    tl.kick(t, (0, -0.004 * k, 0), (-2 * k, 0, 0), attack=0.5, release=2.5); r = t + P.get('drop_after', 2); tl.mark('release', r)
    tl.hold(r + 6); th, rot = stn(c, 'thigh'); pre = th + c.along(rot, c.v['enter'], 0.14); arr = r + 6 + L(P, 7)
    arc(tl, arr, (0.13, -0.08, 0.04), pre, rot, 'heavy'); tl.kick(arr, c.along(rot, c.v['enter'], -0.006), (-2, 0, 0), release=2.5)
    tl.hold(se - 5); tl.to(se, th, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], 0.014 * k), (-3 * k, 0, 0), attack=0.5, release=3.0)
    tl.hold(C - 6 - L(P, 8)); rise_to(c, tl, C - 6, (-0.012, 0.004, -0.01), (0, 9, 2)); tl.hold(C - 4)
    tl.to(C, (0.03, 0.004, 0.0), (0, -10, -3), PUNCH, rlag=0); tl.kick(C, (-0.006 * k, 0, 0), (0, 3 * k, 0), attack=0.5, release=2.5); tl.mark('hit', C)
    settle(c, tl, C + 3 + (1 if P['w'] > 1 else 0))
    return {'mag': {'release': r, 'mode': 'inertia', 'tumble': 3, 'push': P.get('push', 0.02), 'appear': arr + 2, 'seated': se}}


def h13(c, tl):
    """Hammer drop, uppercut. A short downward jolt pops the latch. The rifle is wound up (muzzle up) and hammered
    down along the cassette's own axis, stopping dead in mid-air: the loose cassette flies on out of the bottom and
    falls. Down to the belt rig and onto the fresh cassette. From the belt an uppercut that stops dead above the idle
    on the latch frame shuts it; it settles."""
    P = c.P; Lf, C, se = frames(c); k = P['k']; ex = c.v['exit']
    open_latch(c, tl, 'jolt')
    hrot = (-6, 0, 0); drop = np.array(P.get('stop', (0.0, -0.02, 0.02))); wu = drop - c.along(hrot, ex, P.get('drop', 0.15))   # hammered along the well axis
    w = 41; tl.hold(w - L(P, 9)); tl.to(w, wu, (14, 0, -3), 'rise', antic=P['a'] * 0.5); tl.hold(w + 2); s = w + 2 + L(P, 5)
    tl.to(s, drop, hrot, 'slam', rlag=0); tl.kick(s, -c.along(hrot, ex, 0.012 * k), (3 * k, 0, 0), attack=0.5, release=2.5)
    r = peak_mag(c, tl, w + 3, s); tl.mark('release', r)
    tl.hold(s + 7); bp, rot = stn(c, 'belt_wide'); arr = s + 7 + L(P, 6); seat_block(c, tl, bp, rot, arr, se)
    tl.hold(C - L(P, 9)); tl.to(C, (0.006, 0.04, -0.014), (8, 0, -2), 'slam', rlag=0); tl.kick(C, (0, -0.008 * k, 0.002), (-3 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', C)
    settle(c, tl, C + 3 + (1 if P['w'] > 1 else 0))
    return {'mag': {'release': r, 'mode': 'inertia', 'tumble': 4, 'appear': arr + 2, 'seated': se}}


def h14(c, tl):
    """Up-snap, cant snap. A short forward thrust pops the latch. Counter dip, then the rifle is ripped straight up
    off the cassette: the cassette stays where it was and drops. Down to the stomach rig and pressed onto the fresh
    cassette. Up into view canted outward, then snapped upright, dead stop on the latch frame: it shuts."""
    P = c.P; Lf, C, se = frames(c); k = P['k']; ex = c.v['exit']
    open_latch(c, tl, 'thrust')
    r = 46; tl.hold(r - 5 - L(P, 2)); d0 = np.array((0, -0.03, 0.006)); tl.to(r, d0, (-3, 0, 0), 'ease'); tl.mark('release', r)
    up = d0 - c.along((-3, 0, 0), ex, P.get('snap', 0.13)); tl.to(r + 3, up, (-3, 0, 0), PUNCH, rlag=0); tl.kick(r + 3, (0, -0.008 * k, 0), (-2 * k, 0, 0), attack=0.5, release=2.5); tl.nodrag.append((r - 1, r + 5))
    tl.hold(r + 6); sp, rot = stn(c, 'stomach'); arr = r + 6 + L(P, 7); seat_block(c, tl, sp, rot, arr, se, d=0.11, reb=0.008)
    tl.hold(C - 6 - L(P, 8)); rise_to(c, tl, C - 6, (0.016, -0.01, -0.004), (2, 0, -28)); tl.hold(C - 4)
    tl.to(C, (0, 0.004, 0), (0, 0, 5), PUNCH, rlag=0); tl.kick(C, (0, 0.002, 0), (0, 0, -3 * k), attack=0.5, release=2.5); tl.mark('hit', C)
    settle(c, tl, C + 3 + (1 if P['w'] > 1 else 0))
    return {'mag': {'release': r, 'mode': 'inertia', 'tumble': 2, 'appear': arr + 2, 'seated': se}}


def h15(c, tl):
    """Thigh slam, yank shut. A short outward whip pops the latch. The rifle swings muzzle-down beside the leg and
    the cassette catches on the thigh rig; the rifle is ripped up off it and the cassette drops. Wound up high over
    the fresh cassette and slammed down onto it. Up into view held forward, then yanked back toward the body, dead
    stop on the latch frame: it shuts."""
    P = c.P; Lf, C, se = frames(c); k = P['k']; ex = c.v['exit']
    open_latch(c, tl, 'whip')
    th, rot = stn(c, 'thigh'); r = 48
    tl.hold(r - 10 - L(P, 3)); tl.to(r - 10, (0, 0.025, 0.0), (5, 0, 0), 'ease'); tl.to(r - 2, th, rot, 'heavy'); tl.kick(r - 2, (0, -0.008 * k, 0), (-2, 0, 0), attack=0.5, release=2.0); tl.hold(r); hook_off(c, tl, r, th, rot)
    tl.hold(r + 13); pre = th + c.along(rot, c.v['enter'], P.get('windup', 0.22)); tl.to(r + 13 + L(P, 6), pre, rot, 'ease')
    tl.hold(se - 5); tl.to(se, th, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], 0.02 * k), (-5 * k, 0, 0), attack=0.5, release=3.5)
    tl.hold(C - 6 - L(P, 9)); rise_to(c, tl, C - 6, (0.0, 0.0, -0.05), (2, 0, -2)); tl.hold(C - 4)
    tl.to(C, (0, 0.008, 0.025), (-3, 0, 0), PUNCH, rlag=0); tl.kick(C, (0, 0, -0.01 * k), (2 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', C)
    settle(c, tl, C + 3 + (1 if P['w'] > 1 else 0))
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 5, 'tumble': 3, 'appear': r + 13 + L(P, 6) + 2, 'seated': se}}


def h16(c, tl):
    """Two chops. A short outward cant pops the latch. The muzzle is raised, then chopped down hard and stopped dead:
    the loose cassette flies on out of the bottom. Down to the hip rig and onto the fresh cassette. Up into view
    muzzle high, a second chop stops dead on the latch frame: it shuts."""
    P = c.P; Lf, C, se = frames(c); k = P['k']
    open_latch(c, tl, 'cant')
    w = 42; tl.hold(w - L(P, 9)); tl.to(w, P.get('chop_from', (0.0, 0.07, -0.05)), (22, 0, -3), 'rise', antic=P['a'] * 0.5); tl.hold(w + 2)
    s = w + 2 + L(P, 4); tl.to(s, P.get('chop_pos', (0.0, 0.01, 0.065)), (-20, 0, 0), 'slam', rlag=0); tl.kick(s, (0, 0.006 * k, 0), (4 * k, 0, 0), attack=0.5, release=2.5)
    r = peak_mag(c, tl, w + 3, s); tl.mark('release', r); tl.nodrag.append((w + 1, s + 2))   # the chop also moves back: the cassette leaves along the well
    tl.hold(s + 7); hp, rot = stn(c, 'hip'); arr = s + 7 + L(P, 6); seat_block(c, tl, hp, rot, arr, se)
    tl.hold(C - 6 - L(P, 8)); rise_to(c, tl, C - 6, (0.0, 0.025, 0.01), (20, 0, -3)); tl.hold(C - 4)
    tl.to(C, (0, -0.012, 0.0), (-5, 0, 0), PUNCH, rlag=0); tl.kick(C, (0, 0.006 * k, 0), (3 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', C)
    settle(c, tl, C + 3 + (1 if P['w'] > 1 else 0))
    return {'mag': {'release': r, 'mode': 'inertia', 'tumble': 4, 'appear': arr + 2, 'seated': se}}


def h17(c, tl):
    """Stomach tuck, belly bump. A thumb-sized wrist dip pops the latch. The rifle is drawn in and down to the
    stomach rig, muzzle down; the cassette catches on the rig and the rifle is pushed out off it, the cassette drops.
    Pressed back onto the fresh cassette, then eased out and knocked back against the belly on the latch frame: it
    shuts. Up."""
    P = c.P; Lf, C, se = frames(c); k = P['k']
    open_latch(c, tl, 'thumb')
    sp, rot = stn(c, 'stomach'); r = 50
    tl.hold(r - 2 - L(P, 7)); arc(tl, r - 2, (0.09, -0.06, 0.03), sp, rot, 'drive'); tl.kick(r - 2, (0, -0.006 * k, 0.004), (-2, 0, 0), attack=0.5, release=2.0); tl.hold(r)
    hook_off(c, tl, r, sp, rot, 0.15)
    tl.hold(r + 12); seat_block(c, tl, sp, rot, r + 12 + L(P, 6), se, d=0.12, reb=0.008)
    tl.hold(se + 6); out = sp + c.along(rot, c.v['enter'], 0.06); tl.to(C - 5, out, [rot[0] + 4, rot[1], rot[2]], 'ease'); tl.to(C, sp + c.along(rot, c.v['enter'], 0.005), rot, 'slam', rlag=0)
    tl.kick(C, c.along(rot, c.v['enter'], 0.012 * k), (-3 * k, 0, 0), attack=0.5, release=2.5); tl.mark('hit', C); tl.hold(C + 3); end_rise(c, tl, 11)
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 5, 'tumble': 3, 'appear': r + 12 + L(P, 6) + 2, 'seated': se}}


def h18(c, tl):
    """Hip hook, hip bump. A short tug back pops the latch. The rifle swings down to the hip rig and the cassette
    catches there; the rifle is ripped up off it and the cassette drops. Wound up over the fresh cassette and slammed
    onto it; the butt is knocked back on the hip on the latch frame (out of view); up. The Masamune's M03 for the
    Hercules."""
    P = c.P; Lf, C, se = frames(c); k = P['k']; ex = c.v['exit']
    open_latch(c, tl, 'tug')
    th, rot = stn(c, 'hip'); r = 48
    tl.hold(r - 10 - L(P, 3)); tl.to(r - 10, (0, 0.025, 0.0), (5, 0, 0), 'ease'); tl.to(r - 2, th, rot, 'heavy'); tl.kick(r - 2, (0, -0.008 * k, 0), (-2, 0, 0), attack=0.5, release=2.0); tl.hold(r); hook_off(c, tl, r, th, rot)
    tl.hold(r + 13); pre = th + c.along(rot, c.v['enter'], P.get('windup', 0.20)); tl.to(r + 13 + L(P, 5), pre, rot, 'ease')
    tl.hold(se - 5); tl.to(se, th, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], 0.02 * k), (-5 * k, 0, 0), attack=0.5, release=3.5)
    tl.hold(se + 5); hip_bump_close(c, tl, th, rot)
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 5, 'tumble': 3, 'appear': r + 13 + L(P, 5) + 2, 'seated': se}}


PICKS = {'H11': ('Belt dip', h11), 'H12': ('Tip-up drop, whip shut', h12), 'H13': ('Hammer drop, uppercut', h13), 'H14': ('Up-snap, cant snap', h14),
         'H15': ('Thigh slam, yank shut', h15), 'H16': ('Two chops', h16), 'H17': ('Stomach tuck, belly bump', h17), 'H18': ('Hip hook, hip bump', h18)}
PARAMS = {}          # per draft overrides of the take parameters (tuning)


def stem(pick, side='right'): return prod.stem(GUN, pick, TAKE, CLIP, side)


def build(pick, side='right', body='pma', out=None, quiet=False):
    """prod.build for a round 3 draft: same spec, track and gate files, magtrack3 for the track."""
    import rgate
    out = out or OUT; d = f'{out}/{body}'; os.makedirs(d, exist_ok=True); name = stem(pick, side)
    S = side.capitalize(); P = dict(prod.TAKES[TAKE]); P.update(PARAMS.get(pick, {})); c = prod.Ctx(GUN, body, CLIP, P, S); tl = TL(c, P['lag'], P['drag']); m = PICKS[pick][1](c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    if S == 'Left':
        Pk = Pk * prod.MIR_P; Rk = Rk * prod.MIR_R
        for k in kicks: k['move'] = list(np.array(k['move'], float) * prod.MIR_P); k['rot'] = list(np.array(k['rot'], float) * prod.MIR_R)
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    fn = PICKS[pick][1]
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {TAKE}', '_doc': ' '.join((fn.__doc__ or '').split()), '_gun': GUN, '_left_gun': GUN, '_body': body, '_side': S,
            '_gun_clip': CLIP, '_pick': pick, '_take': TAKE, '_timing': c.T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False, '_round': '3-hercules',
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, ('Left' if S == 'Right' else 'Right'): [K(0)]},
            'shakes': {S: kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); G = [cl.world(f)[i] for f in range(c.N)]
    track = magtrack3.build(GUN, CLIP, [(np.array(t), np.array(q)) for t, q in G], m['mag']); spec['_track'] = f'{d}/{name}_track.json'
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); o['elbow_step_deg'] = elbow_step(spec); o['exit_at_10cm'] = exit_at(track)
    if o['exit_at_10cm'] is not None and o['exit_at_10cm'] > rgate.LIM['off_axis_max_cm']: o['fails'].append(f"exit {o['exit_at_10cm']} cm off axis at 10 cm out")
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, rgate.line(o), 'elbow step', o['elbow_step_deg'], flush=True)
    return spec, o


def exit_at(track, at=0.10):
    """Sideways offset (cm) of the leaving cassette from the well axis where it is `at` metres out along it,
    interpolated between frames. rgate samples only frames inside the first 10 cm and a fast cassette can pass them
    in one frame; this reads the path itself. None for a cassette that never gets that far."""
    import magtrack2
    v = magtrack2.vanilla(track['gun'], track['clip']); cen = np.r_[v['centre'], 1]; s0 = (v['seat'] @ cen)[:3]; ex = np.array(track['exit_gun_axes'], float); ex /= np.linalg.norm(ex)
    prev = (0.0, 0.0)
    for f in range(track['release'] + 1, len(track['frames'])):
        row = track['frames'][f]
        if row['state'] not in ('guided', 'falling') or row['s'] < 0.5: break
        d = (np.array(row['m']).reshape(4, 4) @ cen)[:3] - s0; al = float(d @ ex); lat = float(np.linalg.norm(d - al * ex))
        if al >= at:
            t = (at - prev[0]) / max(al - prev[0], 1e-9); return round((prev[1] + t * (lat - prev[1])) * 100, 2)
        prev = (al, lat)
    return None


def elbow_step(spec):
    """Largest change of the elbow direction (about the shoulder-hand line) from one frame to the next, degrees:
    an elbow flip shows as a jump far above the rest (the production fix keeps it under about 30)."""
    S = spec['_side']; g = Glb(spec['out']); c = Clip(g, spec['clip']); ix = {n: i for i, n in enumerate(g.names)}; prev = None; worst = 0.0
    for f in range(spec['frames']):
        W = c.world(f); s, e, h = (np.array(W[ix[S + n]][0]) for n in ('Arm', 'ForeArm', 'Hand')); ax = (h - s) / np.linalg.norm(h - s)
        p = (e - s) - ((e - s) @ ax) * ax; p /= (np.linalg.norm(p) or 1)
        if prev is not None: worst = max(worst, float(np.degrees(np.arccos(np.clip(p @ prev, -1, 1)))))
        prev = p
    return round(worst, 1)


def stats(ids, out=None):
    """motionstats of every draft, of today's H02B and of the approved clips; table and plot."""
    import motionstats
    out = out or OUT; rows = []; ref = common.mp('C:/Modding/anim-work/rifle-reloads/round2/measure/motion_all.json')
    prodh02 = common.mp('C:/Modding/anim-work/rifle-reloads/production/clips/pma/hercules_right_H02B_reload.glb')
    if os.path.exists(prodh02): rows.append(('H02B (today, production)', motionstats.stats(prodh02, 'reload_draft', 'Right', 0.55)))
    for pick in ids: rows.append((f'{pick}B {PICKS[pick][0]}', motionstats.stats(f'{out}/pma/{stem(pick)}.glb', 'reload_draft', 'Right', 0.55)))
    J = {}
    if os.path.exists(ref):
        J = json.load(open(ref)); appr = [(k, v) for k, v in J.items() if k.startswith('APPROVED')]
        rows = appr + rows
    T = ['| clip | peak cm/f | p90 | peak at | stop | jerks | still | whip | muzzle peak | big moves |', '|---|---|---|---|---|---|---|---|---|---|']
    for lab, s in rows: T.append(f"| {lab} | {s['peak_speed']} | {s['p90_speed']} | {s['peak_at']} | {s['stop']} | {s['jerk_events']} | {int(s['hold_share'] * 100)} % | {s['whip']} | {s['peak_muzzle_speed']} | {s['big_moves']} |")
    os.makedirs(renv.OUT + '/measure', exist_ok=True); open(renv.OUT + '/measure/motion_round3.md', 'w').write('\n'.join(T) + '\n'); print('\n'.join(T))
    json.dump({l: s for l, s in rows}, open(renv.OUT + '/measure/motion_round3.json', 'w')); motionstats.plot(rows, renv.OUT + '/measure/motion_round3.png')


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(PICKS)
    sides = (o('--sides') or 'right').split(','); bodies = (o('--bodies') or 'pma').split(','); out = o('--out'); jobs = int(o('--jobs') or 1)
    if cmd == 'list':
        for p, (n, fn) in PICKS.items(): print(p, n, '|', ' '.join((fn.__doc__ or '').split()))
    elif cmd == 'build':
        todo = [(p, s, b) for p in ids for s in sides for b in bodies]
        if jobs > 1:
            procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), '_part', json.dumps(todo[k::jobs])] + (['--out', out] if out else [])) for k in range(jobs) if todo[k::jobs]]
            for p in procs: p.wait()
        else:
            for t in todo: build(*t, out=out)
    elif cmd == '_part':
        for t in json.loads(argv[1]): build(*t, out=out)
    elif cmd == 'stats': stats(ids, out)
    else: raise SystemExit(__doc__)
