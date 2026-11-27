"""BREAK-OPEN shotguns, round 1: ten one-handed ways to break the action, get the spent shells out, load two fresh
ones and snap it shut. Take A on the Palica (light, 2.9 l), take B on the Satara (heavy, 5.8 l). Right hand, male V,
empty reload (both barrels).

usage: break1.py list | build [ids] [--takes A,B] [--jobs n]
Output: <OUT>/clips/pma/<gun>_right_<id><take>_empty_reload.glb, .json, _objects.json (shells), _gate.json

Method (BRIEF-NEW-TECHNIQUES.md):
- The hand follows a target timeline; the gun follows the hand as a spring-damper mass (inertia.spring).
- The barrels are a rigid body on the hinge pin (phys.hinge): held shut by the latch until the thumb releases it,
  then moved by gravity and the gun's own accelerations (a jerk swings them open, a flick or a sudden stop swings them
  shut), or by a contact (pressed open on the thigh, slapped shut); the cocking springs push them toward the open stop
  with 1 g at their centre, so only a decisive flick or stop swings them home; the latch catches when they come home, and the gun takes a jolt there.
- Spent shells ride in the chambers and are kicked out along the chamber axis by the ejector when the barrels reach
  the open stop (EJECT), with the velocity and spin the moving barrels give them; then free fall (rigid bodies).
- Fresh shells wait in a rig (world-fixed) and go in nose first along the chamber axis: pressed (the open chambers
  are pushed onto them), dropped (they fall from a dispenser into chambers held mouth-up), or thrown and caught.
Timing budget: take A 76 frames (latch f6, barrels open by about f12, hidden loading window about f28 to f46, shut
on f57, idle at f75); take B the same beats 13 % later (86 frames, shut on f64).
"""
import os, sys, json, subprocess, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, rlib2, prod, rgate, timing, magtrack2, phys
import inertia_r1 as inertia      # the spring model (spring, report, END); inertia.py is the round 4 simulation
from rlib import K
from glb import Glb
from fk import Clip, qrot

OUT = renv.OUT; CLIP = 'empty_reload'
GUNS = {'A': 'palica', 'B': 'satara'}
MESH = {'palica': 'w_shotgun_dual__rostovic_palica', 'satara': 'w_shotgun_dual__rostovic_satara'}
GEO = {g: json.load(open(f'{OUT}/ref/{g}_geometry.json')) for g in GUNS.values()}
BARREL_CM = {'palica': np.array([0.0, 0.0, -0.215]), 'satara': np.array([0.0, 0.0, -0.40])}
EJECT = 0.04        # ejector kick along the chamber axis, m/frame (the game's shells leave at 5 to 33 cm/f)
BUDGET = {'A': {'latch': 6, 'seat': 38, 'shut': 57, 'frames': 76}, 'B': {'latch': 7, 'seat': 43, 'shut': 64, 'frames': 86}}
TAKES_P = {'A': dict(prod.TAKES['A'], drag=0.0, lag=0), 'B': dict(prod.TAKES['B'], w=1.13, drag=0.0, lag=0)}
PUNCH = prod.PUNCH; L = prod.L
ST = {'thigh': ((0.29, 0.10, -0.035), (-10, -10, 10)), 'hip': ((0.31, 0.165, -0.04), (-10, -14, 14)), 'belt': ((0.285, 0.145, -0.06), (-8, -8, 6)),
      'chest': ((0.16, 0.36, -0.20), (0, 6, 0)), 'shoulder': ((0.22, 0.62, -0.08), (30, -8, 0))}


def take_of(gid): return 'A' if gid == 'palica' else 'B'
def bud(c): return BUDGET[take_of(c.gun)]
def geo(c): return GEO[c.gun]
def joints(gid): return GEO[gid]['joints']
def closed(gid, j): return np.array(GEO[gid]['closed'][j])
def tmax(gid): return math.radians(GEO[gid]['open_deg'])
def H(gid, th): return phys.hinge_rot(GEO[gid]['hinge_axis'], GEO[gid]['hinge_pivot'], th)
def shell_centre(gid):
    import gungeo
    V = gungeo.verts(common.find('weapon_meshes', MESH[gid] + '__mag_std_01.glb')); return V.mean(0)


def chamber_pt(gid, th=None):
    """Mean of the two chamber shell centres in gun axes, barrels at angle th (open stop by default)."""
    th = tmax(gid) if th is None else th; sc = shell_centre(gid)
    return np.mean([(H(gid, th) @ closed(gid, j) @ np.r_[sc, 1])[:3] for j in joints(gid)], axis=0)


def u_out(gid, th=None):
    """Chamber axis outward (toward the mouth), gun axes, barrels at th."""
    th = tmax(gid) if th is None else th; R = (H(gid, th) @ closed(gid, joints(gid)[0]))[:3, :3]; return R @ np.array([0, 0, 1.0])


