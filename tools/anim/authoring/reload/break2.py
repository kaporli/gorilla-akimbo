"""BREAK-OPEN shotguns, round 2: one-handed reloads of the double-barrel break action, grounded in captured game
references (refs/refs.md) and the mechanism research (RESEARCH.md). Take A on the Palica (snappy), take B on the
Satara (heavy); right hand, male V, empty reload (both barrels). Previews only.

usage: break2.py list | build [ids] [--takes A,B] | table | stats
Output: <OUT>/clips/pma/<gun>_right_<id><take>_empty_reload.glb, .json (spec), _objects.json (shells), _prims.json
(drawn rig), _gate.json, _phys.json

Pipeline per take
 1. The draft writes the hand's TARGET timeline (TL) and a plan (lever frame, body contacts, loading).
 2. inertia.simulate_gun (FRONT round 4 model): the gun follows the target as a mass on an underdamped
    spring-damper (overshoot, rebound, rotation lag, muzzle trail); body stops are contact planes.
 3. author.py builds the arm clip from the simulated gun; the gun's world pose per frame is read back.
 4. breakphys.simulate: the barrels on the hinge pin under the gun's real motion (inertia about the pin, gravity,
    cocking and ejector springs, friction, open stop, the bolt that latches only above w_latch, body contacts).
 5. The reactions go back into the gun: the barrels hitting the open stop and the bolt catching give the gun an
    angular impulse (barrels' angular momentum over the gun-and-hand inertia); steps 2 to 4 run again (3 passes).
 6. Spent shells (ejectors at the trip angle), fresh shells (rigid bodies from the drawn rig), gate, stats.
"""
import os, sys, json, math, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, rlib2, prod, rgate, timing, magtrack2, inertia, breakphys as bp
from rlib import K
from glb import Glb
from fk import Clip, qrot

OUT = renv.OUT; CLIP = 'empty_reload'; FPS = 30.0
GUNS = {'A': 'palica', 'B': 'satara'}
MESH = bp.MESH
GEO = bp.GEO
# One budget per take. A: the length of the game's own Palica empty reload (66 f). B: 13 % longer (75 f); its shut
# beat f58 is the game's own Satara shut frame (f57 to f58 in its anim). The seat comes late enough for thrown hulls to
# leave the screen before the hidden window.
BUDGET = {'A': {'frames': 66, 'lever': 4, 'open_by': 11, 'seat': 38, 'shut': 51}, 'B': {'frames': 75, 'lever': 5, 'open_by': 12, 'seat': 43, 'shut': 58}}
TAKES_P = {'A': dict(prod.TAKES['A'], drag=0.0, lag=0), 'B': dict(prod.TAKES['B'], w=1.13, drag=0.0, lag=0)}
I_GUN = {'palica': 0.045, 'satara': 0.16}     # gun and hand inertia about the wrist (kg m2) for the reaction jolts, unverified
JOLT_CAP_DEG = 9.0


def take_of(gid): return 'A' if gid == 'palica' else 'B'
def bud(c): return BUDGET[take_of(c.gun)]
def joints(gid): return GEO[gid]['joints']
def closed(gid, j): return np.array(GEO[gid]['closed'][j])
def tmax(gid): return math.radians(GEO[gid]['open_deg'])
def H(gid, th): return bp.hinge_rot(gid, th)
def F(c, f): return int(round(f * c.P['w']))


_sc = {}
def shell_centre(gid):
    if gid not in _sc:
        import gungeo
        _sc[gid] = gungeo.verts(common.find('weapon_meshes', MESH[gid] + '__mag_std_01.glb')).mean(0)
    return _sc[gid]


def chamber_pt(gid, th=None):
    th = tmax(gid) if th is None else th; sc = shell_centre(gid)
    return np.mean([(H(gid, th) @ closed(gid, j) @ np.r_[sc, 1])[:3] for j in joints(gid)], axis=0)


def u_out(gid, th=None):
    th = tmax(gid) if th is None else th; R = (H(gid, th) @ closed(gid, joints(gid)[0]))[:3, :3]; return R @ np.array([0, 0, 1.0])


def setup(gid):
    T = timing._cache.get((gid, CLIP))
    if T and T.get('_break2'): return T
    B = BUDGET[take_of(gid)]
    T = {'gun': gid, 'clip': CLIP, 'frames': B['frames'], 'out': B['lever'], 'clear': None, 'far': None, 'near': B['seat'], 'seated': B['seat'], 'exit_dir': [0, 1, 0],
         'exit_speed_cm_f': 0, 'in_dir': [0, 1, 0], 'slot': [0, 0, 0], 'parts': {}, 'handle': [B['shut'], B['shut']], 'budget': B, '_break2': True}
    timing._cache[(gid, CLIP)] = T; C = closed(gid, joints(gid)[0])
    magtrack2._van[(gid, CLIP)] = {'M': [C], 'seat': C, 'centre': shell_centre(gid), 'exit': np.array([0, 1.0, 0]), 'enter': np.array([0, -1.0, 0]), 'dist': np.zeros(2), 'out': 0, 'seated': 1}
    return T


class TL(rlib2.TL):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.guides = []

    def path(self, f0, f1, fn):
        for f in range(int(f0) + 1, int(f1) + 1):
            p, r = fn(f); self.P[f] = p; self.R[f] = r
        self.P[int(f1) + 1:] = self.P[int(f1)]; self.R[int(f1) + 1:] = self.R[int(f1)]
        self.f = int(f1); self.rf = int(f1); self.p = np.array(self.P[int(f1)]); self.r = np.array(self.R[int(f1)]); return self


def q_of(c, rot): return author.qmul(c.q0, author.qeuler(*rot))
def gun_vec(c, rot, v): return qrot(q_of(c, rot), np.asarray(v, float))
def place(c, X, rot, pt):
    """Grip offset that puts the gun-axes point pt at world X with the gun at angles rot."""
    return np.asarray(X, float) - c.g0 - qrot(q_of(c, rot), np.asarray(pt, float))
def world_of(c, off, rot, pt): return c.g0 + np.asarray(off, float) + qrot(q_of(c, rot), np.asarray(pt, float))


def go(c, tl, f, pos, rot, prof='drive', avg=0.055, avg_r=11.0, nmin=3):
    d = float(np.linalg.norm(np.asarray(pos, float) - tl.p)); r = float(np.max(np.abs(np.asarray(rot, float) - tl.r)))
    n = max(nmin, int(math.ceil(max(d / avg, r / avg_r) * c.P['w']))); tl.hold(f - n)
    if f <= tl.f: f = tl.f + nmin
    tl.to(f, pos, rot, prof); return f


def settle(c, tl, f, n=10):
    tl.hold(f + 2); e = min(f + 2 + prod.L(c.P, n), c.N - 4)
    if e > tl.f: tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')


def thumb(c, tl):
    """The thumb pushes the top lever over on the lever beat: a small twitch of the gun (the thumb's reach)."""
    f = bud(c)['lever']; tl.hold(f - 2); tl.to(f, tl.p + np.array((0.0, 0.003, 0.004)), tl.r + np.array((1.5, 0, -1.5)), 'snap'); tl.mark('lever', f); return f


def insert_onto(c, tl, f_seat, X, rot, depth=0.07, n=4, th=None, avg_r=7.0, arrive=None, prof=(3.2, 1.6)):
    """Drive the open chambers (barrels at th, open stop by default) onto shells whose centres sit at world X, along
    the chamber axis: hover `depth` back (arriving on `arrive`, profile prof: a gentle start, so the open barrels are
    not thrown shut by the gun's own acceleration), then push home on f_seat; the hand drives 1 cm past and the
    shells stop the gun (contact plane). Returns the gun contact."""
    gid = c.gun; o = place(c, X, rot, chamber_pt(gid, th)); uo = gun_vec(c, rot, u_out(gid, th))
    if arrive is None: go(c, tl, f_seat - n, o - uo * depth, rot, prof, avg_r=avg_r)
    else: tl.to(arrive, o - uo * depth, rot, prof); tl.hold(f_seat - n)
    tl.to(f_seat - 1, o + uo * 0.010, rot, (2.6, 1.6)); tl.to(f_seat + 1, o, rot, 'ease')
    return {'name': 'shells seat', 'f': [f_seat - n, f_seat + 1], 'anchor': np.array(o, float), 'n': uo / np.linalg.norm(uo), 'axis': tuple(np.array(GEO[gid]['hinge_axis'])), 'e': 0.2, 'jolt': 0.6}


# ------------------------------------------------------------------------------------------------ fresh shells and drawn rigs
LEATHER = [0.36, 0.22, 0.12, 1]; STEEL = [0.45, 0.47, 0.5, 1]


def mrow(M): return [round(float(x), 6) for x in np.asarray(M, float).ravel()]


def box_at(M, centre, size, color, frames, rot=None):
    """A drawn box: pose M (shell or rig frame, world), centre in that frame, size (x, y, z of that frame)."""
    B = np.array(M, float).copy()
    if rot is not None: B[:3, :3] = B[:3, :3] @ rot
    B[:3, 3] = (np.asarray(M, float) @ np.r_[centre, 1])[:3]
    return {'shape': 'box', 'size': [float(s) for s in size], 'color': color, 'frames': [mrow(B) if f in frames else None for f in range(frames[-1] + 1 if frames else 0)]}


def static(prim, N):
    rows = prim['frames']; row = next(r for r in rows if r is not None); prim['frames'] = [row] * N; return prim


def chamber_world(c, GW, th, f, j): return GW[f] @ H(c.gun, th[f]) @ closed(c.gun, j)


