"""TUBE round 2: the owner's three picks (TU01 throw and meet, TU10 saddle flick, TU02 belt-row sweep) shortened so the
visible opening (first frame to hide start) fits the game's reload time on the Carnage and the Tactician.

Rule (GorillaAkimbo.reds, OnEnter): a pick falls back to the quick drop when hide_start / 30 / (0.75 x reload time)
is above 1.15. Max hide start, frames: Carnage 0.75 / 1.5 s: 19 / 38 (Body 10: 14 / 29, Body 20: 12 / 24);
Tactician 0.43 / 0.8 s: 11 / 20 (Body 10: 8 / 15, Body 20: 6 / 12). The rise after the hidden window plays at speed 1.

What changes against round 1: the opening is one move (a lunge forward and down: the loose fore-end lags open under
the forward acceleration, the spent shell is kicked out in view, the gun keeps going down out of view); the tube is
filled out of view; the pick's own way of loading moves onto the rise, in view (TU21: a belt rig throws a shell and the
rising port meets it; TU22: the rise stops dead, the saddle shell flies up off the gun and is caught in the open
ejection port; TU23: the sweep along the belt row out of view, gravity close on the rise as before).

usage: tube2.py build [--guns ..] [--picks TU21,..] [--sides ..] [--bodies ..] | layout | fit
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import tube1, tubeprod, timing, phys, prod
from tube1 import go, place, station, port_c, gun_vec, q_of, press, settle
from fk import qrot

SRC = {'TU21': 'TU01', 'TU22': 'TU10', 'TU23': 'TU02'}
BUD = {'TU21': {'open': 4, 'first_in': 16, 'seat': 17, 'home': 0, 'frames': 0},
       'TU22': {'open': 4, 'first_in': 16, 'seat': 17, 'home': 0, 'frames': 0},
       'TU23': {'open': 4, 'first_in': 16, 'seat': 20, 'home': 0, 'frames': 0}}
import math
YANK = (0.0, -0.12 * math.sin(math.radians(50)), 0.12 * math.cos(math.radians(50)))      # 12 cm back and down along a muzzle-up barrel
DIVE = {'carnage': 11, 'tactician': 10}      # the dive's last frame: Carnage hidden by f12, Tactician by f11
RISE_END = 12                    # arrival in the idle to the last frame: the gun settles on its spring, inertia end blend 8


def lunge(c, tl):
    """The gun is yanked back along the barrel (muzzle up 30 deg, so the yank also goes down) and stopped dead on f3:
    the loose fore-end carries on back to its rear stop (open on f6), the spent shell is kicked out in view."""
    P = c.P; f = P.get('lunge_f', 3); tl.to(f, P.get('lunge', YANK), P.get('lunge_rot', (30, 0, -2)), P.get('lunge_prof', 'slam')); tl.mark('open', f)


def dive_press(c, tl, X, rot, approach=0.06, depth=0.065):
    """Straight from the yank down to a rig (no hold): the loading port lands above the shell at X on the dive frame
    and is pushed down onto it 3 frames later."""
    X = np.asarray(X, float) + np.array(c.P.get('rig_off', (0.0, 0.0, 0.0))); o = place(c, X, rot, port_c()); f = c.P.get('dive_f', DIVE[c.gun]); tl.hold(c.P.get('dive_start', 5))
    tl.to(f, o + gun_vec(c, rot, (0, approach + depth * 0.5, 0)), rot, c.P.get('dive_prof', 'drive')); tl.to(f + 3, o + gun_vec(c, rot, (0, -0.004, 0)), rot, 'slam')
    return ('press', f, f + 3)


RISE_N = 5                       # frames of the last rise into the idle


def rise_close(c, tl, h):
    """The close is the rise itself: from the loading pose the gun goes to a low pose with the muzzle up (the fore-end
    still held at its rear stop by friction), then rises straight into the idle, levelling as it comes: the hold lets
    go as the rise starts, the upward and forward deceleration into the idle drives the loose fore-end along the
    barrel toward the muzzle and it runs home as the gun arrives; the gun then settles on its spring."""
    P = c.P; n = P.get('rise_n', RISE_N); pre = P.get('pre', (0.0, -0.17, 0.05)); prot = P.get('pre_rot', (28, 0, -3))
    if pre is None: n = P.get('rise_n', 8); tl.hold(h - n)          # one continuous rise from the rig into the idle
    else: go(c, tl, h - n, pre, prot, 'drive')
    tl.mark('rack_start', h - n); tl.to(h, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), P.get('rise_prof', (2.0, 1.3))); tl.mark('hit', h); tl.hold(c.N - 1)


def t21(c, tl):
    """Throw and meet, short. Lunge open. The tube is filled at the belt out of view. On the rise a spring rig on the
    belt throws a shell up in an arc and the rising gun meets it in the air with the loading port, in view; up, and a
    punch that stops dead throws the fore-end home."""
    lunge(c, tl); bx, br = station(c, 'belt'); loads = [dive_press(c, tl, bx, br)]; tl.hold(tl.f + c.P.get('hold', 4))
    mr = (4, -6, -4); hm = c.P.get('meet_f', MEET[c.gun]); m = place(c, bx + np.array(c.P.get('meet_off', (0.02, 0.36, -0.22))), mr, port_c())
    go(c, tl, hm, m, mr, 'rise'); loads.append(('toss', hm - c.P.get('flight', 7), hm)); tl.hold(hm + 1)
    h = hm + 4 + RISE_N; rise_close(c, tl, h)
    return {'loads': loads, 'home': h}


def t22(c, tl):
    """Saddle flick, short. Yank open. The tube is filled at the hip caddy out of view. Up into view and held, then a
    short upward flick that stops dead: the shell in the side saddle flies on up off the gun (the gun's speed at the
    stop), the gun is brought under it and catches it in the open ejection port as it falls; a punch that stops dead
    closes the pump on it."""
    lunge(c, tl); hx, hr = station(c, 'hip'); loads = [dive_press(c, tl, hx, hr)]; tl.hold(c.P.get('rise_start', 20))
    r0 = (0, 0, -6); up = np.array(c.P.get('flick_to', (0.0, -0.05, 0.0))); hf = T22[c.gun]['flick']; fl = c.P.get('flight', 6)
    tl.to(hf - 4, up + np.array([0.0, -0.10, 0.01]), r0, 'rise'); tl.hold(hf - 3); tl.to(hf, up, r0, 'slam'); tl.mark('flick', hf)
    fc = hf + fl; q = q_of(c, r0); S = tube1.SADDLE; SC = tube1.SC; CH = tube1.CH
    c1 = c.g0 + up + qrot(q, (S @ np.r_[SC, 1])[:3]); c0 = c.g0 + tl.P[hf - 1] + qrot(q, (S @ np.r_[SC, 1])[:3]); v = c1 - c0; n = fc - hf
    pc = np.array(c.P.get('catch_pc', c1 + v * n + np.array([0, -phys.G_ACC, 0]) * n * (n + 1) / 2)); fr = c.P.get('release_f', hf)
    cp = place(c, pc, r0, (CH @ np.r_[SC, 1])[:3]); tl.to(fc, cp, r0, 'drive'); tl.hold(fc + 1); tl.mark('catch', fc)
    tube1.SADDLE_WIN = (hf - 3, hf + 3, fc); loads.append(('saddle', fr, fc))
    h = fc + 4 + RISE_N; [c.P.setdefault(k, v) for k, v in (('pre', (0.0, -0.12, 0.12)), ('rise_n', 6), ('rise_prof', (1.8, 2.2)))]; rise_close(c, tl, h)
    return {'loads': loads, 'home': h}


def t23(c, tl):
    """Belt-row sweep, short. Lunge open. The gun dives to a row of shells along the belt and sweeps along it in one
    pass, the port taking a shell each time it crosses one (out of view). Up, the muzzle tipped down: the fore-end
    slides home by its weight."""
    lunge(c, tl); bx, br = station(c, 'belt'); loads = []; sw = np.array([-0.07, 0.0, 0.0])
    d = c.P.get('dive_f', DIVE[c.gun]); o0 = place(c, bx - sw, br, port_c()) + gun_vec(c, br, (0, 0.01, 0)); tl.hold(c.P.get('dive_start', 5)); tl.to(d, o0 + gun_vec(c, br, (0, 0.07, 0)), br, c.P.get('dive_prof', 'drive')); tl.to(d + 2, o0, br, 'heavy')
    for k in range(3): loads.append(('sweep', d + 2 + 3 * k, bx - sw + sw * k))
    tl.to(d + 9, o0 + sw * 2, br, (1.6, 1.6)); tl.hold(d + 10)
    h = tube1.BUDGET['home']; [c.P.setdefault(k, v) for k, v in (('pre', None), ('rise_n', 9), ('rise_prof', (1.8, 2.2)))]; rise_close(c, tl, h)
    return {'loads': loads, 'home': h}


FUN = {'TU21': ('Throw and meet, short', t21), 'TU22': ('Saddle flick, short', t22), 'TU23': ('Belt-row sweep, short', t23)}
MEET = {'carnage': 28, 'tactician': 27}       # TU21: the rising port meets the thrown shell (Carnage a frame later: its longer gun shows sooner)
T22 = {'carnage': {'flick': 31}, 'tactician': {'flick': 31}}
HOME = {'TU21': lambda g: MEET[g] + 4 + RISE_N, 'TU22': lambda g: T22[g]['flick'] + 6 + 4 + RISE_N, 'TU23': lambda g: 34}       # arrival in the idle (clip length: + RISE_END)
PARAMS = {('TU22', 'carnage', 'pwa'): {'rig_off': (0.0, -0.03, 0.0)}}      # female V: her forearm stayed in view at f12 on the way to the hip caddy (hide f13): caddy 3 cm lower


def use(pick, gid):
    h = HOME[pick](gid); B = dict(BUD[pick], home=h, frames=h + RISE_END); tube1.BUDGET = B
    timing._cache.pop((gid, 'empty_reload'), None); timing._cache.pop((tube1.GID, 'empty_reload'), None)


for k, (n, fn) in FUN.items(): tube1.PICKS[k] = (n, fn); tube1.DOC[k] = ' '.join((fn.__doc__ or '').split())
tubeprod.SLOTS = list(FUN); tubeprod.OUT = renv.OUT + '/clips'
GUNS, CLIP, SLOTS, OUT, stem, plan, use_gun = tubeprod.GUNS, tubeprod.CLIP, tubeprod.SLOTS, tubeprod.OUT, tubeprod.stem, tubeprod.plan, tubeprod.use_gun      # for prodsheet.py
_build = tubeprod.build


def build(gid, pick, side, body, quiet=False, extra=None):
    tubeprod.use_gun(gid); use(pick, gid)
    for key in ((pick, gid), (pick, gid, body), (pick, gid, side)): tubeprod.PARAMS[key] = PARAMS.get(key, {})
    spec, o = _build(gid, pick, side, body, quiet, extra)
    if True:      # every build: the pump gate
        o['pump_motion'] = pc = pump_check(spec); o['fails'] += pc['fails']
        d = f"{tubeprod.OUT}/{body}"; json.dump(o, open(f"{d}/{tubeprod.stem(gid, side, pick)}_gate.json", 'w'), indent=1)
        if not quiet: print('   pump check', {k: v for k, v in pc.items() if k != 'per_frame'}, flush=True)
    return spec, o
tubeprod.build = build


# ------------------------------------------------------------------------------------------------ pump gate
JUMP_MAX = 0.06                       # m per frame: the fastest the fore-end runs in these clips is about 4.3 cm/f
def pump_check(spec):
    """The fore-end must move only by the slider physics: no frame-to-frame jump above JUMP_MAX, and every change of its
    velocity explained by the gun's acceleration and gravity along the stroke (1.5x margin plus 0.3 cm), or by a stop
    (it arrives at or leaves 0 or the full stroke) or by the friction hold (zero velocity at the rear stop). The gun
    anim frame that poses it must follow the stroke monotonically."""
    from glb import Glb
    from fk import Clip
    S = spec['_side']; g = Glb(spec['out']); cl = Clip(g, spec['clip']); i = g.names.index('Weapon' + S); N = spec['frames']
    GW = phys.worlds([(np.array(cl.world(f)[i][0]), np.array(cl.world(f)[i][1])) for f in range(N)])
    s = np.array(spec['_pump_cm']) / 100.0; pf = np.array(spec['_part_frames']); PM = s.max(); u = np.array([0.0, 0.0, 1.0]); fails = []; worst = 0.0; worst_f = None
    jump = np.abs(np.diff(s)); jf = int(np.argmax(jump))
    if jump.max() > JUMP_MAX: fails.append(f'pump jumps {jump.max() * 100:.1f} cm at f{jf}')
    at = lambda x: x < 2e-4 or x > PM - 2e-4
    for f in range(1, N - 1):
        dd = s[f + 1] - 2 * s[f] + s[f - 1]
        if at(s[f - 1]) or at(s[f]) or at(s[f + 1]): continue
        a = max(abs(float((phys.GV - phys.point_acc(GW, k, tube1.PUMP_P + u * s[f])) @ (GW[k][:3, :3] @ u))) for k in (f, min(f + 1, N - 1)))
        ex = abs(dd) - (1.5 * a + 0.003)
        if ex > worst: worst, worst_f = ex, f
    if worst > 0: fails.append(f'pump velocity changes {worst * 100:.2f} cm/f more than the physics allows at f{worst_f}')
    order = np.argsort(s, kind='stable'); mono = all(pf[order[k + 1]] >= pf[order[k]] - 1e-6 for k in range(N - 1))
    if not mono: fails.append('gun anim frame of the pump not monotone in its travel')
    # overlap: pump travel only while the gun moves; at rest (speed under 0.3 cm/f and axial acceleration under 0.15 cm/f2) at most 1 cm in all
    gp = np.array([M[:3, 3] for M in GW]); sp = np.r_[0.0, np.linalg.norm(np.diff(gp, axis=0), axis=1)]
    ax = np.array([abs(float((phys.GV * 0 - phys.point_acc(GW, f, tube1.PUMP_P)) @ (GW[f][:3, :3] @ u))) for f in range(N)])
    ds = np.r_[0.0, np.abs(np.diff(s))]; rest = (sp < 0.003) & (ax < 0.0015); at_rest_cm = float(ds[rest].sum()) * 100
    if at_rest_cm > 1.0: fails.append(f'pump travels {at_rest_cm:.1f} cm while the gun is at rest')
    mv = lambda a, b: [f for f in range(a, b) if sp[f] >= 0.003]
    full = [f for f in range(N) if s[f] >= PM - 2e-4]; o0 = next((f for f in range(N) if s[f] > 0.001), None); o1 = full[0] if full else None
    c0 = (full[-1] + 1) if full else None; c1 = next((f for f in range(c0 or N, N) if s[f] <= 1e-4), None) if c0 else None
    rk = int(spec['_marks'].get('rack_start', 0)); arr = next((f for f in range(int(spec['_marks'].get('hit', rk)), N) if sp[f] < 0.003), None)
    yk = mv(0, 12); stroke = {'open': [o0, o1], 'yank_moving': [yk[0], yk[-1]] if yk else None, 'close': [c0, c1], 'rise': [rk, spec['_marks'].get('hit')], 'gun_at_rest_from': arr, 'travel_at_rest_cm': round(at_rest_cm, 2)}
    return {'stroke': stroke, 'max_jump_cm_f': round(float(jump.max()) * 100, 2), 'max_jump_f': jf, 'unexplained_accel_cm': round(worst * 100, 3), 'unexplained_f': worst_f, 'frame_map_monotone': mono, 'fails': fails}


# ------------------------------------------------------------------------------------------------ fit
LIMITS = {'carnage': (0.75, 1.5), 'tactician': (0.43, 0.8)}
BODY = {'base': 1.0, 'Body 10': 1.3, 'Body 20': 1.6}


def rate(hide_start, T, mult): return hide_start / 30.0 / (0.75 * T / mult)


def fit_rows(lay):
    rows = []
    for gid in lay:
        one, emp = LIMITS[gid]
        for pk in lay[gid]:
            hs = lay[gid][pk]['empty_reload']['hide_start']
            r = {'gun': gid, 'pick': pk, 'hide_start': hs, 'length': lay[gid][pk]['empty_reload']['length'], 'hide_end': lay[gid][pk]['empty_reload']['hide_end']}
            for b, m in BODY.items(): r[b] = [round(rate(hs, one, m), 2), round(rate(hs, emp, m), 2)]
            rows.append(r)
    return rows


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None; cmd = argv[0] if argv else 'build'
    if cmd == 'build':
        for p in tubeprod.plan(cs(o('--guns')), cs(o('--picks')), cs(o('--sides')), cs(o('--bodies'))): build(*p)
    elif cmd == 'layout': tubeprod.layout()
    elif cmd == 'fit':
        lay = json.load(open(tubeprod.OUT + '/layout_tube.json'))
        for r in fit_rows(lay): print(r)
    else: raise SystemExit(__doc__)