def setup(gid):
    T = timing._cache.get((gid, CLIP))
    if T and T.get('_break'): return T
    B = BUDGET[take_of(gid)]
    T = {'gun': gid, 'clip': CLIP, 'frames': B['frames'], 'out': B['latch'], 'clear': None, 'far': None, 'near': B['seat'], 'seated': B['seat'], 'exit_dir': [0, 1, 0],
         'exit_speed_cm_f': 0, 'in_dir': [0, 1, 0], 'slot': [0, 0, 0], 'parts': {}, 'handle': [B['shut'], B['shut']], 'budget': B, '_break': True}
    timing._cache[(gid, CLIP)] = T; C = closed(gid, joints(gid)[0])
    magtrack2._van[(gid, CLIP)] = {'M': [C], 'seat': C, 'centre': shell_centre(gid), 'exit': np.array([0, 1.0, 0]), 'enter': np.array([0, -1.0, 0]), 'dist': np.zeros(2), 'out': 0, 'seated': 1}
    return T


class TL(rlib2.TL):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.stops = []

    def to(self, f, pos, rot, prof='drive', antic=0.0, antic_f=3, rlag=None, rprof=None):
        if int(f) <= self.f: raise ValueError(f'move to f{f} from f{self.f}')
        p0 = self.p.copy(); super().to(f, pos, rot, prof, antic, antic_f, 0, rprof); d = np.array(pos, float) - p0
        if np.linalg.norm(d) > 0.03: self.stops.append((int(f), d / np.linalg.norm(d)))
        return self


def q_of(c, rot): return author.qmul(c.q0, author.qeuler(*rot))
def gun_vec(c, rot, v): return qrot(q_of(c, rot), np.asarray(v, float))
def place(c, X, rot, pt): return np.asarray(X, float) - c.g0 - qrot(q_of(c, rot), np.asarray(pt, float))
def station(c, name): off, hint = ST[name]; return c.hips + np.array(off), hint
def F(c, f): return int(round(f * c.P['w']))       # a beat of the A budget in this take


def go(c, tl, f, pos, rot, prof='drive', avg=0.055, avg_r=11.0, nmin=3):
    d = float(np.linalg.norm(np.asarray(pos, float) - tl.p)); r = float(np.max(np.abs(np.asarray(rot, float) - tl.r)))
    n = max(nmin, int(math.ceil(max(d / avg, r / avg_r) * c.P['w']))); tl.hold(f - n)
    if f <= tl.f: f = tl.f + nmin
    tl.to(f, pos, rot, prof); return f


def settle(c, tl, f):
    tl.hold(f + 3); e = min(f + 3 + L(c.P, 9), c.N - inertia.END - 1)
    if e > tl.f: tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')


def thumb(c, tl):
    """The thumb pushes the top lever on the latch frame: a small twitch of the gun."""
    f = bud(c)['latch']; tl.hold(f - 3); tl.to(f, (0.0, 0.004, 0.006), (2, 0, -2), 'snap'); tl.mark('latch', f)


def mouth_up_rot(c, yaw=0, roll=0):
    """Gun angles that turn the open chamber mouths straight up (pitch the gun down by 90 deg less the open angle)."""
    return (-(90 - GEO[c.gun]['open_deg']), yaw, roll)


def insert_from(c, tl, f_seat, X, rot, depth=0.08, n=4):
    """The open chambers are pushed onto shells held at X (their seated centres) along the chamber axis."""
    gid = c.gun; o = place(c, X, rot, chamber_pt(gid)); uo = gun_vec(c, rot, u_out(gid))
    go(c, tl, f_seat - n, o - uo * depth, rot, 'drive', avg_r=6.0); tl.to(f_seat, o + uo * 0.004, rot, 'heavy'); return o     # turned slowly: a fast turn swings the open barrels shut


# ------------------------------------------------------------------------------------------------ closers (shut on the shut beat)
def close_flick(c, tl):
    """Up into view low, then an upward flick that stops dead: the barrels carry on up and lock."""
    s = bud(c)['shut']; lg = c.gun == 'satara'; fp, fr = c.P.get('flick_from', ((0.01, -0.17, -0.04), -36)) if lg else ((0.01, -0.14, -0.02), -50); go(c, tl, s - 5, fp, (fr, 0, -3), 'rise'); tl.hold(s - 4); tl.to(s, (0.0, 0.0, -0.03), (10, 0, -2), PUNCH); tl.mark('close', s); settle(c, tl, s)


def close_drop(c, tl):
    """Held up, then snapped down sharply: the barrels lag behind and swing up into the lock."""
    s = bud(c)['shut']; go(c, tl, s - 5, (0.01, 0.04, -0.03), (14, 0, -3), 'rise'); tl.hold(s - 4); tl.to(s, (0.0, -0.07, -0.02), (-6, 0, -2), (1.3, 2.6)); tl.mark('close', s); settle(c, tl, s)


# ------------------------------------------------------------------------------------------------ drafts
def b01(c, tl):
    """Weight break, bandolier. The thumb trips the latch with the gun held level: the barrels fall open under their
    own weight and the ejector throws both shells up and back. The gun is turned muzzle-down a little so the chamber
    mouths face up, raised under a chest bandolier and pushed up onto two hanging shells. Up into view low and an
    upward flick that stops dead: the barrels carry on up and lock."""
    thumb(c, tl); tl.hold(F(c, 16)); cx, _ = station(c, 'chest'); rot = mouth_up_rot(c, 6, 0)
    insert_from(c, tl, F(c, 36), cx + np.array([0.04, -0.02, -0.10]), rot); tl.hold(F(c, 40))
    close_flick(c, tl); return {'loads': [('press', F(c, 36))]}