def rig_holder(c, mats, N, strap=None, depth=0.018):
    """A rim-clip shell holder (cowboy-action caddy style): a block behind the rims of both shells, clips round the
    last 15 mm of each, and a strap to the body (world end point) if given. mats: {joint: shell world matrix}."""
    js = list(mats); M0 = mats[js[0]]; M1 = mats[js[-1]]; sc = shell_centre(c.gun)
    mid = 0.5 * (M0 + M1); mid[:3, :3] = M0[:3, :3]; w = float(np.linalg.norm(M0[:3, 3] - M1[:3, 3])) + 0.05
    loc = np.linalg.inv(M0) @ np.r_[mid[:3, 3], 1]
    pr = [static(box_at(M0, (loc[0], sc[1], depth * 0.5 + 0.004), (w, 0.032, depth), LEATHER, [0]), N)]
    for j in js: pr.append(static(box_at(mats[j], (sc[0], sc[1], -0.006), (0.036, 0.036, 0.014), STEEL, [0]), N))
    if strap is not None:
        a = (M0 @ np.r_[loc[0], sc[1], depth + 0.004, 1])[:3]; b = np.asarray(strap, float); d = b - a; L = float(np.linalg.norm(d))
        if L > 0.01:
            y = d / L; x = np.cross(y, [0, 0, 1.0]); x = x / (np.linalg.norm(x) or 1); z = np.cross(x, y); S = np.eye(4); S[:3, :3] = np.c_[x, y, z]; S[:3, 3] = (a + b) / 2
            pr.append(static({'shape': 'box', 'size': [0.035, L, 0.008], 'color': LEATHER, 'frames': [mrow(S)]}, N))
    return pr


def load_press(rig='holder', strap=None):
    """The open chambers are driven onto two shells waiting rim-first in a holder (world-fixed, on the body): the
    shells stand still until the breech face reaches the rim (the seat frame), then ride the chambers; the gun stops
    on them (contact plane in the gun simulation). The holder pose comes from the built clip (where the chambers
    actually are on the seat frame)."""
    def fn(c, GW, th, ph, plan):
        se = plan['seat']; N = len(GW); js = joints(c.gun); fresh = {}; mats = {j: chamber_world(c, GW, th, se, j) for j in js}
        for j in js: fresh[j] = [mats[j] if f < se else chamber_world(c, GW, th, f, j) for f in range(N)]
        cen = np.r_[shell_centre(c.gun), 1]; u = mats[js[0]][:3, :3] @ np.array([0, 0, 1.0])
        a = [(chamber_world(c, GW, th, f, js[0]) @ cen)[:3] for f in (se - 2, se - 1, se)]; v = (a[2] - a[1]) * 100; lat = float(np.linalg.norm(v - (v @ u) * u))
        st = {'kind': 'press', 'seat': se, 'insert_cm_f': round(float(-(v @ u)), 2), 'off_axis_cm_f': round(lat, 2), 'barrels_deg_at_seat': round(math.degrees(th[se]), 1)}
        return fresh, st, rig_holder(c, mats, N, strap)
    return fn


def load_toss(launch, rig_off, strap=None):
    """A spring rig throws both shells; they fly as rigid bodies (gravity, constant spin) into the open chambers,
    which meet them on the seat frame. rig_off: world offset of the rig from the catch point (the launch velocity
    follows from it and the flight time)."""
    def fn(c, GW, th, ph, plan):
        se = plan['seat']; N = len(GW); js = joints(c.gun); T = se - launch; fresh = {}; st = {'kind': 'toss', 'launch': launch, 'seat': se}
        g = np.array([0, -bp.G / FPS / FPS, 0]); cen = np.r_[shell_centre(c.gun), 1]; mats0 = {}
        for j in js:
            M1 = chamber_world(c, GW, th, se, j); p1 = (M1 @ cen)[:3]; p0 = p1 + np.asarray(rig_off, float)
            R1 = M1[:3, :3]; R0 = magtrack2.rot_axis([1, 0, 0], math.radians(-35)) @ R1           # in the rig the shell leans back 35 deg
            v0 = (p1 - p0 - 0.5 * g * T * T) / T; Rr = R1 @ R0.T; ang = math.acos(max(-1, min(1, (np.trace(Rr) - 1) / 2)))
            ax = np.array([Rr[2, 1] - Rr[1, 2], Rr[0, 2] - Rr[2, 0], Rr[1, 0] - Rr[0, 1]]); ax = ax / (np.linalg.norm(ax) or 1)
            W = []
            for f in range(N):
                if f < launch: R, p = R0, p0
                elif f < se: t = f - launch; p = p0 + v0 * t + 0.5 * g * t * t; R = magtrack2.rot_axis(ax, ang * t / T) @ R0
                else: W.append(chamber_world(c, GW, th, f, j)); continue
                M = np.eye(4); M[:3, :3] = R; M[:3, 3] = p - R @ cen[:3]; W.append(M)
            fresh[j] = W; mats0[j] = W[0]; st.setdefault('launch_m_s', round(float(np.linalg.norm(v0)) * FPS, 2)); st.setdefault('spin_deg_f', round(math.degrees(ang) / T, 1))
            vrel = (p1 - (p0 + v0 * (T - 1) + 0.5 * g * (T - 1) ** 2)) - ((chamber_world(c, GW, th, se, j) @ cen)[:3] - (chamber_world(c, GW, th, se - 1, j) @ cen)[:3])
            st.setdefault('catch_rel_cm_f', round(float(np.linalg.norm(vrel)) * 100, 2))
        return fresh, st, rig_holder(c, mats0, N, strap)
    return fn


# ------------------------------------------------------------------------------------------------ drafts (after refs/refs.md)
# Rig stations: world offset from the hips joint of the chamber centre on the seat frame (x right, y up, z back).
# grip position (offset from the hips joint) on the seat frame for each rig; the holder hangs where the chambers are
RIG = {'belt': (0.20, 0.19, -0.03), 'hip': (0.25, 0.16, 0.0), 'thigh': (0.24, 0.10, -0.04), 'chest': (0.14, 0.30, -0.12),
       'thigh_front': (0.13, 0.16, -0.12), 'buckle': (0.04, 0.19, -0.15), 'shoulder': (0.20, 0.42, -0.06)}
STRAP = {'belt': (0.15, 0.10, -0.13), 'hip': (0.22, 0.06, -0.04), 'thigh': (0.13, -0.14, -0.05), 'chest': (0.05, 0.36, -0.12), 'buckle': (0.0, 0.05, -0.14), 'shoulder': (0.16, 0.50, -0.02)}


def rig_x(c, name, rot, th=None):
    """World point of the chamber centre when the grip is at the rig's grip position with the gun at angles rot."""
    off = c.hips + np.array(c.P.get('rig_' + name, RIG[name])) - c.g0; return world_of(c, off, rot, chamber_pt(c.gun, th))
def strap_x(c, name): return c.hips + np.array(STRAP[name])


def hidden_press(c, tl, rig, rot, start, depth=0.07, n=4, arrive=None, prof=(3.2, 1.6)):
    """From frame `start`, down to the body rig (off screen), hover, and onto the two shells in it on the seat beat."""
    se = bud(c)['seat']; tl.hold(start); arrive = arrive if arrive is None else min(arrive, se - n - 1)
    if c.P.get('via_f'):        # round 3: first lower out of view still pointing out to the side, then turn to the holder (the long barrels would sweep through the view)
        tl.to(c.P['via_f'], np.array(c.P['via_pos']), np.array(c.P['via_rot']), (2.0, 2.0)); start = c.P['via_f']
    ct = insert_onto(c, tl, se, rig_x(c, rig, rot, c.P.get('seat_th')), rot, depth=depth, n=n, th=c.P.get('seat_th'), arrive=arrive, prof=prof); tl.mark('seat', se); tl.hold(se + 2)
    return se, ct


def ret_idle(c, tl, f, n=12):
    """Back to the idle, arriving on f + n (eased: the clip ends in the idle)."""
    tl.hold(f); e = min(f + prod.L(c.P, n), c.N - 4); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')


def b12(c, tl):
    """Tip-down, wrist flick. The thumb pushes the lever and the wrist tips the gun forward and down and stops it
    hard: the barrels go on turning and fall open, the ejectors throw both hulls up and back past the hand. Held low
    with the breech up, then down to the hip holder (off screen) and pushed onto two shells. Brought up low in front
    and flicked up to vertical: the gun stops, the barrels swing on up and the bolt catches. Back to the idle."""
    P = c.P; lv = thumb(c, tl); a = P.get('tip', -40); n = P.get('tip_n', 4)
    tl.to(lv + n, P.get('tip_pos', (0.0, -0.02, -0.01)), (a, 0, -4), 'slam'); tl.mark('break', lv + n); tl.hold(lv + n + 3)
    tl.to(lv + n + P.get('hold_n', 8), P.get('hold_pos', (0.0, -0.07, 0.02)), (P.get('hold_pitch', -4), 0, -6), 'ease')     # held low, barrels hanging on the stop, breech toward the eye
    se, ct = hidden_press(c, tl, 'hip', P.get('load_rot', (-8, -10, 8)), lv + n + 8, arrive=bud(c)['seat'] - 5)
    s = bud(c)['shut']; fn = P.get('flick_n', 9); tl.hold(s - fn)
    tl.to(s, P.get('flick_pos', (0.0, 0.03, 0.05)), (P.get('flick_to', 55), 0, -3), P.get('flick_prof', (2.6, 1.3))); tl.mark('close', s); ret_idle(c, tl, s + 3, 13)   # one upward swing out of the holder, accelerating all the way (the barrels pressed to the stop) and stopped dead at vertical: they swing on and latch
    return {'lever': lv, 'lever_until': lv + n + 1, 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'hip'))}


def bcontact(c, f0, f1, X, n, pt, name, rad=None):
    """A body surface the barrels may hit: world point X, normal n out of the body, barrel point pt (gun axes, barrels
    closed) that touches it."""
    return {'f': [int(f0), int(f1)], 'p': [float(x) for x in X], 'n': [float(x) for x in n], 'pt': [float(x) for x in pt], 'name': name, 'rad': rad}


def muzzle_under(c):
    """The barrels' underside a short way ahead of the hinge: a body surface there folds them shut over a short stroke
    (pressed at the muzzle the action would have to travel 25 cm into the body)."""
    return (0.0, -0.035, -0.225) if c.gun == 'palica' else (0.0, -0.035, -0.26)


