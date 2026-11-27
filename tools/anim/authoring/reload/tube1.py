"""TUBE shotguns (Carnage, Tactician: both light by bulk, one take A), round 1: ten one-handed ways to rack the pump
and feed the tube while the other hand holds its gun. Built on the Carnage, right hand, male V, empty reload.

usage: tube1.py list | build [ids] [--jobs n] | stats
Output: <OUT>/clips/pma/carnage_right_<id>A_empty_reload.glb, .json (spec), _objects.json (shells), _gate.json

Method (BRIEF-NEW-TECHNIQUES.md):
- The hand follows a target timeline (rlib2 moves); the gun is a mass on it (inertia.spring: underdamped
  spring-damper, position and rotation), so moves overshoot and settle, rotation lags, the muzzle trails.
- The pump fore-end is a loose slider (phys.slider) along the gun, opened and closed by the gun's own
  accelerations, gravity, or a contact that drives it; it locks once home after the loading. The spent shell rides
  back with the bolt and leaves the port when the bolt passes 6 cm, with its velocity from the bolt and the gun plus
  the ejector's sideways kick (EJECT); then free fall.
- Fresh shells wait in a rig (world-fixed) and are pressed into the loading port under the gun, pushed in by a rig,
  dropped in by gravity or thrown up by a rig spring and caught (free flight). The script loads the rest of the tube
  while the gun is out of view (the hidden window).
Timing budget (A, 76 frames): pump open by f10, first shell in by f24, hidden window about f28 to f46 (seat beat f38),
rise, pump shut on f57 (the rack hit), settle, idle at f75.
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

OUT = renv.OUT; GID = 'carnage'; CLIP = 'empty_reload'; TAKE = 'A'
GEO = json.load(open(OUT + '/ref/carnage_geometry.json' if os.path.exists(OUT + '/ref/carnage_geometry.json') else renv.SMG_REF + '/carnage_geometry.json'))      # OUT/ref, else the SMG production ref (rifle output folders have none)
CH, PORT, TUBEP = (np.array(GEO[k]) for k in ('chamber', 'port', 'tube')); SC = np.array(GEO['shell_centre'])
PUMP_P = np.array(GEO['pump_point']); PUMP_U = np.array([0.0, 0.0, 1.0]); PUMP_MAX = 0.085
PUMP_CURVE = np.array(GEO['pump_curve'])
SHELL_MESH = common.find('weapon_meshes', 'w_shotgun__budget_carnage__mag_std_01.glb')
EJECT = np.array([0.035, 0.02, 0.0])      # the ejector's kick, gun axes, m/frame (right and up): the only push not from the arm
BUDGET = {'open': 10, 'first_in': 24, 'seat': 38, 'home': 57, 'frames': 76}
PUNCH = prod.PUNCH; L = prod.L
ST = {'thigh': ((0.29, 0.10, -0.035), (-10, -10, 10)), 'hip': ((0.31, 0.165, -0.04), (-10, -14, 14)), 'belt': ((0.285, 0.145, -0.06), (-8, -8, 6)),
      'chest': ((0.16, 0.36, -0.20), (0, 6, 0)), 'shoulder': ((0.22, 0.62, -0.08), (30, -8, 0))}


def port_c(): return (PORT @ np.r_[SC, 1])[:3]


def setup():
    """Timing table and magazine data for the tools that expect them (Ctx, rgate); the magazine track is a dummy."""
    T = timing._cache.get((GID, CLIP))
    if T and T.get('_tube'): return T
    T = {'gun': GID, 'clip': CLIP, 'frames': BUDGET['frames'], 'out': BUDGET['open'], 'clear': None, 'far': None, 'near': BUDGET['seat'], 'seated': BUDGET['seat'],
         'exit_dir': [0, 1, 0], 'exit_speed_cm_f': 0, 'in_dir': [0, 1, 0], 'slot': [0, 0, 0], 'parts': {}, 'handle': [BUDGET['home'], BUDGET['home']], 'budget': BUDGET, '_tube': True}
    timing._cache[(GID, CLIP)] = T
    magtrack2._van[(GID, CLIP)] = {'M': [CH], 'seat': CH, 'centre': SC, 'exit': np.array([0, 1.0, 0]), 'enter': np.array([0, -1.0, 0]), 'dist': np.zeros(2), 'out': 0, 'seated': 1}
    return T


class TL(rlib2.TL):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.stops = []

    def to(self, f, pos, rot, prof='drive', antic=0.0, antic_f=3, rlag=None, rprof=None):
        if int(f) <= self.f: raise ValueError(f'move to f{f} from f{self.f}')
        p0 = self.p.copy(); super().to(f, pos, rot, prof, antic, antic_f, 0, rprof)
        d = np.array(pos, float) - p0
        if np.linalg.norm(d) > 0.03: self.stops.append((int(f), d / np.linalg.norm(d)))
        return self


def q_of(c, rot): return author.qmul(c.q0, author.qeuler(*rot))
def gun_vec(c, rot, v): return qrot(q_of(c, rot), np.asarray(v, float))


def place(c, X, rot, pt):
    """Grip offset that puts gun point pt (gun axes) on world point X with the gun at angles rot."""
    return np.asarray(X, float) - c.g0 - qrot(q_of(c, rot), np.asarray(pt, float))


def station(c, name):
    off, hint = ST[name]; return c.hips + np.array(off), hint


def left_forearm(c):
    a, b = c.joint('LeftForeArm'), c.joint('LeftHand'); return a + (b - a) * 0.45 + np.array([0.0, 0.05, 0.0])


def settle(c, tl, f):
    P = c.P; tl.hold(f + 3); e = min(f + 3 + L(P, 9), c.N - inertia.END - 1); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')


def go(c, tl, f, pos, rot, prof='drive', avg=0.055, avg_r=11.0, nmin=3):
    """Move arriving on f, started as late as its distance and turn allow (mean 5.5 cm or 11 deg per frame, so the
    peak lands near 9 to 10 cm/f); holds before it."""
    d = float(np.linalg.norm(np.asarray(pos, float) - tl.p)); r = float(np.max(np.abs(np.asarray(rot, float) - tl.r)))
    n = max(nmin, int(math.ceil(max(d / avg, r / avg_r)))); tl.hold(f - n)
    if f <= tl.f: f = tl.f + nmin
    tl.to(f, pos, rot, prof); return f


def rise_and_rack(c, tl, kind):
    """From the hidden rig up into view and the pump shut on the home frame h:
       punch    pushed forward and stopped dead: the fore-end runs on forward (inertia)
       yank     held out, a sharp start back: the fore-end stays and the gun runs back under it
       tipdown  the muzzle is tipped down 36 deg and held: the fore-end slides home by its weight
       flip     a muzzle-over flip about the wrist (Gorilla Arms): the fore-end is slung home by the spin"""
    P = c.P; h = BUDGET['home']
    if kind == 'punch':
        go(c, tl, h - 5, (0.02, -0.05, 0.05), (-4, 0, -4), 'rise'); tl.hold(h - 4); tl.mark('rack_start', h - 3); tl.to(h, (0.0, 0.005, -0.07), (1, 0, 0), PUNCH); end = h
    elif kind == 'yank':
        go(c, tl, h - 2, (0.01, -0.03, -0.07), (-3, 0, -3), 'rise'); tl.hold(h); tl.mark('rack_start', h); tl.to(h + 4, (0.0, -0.02, 0.07), (2, 0, -2), (1.15, 2.8)); end = h + 4
    elif kind == 'tipdown':
        go(c, tl, h - 7, (0.02, -0.06, -0.05), (0, 0, -3), 'rise'); tl.hold(h - 6); tl.mark('rack_start', h - 5); tl.to(h - 1, (0.02, -0.09, -0.06), (-P.get('tipdown', 36), 0, -3), 'heavy'); tl.hold(h + 2); end = h + 2
    elif kind == 'flip':
        go(c, tl, h - 11, (0.03, -0.06, -0.02), (-8, 0, -4), 'rise'); tl.hold(h - 10); tl.mark('rack_start', h - 9); tl.to(h - 5, (0.02, 0.03, 0.0), (48, 0, -4), 'drive'); tl.to(h, (0.01, -0.02, -0.03), (-22, 0, -2), 'slam'); end = h
    else: raise ValueError(kind)
    tl.mark('hit', h); settle(c, tl, end)


# ------------------------------------------------------------------------------------------------ openers
def open_thrust(c, tl):
    """From a short pull back the gun is thrust forward hard: the loose fore-end lags and slides open."""
    tl.hold(1); tl.to(5, (0.0, -0.01, 0.05), (2, 0, 0), 'ease'); tl.to(9, (0.0, 0.0, -0.08), (-1, 0, 0), (2.0, 1.2)); tl.mark('open', 7)


def open_flipup(c, tl):
    """The muzzle is flipped up steeply and held: the fore-end slides back down the barrel by its own weight."""
    tl.hold(1); tl.to(9, (0.0, 0.03, 0.03), (60, 0, -4), 'drive'); tl.mark('open', 9); tl.hold(15)      # held: the fore-end falls open in view


def press(c, tl, f, X, rot, depth=0.065, approach=0.06):
    """The loading port comes down on the shell at X from `approach` above (gun axes) and pushes it in."""
    o = place(c, X, rot, port_c()); go(c, tl, f - 3, o + gun_vec(c, rot, (0, approach + depth * 0.5, 0)), rot, 'drive'); tl.to(f, o + gun_vec(c, rot, (0, -0.004, 0)), rot, 'slam'); return ('press', f - 3, f)


# ------------------------------------------------------------------------------------------------ drafts
def t01(c, tl):
    """Throw and meet. The pump is thrown open by a hard thrust. A spring rig on the belt flicks a shell up in a short
    arc and the gun swoops down to meet it in the air with the loading port, then a second one; the rest of the tube is
    filled at the belt out of view; up, and a punch that stops dead throws the fore-end home."""
    open_thrust(c, tl); bx, br = station(c, 'belt'); loads = []; mr = (4, -6, -4)
    m1 = place(c, bx + np.array([0.02, 0.30, -0.18]), mr, port_c()); go(c, tl, 19, m1, mr, 'drive'); tl.hold(20); loads.append(('toss', 12, 19))
    m2 = place(c, bx + np.array([0.04, 0.26, -0.20]), mr, port_c()); go(c, tl, 25, m2, mr, 'snap'); tl.hold(26); loads.append(('toss', 17, 25))
    loads.append(press(c, tl, 36, bx, br)); tl.hold(38); rise_and_rack(c, tl, 'punch')
    return {'loads': loads}


def t02(c, tl):
    """Belt-row sweep. The muzzle is flipped up and the fore-end falls open by its own weight. The gun dives to a row
    of shells along the belt and sweeps along it in one continuous pass, the port taking a shell each time it crosses
    one (out of view). Up, muzzle tipped down: the fore-end slides home by its weight."""
    open_flipup(c, tl); bx, br = station(c, 'belt'); loads = []; sw = np.array([-0.07, 0.0, 0.0])
    o0 = place(c, bx - sw, br, port_c()) + gun_vec(c, br, (0, 0.01, 0)); go(c, tl, 24, o0 + gun_vec(c, br, (0, 0.07, 0)), br, 'drive'); tl.to(27, o0, br, 'heavy')
    for k in range(3): loads.append(('sweep', 27 + 4 * k, bx - sw + sw * k))
    tl.to(36, o0 + sw * 2, br, (1.6, 1.6)); tl.hold(38); rise_and_rack(c, tl, 'tipdown')
    return {'loads': loads}


def t03(c, tl):
    """Butt slam. The gun is swung muzzle-up and its butt slammed down on the outer thigh: the sudden stop throws the
    loose fore-end down the barrel, open. Shells pressed in at the hip caddy out of view. Up, the muzzle tipped down:
    the fore-end slides home by its weight."""
    tx, _ = station(c, 'thigh'); rot = (78, -8, 4); butt = np.array([0.0, -0.04, 0.27])
    top = place(c, tx + np.array([0.04, 0.24, -0.06]), rot, butt); go(c, tl, 9, top, rot, 'drive', avg_r=13); tl.hold(10)
    tl.to(13, place(c, tx + np.array([0.04, 0.10, -0.06]), rot, butt), rot, 'slam'); tl.mark('open', 13)
    hx, hr = station(c, 'hip'); loads = [press(c, tl, 26, hx, hr), press(c, tl, 34, hx + np.array([0, 0, 0.03]), hr, approach=0.05)]
    rise_and_rack(c, tl, 'tipdown')
    return {'loads': loads}


def t04(c, tl):
    """Inverted gravity feed. Gorilla wrist: the gun is rolled upside down above the shoulder so the loading port faces
    up under a shoulder dispenser, which lets two shells fall into it by their own weight. Rolled back, down to the
    hip caddy for the rest; up, and a punch that stops dead throws the fore-end home."""
    open_thrust(c, tl); sx, _ = station(c, 'shoulder'); rot = (6, -6, 172); off = place(c, sx + np.array([0.06, -0.10, -0.10]), rot, port_c())
    go(c, tl, 20, off, rot, 'drive', avg_r=14); tl.hold(27); loads = [('drop', 19, 24), ('drop', 22, 27)]
    hx, hr = station(c, 'hip'); loads.append(press(c, tl, 36, hx, hr)); tl.hold(38); rise_and_rack(c, tl, 'punch')
    return {'loads': loads}


def t05(c, tl):
    """Chest presenter. The muzzle is flipped up and the fore-end falls open. The gun is brought flat under a spring rig
    on the chest and held still: the rig pushes a shell up into the port (the rig moves, not the gun), twice; the rest
    at the belt caddy; a punch that stops dead throws the fore-end home."""
    open_flipup(c, tl); cx, cr = station(c, 'chest'); cr = (-4, 2, 4); oc = place(c, cx + np.array([0.02, -0.08, -0.10]), cr, port_c()); loads = []
    go(c, tl, 21, oc, cr, 'drive'); tl.hold(29); loads += [('present', 21, 24), ('present', 25, 28)]
    bx, br = station(c, 'belt'); loads.append(press(c, tl, 37, bx, br)); tl.hold(38); rise_and_rack(c, tl, 'punch')
    return {'loads': loads}


def t06(c, tl):
    """Stab loading, flip shut. Thrust open; the gun stabs down onto the hip caddy three times in quick succession,
    a shell each stab; up, and a muzzle-over flip about the wrist (Gorilla Arms) slings the fore-end home."""
    open_thrust(c, tl); hx, hr = station(c, 'hip'); loads = []
    for k, f in enumerate((22, 30, 38)): loads.append(press(c, tl, f, hx + np.array([0.0, 0.0, 0.03 * k]), hr, approach=0.05))
    rise_and_rack(c, tl, 'flip')
    return {'loads': loads}


def t07(c, tl):
    """Thigh station. The fore-end is slapped back against the outer thigh (the slap opens it), shells are pressed in
    from the thigh caddy right there, and a slap forward against the thigh drives it home; everything at the leg, then
    up into the idle."""
    tx, tr = station(c, 'thigh'); slap = place(c, tx + np.array([0.02, 0.10, -0.10]), tr, PUMP_P); loads = []
    go(c, tl, 9, slap + gun_vec(c, tr, (0, 0, -0.06)), tr, 'drive'); tl.to(12, slap + gun_vec(c, tr, (0, 0, 0.03)), tr, 'slam'); tl.mark('open', 11)
    for k, f in enumerate((20, 28, 36)): loads.append(press(c, tl, f, tx + np.array([0, 0, 0.02 * k]), tr, approach=0.05))
    h = 46; tl.hold(h - 6); tl.to(h - 3, slap + gun_vec(c, tr, (0, 0, 0.09)), tr, 'snap'); tl.to(h, slap + gun_vec(c, tr, (0, 0, -0.02)), tr, PUNCH); tl.mark('shut', h)
    tl.hold(h + 1); e = BUDGET['home']; go(c, tl, e, (0.004, -0.02, -0.03), (-2, 0, 0), 'rise'); tl.mark('hit', e); settle(c, tl, e)
    return {'loads': loads, 'pump': {'drives': [(9, 12, 0.0, PUMP_MAX), (h - 1, h + 1, PUMP_MAX, 0.0)]}}


def t08(c, tl):
    """Shoulder loops. The gun is lifted high beside the head, muzzle up (the fore-end falls open), and the port is
    pushed up onto shell loops on the shoulder strap; lowered to the belt caddy for the rest; up and the muzzle tipped
    down: the fore-end slides home by its weight."""
    sx, sr = station(c, 'shoulder'); rot = (58, -10, 2); loads = []
    tl.hold(1); tl.to(10, (0.04, 0.10, 0.02), rot, 'drive'); tl.mark('open', 10)
    o = place(c, sx, rot, port_c()); go(c, tl, 17, o + gun_vec(c, rot, (0, -0.06, 0)), rot, 'drive'); tl.to(20, o, rot, 'slam'); loads.append(('pressup', 17, 20))
    bx, br = station(c, 'belt'); loads.append(press(c, tl, 32, bx, br)); loads.append(press(c, tl, 38, bx + np.array([0, 0, 0.03]), br, approach=0.04))
    rise_and_rack(c, tl, 'tipdown')
    return {'loads': loads}


def t09(c, tl):
    """Chamber drop. Thrust open. The gun is rolled onto its left side so the open ejection port faces up and held
    still under the shoulder dispenser, which drops one shell straight into the open chamber; the tube is filled at
    the hip caddy out of view; a punch that stops dead closes the pump on the dropped shell."""
    open_thrust(c, tl); sx, _ = station(c, 'shoulder'); rot = (4, -4, 86); off = place(c, sx + np.array([0.08, -0.14, -0.14]), rot, (CH @ np.r_[SC, 1])[:3])
    go(c, tl, 19, off, rot, 'drive', avg_r=13); tl.hold(25); loads = [('chamber', 19, 25)]
    hx, hr = station(c, 'hip'); loads.append(press(c, tl, 33, hx, hr)); loads.append(press(c, tl, 38, hx + np.array([0, 0, 0.03]), hr, approach=0.04))
    rise_and_rack(c, tl, 'punch')
    return {'loads': loads}


SADDLE = CH.copy(); SADDLE[:3, 3] += np.array([0.045, -0.055, 0.03])     # a shell in a side saddle on the right of the receiver


def t10(c, tl):
    """Saddle flick. Thrust open. The gun's own side saddle carries a shell: an upward flick that stops dead throws it
    off the saddle into the air (the gun's speed at the stop), and the gun slides under it and catches it in the open
    ejection port as it falls; the tube is filled at the hip caddy out of view; a punch that stops dead closes the pump
    on the caught shell."""
    open_thrust(c, tl); r0 = (0, 0, -6); p0 = np.array((0.0, -0.04, -0.03)); go(c, tl, 13, p0, r0, 'ease'); tl.hold(14)
    up = p0 + np.array([0.0, 0.10, -0.01]); tl.to(17, up, r0, 'slam'); tl.mark('flick', 17)
    # predicted flight of the saddle shell from the stop (target path): catch it with the chamber on f25
    q = q_of(c, r0); c1 = c.g0 + up + qrot(q, (SADDLE @ np.r_[SC, 1])[:3]); c0 = c.g0 + tl.P[16] + qrot(q, (SADDLE @ np.r_[SC, 1])[:3])
    v = c1 - c0; n = 8; pc = c1 + v * n + np.array([0, -phys.G_ACC, 0]) * n * (n + 1) / 2
    pc = np.array(c.P.get('catch_pc', pc)); fr = c.P.get('release_f', 17)      # second pass: the flight of the built clip
    tl.to(25, place(c, pc, r0, (CH @ np.r_[SC, 1])[:3]), r0, 'drive'); tl.hold(27); tl.mark('catch', 25)
    hx, hr = station(c, 'hip'); loads = [('saddle', fr, 25), press(c, tl, 36, hx, hr)]; tl.hold(38)
    rise_and_rack(c, tl, 'punch')
    return {'loads': loads}


PICKS = {'TU01': ('Throw and meet', t01), 'TU02': ('Belt-row sweep', t02), 'TU03': ('Butt slam', t03), 'TU04': ('Inverted gravity feed', t04),
         'TU05': ('Chest presenter', t05), 'TU06': ('Stab loading, flip shut', t06), 'TU07': ('Thigh station', t07), 'TU08': ('Shoulder loops', t08),
         'TU09': ('Chamber drop', t09), 'TU10': ('Saddle flick', t10)}

DOC = {k: ' '.join((fn.__doc__ or '').split()) for k, (n, fn) in PICKS.items()}


# ------------------------------------------------------------------------------------------------ physics of the shells and the pump
def pump_frames(s):
    """Gun anim frame (cocking_handle) for each fore-end position: the game's opening stroke, read backwards."""
    c = PUMP_CURVE; a = int(np.argmax(c[:, 1] > c[0, 1] + 1e-4)); b = int(np.argmax(c[:, 1] >= c[:, 1].max() - 1e-5))      # the rising part only: the flat ends map one travel to many frames
    seg = c[max(a - 1, 0):b + 1]
    return [round(float(np.interp(x, seg[:, 1], seg[:, 0])), 3) for x in s]


def shell_tracks(c, GW, plan, s_pump, hit_open):
    """World matrix (or None) per frame for every shell: the spent one on the bolt, then free; the fresh ones waiting,
    pressed, dropped, presented or tossed into the port, then gone into the tube."""
    N = len(GW); objs = []; inv = [np.linalg.inv(M) for M in GW]
    # spent shell: on the bolt (chamber pose moved back with the fore-end), leaves the port past 6 cm
    W = [None] * N; rel = next((f for f in range(N) if s_pump[f] >= 0.06), None)
    for f in range(N):
        if rel is None or f <= rel: W[f] = GW[f] @ np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, s_pump[f]], [0, 0, 0, 1.0]]) @ CH
    info = {'spent_release': rel}
    if rel is not None:
        kick = GW[rel][:3, :3] @ EJECT; fl, land, v = phys.free_from(W[rel - 1], W[rel], N, rel, mesh_centre=SC, extra_v=kick)
        for g, M in fl.items(): W[g] = M
        info['spent_land'] = land; info['spent_speed_cm_f'] = round(float(np.linalg.norm((W[rel] @ np.r_[SC, 1])[:3] - (W[rel - 1] @ np.r_[SC, 1])[:3])) * 100, 2)
        info['spent_kick_cm_f'] = round(float(np.linalg.norm(EJECT)) * 100, 2)
    objs.append(('spent', W))
    out_up = np.eye(4); out_up[1, 3] = -0.065                       # port mouth: 6.5 cm below the seat, along the gun's down axis
    for k, ld in enumerate(plan['loads']):
        kind = ld[0]; W = [None] * N
        if kind in ('press', 'pressup'):
            f0, f1 = ld[1], ld[2]; Wr = GW[f1] @ PORT                 # the rig holds it where the port ends up at the bottom of the press
            for f in range(0, f1 + 1): W[f] = Wr
            for f in range(f1 + 1, min(f1 + 3, N)): W[f] = GW[f] @ (inv[f1] @ Wr)
        elif kind == 'sweep':
            f1, X = ld[1], ld[2]; Wr = GW[f1] @ PORT
            for f in range(0, f1 + 1): W[f] = Wr
            for f in range(f1 + 1, min(f1 + 3, N)): W[f] = GW[f] @ (inv[f1] @ Wr)
        elif kind == 'present':
            f0, f1 = ld[1], ld[2]                                    # the rig pushes it from 6.5 cm under the port up into it while the gun holds still
            for f in range(0, f0 + 1): W[f] = GW[f0] @ out_up @ PORT
            for f in range(f0 + 1, f1 + 1): t = (f - f0) / (f1 - f0); M = np.eye(4); M[1, 3] = -0.065 * (1 - t * t); W[f] = GW[f] @ M @ PORT
            for f in range(f1 + 1, min(f1 + 3, N)): W[f] = GW[f] @ PORT
        elif kind in ('drop', 'chamber'):
            f0, f1 = ld[1], ld[2]; Wt = GW[f1] @ (PORT if kind == 'drop' else CH); d = 0.5 * phys.G_ACC * (f1 - f0) ** 2   # released from rest that far above, it falls into the port on f1
            for f in range(0, f0 + 1): M = Wt.copy(); M[1, 3] += d; W[f] = M
            for f in range(f0 + 1, f1 + 1): M = Wt.copy(); M[1, 3] += d - 0.5 * phys.G_ACC * (f - f0) ** 2; W[f] = M
            for f in range(f1 + 1, min(f1 + 3, N)): W[f] = GW[f] @ (inv[f1] @ Wt)
        elif kind == 'toss':
            f0, f1 = ld[1], ld[2]; Wt = GW[f1] @ PORT; n = f1 - f0; bx, _ = station(c, 'belt'); p0 = bx + np.array([0.04, 0.02, -0.12])
            pt = (Wt @ np.r_[SC, 1])[:3]; v0 = (pt - p0) / n - np.array([0, -phys.G_ACC, 0]) * (n + 1) / 2   # ballistic from the rig's spring to the port on f1
            for f in range(0, f0 + 1): M = Wt.copy(); M[:3, 3] += p0 - pt; W[f] = M
            for f in range(f0 + 1, f1 + 1):
                j = f - f0; p = p0 + v0 * j + np.array([0, -phys.G_ACC, 0]) * j * (j + 1) / 2; M = Wt.copy(); M[:3, 3] += p - pt; W[f] = M
            for f in range(f1 + 1, min(f1 + 3, N)): W[f] = GW[f] @ (inv[f1] @ Wt)
            info.setdefault('toss_speed_cm_f', []).append(round(float(np.linalg.norm(v0)) * 100, 2))
        if kind == 'saddle':
            f0, f1 = ld[1], ld[2]
            for f in range(0, f0 + 1): W[f] = GW[f] @ SADDLE
            fl, land, v = phys.free_from(W[f0 - 1], W[f0], N, f0, mesh_centre=SC)
            for g in range(f0 + 1, f1): W[g] = fl.get(g)
            Wc = GW[f1] @ CH; err = float(np.linalg.norm(((fl.get(f1, Wc) @ np.r_[SC, 1]) - (Wc @ np.r_[SC, 1]))[:3])) * 100
            for f in range(f1, min(f1 + 30, N)): W[f] = GW[f] @ CH
            car = [(GW[f] @ SADDLE @ np.r_[SC, 1])[:3] for f in (f0 - 3, f0 - 2, f0 - 1, f0)]
            info['saddle'] = {'release': f0, 'exit_cm_f': round(float(np.linalg.norm((W[f0 + 1] @ np.r_[SC, 1])[:3] - (W[f0] @ np.r_[SC, 1])[:3] - np.array([0, -phys.G_ACC, 0]))) * 100, 2),
                              'gun_cm_f': round(max(float(np.linalg.norm(car[i + 1] - car[i])) for i in range(3)) * 100, 2), 'catch_error_cm': round(err, 2)}
        objs.append((f'fresh{k + 1}', W))
    return objs, info