def b02(c, tl):
    """Up-jerk break, gravity feed. Latch tripped, the gun is jerked up hard: the barrels lag and swing open fast and
    the shells are thrown up and back. Held still beside the hip with the mouths up under a dispenser, two shells fall
    in by their own weight. Held up, then snapped down: the barrels lag up into the lock."""
    thumb(c, tl); f = bud(c)['latch']; tl.to(f + 4, (0.0, 0.05, -0.06) if c.gun == 'satara' else (0.0, 0.07, 0.0), (4, 0, -2), (1.6, 1.4)); tl.mark('jerk', f + 4)
    sx, _ = station(c, 'hip'); rot = mouth_up_rot(c, -4, 0); o = place(c, sx + np.array([0.04, 0.10, -0.18]), rot, chamber_pt(c.gun))
    go(c, tl, F(c, 26), o, rot, 'drive'); tl.hold(F(c, 38)); close_drop(c, tl)
    return {'loads': [('drop', F(c, 30), F(c, 36))]}


def b03(c, tl):
    """Thigh workstation. The muzzles are pressed down on the outer thigh and the barrels pried open against it; the
    ejector throws the shells. The gun hangs muzzle-down beside the thigh and is pulled back onto two shells in a
    thigh holder. Up beside the leg, the barrels are slapped shut against the thigh."""
    gid = c.gun; lg = gid == 'satara'; thumb(c, tl); tx, _ = station(c, 'thigh'); rot = tuple(c.P.get('h03prot', (-24 if lg else -35, -8, 6))); mz = np.array([0, 0.0, c.P.get('h03mz', -0.30 if gid == 'palica' else -0.62)])
    o = place(c, tx + np.array([0.06, 0.12, -0.14]), rot, mz); go(c, tl, F(c, 12), o, rot, 'drive'); tl.hold(F(c, 13)); tl.to(F(c, 16), o + np.array([0, 0.05, 0]), (rot[0] - 1, rot[1], rot[2]) if lg else (-25, -8, 6), 'heavy'); tl.mark('pry', F(c, 13))
    hrot = tuple(c.P.get('h03rot', (-20 if lg else -68, -10 if lg else -8, 6))); insert_from(c, tl, F(c, 34), tx + np.array(c.P.get('h03off', (0.10 if lg else 0.03, 0.14 if lg else 0.02, -0.20 if lg else -0.06))), hrot); tl.hold(F(c, 40))
    s = bud(c)['shut']; sl = place(c, tx + np.array([0.06, 0.16, -0.16]), (-20, -8, 6), mz); go(c, tl, s - 3, sl + np.array([0, -0.02, 0]), (-20, -8, 6), 'drive'); tl.to(s, sl, (-12, -8, 6), 'slam'); tl.mark('close', s)
    settle(c, tl, s); return {'loads': [('press', F(c, 34))], 'drives': [(F(c, 13), F(c, 16), 0.0, tmax(gid)), (s - 1, s, None, 0.0)]}


def b04(c, tl):
    """Spin break, throw and meet. Gorilla wrist: a fast forward roll pitches the gun muzzle-down and back up; the
    spin slings the barrels open and the shells out. A spring rig on the belt flicks two shells up and the open
    chambers meet them in the air, mouths up. An upward flick that stops dead shuts it."""
    thumb(c, tl); f = bud(c)['latch']; lg = c.gun == 'satara'; tl.to(f + 5, (0.02, -0.08, -0.05) if lg else (0.02, -0.04, -0.02), (-36 if lg else -62, 0, -4), (1.6, 1.4)); tl.to(f + 8, (0.01, -0.06, -0.08) if lg else (0.01, -0.02, -0.02), (-14 if lg else -20, 0, -3), 'slam'); tl.mark('spin', f + 5)
    bx, _ = station(c, 'belt'); rot = mouth_up_rot(c, -6, 0); o = place(c, bx + np.array([0.02, 0.14, -0.16]), rot, chamber_pt(c.gun))
    go(c, tl, F(c, 30), o, rot, 'drive'); tl.hold(F(c, 40)); close_flick(c, tl)
    return {'loads': [('toss', F(c, 23), F(c, 30))], 'seat': F(c, 34)}


def b05(c, tl):
    """Inverted scoop. The barrels fall open by weight. Gorilla wrist: the gun is rolled upside down so the open
    mouths face down and pressed down over two shells standing nose-up in the belt loops (the hinge spring holds the
    barrels open); rolled back, up into view low and an upward flick that stops dead: the barrels carry on up and
    lock."""
    thumb(c, tl); tl.hold(F(c, 16)); bx, _ = station(c, 'belt'); rot = (-(90 - GEO[c.gun]['open_deg']), 10, 178)
    insert_from(c, tl, F(c, 34), bx + np.array([0.02, 0.06, -0.08]), rot); tl.hold(F(c, 36)); go(c, tl, F(c, 48), (0.01, -0.14, -0.02), (-50, 0, -3), 'drive', avg_r=9); close_flick(c, tl)
    return {'loads': [('press', F(c, 34))]}