def b11(c, tl):
    """Roll-up, rise and stop. The thumb pushes the lever and the wrist rolls in and tips the gun up hard: the gun
    turns up faster than the barrels can follow, they fall open and stay on the stop while the gun slows to
    vertical, muzzles up; the ejectors throw both hulls out of the breech, down and back past the hand. The gun drops
    out of view still muzzle-up (that keeps the barrels on their stop while it falls) and is pushed onto the belt
    holder. It comes back up in one rising swing that stops dead at vertical: the barrels swing on and latch.
    Lowered to the idle."""
    P = c.P; lv = thumb(c, tl); n = P.get('up_n', 5)
    tl.to(lv + n, P.get('up_pos', (-0.02, 0.05, 0.03)), (P.get('up_to', 72), 0, P.get('roll_in', 22)), P.get('up_prof', (1.5, 3.2))); tl.mark('break', lv + n)
    if P.get('follow'): tl.to(lv + n + 5, np.array(P.get('up_pos', (-0.02, 0.05, 0.03))) + np.array((0, 0.01, 0)), (P.get('up_to', 72) + P.get('follow'), 0, P.get('roll_in', 22)), 'ease')     # the wrist goes on with the gun's overshoot instead of pulling it back
    se, ct = hidden_press(c, tl, 'belt', P.get('load_rot', (35, -6, 10)), lv + n + 5, arrive=bud(c)['seat'] - 5, prof=P.get('dive_prof', (2.2, 1.8)))
    s = bud(c)['shut']; nn = P.get('rise_n', 9); tl.hold(s - nn); tl.to(s, P.get('rise_pos', (-0.01, 0.06, 0.05)), (P.get('rise_to', 75), 0, 10), (2.4, 1.3)); tl.mark('close', s)
    ret_idle(c, tl, s + 4, 12)
    return {'lever': lv, 'lever_until': lv + n, 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'belt'))}


def b13(c, tl):
    """Fling-down, flick. The gun is raised up and to the left, the thumb pushes the lever, and the arm flings it
    down to point at the floor and stops it: the barrels go on and swing open, the hulls are thrown up out of the
    breech. The muzzle comes up a little so the barrels hang on the stop with the breech up, and the gun is pushed up
    onto two shells hanging in a holder under the chest (off screen). Brought out low in front and flicked up to
    vertical: the barrels swing on and latch."""
    P = c.P; lv = bud(c)['lever']; tl.hold(1); tl.to(lv + 1, P.get('raise_pos', (-0.06, 0.08, 0.03)), (P.get('raise_pitch', 38), 18, 12), 'ease'); tl.mark('lever', lv)
    n = P.get('fling_n', 5); tl.to(lv + 1 + n, P.get('fling_pos', (0.02, -0.08, -0.04)), (P.get('fling_to', -55), 0, -4), 'slam'); tl.mark('break', lv + 1 + n)
    tl.to(lv + n + 5, np.array(P.get('fling_pos', (0.02, -0.08, -0.04))) + np.array((0, -0.01, 0)), (P.get('fling_to', -55) - P.get('follow', 14), 0, -4), 'ease')     # the arm follows the gun's overshoot down instead of pulling it back up (a rebound would throw the barrels shut)
    se, ct = hidden_press(c, tl, 'chest', P.get('load_rot', (-40, -6, 4)), lv + n + 6, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))     # one slow descent (under 0.5 g) under the chest holder
    s = bud(c)['shut']; fn = P.get('flick_n', 9); tl.hold(s - fn)
    tl.to(s, P.get('flick_pos', (0.0, 0.03, 0.05)), (P.get('flick_to', 55), 0, -3), (2.6, 1.3)); tl.mark('close', s); ret_idle(c, tl, s + 3, 13)
    return {'lever': lv, 'lever_until': lv + 1 + n, 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'chest'))}


def from_holder(c, tl, s, pos, rot, prof=(2.2, 1.5)):
    """The close move: one move out of the holder (starting on seat + 2), speeding up into the close event on s. The
    budget leaves no time for a separate soft rise, and any hard arrival before the close would already throw the
    open barrels shut (their stop on the gun's deceleration)."""
    tl.hold(bud(c)['seat'] + 2); tl.to(s, pos, rot, prof); tl.mark('close', s)


def b14(c, tl):
    """Hip drop, hip anvil. The thumb pushes the lever and the gun is dropped to the hip, where the fist lands on
    the hip bone and stops it dead: the barrels go on down and fall open, and the gun hangs from the grip with the
    barrels pointing at the ground. Rolled onto its right side (barrels hanging toward the leg) and pushed onto two
    shells in the hip holder (off screen). Then the hand swings it in against the side of the hip: the hip catches the
    barrels' underside just ahead of the hinge, folds them up and the bolt catches. Up to the idle."""
    P = c.P; lv = thumb(c, tl); hp = np.array(P.get('drop_pos', (0.03, -0.30, 0.10))); n = P.get('drop_n', 5)
    tl.to(lv + n, hp + np.array((0, -0.03, 0)), (P.get('drop_pitch', -15), -6, 6), (2.6, 1.4)); tl.mark('break', lv + n)
    stop = {'name': 'fist on hip', 'f': [lv + 1, lv + n + 3], 'anchor': hp, 'n': np.array((0, -1.0, 0)), 'e': 0.3, 'axis': (1, 0, 0), 'jolt': 0.6}
    tl.to(lv + n + 2, hp, (P.get('drop_pitch', -15), -6, 6), 'ease')
    roll = P.get('roll', -85); lr = P.get('load_rot', (-12, 0, roll)); se, ct = hidden_press(c, tl, 'hip', lr, lv + n + 4, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; g = tl.p.copy(); from_holder(c, tl, s, g + np.array(P.get('swing_in', (-0.15, 0.01, 0.0))), lr, P.get('in_prof', (1.8, 1.6)))     # swung in against the thigh, barrels' underside first
    th = bcontact(c, se + 2, s + 3, c.hips + np.array(P.get('hip_pt', (0.17, 0.10, -0.12))), (1.0, 0, 0), muzzle_under(c), 'outer hip', rad=0.15)     # the side of the pelvis (gate body block), unverified size
    ret_idle(c, tl, s + 3, P.get('ret_n', 14))
    return {'lever': lv, 'lever_until': lv + n, 'seat': se, 'gun_contacts': [stop, ct], 'hinge_contacts': [th], 'load': load_press(strap=strap_x(c, 'thigh'))}


def side_close(c, tl, s, P, d=(0.22, 0.10, -0.04)):
    """From the holder (loaded rolled onto the right side), one swing out to the right and up into view, stopped dead:
    the barrels swing on to the right, toward the top rib, and latch."""
    g = tl.p.copy(); r = tl.r.copy(); from_holder(c, tl, s, g + np.array(P.get('sw_by', d)), r + np.array((0, P.get('sw_yaw', -30), 0)), P.get('sw_prof', (2.4, 1.3)))


def b15(c, tl):
    """Elbow check, swing back. The gun is rolled onto its right side (top rib out) and swung in across the belly;
    the thumb pushes the lever as it goes and the elbow hits the ribs and stops the swing dead: the barrels swing on
    to the left and open, the ejectors throw the hulls back and out to the right. Down to the belt holder, still on
    its side (off screen). Out of the holder in one swing to the right and up, stopped dead: the barrels swing on to
    the right and the bolt catches."""
    P = c.P; lv = bud(c)['lever']; roll = P.get('roll', -85); p0 = np.array(P.get('p0', (0.08, -0.06, 0.02)))
    tl.hold(1); tl.to(lv, p0, (P.get('pitch', -8), -10, roll), 'ease'); tl.mark('lever', lv)
    n = P.get('swing_n', 4); d = np.array(P.get('dir', (-1.0, -0.15, -0.1))); d = d / np.linalg.norm(d); dist = P.get('dist', 0.14)
    tl.to(lv + n, p0 + d * (dist + 0.03), (P.get('pitch', -8), P.get('yaw_in', 25), roll), 'slam'); tl.mark('break', lv + n)
    stop = {'name': 'elbow on ribs', 'f': [lv + 1, lv + n + 3], 'anchor': p0 + d * dist, 'n': d, 'e': 0.3, 'axis': (0, 1, 0), 'jolt': 0.8}
    tl.to(lv + n + 3, p0 + d * dist, (P.get('pitch', -8), P.get('yaw_in', 25), roll), 'ease')
    se, ct = hidden_press(c, tl, 'belt', P.get('load_rot', (-10, 15, roll)), lv + n + 4, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; side_close(c, tl, s, P); ret_idle(c, tl, s + 3, 13)
    return {'lever': lv, 'lever_until': lv + n, 'seat': se, 'gun_contacts': [stop, ct], 'load': load_press(strap=strap_x(c, 'belt'))}


def thrust_close(c, tl, s, P):
    """From the holder, the gun is thrust forward and up toward the aim and stopped dead: the hanging barrels swing
    on forward, up into the breech, and latch."""
    from_holder(c, tl, s, np.array(P.get('thrust_pos', (0.0, -0.05, -0.04))), (P.get('thrust_pitch', -5), 0, -3), P.get('thrust_prof', (2.6, 1.3)))


def b16(c, tl):
    """Recoil kick, thrust. The thumb pushes the lever and the hand kicks the gun up and back the way the last shot
    threw it: the gun turns up faster than the barrels follow and they fall open; the hulls are thrown up and back
    over the shoulder. The muzzle comes down, the barrels hang, and the gun goes down to the belt holder (off
    screen). Out of the holder it is thrust forward to the aim and stopped dead: the hanging barrels swing on up into
    the breech and latch. Settles into the idle."""
    P = c.P; lv = thumb(c, tl); n = P.get('kick_n', 3)
    tl.to(lv + n, P.get('kick_pos', (0.0, 0.07, 0.06)), (P.get('kick_to', 50), 0, -4), P.get('kick_prof', (1.3, 3.4))); tl.mark('break', lv + n)
    if P.get('follow'): tl.to(lv + n + 5, np.array(P.get('kick_pos', (0.0, 0.07, 0.06))) + np.array((0, 0.01, 0.01)), (P.get('kick_to', 50) + P.get('follow'), 0, -4), 'ease')
    tl.to(lv + n + 9, P.get('hold_pos', (0.02, -0.04, 0.04)), (P.get('hold_pitch', 20), 0, -4), (2.0, 2.4))
    lr = P.get('load_rot', (-8, -6, 6)); se, ct = hidden_press(c, tl, 'belt', lr, lv + n + 10, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; thrust_close(c, tl, s, P); ret_idle(c, tl, s + 3, 13)
    return {'lever': lv, 'lever_until': lv + n, 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'belt'))}


def b17(c, tl):
    """Chest roll-up, thrust. The thumb pushes the lever and the gun is swung across the chest, pointing down and left,
    and stopped hard: the barrels go on, fall open and the ejectors throw the hulls up across the view. Then it is
    rolled up beside the face, muzzle up (the barrels stay on their stop).
    The muzzle comes down slowly (the barrels hang) and the gun goes to the hip holder (off screen). Out of the holder
    it is snapped forward to the aim and stopped dead: the hanging barrels swing on up into the breech and latch."""
    P = c.P; lv = bud(c)['lever'] + P.get('late', 3); cp = np.array(P.get('cross_pos', (-0.10, -0.12, 0.10)))     # the lever goes once the gun is across the chest (a hard arrival there would already open it)
    lv0 = None
    if P.get('cross_open'):    # the thumb pushes the lever as the gun is swung across the chest, muzzle down-left, and stopped hard: that
        lv0 = thumb(c, tl); tl.to(lv, cp, (P['cross_open'], P.get('cross_yaw', 55), -10), 'slam'); tl.mark('break', lv); tl.hold(lv + P.get('cross_hold', 3)); lv = lv + P.get('cross_hold', 3)   # stop breaks it and throws the hulls up across the view
    else: tl.hold(0); tl.to(lv, cp, (P.get('cross_pitch', 0), P.get('cross_yaw', 55), -10), (2.0, 2.6)); tl.mark('lever', lv)
    n = P.get('roll_n', 8)
    tl.to(lv + n, P.get('face_pos', (-0.02, 0.0, 0.10)), (P.get('face_pitch', 70), P.get('face_yaw', 25), -20), P.get('roll_prof', (1.15, 4.0))); tl.mark('break', lv + n)
    if P.get('follow'): tl.to(lv + n + 5, np.array(P.get('face_pos', (-0.02, 0.0, 0.10))) + np.array((0, 0.01, 0)), (P.get('face_pitch', 70) + P.get('follow'), P.get('face_yaw', 25), -20), 'ease')
    lr = P.get('load_rot', (-8, -8, 6)); se, ct = hidden_press(c, tl, 'hip', lr, lv + n + 1, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; thrust_close(c, tl, s, P); ret_idle(c, tl, s + 3, 13)
    return {'lever': lv0 if lv0 is not None else lv, 'lever_until': lv + n, 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'hip'))}