# ------------------------------------------------------------------------------------------------ build and gate
def obj_checks(c, spec, GW, objs, layout):
    """Shells on screen inside the hidden window (fails), free-fall check of the spent shell, landing."""
    import rchecks, gungeo
    V = gungeo.verts(SHELL_MESH)[::3]; V1 = np.c_[V, np.ones(len(V))]; hs, he = layout['hide_start'], layout['hide_end']; fails = []; seen = {}
    for name, W in objs:
        on = [f for f, M in enumerate(W) if M is not None and rchecks.screen((V1 @ M.T)[:, :3])[2].any()]
        seen[name] = [on[0], on[-1]] if on else None
        if hs is not None and any(hs <= f <= he for f in on): fails.append(f'{name} on screen in the hidden window')
    sp = objs[0][1]; C = np.array([(M @ np.r_[SC, 1])[:3] if M is not None else [np.nan] * 3 for M in sp]); A = C[2:] - 2 * C[1:-1] + C[:-2]
    return fails, seen


def build(pick, side='right', body='pma', quiet=False, extra=None):
    T = setup(); d = f'{OUT}/clips/{body}'; os.makedirs(d, exist_ok=True); name = prod.stem(GID, pick, TAKE, CLIP, side)
    P = dict(prod.TAKES['A'], drag=0.0, lag=0); P.update(extra or {}); c = prod.Ctx(GID, body, CLIP, P, 'Right'); tl = TL(c, 0, 0.0)
    plan = PICKS[pick][1](c, tl)
    Pt, Rt = tl.P.copy(), tl.R.copy(); Pt[-1] = 0; Rt[-1] = 0; Ps, Rs = inertia.spring(Pt, Rt, TAKE); rep = inertia.report(Ps, Rs, Pt, Rt, tl.stops)
    keys = [K(f, Ps[f], Rs[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {TAKE}', '_doc': DOC[pick], '_gun': GID, '_left_gun': GID, '_body': body, '_side': 'Right',
            '_gun_clip': CLIP, '_pick': pick, '_take': TAKE, '_timing': T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_two_arm': False, '_round': 'tube-1',
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {'Right': keys, 'Left': [K(0)]}, 'shakes': {'Right': []},
            'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb', '_inertia': rep}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('WeaponRight'); G = [(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(c.N))]; GW = phys.worlds(G)
    sad = next((ld for ld in plan['loads'] if ld[0] == 'saddle'), None)
    if sad is not None and extra is None:      # catch where the built clip actually throws it: release on the saddle's fastest frame, fly it, rebuild
        cs = [(GW[f] @ SADDLE @ np.r_[SC, 1])[:3] for f in range(12, 21)]; sp = [np.linalg.norm(cs[k + 1] - cs[k]) for k in range(len(cs) - 1)]; fr = 13 + int(np.argmax(sp))
        p1 = (GW[fr] @ SADDLE @ np.r_[SC, 1])[:3]; v = p1 - (GW[fr - 1] @ SADDLE @ np.r_[SC, 1])[:3]; n = 25 - fr; pc = p1 + v * n + np.array([0, -phys.G_ACC, 0]) * n * (n + 1) / 2
        return build(pick, side, body, quiet, {'catch_pc': [float(x) for x in pc], 'release_f': fr})
    drives = plan.get('pump', {}).get('drives', []); s, hit = phys.slider(GW, PUMP_P, PUMP_U, PUMP_MAX, drives=drives, lock_home_after=BUDGET['seat'], rest=0.1)
    if hit is not None:      # once at its rear stop the fore-end stays there (friction) until the rack starts: re-run with that hold
        rack0 = int(tl.marks.get('rack_start', BUDGET['seat'] + 6)); s, hit = phys.slider(GW, PUMP_P, PUMP_U, PUMP_MAX, drives=drives, locks=[(hit + 1, rack0, PUMP_MAX)], lock_home_after=rack0, rest=0.1)
    s = np.where(np.arange(c.N) > c.N - 4, 0.0, s)
    objs, info = shell_tracks(c, GW, plan, s, hit); spec['_first_load'] = int(plan['loads'][0][2] if plan['loads'][0][0] not in ('sweep', 'saddle') else plan['loads'][0][1]); spec['_part_frames'] = pump_frames(s); spec['_pump_cm'] = [round(float(x) * 100, 2) for x in s]
    inv = [np.linalg.inv(M) for M in GW]
    J = {'joints': {}, 'names': []}
    for nm, W in objs: J['names'].append(nm); J['joints'][nm] = [None if M is None else [round(float(x), 6) for x in (inv[f] @ M).ravel()] for f, M in enumerate(W)]
    spec['_objects'] = f'{d}/{name}_objects.json'; json.dump(J, open(spec['_objects'], 'w'))
    dummy = {'frames': [{'m': [round(float(x), 6) for x in CH.ravel()], 's': 0.0, 'state': 'seated'}] * c.N, 'release': 1, 'free_from': 2, 'gone': c.N, 'exit_gun_axes': [0, 1, 0], 'enter_gun_axes': [0, -1, 0], 'plan': {'mode': 'none'}}
    spec['_track'] = f'{d}/{name}_track.json'; json.dump(dummy, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, dummy); f2, seen = obj_checks(c, spec, GW, objs, o['layout']); o['fails'] += f2; o['shells_seen'] = seen; o['shells'] = info
    opened = next((f for f in range(c.N) if s[f] >= PUMP_MAX - 0.002), None); home = next((f for f in range(BUDGET['seat'], c.N) if s[f] <= 0.002), None)
    o['pump'] = {'open_frame': opened, 'home_frame': home, 'max_cm': round(float(s.max()) * 100, 2)}
    if opened is None: o['fails'].append('pump never opens')
    if home is None or home > c.N - 6: o['fails'].append('pump never closes')
    if info.get('spent_release') is None: o['fails'].append('spent shell never leaves')
    elif info.get('spent_land') is None: o['fails'].append('spent shell does not land')
    o['inertia'] = rep; json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(name, '| fails', o['fails'], '| pump open', opened, 'home', home, '| spent', info, '| eye', o['eye_cm'], 'cover', o['cover_peak'], 'reach', o['reach'], 'sh', o['shoulder_pull_cm'], 'wrist', o['wrist'], o['wrist_view'], 'body', o['body_cm'], 'gap', o['guns_gap_cm'], 'hide', o['layout']['hide_start'], o['layout']['hide_end'], '| motion', o['motion']['peak_speed'], o['motion']['stop'], '| over', rep['max_overshoot_cm'], rep['max_overshoot_deg'], 'lag', rep['rotation_lag_f'], flush=True)
    return spec, o


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'; jobs = int(o('--jobs') or 1)
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(PICKS)
    if cmd == 'list':
        for p, (n, fn) in PICKS.items(): print(p, n, '|', DOC[p])
    elif cmd == 'build':
        if jobs > 1:
            procs = [subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), '_part', json.dumps(ids[k::jobs])]) for k in range(jobs) if ids[k::jobs]]
            for p in procs: p.wait()
        else:
            for p in ids: build(p)
    elif cmd == '_part':
        for p in json.loads(argv[1]): build(p)
    else: raise SystemExit(__doc__)