def b06(c, tl):
    """Stock sleeve, flick and catch. Up-jerk break. The two shells ride in a sleeve on the stock: a sharp upward flick
    that stops dead throws them off the sleeve, and the gun is turned mouths-up under them and catches them as they fall.
    Down to the hip and the barrels are knocked up shut against the hip."""
    thumb(c, tl); f = bud(c)['latch']; tl.to(f + 4, (0.0, 0.03, -0.03) if c.gun == 'satara' else (0.0, 0.07, 0.0), (4, 0, -2), (1.6, 1.4)); tl.hold(F(c, 12))
    tl.to(F(c, 16), (0.0, -0.03, -0.02) if c.gun == 'satara' else (0.0, 0.01, 0.0), (4, 0, -2), 'drive')       # dip, then a flick of about 9 cm in 3 frames
    tl.to(F(c, 19), (0.0, 0.05, -0.05) if c.gun == 'satara' else (0.0, 0.10, 0.0), (2, 0, -2), 'slam'); tl.mark('flick', F(c, 19))
    rot = mouth_up_rot(c, 0, 0); pc = np.array(c.P.get('catch_pc', (c.g0 + np.array([0.0, 0.20, 0.10]))))
    if c.gun == 'satara' and 'catch_pc' not in c.P: pc = c.g0 + np.array([0.06, -0.04, -0.10])
    go(c, tl, F(c, 27), place(c, pc, rot, chamber_pt(c.gun)), rot, 'drive'); tl.hold(F(c, 29))
    hx, _ = station(c, 'hip'); s = bud(c)['shut']; mz = np.array([0, -0.03, -0.25 if c.gun == 'palica' else -0.55]); hr = (-30, -10, 10) if c.gun == 'palica' else (-6, -6, 4)
    hp = place(c, hx + (np.array([0.08, 0.14, -0.18]) if c.gun == 'satara' else np.array([0.03, 0.10, -0.12])), hr, mz); go(c, tl, F(c, 40), hp + np.array([0, -0.04, 0]), hr, 'drive'); tl.hold(s - 3); tl.to(s, hp, (hr[0] + 6, hr[1], hr[2]), 'slam'); tl.mark('close', s)
    settle(c, tl, s); return {'loads': [('sleeve', c.P.get('release_f', F(c, 19)), F(c, 27))], 'drives': [(s - 1, s, None, 0.0)], 'seat': s - 12}


def b07(c, tl):
    """Buckle pry. The muzzles are hooked under the front of the belt and the stock is pushed up: the belt holds the
    barrels and the action pries open, the ejector throws the shells down past the leg (all below the view). Pushed up
    onto two shells hanging in a stomach bandolier, mouths up. Up into view low and an upward flick that stops dead:
    the barrels carry on up and lock."""
    gid = c.gun; thumb(c, tl); bx = c.hips + (np.array([0.22, 0.04, -0.40]) if gid == 'satara' else np.array([0.12, 0.10, -0.16])); rot = (-30 if gid == 'satara' else -48, -6, 4); mz = np.array([0, -0.03, -0.22 if gid == 'palica' else -0.50])
    o = place(c, bx, rot, mz); go(c, tl, F(c, 12), o, rot, 'drive'); tl.hold(F(c, 13)); tl.to(F(c, 16), o + np.array([0, 0.06, 0.02]), (-30, -6, 4), 'heavy'); tl.mark('pry', F(c, 13))
    sx = c.hips + np.array([0.185, 0.16, -0.115]); insert_from(c, tl, F(c, 34), sx + np.array([0.03, 0.10, -0.06]), mouth_up_rot(c, 6, 0)); tl.hold(F(c, 40))
    close_flick(c, tl); return {'loads': [('press', F(c, 34))], 'drives': [(F(c, 13), F(c, 16), 0.0, tmax(gid))]}


def b08(c, tl):
    """Hip bounce. The gun is dropped onto the hip and caught as it bounces: the stop flings the barrels open and the
    shells out. Mouths up beside the hip, two shells drop in from a hip dispenser. The gun is swung up and stopped dead
    in front: the barrels carry on up and lock."""
    gid = c.gun; thumb(c, tl); hx, _ = station(c, 'hip'); rot = (-8, -10, 8); o = place(c, hx + np.array([0.05, 0.16, -0.20]), rot, chamber_pt(gid, 0.0))
    go(c, tl, F(c, 13), o, rot, (2.0, 1.0)); tl.to(F(c, 16), o + np.array([0, 0.03, 0]), rot, 'snap'); tl.mark('bounce', F(c, 13))
    hr = mouth_up_rot(c, -6, 4); o2 = place(c, hx + np.array([0.06, 0.10, -0.16]), hr, chamber_pt(gid)); go(c, tl, F(c, 25), o2, hr, 'drive'); tl.hold(F(c, 38))
    close_flick(c, tl); return {'loads': [('drop', F(c, 28), F(c, 34))]}


