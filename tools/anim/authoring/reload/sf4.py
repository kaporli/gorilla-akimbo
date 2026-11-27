"""SMG and shotgun FRONT family, round 4: ten new techniques SF31 to SF40 for picks 2 and 3 (pick 1: round 2's SF13
low chop). Take A on the Saratoga (72 frames), take B on the Zhuo (81 frames); right hand, male V, empty reload.
Round 2's budget and beats (sf2.BUDGET), part-frame map and racks. New: every draft runs through the inertia model
(inertia.py): the timeline below is the hand target, the gun is simulated on it (overshoot, rebound, rotation lag,
muzzle trail, seat jolt), the magazine slides along the well under the pseudo-forces and flies as a rigid body.

usage: sf4.py list | build [ids csv] [--takes A,B] [--jobs n] | stats [ids] | table
Output: <OUT>/clips/pma/<gun>_right_<id><take>_empty_reload.glb, .json (spec), _track.json, _gate.json, _inertia.json
"""
import os, sys, json, math, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, prod, rgate, magtrack2, sf2, inertia, rlib2
from sf2 import BUDGET, GUNS, CLIP, L, PUNCH, bud, long_gun, exw, mag_point, opener, rack, setup, part_frames, elbow_step, gone_height, stem
from rlib import K
from glb import Glb
from fk import Clip, qrot

OUT = renv.OUT
TAKES = {t: dict(sf2.TAKES[t], lag=0, drag=0.0) for t in 'AB'}
TAKES['B'].update(rise=(0.03, -0.11, -0.02), dive=(2.2, 2.6))     # Zhuo: the rack's rise less far forward (the simulated overshoot pulled the shoulder), softer arrival above the rig     # no authored lag or drag: the simulation makes them
MAG_RATIO = (0.85, 1.15)


class TL(sf2.TL):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.guides = []

    def path(self, f0, f1, fn):
        """Frames f0+1..f1 from fn(f) -> (offset, angles); the pose at f0 is the current one."""
        for f in range(int(f0) + 1, int(f1) + 1):
            p, r = fn(f); self.P[f] = p; self.R[f] = r
        self.P[int(f1) + 1:] = self.P[int(f1)]; self.R[int(f1) + 1:] = self.R[int(f1)]
        self.f = int(f1); self.rf = int(f1); self.p = np.array(self.P[int(f1)]); self.r = np.array(self.R[int(f1)])
        return self


# slap-home station: beside the right thigh, muzzle down, well facing the leg (the magazine's base meets the thigh at
# the seat; the thigh is the gate's leg capsule, radius 8.5 cm: its surface is where the base stops, unverified in game)
prod.STATION.setdefault('slap_thigh', ((0.37, 0.06, -0.02), (-75, 0, -80)))
prod.STATION.setdefault('slap_thigh_m', ((0.33, 0.12, -0.06), (-75, 0, -80)))       # Zhuo: less far out (shoulder)


def stn(c, name): return sf2.STN_LONG.get(name, name) if long_gun(c) else name


def dive(c, tl, f, pos, rot, prof):
    """Move to (pos, rot) arriving on f; with P['via'] (Zhuo) first out to the side and forward at mid-way, so the
    long stock clears the torso."""
    v = c.P.get('via')
    if v is not None and f - tl.f >= 4:
        m = (tl.f + f) // 2; tl.to(m, (np.array(tl.p) + np.array(pos)) / 2 + np.array(v), np.array(tl.r) if c.P.get('via_keep_rot') else rot, 'drive')
    tl.to(f, pos, rot, prof)


def seat(c, tl, pos, rot, arrive, se, d=0.18, slam=5):
    """Dive to `d` above the fresh magazine on the rig (arrive), hold, slam along the well onto it. The fresh
    magazine is the stop: a contact plane at the seat (restitution, jolt); the target arrives one frame early so the
    gun meets the plane on the seat frame."""
    pre = np.array(pos) + c.along(rot, c.v['enter'], d); dive(c, tl, arrive, pre, rot, c.P.get('dive', (2.4, 2.2))); tl.hold(se - slam)
    over = c.along(rot, c.v['enter'], -0.012)                     # the hand drives a little past the seat: the magazine stops the gun
    tl.to(se - 1, np.array(pos) + over, rot, c.P.get('slam', (2.8, 1.5))); tl.to(se + 1, pos, rot, 'ease'); tl.mark('arrive', arrive)
    if c.P.get('post_seat') is not None: tl.to(se + 4, np.array(pos) + np.array(c.P['post_seat']), rot, 'drive')   # out to the side first: the long stock clears the hip
    n = -c.along(rot, c.v['enter'], 1.0); n = n / np.linalg.norm(n)
    tl.guides.append({'f': [se - 7, se], 'seat': se, 'axis': list(c.v['enter'])})
    return {'name': 'seat', 'f': [se - 4, se + 1], 'anchor': np.array(pos, float), 'n': n, 'axis': (1, 0, 0)}


def to_rig(c, tl, station, start, d=0.18):
    """From frame `start`, dive to the rig and slam onto the fresh magazine on the seat frame."""
    P = c.P; se = bud(c)['seat']; pos, rot = c.station(stn(c, station)); tl.hold(start); arr = min(start + L(P, 10), se - 6)
    ct = seat(c, tl, pos, rot, arr, se, d=d)
    if long_gun(c): tl.mark('clamp', se)
    return arr, ct


def plan(c, release, **kw):
    d = {'release': int(release), 'seated': bud(c)['seat'], 'appear': bud(c)['seat'] - 8, 'lead': 3, 'clear': c.P.get('clear', 0.13 if long_gun(c) else 0.11), 'floor': 0.08}; d.update(kw); return d


def roll_axis_angles(r0, droll):
    return np.array(r0, float) + np.array([0, 0, droll])


# ------------------------------------------------------------------------------------------------ drafts
def smooth(t): t = min(max(t, 0.0), 1.0); return t * t * (3 - 2 * t)