# ------------------------------------------------------------------------------------------------ review hooks (shellreview.py)
TAKES = ['A']; TAKE_NAME = {'A': 'A, Carnage (light; the Tactician is light too)'}; FILE = 'tube_round1'
TITLE = 'Tube Shotgun Reloads, Round 1'
SHEET_TITLE = 'TUBE shotguns, round 1: ten one-handed ways to rack the pump and feed the tube (Carnage, right hand, male V, empty reload, 76 frames).'
INTRO = ('<p>Ten one-handed techniques for a pump shotgun with a tube magazine while the other hand holds its gun: how the pump is opened, '
         'how shells get into the loading port, how it is closed. Built on the <b>Carnage</b> (light by bulk, 4.8 l); the Tactician is light too (2.9 l), '
         'so there is one take; its loading port and pump were not built (unverified). Right hand, male V, empty reload, from the dual-wield idle back to it.</p>'
         '<p class="muted"><b>Timing budget</b> (all ten, 30 fps): pump open by f10, first shell in by about f24, hidden window about f28 to f46 '
         '(the script loads the rest of the tube there, as today), rise, pump shut on f57, idle at f75 (76 frames). '
         '<b>Inertia:</b> the hand follows the timeline and the gun follows the hand as a spring-damper mass (overshoot, rebound, rotation lag, muzzle trail). '
         '<b>Pump:</b> the fore-end is a loose slider driven by the gun\'s accelerations and gravity, or by a contact; it locks once home. '
         '<b>Shells:</b> the spent shell rides back with the bolt and leaves the port with the bolt\'s and the gun\'s velocity plus the ejector\'s kick (3.5 cm/f right, 2 up), then free fall; '
         'fresh shells wait in rigs and are pressed, pushed, dropped or thrown into the port, or thrown off the gun\'s own saddle and caught. Gravity 9.81 m/s2 at 30 fps, no drag. '
         'Previews only; nothing in game.</p>')