def b09(c, tl):
    """Swing break, belt scoop. The gun is swung down and forward in a short arc and stopped dead at arm's length: the
    barrels swing on open and the shells fly forward and out. The open mouths are scooped back onto two shells lying
    in a belt holder (pointing forward). Held up, then snapped down: the barrels lag up into the lock."""
    gid = c.gun; thumb(c, tl); f = bud(c)['latch']; tl.to(f + 5, (0.02, -0.08, -0.05), (-16, 0, -3), (1.8, 1.2)); tl.mark('swing', f + 5)
    bx, _ = station(c, 'belt'); hrot = (-40, -6, 4); insert_from(c, tl, F(c, 34), bx + np.array([0.03, 0.06, -0.12]), hrot); tl.hold(F(c, 40)); close_drop(c, tl)
    return {'loads': [('press', F(c, 34))]}


def b10(c, tl):
    """Shoulder rest. The barrels fall open by weight; the gun is laid back over the right shoulder, mouths up, and two
    shells drop in from a shoulder-strap dispenser; brought forward off the shoulder and stopped dead in front: the
    barrels carry on up and lock."""
    gid = c.gun; thumb(c, tl); tl.hold(F(c, 14)); sx, _ = station(c, 'shoulder'); rot = (28, -14, 4)
    o = place(c, sx + np.array(c.P.get('rest_off', (0.12, -0.08, 0.10))), mouth_up_rot(c, -10, 0), chamber_pt(gid)); go(c, tl, F(c, 24), o, mouth_up_rot(c, -10, 0), 'drive'); tl.hold(F(c, 38))
    close_flick(c, tl); return {'loads': [('drop', F(c, 27), F(c, 33))]}


PARAMS = {'BR10B': {'flick_from': ((0.01, -0.20, -0.01), -30), 'rest_off': (0.18, -0.10, 0.06)},      # BR10B: the flick from the shoulder rest started too near the eye
          'BR03B': {'h03mz': -0.35}}      # BR03B: the barrels pressed on the thigh 19 cm ahead of the hinge, not at the muzzles (the 1.1 m gun folded the wrist to 157 deg)
PICKS = {'BR01': ('Weight break, bandolier', b01), 'BR02': ('Up-jerk break, gravity feed', b02), 'BR03': ('Thigh workstation', b03), 'BR04': ('Spin break, throw and meet', b04),
         'BR05': ('Inverted scoop', b05), 'BR06': ('Stock sleeve, flick and catch', b06), 'BR07': ('Buckle pry', b07), 'BR08': ('Hip bounce', b08),
         'BR09': ('Swing break, belt scoop', b09), 'BR10': ('Shoulder rest', b10)}
DOC = {k: ' '.join((fn.__doc__ or '').split()) for k, (n, fn) in PICKS.items()}
SLEEVE_OFF = np.array([0.045, -0.02, 0.16])       # shells in a sleeve on the right side of the stock, gun axes


# ------------------------------------------------------------------------------------------------ physics of the barrels and shells
def hinge_frames(gid, th):
    hc = np.array(GEO[gid]['hinge_curve']); mx = hc[:, 1].max(); a = int(np.argmax(hc[:, 1] > 0.3)); b = int(np.argmax(hc[:, 1] >= mx - 0.3))
    seg = hc[a - 1:b + 1]; d = np.degrees(th)
    return [0.0 if x < 0.2 else round(float(np.interp(x, seg[:, 1], seg[:, 0])), 3) for x in d]