def orbit(tl, f0, f1, R, u, v, th_end, turns, rot, prof=(2.4, 1.6), grow=0.3, off=(0, 0, 0)):
    """Translational circle of the grip (the gun keeps the angles rot), centred on the current grip (plus off, eased
    in): the radius grows in over the first `grow` share, the angle runs through `turns` turns (negative: the other
    way round) with the speed profile prof (late peak, slows to rest at th_end). Returns {frame: theta in degrees}."""
    c0 = np.array(tl.p, float); r0 = np.array(tl.r, float); u, v = np.array(u, float), np.array(v, float); n = f1 - f0
    S = rlib2.beta_cdf(*prof, n); th0 = th_end - 360.0 * turns; TH = {}
    def at(f):
        k = f - f0; x = k / n; rr = R * smooth(x / grow); th = th0 + (th_end - th0) * S[k]; TH[f] = th
        p = c0 + np.array(off, float) * smooth(x / grow) + rr * (math.cos(math.radians(th)) * u + math.sin(math.radians(th)) * v)
        return p, r0 + (np.array(rot, float) - r0) * smooth(x / grow)
    tl.path(f0, f1, at); return TH


def first(TH, cond):
    return next(f for f in sorted(TH) if cond(TH[f]))


def well_vertical(c, inverted=False):
    """Gun angles that put the well axis straight up and down (pitch only; inverted: rolled over, well up)."""
    e = np.array(c.v['exit'], float); p = math.degrees(math.atan2(-e[2], -e[1]))
    return np.array((-p, 0.0, 0.0)) if not inverted else np.array((p, 0.0, 180.0))


def strike_contact(c, tl, p0, rot, dirn, dist, n, through=0.03, normal=None, e=0.35, name='body'):
    """A straight strike from p0 along dirn that is stopped by a body contact `dist` along: the hand target aims
    `through` m past it (the arm drives through), the plane stops the gun and it rebounds (restitution e). Returns
    (contact frame of the target, contact dict)."""
    dirn = np.array(dirn, float); dirn /= np.linalg.norm(dirn); f0 = tl.f; f1 = f0 + n
    tl.to(f1, np.array(p0) + dirn * (dist + through), rot, 'slam'); nn = dirn if normal is None else np.array(normal, float) / np.linalg.norm(normal)
    return f1, {'name': name, 'f': [f0, f1 + 3], 'anchor': np.array(p0) + dirn * dist, 'n': nn, 'e': e, 'axis': (1, 0, 0), 'jolt': 0.8}


def sf31(c, tl):
    """Barrel roll. The forearm rolls the gun over about its bore toward the outside, fast. The latch lets go as the
    roll starts and the spin slings the magazine out along the well: it leaves out to the right, turning with the
    roll, while the gun coasts on to nearly upside down with the empty well showing, rebounds, and rolls back on the
    way down to the belt rig. Punched forward on the home frame."""
    P = c.P; s = bud(c)['stop'] - P.get('early', 3); opener(c, tl, 'tug'); p0 = np.array(P.get('p0', (0.02, -0.02, -0.02))); r0 = np.array(P.get('r0', (-4, 0, -30)))
    n = L(P, P.get('n', 8)); a = s - n; tl.hold(a - L(P, 5)); tl.to(a, p0, r0, 'ease')
    re = r0 + (0, 0, P.get('roll', 150)); tl.to(s, p0 + np.array(P.get('lift', (0.0, 0.015, 0.0))), re, P.get('prof', (2.2, 1.7)))
    rel = a + P.get('rel', 1); tl.mark('release', rel); tl.mark('stop', s); tl.hold(s + 3)
    arr, ct = to_rig(c, tl, 'belt', s + 3); rack(c, tl, 'punch')
    return {'mag': plan(c, rel), 'contacts': [ct]}


def sf32(c, tl):
    """Crank wheel. The hand cranks the gun round a small upright circle in front of the chest, inward over the
    bottom, the gun level throughout, faster to the end. On the last pass the latch lets go: at the bottom the hand
    pulls the gun up and out while the magazine goes on, so it slides out down the well and is thrown inward along
    the circle, down between the guns. The gun runs out of the circle down to the hip rig. Rack: the muzzle is
    thrown down on the home frame."""
    P = c.P; s = bud(c)['stop']; opener(c, tl, 'tug'); f0 = bud(c)['cock'] + P.get('f0', 1); f1 = s - P.get('early', 1); th_end = P.get('th_end', -110.0)
    tl.hold(f0); TH = orbit(tl, f0, f1, P.get('R', 0.08), (1, 0, 0), (0, 1, 0), th_end, -P.get('turns', 1.0), (-4, 0, 0), off=P.get('off', (-0.04, 0.0, 0.0)))
    rel = first(TH, lambda th: th <= th_end + P.get('lead_deg', 150)); tl.mark('release', rel); tl.mark('stop', f1)
    arr, ct = to_rig(c, tl, 'hip', f1 + 1); rack(c, tl, 'nod')
    return {'mag': plan(c, rel), 'contacts': [ct]}


def tablecloth(c, tl, hold, rinv, dirn):
    """Upside down and held (latch open, gravity keeps the magazine in), then ripped away at P['g'] g along dirn and
    kept going until the magazine is clear. Returns the release frame and the frame the pull ends."""
    P = c.P; s = bud(c)['stop']; ph = np.array(P.get('hold', hold)); ri = np.array(P.get('rinv', rinv))
    fh = s - L(P, P.get('pre', 5)); tl.hold(fh - L(P, 7)); tl.to(fh, ph, ri, 'drive'); tl.hold(fh + L(P, 2)); fp = tl.f
    a = P.get('g', 2.3) * magtrack2.G_ACC; dr = np.array(P.get('dir', dirn), float); dr = dr / np.linalg.norm(dr); n = L(P, 3)
    k = P.get('coast', L(P, 2)); vend = dr * a * n
    tl.path(fp, fp + n + k, lambda f: ((ph + dr * 0.5 * a * (f - fp) ** 2) if f - fp <= n else (ph + dr * 0.5 * a * n * n + vend * (f - fp - n)), ri))
    tl.mark('release', fh); tl.mark('stop', fp + n + k); return fh, fp + n + k


def sf33(c, tl):
    """Tablecloth. The gun is turned upside down, well up, and held: the latch lets go but gravity keeps the
    magazine in. Then the hand rips the gun down and away faster than it can fall (about 2.3 g): the magazine is
    left floating where the gun was, hangs for a moment and falls, while the gun rolls back upright on its way down
    to the hip rig. Rack: held out, yanked back on the home frame."""
    opener(c, tl, 'tip'); fh, fe = tablecloth(c, tl, (0.0, 0.03, -0.03), (-6, 0, -165), (0.35, -1.0, 0.12))
    se = bud(c)['seat']; pos, rot = c.station(stn(c, 'hip')); arr = se - 7
    dive(c, tl, arr, np.array(pos) + c.along(rot, c.v['enter'], 0.18), rot, (1.25, 2.4)); ct = seat(c, tl, pos, rot, arr + 1, se); rack(c, tl, 'yank')
    return {'mag': plan(c, fh), 'contacts': [ct]}