def stem(pick, take='A', side='right'): return prod.stem(GID, pick, take, CLIP, side)


def objects(spec):
    J = json.load(open(spec['_objects'])); col = {'spent': (0.85, 0.75, 0.2, 1)}
    return [{'mesh': SHELL_MESH, 'joints': {'mag_std': J['joints'][n]}, 'color': col.get(n, (1, 0.35, 0.1, 1))} for n in J['names']]


def key(s, g):
    mk = s['_marks']; L = g['layout']; ld = g['shells']
    first = next((f for f in range(s['frames']) if s['_pump_cm'][f] > 4), 8)
    vis = int(s['_first_load']) if s.get('_first_load') else 20
    home = g['pump']['home_frame'] or mk.get('hit', BUDGET['home'])
    return [('pump opens', first), ('first shell', vis), ('hidden: loading', (L['hide_start'] or 30) + 3), ('pump shut', home)]


def phase(s, g, f):
    L = g['layout']; mk = s['_marks']; pc = s['_pump_cm'][min(f, len(s['_pump_cm']) - 1)]
    if L['hide_start'] is not None and L['hide_start'] <= f <= L['hide_end']: return 'HIDDEN (loading, fast-forward)'
    if abs(f - mk.get('hit', 999)) <= 2: return f'pump shut ({pc:.1f} cm)'
    if f < 12: return f'opening ({pc:.1f} cm)'
    if f < 30: return 'loading'
    return 'up'