def shells(c, GW, plan, th, events):
    gid = c.gun; N = len(GW); js = joints(gid); sc = shell_centre(gid); cen = np.r_[sc, 1]; info = {}; objs = []
    Hs = [H(gid, t) for t in th]; tm = tmax(gid)
    fe = next((f for f in range(N) if th[f] >= tm - math.radians(1.0)), None); info['eject'] = fe
    spent = {}
    for j in js:
        C = closed(gid, j); W = [GW[f] @ Hs[f] @ C for f in range(N)]
        if fe is not None:
            uo = (GW[fe] @ Hs[fe] @ C)[:3, :3] @ np.array([0, 0, 1.0]); fl, land, v = phys.free_from(W[fe - 1], W[fe], N, fe, mesh_centre=sc, extra_v=uo * EJECT)
            for f in range(fe + 1, N): W[f] = fl.get(f)
            car = np.linalg.norm((W[fe] @ cen)[:3] - (W[fe - 1] @ cen)[:3]) * 100
            info.setdefault('spent', []).append({'land': land, 'carry_cm_f': round(float(car), 2), 'kick_cm_f': EJECT * 100})
        spent[j] = W
    objs.append(('spent', spent))
    ld = plan['loads'][0]; kind = ld[0]; fresh = {}
    for j in js:
        C = closed(gid, j); W = [None] * N
        if kind == 'press':
            f1 = ld[1]; Ws = GW[f1] @ Hs[f1] @ C
            for f in range(0, f1 + 1): W[f] = Ws
        elif kind == 'drop':
            f0, f1 = ld[1], ld[2]; Ws = GW[f1] @ Hs[f1] @ C; d = 0.5 * phys.G_ACC * (f1 - f0) ** 2
            for f in range(0, f1 + 1): M = Ws.copy(); M[1, 3] += d - (0.5 * phys.G_ACC * (f - f0) ** 2 if f > f0 else 0); W[f] = M
        elif kind == 'toss':
            f0, f1 = ld[1], ld[2]; Ws = GW[f1] @ Hs[f1] @ C; n = f1 - f0; bx, _ = station(c, 'belt'); pt = (Ws @ cen)[:3]; p0 = bx + np.array([0.04, 0.02, -0.12]) + (pt - (GW[f1] @ Hs[f1] @ closed(gid, js[0]) @ cen)[:3])
            v0 = (pt - p0) / n - np.array([0, -phys.G_ACC, 0]) * (n + 1) / 2; info['toss_cm_f'] = round(float(np.linalg.norm(v0)) * 100, 2)
            for f in range(0, f1 + 1):
                jj = max(f - f0, 0); p = p0 + v0 * jj + np.array([0, -phys.G_ACC, 0]) * jj * (jj + 1) / 2; M = Ws.copy(); M[:3, 3] += p - pt; W[f] = M
        elif kind == 'sleeve':
            f0, f1 = ld[1], ld[2]; S = C.copy(); S[:3, 3] += SLEEVE_OFF
            for f in range(0, f0 + 1): W[f] = GW[f] @ S
            fl, land, v = phys.free_from(W[f0 - 1], W[f0], N, f0, mesh_centre=sc)
            for f in range(f0 + 1, f1): W[f] = fl.get(f)
            Wc = GW[f1] @ Hs[f1] @ C; info.setdefault('catch_error_cm', []).append(round(float(np.linalg.norm(((fl.get(f1, Wc) - Wc) @ cen)[:3])) * 100, 2))
            car = [(GW[f] @ S @ cen)[:3] for f in (f0 - 3, f0 - 2, f0 - 1, f0)]; info['sleeve'] = {'release': f0, 'exit_cm_f': round(float(np.linalg.norm((fl[f0 + 1] @ cen)[:3] - (W[f0] @ cen)[:3] - np.array([0, -phys.G_ACC, 0]))) * 100, 2), 'gun_cm_f': round(max(float(np.linalg.norm(car[i + 1] - car[i])) for i in range(3)) * 100, 2)}
            f1 = f1 - 1
        for f in range(ld[-1] + (0 if kind != 'sleeve' else 0), N): W[f] = GW[f] @ Hs[f] @ C
        fresh[j] = W
    objs.append(('fresh', fresh)); return objs, info