def crest(c, tl, start, top, end, rinv):
    P = c.P; s = bud(c)['stop'] - P.get('early', 5); ri = np.array(P.get('rinv', rinv))
    st = np.array(P.get('start', start)); tp = np.array(P.get('top', top)); en = np.array(P.get('end', end))
    fa = s - L(P, P.get('n', 7)); tl.hold(fa - L(P, 3)); tl.to(fa, st, ri, 'drive'); n = s - fa; S = rlib2.beta_cdf(2.0, 2.0, n)
    def at(f):
        u = S[f - fa]; x = st[0] + (en[0] - st[0]) * u; z = st[2] + (en[2] - st[2]) * u
        y = (1 - u) ** 2 * st[1] + 2 * u * (1 - u) * (2 * tp[1] - 0.5 * (st[1] + en[1])) + u * u * en[1]
        return np.array((x, y, z)), ri
    tl.path(fa, s, at); rel = fa + 1; tl.mark('release', rel); tl.mark('stop', s); tl.hold(s + 1); return rel


def sf34(c, tl):
    """Crest. The gun, upside down with the well up, is carried in a quick arc from low right up over a crest and
    down to the left, like a car over a hump. The latch is open; over the crest the path drops away faster than the
    magazine can fall, so it lifts out of the well, floats up above the gun and falls in front. The gun rolls back
    upright and goes down to the stomach rig. Rack: muzzle thrown down on the home frame."""
    opener(c, tl, 'tip'); rel = crest(c, tl, (0.08, -0.05, -0.02), (0.0, 0.06, -0.03), (-0.09, -0.06, -0.01), (-4, 0, -165))
    s = tl.f; arr, ct = to_rig(c, tl, 'stomach', s + 1); rack(c, tl, 'nod')
    return {'mag': plan(c, rel), 'contacts': [ct]}


def sf35(c, tl):
    """Bat. A short, slow roll outward lets the magazine slide out of the well and drop beside the gun. Before it
    has fallen a hand's width the gun swings back under it and bats it away with its underside: the magazine's
    flight comes from the hit. Down to the belt rig. Rack: cocked back, punched forward on the home frame."""
    P = c.P; s = bud(c)['stop']; opener(c, tl, 'tug'); p0 = np.array(P.get('p0', (0.0, 0.0, -0.02))); r0 = np.array(P.get('r0', (-4, 0, 0)))
    a = s - L(P, 10); tl.hold(a - L(P, 3)); tl.to(a, p0, r0, 'ease'); tl.to(a + L(P, 4), p0 + np.array((-0.02, 0.01, 0.0)), r0 + (0, 0, P.get('roll', 60)), 'ease')
    rel = a + 1; tl.mark('release', rel)
    bat = P.get('_bat')                    # (frame of the hit, gun offset and angles at the hit) from the first pass (see build)
    if bat:
        fb, pb, rb, fs = bat; tl.hold(max(fs, tl.f))           # the gun holds still until the magazine is out, then swings through it
        tl.to(fb + 1, np.array(pb) + np.array(P.get('through', (0.02, -0.015, 0.0))), rb, P.get('bat_prof', (2.0, 1.8)))   # production: bat_prof (default as reviewed); tl.mark('bat', fb)
        start = fb + 3
    else: start = s + 2
    tl.mark('stop', start); arr, ct = to_rig(c, tl, 'belt', start); rack(c, tl, 'punch')
    return {'mag': plan(c, rel, hits=[{'body': 'gun', 'f': [rel + 3, start], 'p': list(P.get('pad', (0.0, -0.05, -0.24))), 'n': [0, -1, 0], 'rad': 0.2, 'e': 0.35, 'mu': 0.25}]), 'contacts': [ct], 'bat': True}


def elbow_check(c, tl, p0, r0, dirn, dist):
    """Swing in and down along the well until the elbow meets the ribs: a body contact stops the gun dead (it
    rebounds), the magazine goes on out of the well at the gun's speed."""
    P = c.P; s = bud(c)['stop']; tl.hold(s - L(P, 5) - L(P, 6)); tl.to(s - L(P, 5), p0, r0, 'drive'); tl.hold(s - L(P, 5) + 1)
    dirn = exw(c, r0) if dirn is None else dirn
    fc, ct = strike_contact(c, tl, p0, r0, dirn, dist, L(P, 4) - 1, e=0.3, name='elbow on ribs')
    rel = fc - 1; tl.mark('release', rel); tl.mark('stop', fc); tl.hold(fc + 2); return rel, fc, ct


def sf36(c, tl):
    """Elbow check. The gun is rolled onto its right side, well facing down and in, and swung in across the belly;
    the elbow slams into the ribs and the swing stops dead, harder than any muscle stop, and the gun bounces back a
    little: the magazine goes on, out of the well, down and to the left in front of the belt. Down to the belt
    rig. Rack: the thumb drops the cocking piece and the gun jolts."""
    P = c.P; opener(c, tl, 'tug'); rel, fc, ct0 = elbow_check(c, tl, np.array(P.get('p0', (0.12, -0.05, 0.02))), np.array(P.get('r0', (-4, 0, -50))), P.get('dir'), P.get('dist', 0.13))
    arr, ct = to_rig(c, tl, 'belt', fc + 2); rack(c, tl, 'thumb')
    return {'mag': plan(c, rel), 'contacts': [ct0, ct], 'thrown': True}


def hammer_fist(c, tl):
    """The fist comes down on the top of the right hip: the body stops the gun dead and it bounces back up, the
    magazine goes on down the well past the hip."""
    P = c.P; s = bud(c)['stop']; rv = well_vertical(c); up = np.array(P.get('up', (0.08, -0.10, 0.24)))
    tl.hold(s - L(P, 5) - L(P, 7)); tl.to(s - L(P, 5), up, rv, 'drive'); tl.hold(s - L(P, 5) + 1)
    fc, ct = strike_contact(c, tl, up, rv, (0, -1, 0), P.get('drop', 0.20), L(P, 5), e=0.35, name='fist on hip')
    rel = fc - 1; tl.mark('release', rel); tl.mark('stop', fc); tl.hold(fc + 2); return rel, fc, ct