def b18(c, tl):
    """Shoulder snap, backhand. The thumb pushes the lever, the muzzle is dipped and stopped hard (the stop breaks the
    action and the ejectors throw the hulls up and forward through the view), and the gun is snapped back and up toward
    the right shoulder, muzzle up. Down to
    the belt holder, rolled onto its left side, top rib inward (off screen). Out of the holder in one backhand swing up
    and in to the left, stopped dead short of the other gun: the barrels swing on to the left, toward the top rib,
    and latch. Back to the idle."""
    P = c.P; n = P.get('snap_n', 8); lv0 = None
    if P.get('dip_open'):    # the thumb pushes the lever and the muzzle is dipped and stopped hard: that stop breaks the action and throws the
        lv = thumb(c, tl); lv0 = lv; nd = P.get('dip_n', 4)     # hulls up and forward through the view; then the snap back to the shoulder
        tl.to(lv + nd, P.get('dip_pos', (0.0, -0.04, -0.02)), (P['dip_open'], P.get('sh_yaw', -10), 0), 'slam'); tl.mark('break', lv + nd)
        tl.hold(lv + nd + P.get('dip_hold', 3)); lv = lv + nd + P.get('dip_hold', 3)
    elif P.get('dip'):         # a short dip, muzzle down, before the snap (the action still latched): the barrels then open while the
        dl = bud(c)['lever'] + P.get('late', 3); tl.hold(0); tl.to(dl, P.get('dip_pos', (0.0, -0.04, -0.02)), (P['dip'], 0, 0), (2.0, 2.6))   # muzzle is still low and the ejectors throw the hulls up, not back at the eye
        lv = dl; tl.mark('lever', lv)
    else: lv = thumb(c, tl)
    tl.to(lv + n, P.get('sh_pos', (0.04, 0.06, 0.12)), (P.get('sh_pitch', 62), P.get('sh_yaw', -10), P.get('sh_roll', 8)), P.get('sh_prof', (1.15, 4.0))); tl.mark('break', lv + n)
    if P.get('follow'): tl.to(lv + n + 5, np.array(P.get('sh_pos', (0.04, 0.06, 0.12))) + np.array((0, 0.01, 0)), (P.get('sh_pitch', 62) + P.get('follow'), P.get('sh_yaw', -10), P.get('sh_roll', 8)), 'ease')
    roll = P.get('roll', 85); lr = P.get('load_rot', (-10, -15, roll)); se, ct = hidden_press(c, tl, 'belt', lr, lv + n + 1, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; g = tl.p.copy(); r = tl.r.copy()
    from_holder(c, tl, s, g + np.array(P.get('bh_by', (-0.14, 0.14, -0.06))), r + np.array((0, P.get('bh_yaw', 30), 0)), P.get('bh_prof', (2.4, 1.3)))
    ret_idle(c, tl, s + 3, 13)
    return {'lever': lv0 if lv0 is not None else lv, 'lever_until': lv + n, 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'belt'))}


def b19(c, tl):
    """Lower and tip, swing out. The thumb pushes the lever and the hand lowers the gun and tips it muzzle-down in one
    move that stops short: the barrels go on and fall open and the gun hangs from the grip, breech up. Rolled onto its
    right side and pushed onto two shells in the belt holder (off screen). Out of the holder it swings up and out to the
    right into view and is stopped dead: the barrels swing on toward the top rib and latch. Back to the idle."""
    P = c.P; lv = thumb(c, tl); n = P.get('tip_n', 5)
    tl.to(lv + n, P.get('tip_pos', (0.0, -0.14, 0.03)), (P.get('tip', -40), 0, -4), (2.4, 1.3)); tl.mark('break', lv + n)
    tl.to(lv + n + 4, P.get('follow_pos', (0.0, -0.15, 0.03)), (P.get('tip', -40) - P.get('follow', 10), 0, -4), 'ease')
    roll = P.get('roll', -85); se, ct = hidden_press(c, tl, 'belt', P.get('load_rot', (-10, 15, roll)), lv + n + 5, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; side_close(c, tl, s, P, d=(0.20, 0.14, -0.06)); ret_idle(c, tl, s + 3, 13)
    return {'lever': lv, 'lever_until': lv + n, 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'belt'))}


def b20(c, tl):
    """Forward roll-tip, side swing. The thumb pushes the lever and the gun is tipped forward and rolled over to the
    left in one move that stops dead, breech up toward the eye: the barrels go on, swing open, and the hulls are
    thrown up and back. Rolled onto its right side and pushed onto two shells in the hip holder (off screen). Out of
    the holder in one swing to the right and up, stopped dead: the barrels swing on and latch."""
    P = c.P; lv = thumb(c, tl); n = P.get('tip_n', 4)
    tl.to(lv + n, P.get('tip_pos', (-0.02, -0.04, -0.02)), (P.get('tip', -40), 10, P.get('tip_roll', 45)), 'slam'); tl.mark('break', lv + n)
    tl.to(lv + n + 4, P.get('follow_pos', (-0.02, -0.05, -0.02)), (P.get('tip', -40) - P.get('follow', 10), 10, P.get('tip_roll', 45)), 'ease')
    roll = P.get('roll', -85); se, ct = hidden_press(c, tl, 'hip', P.get('load_rot', (-10, 15, roll)), lv + n + 5, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; side_close(c, tl, s, P); ret_idle(c, tl, s + 3, 13)
    return {'lever': lv, 'lever_until': lv + n, 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'hip'))}


PICKS = {'BR11': ('Roll-up, rise and stop', b11), 'BR12': ('Tip-down, wrist flick', b12), 'BR13': ('Fling-down, flick', b13), 'BR14': ('Hip drop, hip anvil', b14),
         'BR15': ('Elbow check, swing back', b15), 'BR16': ('Recoil kick, thrust', b16), 'BR17': ('Chest roll-up, thrust', b17), 'BR18': ('Shoulder snap, backhand', b18),
         'BR19': ('Lower and tip, swing out', b19), 'BR20': ('Forward roll-tip, side swing', b20)}