def build(pick, take, side='right', body='pma', quiet=False, extra=None, kick_at=None, probe=False):
    gid = GUNS[take]; T = setup(gid); d = f'{OUT}/clips/{body}'; os.makedirs(d, exist_ok=True); name = prod.stem(gid, pick, take, CLIP, side)
    P = dict(TAKES_P[take]); P.update(PARAMS.get(pick + take, {})); P.update(extra or {}); c = prod.Ctx(gid, body, CLIP, P, 'Right'); tl = TL(c, 0, 0.0)
    plan = PICKS[pick][1](c, tl)
    for f in (kick_at or []): tl.kick(f, (0, -0.006 * P['k'], 0.004), (-3 * P['k'], 0, 0), attack=0.5, release=2.5)   # the jolt of the latch catching / shells seating
    Pt, Rt = tl.P.copy(), tl.R.copy(); Pt[-1] = 0; Rt[-1] = 0; Ps, Rs = inertia.spring(Pt, Rt, take); rep = inertia.report(Ps, Rs, Pt, Rt, tl.stops)
    keys = [K(f, Ps[f], Rs[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    kicks = [dict(k) for k in tl.kicks]
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {take}', '_doc': DOC[pick], '_gun': gid, '_left_gun': gid, '_body': body, '_side': 'Right',
            '_gun_clip': CLIP, '_pick': pick, '_take': take, '_timing': T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_two_arm': False, '_round': 'break-1',
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {'Right': keys, 'Left': [K(0)]}, 'shakes': {'Right': kicks},
            'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb', '_inertia': rep}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('WeaponRight'); G = [(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(c.N))]; GW = phys.worlds(G)
    drives = []
    for a, b, t0, t1 in plan.get('drives', []): drives.append((a, b, t0 if t0 is not None else tmax(gid), t1))
    th, ev = phys.hinge(GW, GEO[gid]['hinge_pivot'], GEO[gid]['hinge_axis'], BARREL_CM[gid], tmax(gid), bud(c)['latch'], drives=drives)
    if probe: return None, None, [GW[f] @ H(gid, th[f]) for f in range(c.N)]
    ld = plan['loads'][0]
    if ld[0] == 'sleeve' and extra is None:      # catch where the built clip throws them: release on the sleeve's fastest frame, fly, rebuild
        S = closed(gid, joints(gid)[0]).copy(); S[:3, 3] += SLEEVE_OFF; cen = np.r_[shell_centre(gid), 1]
        cs = [(GW[f] @ S @ cen)[:3] for f in range(F(c, 14), F(c, 21))]; sp = [np.linalg.norm(cs[k + 1] - cs[k]) for k in range(len(cs) - 1)]; fr = F(c, 14) + 1 + int(np.argmax(sp))
        p1 = (GW[fr] @ S @ cen)[:3]; v = p1 - (GW[fr - 1] @ S @ cen)[:3]; n = F(c, 27) - fr; pc = p1 + v * n + np.array([0, -phys.G_ACC, 0]) * n * (n + 1) / 2
        tgt = pc.copy(); C0 = closed(gid, joints(gid)[0])
        for it in range(4):      # the spring lags the target: shift the target by the miss until the chamber meets the shell
            _, _, GWi = build(pick, take, side, body, True, {'catch_pc': [float(x) for x in tgt], 'release_f': fr}, kick_at, probe=True)
            miss = pc - (GWi[F(c, 27)] @ C0 @ cen)[:3]; print(pick + take, 'catch iteration', it, 'miss cm', round(float(np.linalg.norm(miss)) * 100, 2), flush=True)
            if np.linalg.norm(miss) < 0.01: break
            tgt = tgt + miss
        return build(pick, take, side, body, quiet, {'catch_pc': [float(x) for x in tgt], 'release_f': fr}, kick_at)
    if kick_at is None and ev.get('shut') is not None:     # second pass: the gun jolts when the latch catches and when the shells seat
        seat_f = ld[-1] if ld[0] != 'sleeve' else ld[2]
        return build(pick, take, side, body, quiet, extra, [ev['shut'], seat_f])
    objs, info = shells(c, GW, plan, th, ev)
    spec['_part_frames'] = hinge_frames(gid, th); spec['_hinge_deg'] = [round(float(math.degrees(x)), 2) for x in th]
    inv = [np.linalg.inv(M) for M in GW]; J = {'names': [], 'joints': {}}
    for nm, per in objs:
        J['names'].append(nm); J['joints'][nm] = {j: [None if M is None else [round(float(x), 6) for x in (inv[f] @ M).ravel()] for f, M in enumerate(W)] for j, W in per.items()}
    spec['_objects'] = f'{d}/{name}_objects.json'; json.dump(J, open(spec['_objects'], 'w'))
    C0 = closed(gid, joints(gid)[0])
    dummy = {'frames': [{'m': [round(float(x), 6) for x in C0.ravel()], 's': 0.0, 'state': 'seated'}] * c.N, 'release': 1, 'free_from': 2, 'gone': c.N, 'exit_gun_axes': [0, 1, 0], 'enter_gun_axes': [0, -1, 0], 'plan': {'mode': 'none'}}
    spec['_track'] = f'{d}/{name}_track.json'; json.dump(dummy, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    if plan.get('seat'): spec['_timing'] = dict(T, seated=int(plan['seat'])); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, dummy)
    import rchecks, gungeo
    V = gungeo.verts(common.find('weapon_meshes', MESH[gid] + '__mag_std_01.glb'))[::4]; V1 = np.c_[V, np.ones(len(V))]; hs, he = o['layout']['hide_start'], o['layout']['hide_end']; seen = {}
    for nm, per in objs:
        on = sorted({f for W in per.values() for f, M in enumerate(W) if M is not None and rchecks.screen((V1 @ M.T)[:, :3])[2].any()})
        seen[nm] = [on[0], on[-1]] if on else None
        if nm == 'spent' and hs is not None and any(hs <= f <= he for f in on): o['fails'].append('spent shells on screen in the hidden window')
    o['shells_seen'] = seen; o['shells'] = info; o['hinge'] = {'events': ev, 'max_deg': round(float(np.degrees(th.max())), 1)}
    if ev.get('open') is None and not plan.get('drives'): o['fails'].append('barrels never reach the open stop')
    if info.get('eject') is None: o['fails'].append('shells never ejected')
    if ev.get('shut') is None: o['fails'].append('barrels never shut')
    elif ev['shut'] > c.N - 8: o['fails'].append(f"barrels shut late (f{ev['shut']})")
    shut_ok = ev.get('shut'); ldf = ld[-1] if ld[0] != 'sleeve' else ld[2]
    if shut_ok is not None and shut_ok < ldf: o['fails'].append(f'barrels shut (f{shut_ok}) before the shells are in (f{ldf})')
    for sp in info.get('spent', []):
        if sp['land'] is None: o['fails'].append('a spent shell does not land')
    o['inertia'] = rep; json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(name, '| fails', o['fails'], '| hinge', ev, 'max', o['hinge']['max_deg'], '| eject', info.get('eject'), info.get('spent'), info.get('catch_error_cm'), '| eye', o['eye_cm'], 'cover', o['cover_peak'], 'reach', o['reach'], 'sh', o['shoulder_pull_cm'], 'wrist', o['wrist'], o['wrist_view'], 'body', o['body_cm'], 'gap', o['guns_gap_cm'], 'hide', o['layout']['hide_start'], o['layout']['hide_end'], '| motion', o['motion']['peak_speed'], o['motion']['stop'], '| over', rep['max_overshoot_cm'], rep['max_overshoot_deg'], 'lag', rep['rotation_lag_f'], flush=True)
    return spec, o


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'; jobs = int(o('--jobs') or 1); takes = (o('--takes') or 'A,B').split(',')
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(PICKS)
    todo = [(p, t) for p in ids for t in takes]
    if cmd == 'list':
        for p, (n, fn) in PICKS.items(): print(p, n, '|', DOC[p])
    elif cmd == 'build':
        if jobs > 1:
            procs = [subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), '_part', json.dumps(todo[k::jobs])]) for k in range(jobs) if todo[k::jobs]]
            for p in procs: p.wait()
        else:
            for t in todo: build(*t)
    elif cmd == '_part':
        for t in json.loads(argv[1]): build(*t)
    else: raise SystemExit(__doc__)