def sf37(c, tl):
    """Hammer fist, toss-and-catch. The gun is drawn up and back above the right hip and the fist is hammered down
    onto the hip: the body stops the gun dead and it bounces back up, the magazine goes on down past the hip. The
    belt rig then flips the fresh magazine up end over end; the gun, turned upside down with the well up, catches
    it as it falls back, and takes the catch. Rolled upright on the way up. Rack: cocked low, a rising punch."""
    P = c.P; se = bud(c)['seat']; opener(c, tl, 'tug'); rel, fc, ct0 = hammer_fist(c, tl)
    cp = np.array(P.get('catch', (0.10, -0.40, 0.24))); ri = well_vertical(c, True) + np.array((P.get('catch_tilt', 0.0), 0, 0))
    tl.to(se - L(P, 7), cp + np.array((0, 0.03, 0)), ri, 'drive'); tl.hold(se - 3); tl.to(se, cp, ri, 'ease')
    tl.kick(se, (0, -0.014, 0), (-2, 0, 0)); tl.guides.append({'f': [se - 6, se], 'seat': se, 'axis': list(c.v['enter'])}); tl.mark('arrive', se - L(P, 7))
    rack(c, tl, 'upper')
    T = P.get('toss_frames', L(P, 11))
    return {'mag': plan(c, rel, fresh={'kind': 'toss', 'launch': se - T, 'below': P.get('below', 0.10)}), 'contacts': [ct0], 'thrown': True}


def sf38(c, tl):
    """Tablecloth, slap home. As SF33, but ripped down and to the left and rolled the other way: the magazine is
    left floating and falls. Then a loading trick: the gun takes the fresh magazine half in from the belt rig,
    carries it to the thigh and slaps it home against the thigh: the magazine's base stops on the leg and the gun
    runs on over it with a jolt. Rack: punched forward on the home frame."""
    P = c.P; opener(c, tl, 'tug'); fh, fe = tablecloth(c, tl, (0.02, 0.03, -0.03), (-6, 0, 165), (-0.30, -1.0, 0.10))
    se = bud(c)['seat']; pb, rb = c.station(stn(c, 'belt')); d0 = P.get('d0', 0.06); pk = se - L(P, 9)
    dive(c, tl, pk - 2, np.array(pb) + c.along(rb, c.v['enter'], 0.15), rb, (1.4, 2.3)); tl.to(pk, np.array(pb) + c.along(rb, c.v['enter'], d0), rb, 'slam'); tl.hold(pk + 1)
    pt, rt = c.station('slap_thigh_m' if long_gun(c) else 'slap_thigh'); ct = seat(c, tl, pt, rt, se - 5, se, d=0.16, slam=4); rack(c, tl, 'punch')
    return {'mag': plan(c, fh, fresh={'kind': 'slap', 'pick': pk, 'd0': d0}), 'contacts': [ct]}


def sf39(c, tl):
    """Crest, presented. As SF34 but carried the other way, from low left over the crest to the right: the magazine
    floats up off the gun and falls outside. A loading trick: the hip rig pushes the fresh magazine up out of its
    pouch to meet the gun, so the gun is driven down onto a magazine still coming up at it: a harder seat. Rack:
    held out, yanked back."""
    opener(c, tl, 'tip'); rel = crest(c, tl, (-0.08, -0.05, -0.02), (0.02, 0.06, -0.03), (0.10, -0.06, -0.01), (-4, 0, 165))
    s = tl.f; se = bud(c)['seat']; arr, ct = to_rig(c, tl, 'hip', s + 1); rack(c, tl, 'yank')
    return {'mag': plan(c, rel, fresh={'kind': 'pop', 'p0': se - L(c.P, 6), 'rise': 0.07}), 'contacts': [ct]}


def sf40(c, tl):
    """Elbow check, slap home. As SF36 but from higher, the gun more on its side, the stop at the ribs under the
    chest: the magazine is driven out down and in. Then the slap-home load of SF38: half in from the belt rig,
    slapped home against the thigh. Rack: the muzzle thrown down on the home frame."""
    P = c.P; opener(c, tl, 'tip'); rel, fc, ct0 = elbow_check(c, tl, np.array(P.get('p0', (0.12, 0.0, 0.0))), np.array(P.get('r0', (-4, 0, -70))), P.get('dir'), P.get('dist', 0.14))
    se = bud(c)['seat']; pb, rb = c.station(stn(c, 'belt')); d0 = P.get('d0', 0.06); pk = se - L(P, 9)
    dive(c, tl, pk - 2, np.array(pb) + c.along(rb, c.v['enter'], 0.15), rb, (1.4, 2.3)); tl.to(pk, np.array(pb) + c.along(rb, c.v['enter'], d0), rb, 'slam'); tl.hold(pk + 1)
    pt, rt = c.station('slap_thigh_m' if long_gun(c) else 'slap_thigh'); ct = seat(c, tl, pt, rt, se - 5, se, d=0.16, slam=4); rack(c, tl, 'nod')
    return {'mag': plan(c, rel, fresh={'kind': 'slap', 'pick': pk, 'd0': d0}), 'contacts': [ct0, ct], 'thrown': True, 'hit_left': True, 'hit_optional': True}


PICKS = {'SF31': ('Barrel roll', sf31), 'SF32': ('Crank wheel', sf32), 'SF33': ('Tablecloth', sf33), 'SF34': ('Crest', sf34), 'SF35': ('Bat', sf35),
         'SF36': ('Elbow check', sf36), 'SF37': ('Hammer fist, toss-and-catch', sf37), 'SF38': ('Tablecloth, slap home', sf38), 'SF39': ('Crest, presented', sf39),
         'SF40': ('Elbow check, slap home', sf40)}
DOC = {k: ' '.join((fn.__doc__ or '').split()) for k, (n, fn) in PICKS.items()}
RELEASE = {'SF31': 'spin about the bore', 'SF32': 'spin: translational orbit', 'SF33': 'pulled away above 1 g, upside down', 'SF34': 'crest airtime, upside down',
           'SF35': 'gravity pour, then batted', 'SF36': 'body contact stop (elbow on ribs)', 'SF37': 'body contact stop (fist on hip)', 'SF38': 'pulled away above 1 g, upside down',
           'SF39': 'crest airtime, upside down', 'SF40': 'body contact stop (elbow on ribs)'}