DOC = {k: ' '.join((fn.__doc__ or '').split()) for k, (n, fn) in PICKS.items()}
def YT(vid, t): return f'<a href="https://www.youtube.com/watch?v={vid}&t={t}s">{vid}</a>'
SOURCE = {      # draft -> reference video and time stamps (refs/refs.md) and what it shows
    'BR11': f"CoD Modern Warfare Remastered, akimbo Ranger (game from the uploader's list order, unverified), {YT('N41XMdrSnrI', 699)} 699.30 to 699.45 s (wrists roll in and tip the guns up, barrels drop open), 699.50 to 699.85 s (snapped vertical, shells slide out downward), 699.90 to 700.75 s (guns drop out of frame, load hidden), 700.77 to 701.08 s (gun returns from below and is closed at vertical), 701.3 to 701.6 s (lowered to idle). Stills: refs/mwr-akimbo-ranger.",
    'BR12': f"Red Dead Redemption 2, sawed-off in first person, {YT('H2A4dDzY4lY', 2)} 2.83 to 3.04 s (gun tips forward and down, barrels fall open, breech toward the camera), 3.25 to 4.32 s (held low, breech facing the camera), 4.53 to 4.95 s (right wrist flicks the gun up to vertical, barrels swing shut). Stills: refs/rdr2-fp-sawedoff.",
    'BR13': f"Into the Radius VR (game from list order, unverified), {YT('N41XMdrSnrI', 988)} 994.14 to 994.43 s (gun raised up and left), 994.72 s (flung down to point at the floor, opens on the downswing), 995.1 to 996.7 s (gun pointing down, breech up, loaded), 997.59 to 998.16 s (flicked up to vertical to close). Stills: refs/into-the-radius-vr.",
    'BR14': f"Real one-handed sawed-off 12 gauge, {YT('pvhMq3g8_mQ', 17)} 18.28 to 18.72 s (gun brought to the hip, barrels fall open), 18.7 to 21.6 s (gun hangs from the grip, barrels straight down), 26.0 to 26.4 s and 32.77 s (closed by lifting the barrels from below: here the thigh does the lifting). Stills: refs/real-sawedoff-onehand.",
    'BR15': f"Blood (One Unit Whole Blood), {YT('DhDWNVjvIM8', 27)} 28.14 to 28.35 s (gun swung left and tipped, breech to the camera), 28.46 s (hulls flicked up and away to the right), 28.57 to 28.78 s (snapped shut and upright). Stills: refs/blood-sawedoff.",
    'BR16': f"Red Dead Redemption 2, {YT('H2A4dDzY4lY', 2)} 2.40 to 2.61 s (the gun carried up by the recoil) and 5.17 s on (gun thrown back out to the aim for the next shot), with the real sawed-off {YT('pvhMq3g8_mQ', 32)} 32.97 to 34.0 s (one-handed recoil flips the muzzle up 60 to 80 deg, estimated) for the size of the kick. Stills: refs/rdr2-fp-sawedoff, refs/real-sawedoff-onehand.",
    'BR17': f"Mad Max (2015), Max's shotgun, {YT('3WKCr7kPjVU', 230)} 230.30 to 231.23 s (gun brought across the chest, held horizontal at chest height), 231.31 to 231.69 s (rolled muzzle-up beside the face, two shells fly out), 231.77 to 232.70 s (the gun snapped away in one move; here forward to the aim). Stills: refs/madmax-game.",
    'BR18': f"BrainBread 2, empty reload (game from list order, unverified), {YT('N41XMdrSnrI', 689)} 693.17 to 694.31 s (gun snapped muzzle-up close to the camera, both hulls thrown up out of the frame by the ejectors), 694.88 to 695.07 s (swung up close to the camera to close); the sideways stop as in Blood {YT('DhDWNVjvIM8', 28)} 28.57 to 28.78 s, mirrored. Stills: refs/brainbread2, refs/blood-sawedoff.",
    'BR19': f"Call of Juarez: Gunslinger, Sawed-Off, {YT('9Gw2QZtm3n4', 31)} 31.28 to 31.78 s (the right hand lowers the gun and tips it muzzle-down, barrels fall open, breech to the camera), akimbo 33.98 to 34.15 s (same in the akimbo set); the gun hanging from the grip after the drop as in the real sawed-off {YT('pvhMq3g8_mQ', 18)} 18.7 to 21.6 s; the close is a sideways swing as in Blood {YT('DhDWNVjvIM8', 28)} 28.57 to 28.78 s. Stills: refs/coj-gunslinger, refs/real-sawedoff-onehand, refs/blood-sawedoff.",
    'BR20': f"Fistful of Frags, variant B (game from list order, unverified), {YT('N41XMdrSnrI', 89)} 90.0 to 90.2 s (gun tipped forward and rolled so the breech is up and faces the camera, held low), 92.8 to 93.0 s (swung up to a diagonal to close); the sideways close as in Blood {YT('DhDWNVjvIM8', 28)} 28.57 to 28.78 s. Stills: refs/fistful-of-frags, refs/blood-sawedoff.",
}
OPEN = {'BR11': 'wrist roll-up, muzzle up', 'BR12': 'wrist tip forward and down, stopped', 'BR13': 'arm fling from up-left down to the floor, stopped', 'BR14': 'dropped to the hip, fist stopped on the hip',
        'BR15': 'rolled cross-body swing, elbow stopped on the ribs', 'BR16': 'recoil kick up and back', 'BR17': 'swung across the chest muzzle-down and stopped, then rolled up beside the face', 'BR18': 'muzzle dipped and stopped, then snapped back and up to the shoulder',
        'BR19': 'lowered and tipped down in one move', 'BR20': 'tipped forward and rolled over, stopped'}
CLOSE = {'BR11': 'rising arm swing stopped at vertical (flick 1 of 3)', 'BR12': 'upward wrist flick to vertical (flick 2 of 3)', 'BR13': 'upward flick to vertical (flick 3 of 3)',
         'BR14': 'barrels folded shut against the side of the hip (body contact)', 'BR15': 'rolled side swing to the right, stopped', 'BR16': 'thrust forward to the aim, stopped', 'BR17': 'snapped forward to the aim, stopped',
         'BR18': 'backhand swing up and in to the left, stopped', 'BR19': 'rolled swing up and out to the right, stopped', 'BR20': 'rolled side swing to the right, stopped'}
LOADM = {'BR11': 'hidden: pushed onto a belt holder', 'BR12': 'hidden: pushed onto a hip holder', 'BR13': 'hidden: pushed up onto a chest holder', 'BR14': 'hidden: pushed onto a hip holder, rolled on its side',
         'BR15': 'hidden: pushed onto a belt holder, rolled on its side', 'BR16': 'hidden: pushed onto a belt holder', 'BR17': 'hidden: pushed onto a hip holder', 'BR18': 'hidden: pushed onto a belt holder, rolled on its side',
         'BR19': 'hidden: pushed onto a belt holder, rolled on its side', 'BR20': 'hidden: pushed onto a hip holder'}
PARAMS = {
          'BR20B': {'follow': 16, 'tip_pos': (0.02, -0.1, -0.04), 'follow_pos': (0.02, -0.11, -0.04)},
          'BR18A': {'bh_by': (-0.12, 0.24, -0.08), 'dip_open': -35, 'sh_prof': (1.6, 2.6), 'snap_n': 10},
          'BR19A': {'tip_pos': (0.0, -0.22, 0.0), 'follow_pos': (0.0, -0.23, 0.0), 'sw_by': (0.16, 0.28, -0.26)},
          'BR20A': {'tip_pos': (-0.02, -0.14, -0.04), 'follow_pos': (-0.02, -0.15, -0.04), 'sw_by': (0.16, 0.28, -0.26)},
          'BR12A': {'tip_pos': (0.0, -0.08, -0.04), 'tip': -40},
          'BR15A': {'swing_n': 6, 'dist': 0.12, 'yaw_in': 15, 'sw_by': (0.16, 0.28, -0.26)},
          'BR14B': {'swing_in': (-0.12, 0.01, 0.0), 'rig_hip': (0.33, 0.17, 0.02), 'ret_n': 16},
          'BR17B': {'late': 4, 'face_pitch': 40, 'face_pos': (0.14, 0.0, 0.06), 'face_yaw': 10, 'cross_pos': (0.1, -0.2, 0.02), 'cross_yaw': 30, 'roll_n': 11, 'thrust_pos': (0.0, 0.02, 0.0), 'thrust_pitch': 10, 'thrust_prof': (3.0, 1.15), 'cross_open': -25, 'roll_prof': (1.8, 2.4)},
          'BR16B': {'kick_prof': (1.15, 4.0), 'kick_n': 8, 'kick_to': 45, 'thrust_pos': (0.0, -0.02, -0.03), 'thrust_pitch': 5, 'thrust_prof': (3.0, 1.15)},
          'BR18B': {'bh_by': (-0.1, 0.14, -0.1), 'dip_open': -22, 'dip_pos': (0.02, -0.17, -0.03), 'sh_pitch': 45, 'sh_pos': (0.04, 0.02, 0.08)},
          'BR19B': {'tip_pos': (0.02, -0.16, -0.02), 'follow_pos': (0.02, -0.17, -0.02), 'rig_belt': (0.26, 0.19, 0.0)},
          'BR13B': {'fling_to': -40, 'follow': 8, 'raise_pitch': 30, 'flick_to': 45, 'rig_chest': (0.16, 0.26, -0.14)},
          'BR11B': {'up_to': 45, 'up_pos': (0.02, 0.02, 0.0), 'up_n': 10, 'rise_to': 45, 'rise_pos': (0.02, 0.06, 0.04), 'load_rot': (-5, -10, 10), 'rig_belt': (0.26, 0.17, 0.02)},
          'BR15B': {'dist': 0.1, 'p0': (0.1, -0.1, 0.0), 'yaw_in': 15, 'rig_belt': (0.26, 0.19, 0.0)},
          'BR17A': {'late': 3, 'face_pitch': 55, 'face_pos': (0.04, 0.04, 0.12), 'cross_pos': (0.0, -0.16, 0.08), 'cross_open': -30, 'roll_prof': (1.8, 2.4), 'roll_n': 10},
          'BR13A': {'follow': 20, 'fling_pos': (0.02, -0.14, -0.02)},
          'BR11A': {'up_prof': (1.15, 4.0), 'up_n': 8, 'up_to': 62, 'up_pos': (-0.02, 0.08, 0.05), 'rise_to': 60, 'rise_pos': (-0.01, 0.12, 0.08), 'rise_n': 8},
          'BR12B': {'tip': -36, 'tip_pos': (0.02, -0.09, -0.04), 'hold_pos': (0.03, -0.11, -0.03), 'flick_to': 48, 'hold_pitch': -25, 'hold_n': 10, 'load_rot': (-20, -14, 10), 'rig_hip': (0.29, 0.17, -0.02)}}


# ------------------------------------------------------------------------------------------------ round 3: short openings
# The game's script plays a pick only if its visible opening (clip start until the gun is out of view, the shared
# hide_start) fits 0.75 x the reload time at no more than 1.15x speed: frames <= 1.15 * 0.75 * T * 30. Palica 0.65 s:
# 16 f; Igla 0.9 s: 23 f; Testera 0.85 s: 22 f; Satara 0.9 s: 23 f (WIRING-NOTES.md, GorillaAkimbo.reds OwnSpeed).
# Same moves as the round 2 picks, faster, with an exit out of view to the right side right after the break: a sideways
# move pushes along the hinge axis, so it neither opens nor shuts the barrels.
FIT_T = {'palica': (0.65, 0.75), 'igla': (0.9,), 'testera': (0.85,), 'satara': (0.9,)}
SHARES = {'A': ('palica', 'igla'), 'B': ('satara', 'testera')}


def fit_frames(T): return int(math.floor(1.15 * 0.75 * T * 30 + 1e-9))
def speedup(frames, T, body=1.0): return frames / 30.0 / (0.75 * T / body)


def lever_at(c, tl, f):
    """The thumb pushes the top lever on frame f (no separate twitch: the move under way carries it)."""
    tl.mark('lever', f); return f


def exit_side(c, tl, P, f_from):
    """Out of view to the right, arriving on out_f (the opening ends there); then the hidden part goes on from it."""
    tl.hold(f_from); tl.to(P['out_f'], np.array(P['out_pos']), np.array(P['out_rot']), P.get('out_prof', 'drive')); tl.mark('out', P['out_f'])