def numbers(s, g):
    I = g['inertia']; m = g['motion']; L = g['layout']; sh = g['shells']; pm = g['pump']
    return [f"peak {m['peak_speed']} cm/f at {m['peak_at']}, stop {m['stop']}", f"overshoot {I['max_overshoot_cm']} cm / {I['max_overshoot_deg']} deg, lag {I['rotation_lag_f']} f",
            f"pump open f{pm['open_frame']}, home f{pm['home_frame']}", f"spent shell out f{sh.get('spent_release')}, lands f{sh.get('spent_land')}",
            f"hidden f{L['hide_start']}-{L['hide_end']} ({g['hidden_frames']} f)", f"eye {g['eye_cm'][0]} cm, cover {g['cover_peak'][0]} %",
            f"wrist {g['wrist'][0]} / in view {g['wrist_view']} deg", 'gate: ' + ('pass' if not g['fails'] else '; '.join(g['fails']))]


def shell_cell(s, g):
    sh = g['shells']; t = f"spent f{sh.get('spent_release')}->f{sh.get('spent_land')}"
    if 'saddle' in sh: t += f", saddle shell {sh['saddle']['exit_cm_f']}/{sh['saddle']['gun_cm_f']} cm/f, caught {sh['saddle']['catch_error_cm']} cm off"
    if 'toss_speed_cm_f' in sh: t += ', tossed ' + '/'.join(str(x) for x in sh['toss_speed_cm_f']) + ' cm/f'
    return t