LOAD = {'SF31': 'rig', 'SF32': 'rig', 'SF33': 'rig', 'SF34': 'rig', 'SF35': 'rig', 'SF36': 'rig', 'SF37': 'toss-and-catch', 'SF38': 'slap home', 'SF39': 'rig presents', 'SF40': 'slap home'}
WHY = {
    'SF31': 'The forearm rolls the gun about its own bore and the spin pulls the magazine out along the well (centrifugal, 1.1 to 1.4 g on top of gravity) while the gun is still turning; every banned throw (chops, flicks, flings, nods, snaps) frees the magazine by stopping a translation or a nod, and none turns the gun about its bore.',
    'SF32': 'The grip runs a circle with the gun level and never stops; the magazine leaves at the bottom because the hand pulls the gun back up toward the centre faster than gravity can (1.8 to 3.1 g of pull along the well from the circling hand, 1 g from gravity); every banned throw needs a stop, a tip or a pull along the well, and a circle has none of them.',
    'SF33': 'Upside down, gravity holds the magazine in, and only pulling the gun away faster than 1 g frees it, so it is left hanging where the gun was; jerk away and jerk up pull an upright or canted gun off a magazine that gravity already pulls out, so neither needs or shows the over-1 g pull against gravity.',
    'SF34': 'The upside-down gun goes over a crest faster than gravity can bend the magazine\'s path, so the magazine lifts out of the well and flies up off a gun that never stops (centripetal, like a car leaving a hump); every banned release stops, tips or pulls the gun, and none lifts the magazine upward.',
    'SF35': 'A slow pour lets the magazine out, and its whole flight comes from a second impact, the gun swinging back and batting it away with its underside (impulse with restitution 0.35); the pour alone is release and let it fall, so the banned part is only the first 5 frames, the bat is new.',
    'SF36': 'The swing is stopped by the elbow hitting the ribs, a contact with restitution 0.3 that stops the gun within a frame and bounces it back, so the magazine leaves at the full swing speed; that is a cross-body stop (banned) with the body as the tool, which the coordinator\'s rule allows: different tool, harder stop, visible rebound.',
    'SF37': 'The fist hits the hip and the body stops the gun (contact, restitution 0.35, bounce back), and the fresh magazine is flipped up by the rig and caught in the upside-down well as it falls; the strike is a banned low stop with the body as the tool, the loading (toss-and-catch, well up) is new.',
    'SF38': 'The release is SF33\'s over-1 g pull (to the left, rolled the other way), the loading is new: the magazine is taken half in from the belt rig and slapped home on the thigh, so its base stops on the leg and the gun runs on over it; it differs from SF33 in loading.',
    'SF39': 'The release is SF34\'s crest (left to right, so the magazine floats out to the right), the loading is new: the hip rig pushes the magazine up out of its pouch to meet the gun, so the gun hits a magazine still coming at it; it differs from SF34 in loading.',
    'SF40': 'The release is SF36\'s elbow stop (from higher, the gun more on its side), the loading is SF38\'s slap home; it differs from SF36 in loading and from SF38 in release.',
}
DEF = {'SF32': {'R': 0.05, 'off': (-0.04, 0.01, -0.03)}, 'SF31': {'p0': (-0.07, -0.01, -0.04), 'roll': 140, 'n': 9}}
PARAMS = {   # Zhuo: the long stock reached the face or the torso, or the arm overreached: lower, closer; upside down
    # the stock rises toward the face (it sits below the bore), so those takes also tip the muzzle up
    'SF32B': {'R': 0.045, 'off': (-0.04, -0.10, -0.02)},
    'SF33B': {'via': (0.10, 0.06, -0.06), 'via_keep_rot': True, 'hold': (0.04, -0.05, -0.03), 'dir': (0.6, -1.0, -0.15), 'coast': 1, 'g': 2.3, 'rinv': (18, 0, -165), 'post_seat': (0.08, 0.02, -0.08), 'clear': 0.10},
    'SF34B': {'via': (0.10, 0.06, -0.06), 'start': (0.08, -0.12, -0.04), 'top': (0.0, -0.06, -0.05), 'end': (-0.09, -0.14, -0.03), 'rinv': (30, 0, -165)},
    'SF39B': {'start': (-0.08, -0.12, -0.04), 'top': (0.02, -0.03, -0.05), 'end': (0.10, -0.13, -0.03), 'rinv': (18, 0, 165)},
    'SF36B': {'p0': (0.12, -0.08, -0.03)}, 'SF40B': {'via': (0.10, 0.06, -0.06), 'p0': (0.12, -0.05, -0.03), 'post_seat': (0.08, 0.02, -0.08)}, 'SF37B': {'catch': (0.14, -0.44, 0.20), 'toss_frames': 9, 'catch_tilt': -25.0}, 'SF31B': {'p0': (-0.04, -0.06, 0.0), 'r0': (12, 0, -30)},
    'SF38B': {'via': (0.06, 0.04, -0.06), 'via_keep_rot': True, 'dir': (-0.5, -1.0, -0.15), 'hold': (0.04, -0.05, -0.03), 'coast': 1, 'g': 2.3, 'rinv': (18, 0, 165), 'post_seat': (0.08, 0.02, -0.08), 'clear': 0.10},
    'SF35B': {'roll': 45}}


# ------------------------------------------------------------------------------------------------ build
def keys_from(c, sim):
    N = c.N; X, E = sim['X'], sim['E']
    keys = [K(f, X[f], E[f]) for f in range(N)]; keys[0] = K(0); keys[-1] = K(N - 1); return keys


def impulses_from(tl):
    """tl.kick calls (the opener's stop, the rack's hits) become velocity impulses on the simulated gun: a kick of m
    metres and r degrees gives about that peak displacement."""
    return [(k['f'], np.array(k['move'], float), np.radians(np.array(k['rot'], float))) for k in tl.kicks]