def b17r3(c, tl):
    """Chest roll-up, thrust (round 3 timing). The gun is swung across the chest, muzzle down and left, the thumb pushes
    the lever on the way and the swing is stopped hard: the barrels go on, fall open and the ejectors throw the hulls up
    across the view. Rolled up beside the face, muzzle up, then carried out to the right, out of view (sideways: the
    barrels stay on their stop). The hidden part goes to the hip holder; out of it the gun is snapped forward to the aim
    and stopped dead: the hanging barrels swing on up into the breech and latch."""
    P = c.P; lv = lever_at(c, tl, P.get('lever_f', 2)); cf = P.get('cross_f', 5); cp = np.array(P['cross_pos'])
    tl.hold(P.get('cross_start', 0)); tl.to(cf, cp, (P['cross_open'], P.get('cross_yaw', 45), -10), 'slam'); tl.mark('break', cf); tl.hold(cf + P.get('cross_hold', 1))
    rf = cf + P.get('cross_hold', 1) + P.get('roll_n', 4)
    tl.to(rf, np.array(P['face_pos']), (P['face_pitch'], P.get('face_yaw', 15), -20), P.get('roll_prof', (1.8, 2.4)))
    exit_side(c, tl, P, rf)
    lr = P.get('load_rot', (-8, -8, 6)); se, ct = hidden_press(c, tl, 'hip', lr, P['out_f'] + 1, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; thrust_close(c, tl, s, P); ret_idle(c, tl, s + 3, 13)
    return {'lever': lv, 'lever_until': P.get('lever_until', P['out_f']), 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'hip'))}


def b18r3(c, tl):
    """Shoulder snap, backhand (round 3 timing). The thumb pushes the lever, the muzzle is dipped and stopped hard (the
    stop breaks the action and the ejectors throw the hulls up and forward through the view), the gun is snapped back
    and up toward the right shoulder, muzzle up, and carried on out to the right, out of view. The hidden part goes to
    the belt holder, rolled onto its left side; out of it one backhand swing up and in to the left, stopped dead short
    of the other gun: the barrels swing on toward the top rib and latch."""
    P = c.P; lv = lever_at(c, tl, P.get('lever_f', 2)); df = P.get('dip_f', 5)
    tl.hold(P.get('dip_start', 1)); tl.to(df, np.array(P['dip_pos']), (P['dip_open'], P.get('sh_yaw', -10), 0), 'slam'); tl.mark('break', df); tl.hold(df + P.get('dip_hold', 1))
    sf = df + P.get('dip_hold', 1) + P.get('snap_n', 5)
    tl.to(sf, np.array(P['sh_pos']), (P['sh_pitch'], P.get('sh_yaw', -10), P.get('sh_roll', 8)), P.get('sh_prof', (1.6, 2.6)))
    exit_side(c, tl, P, sf)
    roll = P.get('roll', 85); lr = P.get('load_rot', (-10, -15, roll)); se, ct = hidden_press(c, tl, 'belt', lr, P['out_f'] + 1, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; g = tl.p.copy(); r = tl.r.copy()
    from_holder(c, tl, s, g + np.array(P.get('bh_by', (-0.14, 0.14, -0.06))), np.array((r[0], r[1] + P.get('bh_yaw', 30), P.get('close_roll', r[2]))), P.get('bh_prof', (2.4, 1.3)))   # close_roll: loaded upright, rolled onto its side during the swing
    ret_idle(c, tl, s + 3, 13)
    return {'lever': lv, 'lever_until': P.get('lever_until', P['out_f']), 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'belt'))}


def b20r3(c, tl):
    """Forward roll-tip, side swing (round 3 timing). The thumb pushes the lever and the gun is tipped forward and rolled
    over to the left in one move that stops dead, breech up toward the eye: the barrels go on, swing open, and the hulls
    are thrown up. The arm follows the overshoot down, then carries the gun out to the right, out of view. Rolled onto
    its right side and pushed onto two shells in the hip holder (hidden). Out of the holder in one swing to the right
    and up, stopped dead: the barrels swing on and latch."""
    P = c.P; lv = lever_at(c, tl, P.get('lever_f', 2)); tf = P.get('tip_f', 5)
    tl.hold(P.get('tip_start', 1)); tl.to(tf, np.array(P['tip_pos']), (P['tip'], P.get('tip_yaw', 10), P.get('tip_roll', 45)), 'slam'); tl.mark('break', tf)
    ff = tf + P.get('follow_n', 3)
    tl.to(ff, np.array(P['tip_pos']) + np.array((0, -0.01, 0)), (P['tip'] - P.get('follow', 10), P.get('tip_yaw', 10), P.get('tip_roll', 45)), 'ease')
    exit_side(c, tl, P, ff)
    roll = P.get('roll', -85); se, ct = hidden_press(c, tl, 'hip', P.get('load_rot', (-10, 15, roll)), P['out_f'] + 1, arrive=bud(c)['seat'] - 5, prof=(2.0, 2.0))
    s = bud(c)['shut']; side_close(c, tl, s, P); ret_idle(c, tl, s + 3, 13)
    return {'lever': lv, 'lever_until': P.get('lever_until', P['out_f']), 'seat': se, 'gun_contacts': [ct], 'load': load_press(strap=strap_x(c, 'hip'))}


R3 = {   # starting values per take (searched below); round 2's close parameters kept where the close is unchanged
    'BR17A': {'cross_pos': (0.0, -0.16, 0.08), 'cross_open': -30, 'face_pos': (0.04, 0.04, 0.12), 'face_pitch': 55, 'out_f': 14,
              'out_pos': (0.30, -0.06, 0.16), 'out_rot': (40, -30, -20)},
    'BR17B': {'cross_pos': (0.1, -0.2, 0.02), 'cross_open': -25, 'cross_yaw': 30, 'face_pos': (0.14, 0.0, 0.06), 'face_pitch': 35, 'face_yaw': 10, 'out_f': 19,
              'out_pos': (0.32, -0.08, 0.14), 'out_rot': (30, -30, -20), 'lever_f': 3, 'cross_f': 7, 'roll_n': 5,
              'thrust_pos': (0.0, 0.02, 0.0), 'thrust_pitch': 10, 'thrust_prof': (3.0, 1.15)},
    'BR18A': {'bh_by': (-0.12, 0.24, -0.08), 'dip_open': -35, 'dip_pos': (0.0, -0.04, -0.02), 'sh_pos': (0.04, 0.06, 0.12), 'sh_pitch': 62, 'out_f': 14,
              'out_pos': (0.30, -0.04, 0.16), 'out_rot': (50, -30, 8)},
    'BR18B': {'bh_by': (-0.1, 0.14, -0.1), 'dip_open': -22, 'dip_pos': (0.02, -0.17, -0.03), 'sh_pitch': 45, 'sh_pos': (0.04, 0.02, 0.08), 'out_f': 19,
              'out_pos': (0.32, -0.06, 0.14), 'out_rot': (40, -30, 8), 'lever_f': 3, 'dip_f': 7, 'snap_n': 6},
    'BR20A': {'tip_pos': (-0.02, -0.04, -0.02), 'tip': -40, 'tip_yaw': -5, 'sw_by': (0.16, 0.28, -0.26), 'out_f': 14,
              'out_pos': (0.30, -0.10, 0.12), 'out_rot': (-45, -20, 20)},
    'BR20B': {'tip_pos': (0.02, -0.1, -0.04), 'tip': -40, 'follow': 16, 'out_f': 19, 'out_pos': (0.32, -0.12, 0.12), 'out_rot': (-45, -20, 20),
              'lever_f': 3, 'tip_f': 7},
}
PICKS = {'BR17': ('Chest roll-up, thrust', b17r3), 'BR18': ('Shoulder snap, backhand', b18r3), 'BR20': ('Forward roll-tip, side swing', b20r3)}
DOC = {k: ' '.join((fn.__doc__ or '').split()) for k, (n, fn) in PICKS.items()}
OPEN['BR17'] = 'swung across the chest muzzle-down and stopped, rolled up beside the face, out to the right'
OPEN['BR18'] = 'muzzle dipped and stopped, snapped up to the shoulder, out to the right'
OPEN['BR20'] = 'tipped forward and rolled over, stopped, out to the right'
for k in ('BR17A', 'BR17B', 'BR18A', 'BR18B', 'BR20A', 'BR20B'): PARAMS[k] = dict(R3[k])
FOUND = {   # searched (work/sweep.py, OPENMAX 15 for A, 21 for B): the exit out of view, and for BR18B a gentler snap, the lever held to the holder and a via point
    'BR17A': {'out_pos': (0.40, -0.16, 0.22), 'out_rot': (10, -90, 0)},
    'BR18A': {'out_pos': (0.37, -0.14, 0.20), 'out_rot': (10, -90, 0)},
    'BR20A': {'out_pos': (0.42, -0.14, 0.20), 'out_rot': (0, -80, 0)},
    'BR17B': {'out_pos': (0.30, -0.26, 0.26), 'out_rot': (0, -90, 0)},
    'BR20B': {'out_pos': (0.12, -0.30, 0.25), 'out_rot': (-56, -5, 45)},
    'BR18B': {'dip_pos': (0.03, -0.18, 0.01), 'sh_pitch': 25, 'sh_pos': (0.04, 0.02, 0.04), 'out_f': 21, 'out_pos': (0.34, -0.16, 0.22), 'out_rot': (25, -60, 0),
              'snap_n': 4, 'dip_hold': 3, 'out_prof': 'ease', 'load_rot': (-12, -15, 0), 'close_roll': 85, 'lever_until': 36, 'bh_prof': (2.8, 1.2),
              'via_f': 30, 'via_pos': (0.16, -0.36, 0.28), 'via_rot': (0, -45, 0)},
}
for k, v in FOUND.items(): PARAMS[k].update(v)


# ------------------------------------------------------------------------------------------------ build
def gun_world(path, N):
    g = Glb(path); cl = Clip(g, 'reload_draft'); i = g.names.index('WeaponRight')
    return [magtrack2.m4(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(N))]


def impulses_from(tl):
    return [(k['f'], np.array(k['move'], float), np.radians(np.array(k['rot'], float))) for k in tl.kicks]


DRIVEN = False      # breakprod sets it: the hinge is driven (breakphys.drive_hinge), so only the first open stop and the latching close act on the gun


