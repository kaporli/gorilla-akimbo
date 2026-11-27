"""Carnage per-shot flick-cock (pshot, owner reference video Dsmzmy7mZEM): after each shot the gun is flicked up to near
vertical, the pump cycles by the flick's momentum, a shell ejects at the pump's rear stroke, the gun swings back down.
One-handed, per hand and body, 31 frames at 30 fps (1.03 s, inside the Carnage cycle time 1.06 s: never slower firing).

Method: tube1's machinery. The hand follows a timeline (rlib2 moves), the gun is a spring-damper mass on it
(inertia_r1.spring), the pump fore-end is a loose slider along the gun (phys.slider) driven only by the gun's own
accelerations and gravity (no kinematic drive), the spent shell rides the bolt and leaves the port past 6 cm
(tube1.shell_tracks) with the ejector's kick; the left hand is authored as a right hand in the mirror image
(prod.Ctx) and the ejector kick is mirrored (the casing leaves to the left).
Gates: the clip's own (rgate minus the reload-only hidden-window rules), R10 arm speeds, R12-style speed caps, pump
opens once and closes once, spent shell leaves and lands, end transition into the idle, the cycle fits 31 frames.
usage: flickprod.py build [--sides ..] [--bodies ..] [--pick FC01]
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, prod, rgate, phys, rarmset
import inertia_r1 as inertia
import tube1, tubeprod
from rlib import K
from glb import Glb
from fk import Clip

OUT = renv.OUT + '/flick'
N_FRAMES = 31
TAKE = 'A'
MIR = np.array([-1.0, 1.0, 1.0])
EJECT0 = tube1.EJECT.copy()
PARAMS = {}


def fc01(c, tl, P=None):
    """Flick up, pump cycles, swing down. Wind-up dip (3 f), snap up to 78 deg muzzle-up (peak f9), the stop throws the
    fore-end back and the ejector kicks the shell out, the arm brings the gun down on a slight overshoot, settle."""
    P = c.P; up = P.get('up', 72); lift = P.get('lift', 0.08); fwd = P.get('fwd', 0.05); f_peak = P.get('f_peak', 9); f_hold = P.get('f_hold', 14); f_down = P.get('f_down', 22)
    wd = P.get('wind', 1.0)
    if wd > 0: tl.hold(1); tl.to(4, (0.0, -0.012 * wd, -0.02 * wd), (-3 * wd, 0, 0), 'ease'); tl.mark('windup', 4)
    else: tl.hold(5)
    tl.to(f_peak, (0.0, lift, fwd), (up, 0, 0), 'snap'); tl.mark('flick', f_peak)
    tl.hold(f_hold)       # near vertical: the fore-end that ran on at the stop slides home under gravity
    tl.to(f_down, (0.0, -0.01, 0.0), (-4, 0, 0), 'drive'); tl.mark('down', f_down)
    e = c.N - 5
    tl.hold(f_down + 1); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')
    return {'loads': []}


PICKS = {'FC01': ('Flick cock', fc01)}


def setup():
    T = {'gun': 'carnage', 'clip': 'empty_reload', 'frames': N_FRAMES, 'out': 8, 'clear': None, 'far': None, 'near': N_FRAMES - 4, 'seated': N_FRAMES - 4,
         'exit_dir': [0, 1, 0], 'exit_speed_cm_f': 0, 'in_dir': [0, 1, 0], 'slot': [0, 0, 0], 'parts': {}, 'handle': [N_FRAMES - 4, N_FRAMES - 4], '_tube': True, '_flick': True}
    tube1.BUDGET.update({'open': 8, 'first_in': 99, 'seat': N_FRAMES - 4, 'home': N_FRAMES - 6, 'frames': N_FRAMES}); T['budget'] = dict(tube1.BUDGET)
    import timing, magtrack2
    timing._cache[('carnage', 'empty_reload')] = T
    magtrack2._van[('carnage', 'empty_reload')] = {'M': [tube1.CH], 'seat': tube1.CH, 'centre': tube1.SC, 'exit': np.array([0, 1.0, 0]), 'enter': np.array([0, -1.0, 0]), 'dist': np.zeros(2), 'out': 0, 'seated': 1}
    return T


def stem(side, pick='FC01'): return f'carnage_{side}_{pick}A_cycle'


def build(side, body, pick='FC01', quiet=False, extra=None):
    gid = 'carnage'; tubeprod.use_gun(gid); T = setup(); S = side.capitalize(); O = 'Left' if S == 'Right' else 'Right'
    d = f'{OUT}/{body}'; os.makedirs(d, exist_ok=True); name = stem(side, pick)
    P = dict(prod.TAKES['A'], drag=0.0, lag=0); P.update(PARAMS.get(pick, {})); P.update(extra or {})
    c = prod.Ctx(gid, body, 'empty_reload', P, S); c.side = S; tl = tube1.TL(c, 0, 0.0)
    plan = PICKS[pick][1](c, tl)
    Pt, Rt = tl.P.copy(), tl.R.copy(); Pt[-1] = 0; Rt[-1] = 0; Ps, Rs = inertia.spring(Pt, Rt, 'A'); rep = inertia.report(Ps, Rs, Pt, Rt, tl.stops)
    if S == 'Left': Ps = Ps * prod.MIR_P; Rs = Rs * prod.MIR_R
    keys = [K(f, Ps[f], Rs[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take A', '_doc': ' '.join((PICKS[pick][1].__doc__ or '').split()), '_gun': gid, '_left_gun': gid, '_body': body, '_side': S,
            '_gun_clip': 'empty_reload', '_pick': pick, '_take': TAKE, '_timing': T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_two_arm': False,
            '_round': 'flick-cock', 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, O: [K(0)]}, 'shakes': {S: []},
            'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb', '_inertia': rep}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); W = [cl.world(f) for f in range(c.N)]; i, io = g.names.index('Weapon' + S), g.names.index('Weapon' + O)
    G = [(np.array(W[f][i][0]), np.array(W[f][i][1])) for f in range(c.N)]; GW = phys.worlds(G)
    PM = tube1.PUMP_MAX
    s, hit = phys.slider(GW, tube1.PUMP_P, tube1.PUMP_U, PM, drives=[], lock_home_after=N_FRAMES - 4, rest=0.1)
    s = np.where(np.arange(c.N) > c.N - 3, 0.0, s)
    tube1.EJECT = EJECT0 * (MIR if S == 'Left' else 1.0)      # the casing leaves to the gun's left for the left hand
    objs, info = tube1.shell_tracks(c, GW, plan, s, hit); tube1.EJECT = EJECT0
    spec['_part_frames'] = tube1.pump_frames(s); spec['_pump_cm'] = [round(float(x) * 100, 3) for x in s]
    inv = [np.linalg.inv(M) for M in GW]; J = {'joints': {}, 'names': []}
    for nm, Wo in objs: J['names'].append(nm); J['joints'][nm] = [None if M is None else [round(float(x), 9) for x in (inv[f] @ M).ravel()] for f, M in enumerate(Wo)]
    spec['_objects'] = f'{d}/{name}_objects.json'; json.dump(J, open(spec['_objects'], 'w'))
    CH = tube1.CH; dummy = {'frames': [{'m': [round(float(x), 6) for x in CH.ravel()], 's': 0.0, 'state': 'seated'}] * c.N, 'release': 1, 'free_from': 2, 'gone': c.N, 'exit_gun_axes': [0, 1, 0], 'enter_gun_axes': [0, -1, 0], 'plan': {'mode': 'none'}}
    spec['_track'] = f'{d}/{name}_track.json'; json.dump(dummy, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, dummy); o['fails'] = [f for f in o['fails'] if 'hidden' not in f and 'hide' not in f]       # a flick has no hidden window
    o['pump'] = {'open_frame': next((f for f in range(c.N) if s[f] >= 0.02), None), 'max_cm': round(float(s.max()) * 100, 2), 'hit_frame': hit, 'travel_frames': int((s > 0.002).sum())}
    import breakphys as bp
    hs = bp.hinge_stats([x * 100 / 8.5 * 60 / 100 * 100 for x in s]) if False else None
    ups = int(sum(1 for f in range(1, c.N) if s[f] > 0.02 and s[f - 1] <= 0.02)); o['pump']['opens'] = ups
    if o['pump']['open_frame'] is None: o['fails'].append('pump never opens')
    if ups != 1: o['fails'].append(f'pump opens {ups} times')
    if s[c.N - 4] > 0.002: o['fails'].append('pump not home at the end')
    if info.get('spent_release') is None: o['fails'].append('spent shell never leaves')
    elif info.get('spent_land') is None: o['fails'].append('spent shell does not land')
    o['shells'] = info; o['elbow_step_deg'] = tubeprod.prod_elbow(spec)
    if o['elbow_step_deg'] > 45: o['fails'].append(f"elbow swings {o['elbow_step_deg']} deg in one frame")
    o['end_transition'] = et = tubeprod.end_transition(spec)
    if et['last3_step_cm'] > 0.5 or et['last_vs_idle_cm'] > 0.02 or et['last_vs_idle_deg'] > 0.02: o['fails'].append(f'end transition {et}')
    o['frames'] = c.N; o['seconds'] = round(c.N / 30.0, 3)
    if c.N / 30.0 > 1.06: o['fails'].append('cycle slower than the Carnage CycleTime 1.06 s')
    o['inertia'] = rep; kn = rarmset.good_keys(c.N); o['layout']['keys'] = kn; tubeprod.pad(spec['out'], 'reload_draft', kn); spec['_keys'] = kn
    json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1); json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1, default=float)
    if not quiet: print(body, side, name, '| fails', o['fails'], '| pump', o['pump'], '| spent', info.get('spent_release'), info.get('spent_land'), '| eye', o['eye_cm'], 'reach', o['reach'], 'wrist', o['wrist'][0], o['wrist_view'], 'body', o['body_cm'], flush=True)
    return spec, o


if __name__ == '__main__':
    argv = sys.argv[1:]; opt = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None
    if (argv or ['build'])[0] == 'build':
        for b in (cs(opt('--bodies')) or ['pma', 'pwa']):
            for sd in (cs(opt('--sides')) or ['right', 'left']): build(sd, b, opt('--pick') or 'FC01')
    else: raise SystemExit(__doc__)