def release_dv(o, track, G):
    """rgate's release_dv compares the last guided frame step with the first free one, so a magazine that is still
    being accelerated along the well (2 to 4 g of centrifugal pull) shows that acceleration as a 'jump'. Here the
    change of frame step around the hand-off (frames ff-2, ff-1, ff) is compared with what the model's accelerations
    give over the same frames (triangle kernel over the guided substeps, gravity after the hand-off): any difference
    is a real jump (rule 1.5 cm/f). rgate's own number is kept as release_dv_rgate_cm_f."""
    v = magtrack2.vanilla(o['gun'], CLIP); cen = np.r_[v['centre'], 1]; ff = track['free_from']
    if ff >= len(G) or ff < 2: return
    C = [(magtrack2.m4(*G[f]) @ np.array(track['frames'][f]['m']).reshape(4, 4) @ cen)[:3] for f in range(ff - 2, ff + 1)]
    d = (C[2] - C[1]) - (C[1] - C[0]); g = np.array([0, -magtrack2.G_ACC, 0]); acc = {round(t, 4): np.array(a) for t, a in track['phys']['acc_guided']}
    n = inertia.SUB; exp = np.zeros(3)
    for k in range(2 * n):
        t = ff - 2 + (k + 1) / n; w = 1 - abs(t - (ff - 1)); a = acc.get(round(t, 4), g) if t <= track['phys']['free_t'] + 0.01 else g
        exp += a * w / n
    for bo in track['phys']['bounces']:      # a bounce inside the window is an impulse the model applied
        if ff - 2 < bo['t'] <= ff: exp += np.array(bo['impulse']) * (1 - abs(bo['t'] - (ff - 1)))
    o['release_dv_rgate_cm_f'] = o['release_dv_cm_f']; o['release_dv_cm_f'] = round(float(np.linalg.norm(d - exp)) * 100, 2)
    o['fails'] = [x for x in o['fails'] if not x.startswith('release velocity jumps')]
    if o['release_dv_cm_f'] > rgate.LIM['release_dv_max_cm_f']: o['fails'].append(f"release velocity jumps {o['release_dv_cm_f']} cm/f beyond the modelled forces")


def left_hits(c, rel):
    """Patches on the left gun the right magazine can strike: the right flank of its magazine and of its body."""
    c0 = (c.v['seat'] @ np.r_[c.v['centre'], 1])[:3]; hw = 0.019 if c.gun == 'saratoga' else 0.04
    return [{'body': 'left', 'f': [rel, rel + 20], 'p': [float(x) for x in c0 + np.array([hw, 0, 0])], 'n': [1, 0, 0], 'rad': 0.12, 'e': 0.35, 'mu': 0.3},
            {'body': 'left', 'f': [rel, rel + 20], 'p': [0.03, 0.0, -0.12], 'n': [1, 0, 0], 'rad': 0.14, 'e': 0.35, 'mu': 0.3}]


def compose(pick, take, side, body, extra=None):
    gid = GUNS[take]; setup(gid); S = side.capitalize(); P = dict(TAKES[take]); P.update(DEF.get(pick, {})); P.update(PARAMS.get(pick + take, {})); P.update(extra or {})
    c = prod.Ctx(gid, body, CLIP, P, S); tl = TL(c, 0, 0.0); m = PICKS[pick][1](c, tl)
    Pt, Rt = tl.P.copy(), tl.R.copy(); Pt[-1] = 0; Rt[-1] = 0
    sim = inertia.simulate_gun(c, take, Pt, Rt, impulses_from(tl), m.get('contacts', []), tl.guides, model=m.get('model'))
    return c, tl, m, sim, Pt, Rt


def author_and_track(c, tl, m, sim, Pt, Rt, pick, take, name, d, S, left_shakes=None):
    keys = keys_from(c, sim); mg = m['mag']; gid = c.gun
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {take}', '_doc': DOC[pick], '_why': WHY.get(pick, ''), '_gun': gid, '_left_gun': gid, '_body': c.body, '_side': S,
            '_gun_clip': CLIP, '_pick': pick, '_take': take, '_timing': c.T, '_params': {k: v for k, v in c.P.items() if not k.startswith('_')}, '_marks': tl.marks, '_mag': mg, '_two_arm': False,
            '_round': 'smg-front-4', '_part_frames': part_frames(take, mg['release']), 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N,
            'keys': {S: keys, ('Left' if S == 'Right' else 'Right'): [K(0)]}, 'shakes': {S: [], 'Left': left_shakes or []}, 'reach': [0.93, 0.985],
            'twist_share': m.get('twist_share', 0.6), 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb',
            '_target': {'P': [[round(float(x), 5) for x in p] for p in Pt], 'R': [[round(float(x), 3) for x in r] for r in Rt]}}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); W = [cl.world(f) for f in range(c.N)]; i = g.names.index('Weapon' + S); il = g.names.index('WeaponLeft')
    G = [(np.array(W[f][i][0]), np.array(W[f][i][1])) for f in range(c.N)]; GL = [(np.array(W[f][il][0]), np.array(W[f][il][1])) for f in range(c.N)]
    mg = dict(mg, hits=mg.get('hits', []) + left_hits(c, mg['release'])); spec['_mag'] = mg     # the left gun is solid for every draft
    track = inertia.simulate_mag(gid, CLIP, G, mg, {'left': inertia.GunPath(GL)})
    return spec, track, G