def reactions(c, ph):
    """Angular impulses on the gun from the barrels: at the open stop (the barrels' angular momentum, 1 + e of it
    reversed) and when the bolt catches (all of it); as a kick of about L / I_gun / w_r rad, capped."""
    gid = c.gun; b = bp.barrel(gid); I = b['I']; wr = inertia.MODEL[take_of(gid)]['wr']; out = []; ev = ph['events']; h = np.array(GEO[gid]['hinge_axis'], float)
    def kick(t, w_deg_f, sign, scale):
        dw = I * math.radians(w_deg_f) * FPS * scale / I_GUN[gid] / FPS          # rad per frame of the gun
        a = min(dw / wr, math.radians(JOLT_CAP_DEG)); out.append((int(math.floor(t)) + 1, np.zeros(3), h * a * sign))
    for s in ev.get('stops', [])[:(1 if DRIVEN else 2)]: kick(s['t'], s['w_deg_f'], 1.0, 1 + bp.PAR[gid]['e_stop'])      # driven hinge (rule H2): the first stop only, a bounce off it no longer happens
    for cl in ev.get('closes', []):
        if DRIVEN and cl['result'] != 'latched': continue          # a bounce off the bolt no longer happens
        if cl['result'] == 'latched': kick(cl['t'], cl['w_deg_f'], -1.0, 1.0)
        else: kick(cl['t'], cl['w_deg_f'], -1.0, 1 + bp.PAR[gid]['e_cam'])
    return out


def compose(pick, take, side='right', body='pma', extra=None):
    gid = GUNS[take]; setup(gid); P = dict(TAKES_P[take]); P.update(PARAMS.get(pick + take, {})); P.update(extra or {})
    c = prod.Ctx(gid, body, CLIP, P, 'Right'); tl = TL(c, 0, 0.0); plan = PICKS[pick][1](c, tl)
    Pt, Rt = tl.P.copy(), tl.R.copy(); Pt[-1] = 0; Rt[-1] = 0
    return c, tl, plan, Pt, Rt


def author_clip(c, tl, plan, sim, name, d, pick, take):
    N = c.N; X, E = sim['X'], sim['E']; keys = [K(f, X[f], E[f]) for f in range(N)]; keys[0] = K(0); keys[-1] = K(N - 1)
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {take}', '_doc': DOC[pick], '_gun': gid_of(take), '_left_gun': gid_of(take), '_body': c.body, '_side': 'Right',
            '_gun_clip': CLIP, '_pick': pick, '_take': take, '_timing': c.T, '_params': {k: v for k, v in c.P.items() if not str(k).startswith('_')}, '_marks': tl.marks, '_two_arm': False,
            '_round': 'break-2', 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': N, 'keys': {'Right': keys, 'Left': [K(0)]}, 'shakes': {'Right': [], 'Left': []},
            'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb',
            '_target': {'P': [[round(float(x), 5) for x in p] for p in tl.P], 'R': [[round(float(x), 3) for x in r] for r in tl.R]}}
    author.build(spec, spec['out']); return spec, gun_world(spec['out'], N)


def gid_of(take): return GUNS[take]


def hinge_frames(gid, th):
    """Frame of the gun's own anim whose barrel angle matches th (the barrels are posed from it)."""
    hc = np.array(GEO[gid]['hinge_curve']); mx = hc[:, 1].max(); a = int(np.argmax(hc[:, 1] > 0.3)); b = int(np.argmax(hc[:, 1] >= mx - 0.3))
    seg = hc[a - 1:b + 1]; d = np.degrees(th)
    return [0.0 if x < 0.2 else round(float(np.interp(x, seg[:, 1], seg[:, 0])), 3) for x in d]


def run_phys(c, plan, GW):
    return bp.simulate(c.gun, GW, plan['lever'], contacts=plan.get('hinge_contacts', []), lever_until=plan.get('lever_until'))


def build(pick, take, side='right', body='pma', quiet=False):
    gid = GUNS[take]; d = f'{OUT}/clips/{body}'; os.makedirs(d, exist_ok=True); name = prod.stem(gid, pick, take, CLIP, side)
    c, tl, plan, Pt, Rt = compose(pick, take, side, body)
    if 'close' in tl.marks:          # the close move: back from the close beat while the hand target moves; a latch before it is not the close's
        f = tl.marks['close']
        while f > 1 and (np.abs(tl.P[f] - tl.P[f - 1]).max() > 2e-4 or np.abs(tl.R[f] - tl.R[f - 1]).max() > 0.05): f -= 1
        plan.setdefault('close_from', f)
    base_imp = impulses_from(tl); react = []; hist = []
    for it in range(3):
        sim = inertia.simulate_gun(c, take, Pt, Rt, base_imp + react, plan.get('gun_contacts', []), tl.guides)
        spec, GW = author_clip(c, tl, plan, sim, name, d, pick, take)
        ph = run_phys(c, plan, GW); hist.append({k: ph['events'].get(k) for k in ('trip', 'open', 'shut')})
        new = reactions(c, ph)
        if it > 0 and [x[0] for x in new] == [x[0] for x in react]: react = new; break
        react = new
    spec['_reactions'] = [(int(f), [round(float(x), 4) for x in dw]) for f, _, dw in react]; spec['_passes'] = hist
    th = ph['theta']; spec['_hinge_deg'] = [round(float(math.degrees(x)), 2) for x in th]; spec['_part_frames'] = hinge_frames(gid, th)
    # shells and rig
    sc = shell_centre(gid); cl = {j: closed(gid, j) for j in joints(gid)}
    spent, sst = bp.spent_shells(gid, GW, th, ph['events'], joints(gid), cl, sc)
    fresh, fst, prims = plan['load'](c, GW, th, ph, plan) if plan.get('load') else ({}, {}, [])
    inv = [np.linalg.inv(M) for M in GW]; J = {'names': [], 'joints': {}}
    for nm, per in (('spent', spent), ('fresh', fresh)):
        if not per: continue
        J['names'].append(nm); J['joints'][nm] = {j: [None if M is None else [round(float(x), 6) for x in (inv[f] @ M).ravel()] for f, M in enumerate(W)] for j, W in per.items()}
    spec['_objects'] = f'{d}/{name}_objects.json'; json.dump(J, open(spec['_objects'], 'w'))
    spec['_prims'] = f'{d}/{name}_prims.json'; json.dump(prims, open(spec['_prims'], 'w'))
    C0 = closed(gid, joints(gid)[0])
    dummy = {'frames': [{'m': [round(float(x), 6) for x in C0.ravel()], 's': 0.0, 'state': 'seated'}] * c.N, 'release': 1, 'free_from': 2, 'gone': c.N, 'exit_gun_axes': [0, 1, 0], 'enter_gun_axes': [0, -1, 0], 'plan': {'mode': 'none'}}
    spec['_track'] = f'{d}/{name}_track.json'; json.dump(dummy, open(spec['_track'], 'w'))
    if plan.get('seat') is not None: spec['_timing'] = dict(c.T, seated=int(plan['seat']))
    spec['_plan'] = {k: v for k, v in plan.items() if k not in ('load', 'hinge_contacts', 'gun_contacts')}
    json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, dummy)
    gs = inertia.gun_stats(sim, tl.marks)
    o['phys'] = phys_stats(c, plan, GW, ph, sst, fst, spec)
    o['inertia'] = {'gun': gs, 'model': sim['model']}
    break_gate(c, o, plan, ph, sst, fst, spent, fresh, GW)
    json.dump({'events': ph['events'], 'hinge_deg': spec['_hinge_deg'], 'w_deg_f': [round(math.degrees(x) / FPS, 2) for x in ph['w']], 'log': ph['log'], 'spent': sst, 'fresh': fst,
               'model': bp.summary(gid), 'stats': o['phys']}, open(f'{d}/{name}_phys.json', 'w'), indent=1)
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet:
        p = o['phys']; print(name, '| fails', o['fails'], '| open', p['open_swing_deg_f'], '->', p['barrel_at_trip_deg_f'], 'trip', p['trip_f'], '| close', p['close_swing_deg_f'], '->', p['latch_w_deg_f'], p['latch'],
                              '| passes', hist, '| eye', o['eye_cm'], 'cover', o['cover_peak'], 'wrist', o['wrist'], o['wrist_view'], 'reach', o['reach'], 'gap', o['guns_gap_cm'], 'hide', o['layout']['hide_start'], o['layout']['hide_end'],
                              '| over', gs['overshoot_cm_max'], gs['overshoot_deg_max'], 'lag', gs['rot_lag_f'], 'trail', gs['muzzle_trail_deg'], flush=True)
    return spec, o


def gun_ang_speed(GW, f0, f1):
    """Largest angular speed of the gun (deg/f) over frames f0..f1 and its frame."""
    best, at = 0.0, None
    for f in range(max(f0, 1), min(f1, len(GW) - 1) + 1):
        Rr = GW[f][:3, :3] @ GW[f - 1][:3, :3].T; a = math.degrees(math.acos(max(-1, min(1, (np.trace(Rr) - 1) / 2))))
        if a > best: best, at = a, f
    return round(best, 1), at


def phys_stats(c, plan, GW, ph, sst, fst, spec):
    ev = ph['events']; w = [math.degrees(x) / FPS for x in ph['w']]; lv = plan['lever']
    trip = ev.get('trip'); ft = int(math.floor(trip)) if trip is not None else None
    sw_open = gun_ang_speed(GW, lv, (ft or lv + 10) + 1)
    lat = [x for x in ev.get('closes', []) if x['result'] == 'latched']; bnc = [x for x in ev.get('closes', []) if x['result'] == 'bounced']
    sh = ev.get('shut'); fs = int(math.floor(sh)) if sh is not None else bud(c)['shut']
    sw_close = gun_ang_speed(GW, fs - 6, fs + 1)
    grip_v = max(float(np.linalg.norm(GW[f][:3, 3] - GW[f - 1][:3, 3])) * 100 for f in range(1, len(GW)))
    return {'lever_f': lv, 'cocked_f': ev.get('cocked'), 'trip_f': trip, 'open_f': ev.get('open'), 'shut_f': sh,
            'open_swing_deg_f': sw_open[0], 'open_swing_at': sw_open[1], 'barrel_at_trip_deg_f': ev.get('trip_w_deg_f'),
            'stop_hits': ev.get('stops', []), 'close_swing_deg_f': sw_close[0], 'close_swing_at': sw_close[1],
            'latch_w_deg_f': lat[0]['w_deg_f'] if lat else None, 'latch_need_deg_f': ph['w_latch_deg_f'], 'bounces': [(b['t'], b['w_deg_f']) for b in bnc],
            'latch': 'latched' if lat else ('bounced, not latched' if bnc else 'never shut'), 'contacts': ev.get('contacts', [])[:3] + ([f"... {len(ev.get('contacts', []))} contact substeps"] if len(ev.get('contacts', [])) > 3 else []),
            'max_open_deg': round(max(spec['_hinge_deg']), 1), 'spent': [{k: v for k, v in s.items() if k != 'path'} for s in sst], 'fresh': fst, 'peak_grip_cm_f': round(grip_v, 1)}