# ------------------------------------------------------------------------------------------------ review hooks (shellreview.py)
TAKES = ['A', 'B']; TAKE_NAME = {'A': 'A snappy, Palica (light, 2.9 l)', 'B': 'B heavy, Satara (heavy, 5.8 l)'}; FILE = 'break_round1'
TITLE = 'Break-Open Shotgun Reloads, Round 1'
SHEET_TITLE = 'BREAK-OPEN shotguns, round 1: ten one-handed ways to break, eject, load two shells and shut (Palica A 76 f, Satara B 86 f; right hand, male V, empty reload).'
INTRO = ('<p>Ten one-handed techniques for a double-barrel break action while the other hand holds its gun: how the barrels are opened, '
         'how the spent shells leave, how two fresh shells go in, how the action is shut. Take <b>A</b> on the Palica (light), take <b>B</b> on the Satara (heavy). '
         'The Igla and the Testera have no shell joints or shell mesh at all (the game shows no shells for them) and the Testera has only an empty reload: '
         'they can play these clips only with borrowed Palica or Satara shells (or none), so they were not drafted. Right hand, male V, empty reload (both barrels).</p>'
         '<p class="muted"><b>Timing budget:</b> A 76 frames (latch f6, barrels open by about f12, hidden loading window about f28 to f46, shut on f57, idle f75); '
         'B the same beats about 13 % later (86 frames, shut on f64). <b>Inertia:</b> the gun follows the hand as a spring-damper mass. '
         '<b>Barrels:</b> a rigid body on the hinge pin, held by the latch until the thumb trips it, then moved by gravity and the gun\'s accelerations, '
         'pushed toward the open stop by the cocking springs (1 g at their centre); a decisive flick or stop swings them home and the latch catches with a jolt. '
         '<b>Shells:</b> the ejector kicks the spent pair out along the chamber axis (4 cm/f) at the open stop, on top of the velocity the moving barrels give them; free fall. '
         'Fresh shells wait in rigs and go in nose first along the chamber axis: pressed, dropped by gravity, thrown and caught. Previews only; nothing in game.</p>')


def stem(pick, take, side='right'): return prod.stem(GUNS[take], pick, take, CLIP, side)


def objects(spec):
    J = json.load(open(spec['_objects'])); mesh = common.find('weapon_meshes', MESH[spec['_gun']] + '__mag_std_01.glb'); col = {'spent': (0.85, 0.75, 0.2, 1)}
    return [{'mesh': mesh, 'joints': J['joints'][n], 'color': col.get(n, (1, 0.35, 0.1, 1))} for n in J['names']]


def key(s, g):
    ev = g['hinge']['events']; L = g['layout']; ej = g['shells'].get('eject') or 12
    return [('barrels open', ev.get('open', ej)), ('shells out', ej + 2), ('hidden: loading', (L['hide_start'] or 30) + 3), ('shut', ev.get('shut', s['_timing']['handle'][0]))]


def phase(s, g, f):
    L = g['layout']; ev = g['hinge']['events']; d = s['_hinge_deg'][min(f, len(s['_hinge_deg']) - 1)]
    if L['hide_start'] is not None and L['hide_start'] <= f <= L['hide_end']: return f'HIDDEN (loading, fast-forward) {d:.0f} deg'
    if ev.get('shut') is not None and abs(f - ev['shut']) <= 2: return f'shut ({d:.0f} deg)'
    if f < (g['shells'].get('eject') or 12) + 6: return f'breaking open ({d:.0f} deg)'
    return f'barrels {d:.0f} deg'


def numbers(s, g):
    I = g['inertia']; m = g['motion']; L = g['layout']; ev = g['hinge']['events']; sp = g['shells'].get('spent') or [{}]
    return [f"peak {m['peak_speed']} cm/f at {m['peak_at']}, stop {m['stop']}", f"overshoot {I['max_overshoot_cm']} cm / {I['max_overshoot_deg']} deg, lag {I['rotation_lag_f']} f",
            f"latch f{ev.get('release')}, open f{ev.get('open')}, shut f{ev.get('shut')}", f"shells out f{g['shells'].get('eject')} at {sp[0].get('carry_cm_f')} + kick 4 cm/f, land f{sp[0].get('land')}",
            f"hidden f{L['hide_start']}-{L['hide_end']} ({g['hidden_frames']} f)", f"eye {g['eye_cm'][0]} cm, cover {g['cover_peak'][0]} %",
            f"wrist {g['wrist'][0]} / in view {g['wrist_view']} deg", 'gate: ' + ('pass' if not g['fails'] else '; '.join(g['fails']))]


def shell_cell(s, g):
    sh = g['shells']; sp = sh.get('spent') or [{}]; ev = g['hinge']['events']
    t = f"out f{sh.get('eject')} ({sp[0].get('carry_cm_f')} cm/f + kick), land f{sp[0].get('land')}; shut f{ev.get('shut')}"
    if sh.get('catch_error_cm'): t += f"; caught {max(sh['catch_error_cm'])} cm off"
    if sh.get('toss_cm_f'): t += f"; tossed {sh['toss_cm_f']} cm/f"
    return t