def build(pick, take, side='right', body='pma', out=None, quiet=False):
    gid = GUNS[take]; out = out or OUT + '/clips'; d = f'{out}/{body}'; os.makedirs(d, exist_ok=True); name = stem(pick, take, side); S = side.capitalize()
    c, tl, m, sim, Pt, Rt = compose(pick, take, side, body)
    spec, track, G = author_and_track(c, tl, m, sim, Pt, Rt, pick, take, name, d, S)
    if m.get('bat'):          # more passes: swing the gun's underside through where the free magazine will be; first hit wins
        fs = track['free_from']; best = None
        for after, bias in ((1, (-0.03, 0.0, 0.06)), (1, (-0.02, -0.02, 0.06)), (2, (-0.03, 0.0, 0.08)), (2, (-0.02, -0.02, 0.06)), (1, (0.0, -0.04, 0.04))):
            fb, pb, rb = aim_bat(c, track, G, m, after, bias)
            c2, tl2, m2, sim2, Pt2, Rt2 = compose(pick, take, side, body, {'_bat': (fb, pb, rb, fs)})
            r2 = author_and_track(c2, tl2, m2, sim2, Pt2, Rt2, pick, take, name, d, S)
            hit = any(b['body'] == 'gun' for b in r2[1]['phys']['bounces'])
            if not quiet: print('   bat try', after, bias, 'hit', hit, flush=True)
            if hit or best is None: best = (c2, tl2, m2, sim2, Pt2, Rt2) + tuple(r2)
            if hit: break
        c, tl, m, sim, Pt, Rt, spec, track, G = best
    lb = [b for b in track['phys']['bounces'] if b['body'] == 'left']
    if lb:                    # the left gun takes the knock: magazine about 0.5 kg against gun and forearm about 4 kg
        J = np.array(lb[0]['impulse']) * -0.125; f = int(round(lb[0]['t']))
        sh = [{'type': 'kick', 'f': f, 'move': [float(x) for x in J * 0.7], 'rot': [float(-J[1] * 300), 0.0, float(J[0] * 300)], 'attack': 0.5, 'release': 2.5, 'lag': 0.6}]
        spec, track, G = author_and_track(c, tl, m, sim, Pt, Rt, pick, take, name, d, S, left_shakes=sh)
    spec['_track'] = f'{d}/{name}_track.json'
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); o['elbow_step_deg'] = elbow_step(spec)
    gs = inertia.gun_stats(sim, tl.marks); ms = inertia.mag_stats(gid, CLIP, track, G)
    hit = [e for e in gs['impacts'] if e['name'] != 'seat' and e['f'] >= m['mag']['release'] - 1]
    if m.get('thrown') and hit:          # the window of frames misses the speed just before the hit; the contact has it
        ms['gun_cm_f'] = round(max(ms['gun_cm_f'], hit[0]['impact_cm_f']), 2); ms['ratio'] = round(ms['exit_cm_f'] / ms['gun_cm_f'], 2); ms['gun_from'] = 'contact'
    o['mag_speed'] = ms; o['mag_gone_height_m'] = gone_height(gid, track, G); release_dv(o, track, G); bounce_hang(o, track, G)
    if m.get('thrown') and (ms['ratio'] is None or not MAG_RATIO[0] <= ms['ratio'] <= MAG_RATIO[1]):
        o['fails'].append(f"thrown magazine {ms['exit_cm_f']} cm/f against the gun's {ms['gun_cm_f']} (ratio {ms['ratio']})")
    if o['mag_gone_height_m'] is not None and o['mag_gone_height_m'] > 0.09: o['fails'].append(f"old magazine removed {o['mag_gone_height_m']} m above the ground")
    if ms['clear_cm'] is not None and ms['clear_cm'] < 0.3: o['fails'].append(f"free magazine {ms['clear_cm']} cm from the gun (through it)")
    if track['phys']['free_t'] is None: o['fails'].append('magazine never leaves the well')
    if m.get('bat') and not any(b['body'] == 'gun' for b in track['phys']['bounces']): o['fails'].append('bat misses the magazine')
    if m.get('hit_left') and not lb and not m.get('hit_optional'): o['fails'].append('magazine misses the left gun')
    o['inertia'] = {'gun': gs, 'mag': ms, 'bounces': track['phys']['bounces']}
    json.dump({'gun': gs, 'mag': ms, 'bounces': track['phys']['bounces'], 'model': sim['model']}, open(f'{d}/{name}_inertia.json', 'w'), indent=1)
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet:
        print(body, rgate.line(o), '| elbow', o['elbow_step_deg'], flush=True)
        print('   gun: over', gs['overshoot_cm_max'], 'cm', gs['overshoot_deg_max'], 'deg reb', gs['rebound_cm_max'], 'settle', gs['settle_f_max'], 'rotlag', gs['rot_lag_f'],
              'trail', gs['muzzle_trail_deg'], 'impacts', [(e['f'], e['impact_cm_f']) for e in gs['impacts']], flush=True)
        print('   mag:', ms, 'free', track['phys']['free_t'], 'gone', track['gone'], 'dir', track['phys']['exit_dir'],
              'bounces', [(b['body'], b['t'], b['in_cm_f'], b['speed_after']) for b in track['phys']['bounces']], flush=True)
    return spec, o


def aim_bat(c, track, G, m, after=2, bias=(-0.02, -0.02, 0.06)):
    """Frame and gun pose for the bat: a few frames after the magazine is free, the gun's underside pad (gun axes) is
    put where the magazine's centre will be; returns (frame, grip offset, angles)."""
    P = c.P; v = c.v; cen = np.r_[v['centre'], 1]; ff = track['free_from']; fb = min(ff + after, len(G) - 1)
    M = magtrack2.m4(*G[fb]) @ np.array(track['frames'][fb]['m']).reshape(4, 4); mc = (M @ cen)[:3]
    rb = np.array(P.get('bat_rot', (-4, 0, 35)), float); q = author.qmul(c.q0, author.qeuler(*rb)); pad = np.array(m['mag']['hits'][0]['p'])
    pb = mc - qrot(q, pad) - c.g0 + np.array(bias)
    return fb, [float(x) for x in pb], [float(x) for x in rb]


def bounce_hang(o, track, G):
    """rgate counts a frame as hanging when the magazine's acceleration is not gravity; at a bounce it is the hit.
    Recount without the frames next to a bounce (a bounce is listed in bounces with its impulse)."""
    B = [b['t'] for b in track['phys']['bounces']]
    if not B or not o['mag_hang']: return
    v = magtrack2.vanilla(o['gun'], CLIP); cen = np.r_[v['centre'], 1]; N = len(G); g0 = magtrack2.G_ACC
    C = np.array([(magtrack2.m4(*G[f]) @ np.array(track['frames'][f]['m']).reshape(4, 4) @ cen)[:3] for f in range(N)])
    st = [x['state'] for x in track['frames']]; ff, gone = track['free_from'], track['gone']; hang = []
    for f in range(1, N - 1):
        if st[f] != 'falling' or f in (ff, gone - 1) or C[f][1] <= 0.15 or any(abs(f - t) <= 1.01 for t in B): continue
        if st[f + 1] != 'falling' or st[f - 1] not in ('falling', 'guided'): continue
        a = C[f + 1] - 2 * C[f] + C[f - 1]
        if abs(a[1] + g0) > 0.25 * g0 or np.linalg.norm(a[[0, 2]]) > 0.25 * g0: hang.append(f)
    o['mag_hang_rgate'] = o['mag_hang']; o['mag_hang'] = len(hang); o['fails'] = [x for x in o['fails'] if not x.startswith('magazine hangs')]
    if hang: o['fails'].append(f'magazine hangs {len(hang)} f')