def break_gate(c, o, plan, ph, sst, fst, spent, fresh, GW):
    """Physics gate on top of rgate: the swing breaks the action (cocks it and reaches the trip angle with the lever
    thumbed), the shells eject and land, the barrels stay open while loading, the close latches (w over w_latch,
    after the shells are in), not late; no spent shell on screen in the hidden window or near the eye."""
    ev = ph['events']; th = ph['theta']; p = o['phys']; N = len(th)
    if ev.get('cocked') is None: o['fails'].append('swing too weak to break the action (hammers not cocked)')
    elif ev.get('trip') is None: o['fails'].append(f"barrels never reach the trip angle (max {p['max_open_deg']} deg)")
    if ev.get('unlatch') is not None and ev['unlatch'] < plan['lever'] - 0.01: o['fails'].append('barrels move before the lever')
    for s in sst:
        if s['land'] is None: o['fails'].append('a spent shell does not land')
    seat = plan.get('seat'); sh = ev.get('shut')
    if sh is None: o['fails'].append('action never latches shut' + (f" ({len(p['bounces'])} bounce(s) off the bolt)" if p['bounces'] else ''))
    else:
        if seat is not None and sh < seat: o['fails'].append(f'barrels shut (f{sh}) before the shells are in (f{seat})')
        if sh > N - 8: o['fails'].append(f'barrels shut late (f{sh})')
        cm = plan.get('close_from')
        if cm is not None and sh < cm: o['fails'].append(f'barrels shut at f{sh}, before the close move (f{cm})')
    if seat is not None and seat < N:
        lo = math.degrees(th[seat]); need = 25.0          # the chambers clear the standing breech
        if lo < need: o['fails'].append(f'barrels {lo:.0f} deg open at the seat (need {need:.0f})')
    hs_ = bp.hinge_stats([math.degrees(x) for x in th]); o['hinge'] = hs_       # rule S1 (rules.json H2): one open, one close, no flap in between
    if hs_['opens'] != 1 or hs_['closes'] != 1 or hs_['dip_deg'] > 3.0: o['fails'].append(f"barrels flap: {hs_['opens']} opens, {hs_['closes']} closes, dip {hs_['dip_deg']} deg (rule S1)")
    if ev.get('trip') is not None and seat is not None:      # the barrels flap back toward the breech and reopen before the load: reads as a glitch
        seg = th[int(ev['trip']) + 1:seat + 1]
        if len(seg) and math.degrees(seg.min()) < 15:        # physical (the gun's own deceleration; the ejector springs and gravity throw them back open), but it reads as a slap: reported, scored under clarity
            fm = int(ev['trip']) + 1 + int(np.argmin(seg)); held = fm <= (plan.get('lever_until') or plan['lever'] + 3)
            o.setdefault('notes', []).append(f"barrels swing back to {math.degrees(seg.min()):.0f} deg at f{fm} as the wrist stops and the ejector springs and gravity reopen them" + (' (lever still held: the bolt cannot catch)' if held else ''))
    # nothing on the hinge may move without a cause: any barrel motion while the gun is still and no contact acts
    still = [f for f in range(2, N - 1) if abs(th[f] - th[f - 1]) > math.radians(0.5) and gun_ang_speed(GW, f - 1, f + 1)[0] < 0.3 and
             float(np.linalg.norm(GW[f + 1][:3, 3] - 2 * GW[f][:3, 3] + GW[f - 1][:3, 3])) * 100 < 0.05 and not any(abs(x['t'] - f) < 2 for x in ev.get('contacts', []) if isinstance(x, dict))]
    # (a barrel in free swing keeps moving on a still gun: only a start from rest is a fail)
    starts = [f for f in still if abs(th[f - 1] - th[f - 2]) < math.radians(0.05)]
    if starts: o['fails'].append(f'barrels start moving without a cause at f{starts[0]}')
    import rchecks
    V = None; L = o['layout']; hs, he = L['hide_start'], L['hide_end']; eye = np.array(rchecks.eye_point(c.body)) if hasattr(rchecks, 'eye_point') else None
    import gungeo
    Vm = gungeo.verts(common.find('weapon_meshes', MESH[c.gun] + '__mag_std_01.glb'))[::4]; V1 = np.c_[Vm, np.ones(len(Vm))]; seen = {}; near = 9.0
    for nm, per in (('spent', spent), ('fresh', fresh)):
        on = sorted({f for W in per.values() for f, M in enumerate(W) if M is not None and rchecks.screen((V1 @ M.T)[:, :3])[2].any()})
        seen[nm] = [on[0], on[-1]] if on else None
    o['shells_seen'] = seen
    sp_on = seen.get('spent'); se = plan.get('seat'); o['open_gun_f'] = hs     # round 3: the gun out of view (rgate) before any hull shift
    fr = min((s_['free'] for s_ in sst), default=None)
    if fr is not None and sp_on: o['hulls_visible_f'] = sp_on[1] - fr
    if fr is not None and (not sp_on or sp_on[1] - fr < 4): o['fails'].append(f"hulls in view only {(sp_on[1] - fr) if sp_on else 0} f after the ejectors throw them (rule 4)")
    if hs is not None and sp_on and sp_on[1] >= hs:      # round 3: the game does not draw the hulls (WIRING-NOTES: not tracked), so the hidden window starts when the gun is out of view; noted
        o.setdefault('notes', []).append(f"hulls still in view until f{sp_on[1]} after the gun leaves the view at f{hs} (preview only: the game does not draw them)")


def table(ids):
    """measure/physics_round2.md and .json: per take the physics gate numbers, the inertia numbers and the rgate body numbers."""
    d = OUT + '/clips/pma'; os.makedirs(OUT + '/measure', exist_ok=True); J = {}
    R = ['| take | open | close | lever f | cocked f | trip f | gun swing at break deg/f | barrels at trip deg/f | open stop hits (f: deg/f) | gun swing at close deg/f | barrels at breech deg/f (need) | latch | shut f | hulls out m/s (carry) | hulls land f | fresh: barrels deg at seat, insert cm/f | notes | fails |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    I = ['| take | max overshoot cm / deg | rebound cm | settle f | rotation lag f | muzzle trail deg | peak grip cm/f | eye cm | cover % | wrist / in view deg | reach | shoulder cm | body cm | guns gap cm | hidden |', '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for p in ids:
        for t in 'AB':
            n = prod.stem(GUNS[t], p, t, CLIP, 'right'); gp = f'{d}/{n}_gate.json'
            if not os.path.exists(gp): continue
            o = json.load(open(gp)); ph = o['phys']; G = o['inertia']['gun']; L = o['layout']; sp = ph['spent'][0] if ph['spent'] else {}; fr = ph['fresh'] or {}
            hits = ', '.join(str(x['t']) + ': ' + str(x['w_deg_f']) for x in ph['stop_hits'][:2])
            J[p + t] = {'phys': ph, 'gun': {k: v for k, v in G.items() if k != 'impacts'}, 'fails': o['fails'], 'notes': o.get('notes', [])}
            R.append(f"| {p}{t} | {OPEN[p]} | {CLOSE[p]} | {ph['lever_f']} | {ph['cocked_f']} | {ph['trip_f']} | {ph['open_swing_deg_f']} | {ph['barrel_at_trip_deg_f']} | {hits} | "
                     f"{ph['close_swing_deg_f']} | {ph['latch_w_deg_f']} ({ph['latch_need_deg_f']}) | {ph['latch']} | {ph['shut_f']} | {sp.get('exit_m_s')} ({sp.get('carry_m_s')}) | {sp.get('land')} | {fr.get('barrels_deg_at_seat')}, {fr.get('insert_cm_f')} | {'; '.join(o.get('notes', [])) or '-'} | {'; '.join(o['fails']) or 'pass'} |")
            I.append(f"| {p}{t} | {G['overshoot_cm_max']} / {G['overshoot_deg_max']} | {G['rebound_cm_max']} | {G['settle_f_max']} | {G['rot_lag_f']} | {G['muzzle_trail_deg']} | {ph['peak_grip_cm_f']} | {o['eye_cm'][0]} | {o['cover_peak'][0]} | {o['wrist'][0]} / {o['wrist_view']} | {o['reach'][0]} | {o['shoulder_pull_cm']} | {o['body_cm'][0]} | {o['guns_gap_cm'][0]} | f{L['hide_start']}-{L['hide_end']} |")
    M = bp.summary('palica'), bp.summary('satara')
    head = ['# BREAK-OPEN round 2: physics and gate numbers', '', 'Model (breakphys.py, RESEARCH.md section 3): ' + '; '.join(f"{g}: " + ', '.join(f'{k} {v}' for k, v in m.items()) for g, m in zip(('Palica', 'Satara'), M)), '',
            "Swing speeds: the gun's largest angular speed (deg per frame, 30 fps) from the lever to the ejector trip, and in the 6 frames before the latch; barrel speeds are relative to the gun.", '']
    open(OUT + '/measure/physics_round2.md', 'w', encoding='utf-8').write(chr(10).join(head + R + ['', '## Gun inertia and body checks', ''] + I) + chr(10))
    json.dump({'model': {'palica': M[0], 'satara': M[1]}, 'takes': J}, open(OUT + '/measure/physics_round2.json', 'w'), indent=1); print(chr(10).join(R))


# ------------------------------------------------------------------------------------------------ CLI
if __name__ == '__main__':
    argv = sys.argv[1:]; opt = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'; takes = (opt('--takes') or 'A,B').split(',')
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(PICKS)
    if cmd == 'list':
        for p, (n, fn) in PICKS.items(): print(p, n, '|', DOC[p])
    elif cmd == 'build':
        for p in ids:
            for t in takes: build(p, t)
    elif cmd == 'table': table(ids)
    else: raise SystemExit(__doc__)