def table(ids):
    """measure/gate_round4.md and measure/inertia_round4.md (+ .json): gate numbers and the inertia model's numbers per take."""
    d = OUT + '/clips/pma'; G = ['| take | release | loading | fails | start/end cm | end step cm | hidden | eye cm | cover % | wrist / in view | reach | shoulder cm | body cm | guns gap cm | hang | release dv cm/f (rgate) | exit / gun cm/f (ratio) | lands (next-frame m) | exit / insert off axis cm |',
                                 '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    I = ['| take | stops (f: overshoot cm / deg, rebound cm, settle f) | max overshoot cm / deg | rebound cm | settle f | rotation lag f | muzzle trail deg | body contacts (f: in cm/f) | seat in / out cm/f | slide f | exit cm/f | spin deg/f | pull along the well (gravity, gun linear, gun turning) g | bounces |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    J = {}
    for p in ids:
        for t in 'AB':
            n = stem(p, t); gp = f'{d}/{n}_gate.json'
            if not os.path.exists(gp): continue
            o = json.load(open(gp)); L = o['layout']; ms = o['mag_speed']; inn = o['inertia']; gs = inn['gun']; J[p + t] = {'gate': {k: v for k, v in o.items() if k != 'inertia'}, 'inertia': inn}
            G.append(f"| {p}{t} | {RELEASE[p]} | {LOAD[p]} | {'pass' if not o['fails'] else '; '.join(o['fails'])} | {max(o['start_cm'], o['end_cm'])} | {o['end_step_cm']} | f{L['hide_start']}-{L['hide_end']} | {o['eye_cm'][0]} | {o['cover_peak'][0]} | "
                     f"{o['wrist'][0]} / {o['wrist_view']} | {o['reach'][0]} | {o['shoulder_pull_cm']} | {o['body_cm'][0]} | {o['guns_gap_cm'][0]} | {o['mag_hang']} | {o['release_dv_cm_f']} ({o.get('release_dv_rgate_cm_f')}) | "
                     f"{ms['exit_cm_f']} / {ms['gun_cm_f']} ({ms['ratio']}) | {o['mag_gone_height_m']} | {o['exit_off_axis_cm']} / {o['insert_off_axis_cm']} |")
            for r in gs['stops']:
                if r['overshoot_cm'] <= 0.2: r['rebound_cm'] = 0.0          # builds before the fix counted lag as rebound
            gs['rebound_cm_max'] = round(max([r['rebound_cm'] for r in gs['stops']] or [0]), 2)
            st = '; '.join(f"f{r['f']}: {r['overshoot_cm']} / {r['overshoot_deg']}, {r['rebound_cm']}, {r['settle_f']}" for r in gs['stops'])
            body = ', '.join(f"{e['name']} f{e['f']}: {e['impact_cm_f']}" for e in gs['impacts'] if e['name'] != 'seat' and e['impact_cm_f'] > 2)
            seat = [e for e in gs['impacts'] if e['name'] == 'seat']; pg = ms['pull_g']
            bo = ', '.join(f"{b['body']} f{b['t']}: {b['in_cm_f']} in, {b['speed_after']} after" for b in inn['bounces'])
            I.append(f"| {p}{t} | {st} | {gs['overshoot_cm_max']} / {gs['overshoot_deg_max']} | {gs['rebound_cm_max']} | {gs['settle_f_max']} | {gs['rot_lag_f']} | {gs['muzzle_trail_deg']} | {body or '-'} | "
                     f"{(str(seat[0]['impact_cm_f']) + ' / ' + str(seat[0]['rebound_cm_f'])) if seat else '-'} | {ms['slide_f']} | {ms['exit_cm_f']} | {ms['spin_deg_f']} | {pg['gravity']}, {pg['gun_linear']}, {pg['gun_turning']} | {bo or '-'} |")
    os.makedirs(OUT + '/measure', exist_ok=True)
    open(OUT + '/measure/gate_round4.md', 'w', encoding='utf-8').write('\n'.join(G) + '\n'); open(OUT + '/measure/inertia_round4.md', 'w', encoding='utf-8').write('\n'.join(I) + '\n')
    json.dump(J, open(OUT + '/measure/gate_inertia_round4.json', 'w'), indent=1); print('\n'.join(G)); print('\n'.join(I))


def stats(ids):
    import motionstats
    rows = []; Jr = json.load(open(OUT + '/ref/motion_all.json')); rows += [(k, v) for k, v in Jr.items() if k.startswith('APPROVED')]
    R2 = common.mp('C:/Modding/anim-work/smg-shotgun/round2-front/clips/pma')
    for t in ('A', 'B'): rows.append((f'SF13{t} Low chop, pick 1 (round 2)', motionstats.stats(f'{R2}/{stem("SF13", t)}.glb', 'reload_draft', 'Right', 0.55 if t == 'A' else 0.6)))
    for p in ids:
        for t in ('A', 'B'):
            g = f'{OUT}/clips/pma/{stem(p, t)}.glb'
            if os.path.exists(g): rows.append((f'{p}{t} {PICKS[p][0]} ({GUNS[t]})', motionstats.stats(g, 'reload_draft', 'Right', 0.55 if t == 'A' else 0.6)))
    Tb = ['| clip | frames | peak cm/f | peak at | stop | jerks | still | whip | muzzle peak | big moves |', '|---|---|---|---|---|---|---|---|---|---|']
    for lab, s in rows: Tb.append(f"| {lab} | {s['frames']} | {s['peak_speed']} | {s['peak_at']} | {s['stop']} | {s['jerk_events']} | {int(s['hold_share'] * 100)} % | {s['whip']} | {s['peak_muzzle_speed']} | {s['big_moves']} |")
    os.makedirs(OUT + '/measure', exist_ok=True); open(OUT + '/measure/motion_round4.md', 'w').write('\n'.join(Tb) + '\n'); print('\n'.join(Tb))
    json.dump({l: s for l, s in rows}, open(OUT + '/measure/motion_round4.json', 'w')); motionstats.plot(rows, OUT + '/measure/motion_round4.png')


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cmd = argv[0] if argv else 'list'
    takes = (o('--takes') or 'A,B').split(','); jobs = int(o('--jobs') or 1)
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(PICKS)
    if cmd == 'list':
        for p, (n, fn) in PICKS.items(): print(p, n, '|', DOC[p])
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
    elif cmd == 'table': table(ids)
    else: raise SystemExit(__doc__)
