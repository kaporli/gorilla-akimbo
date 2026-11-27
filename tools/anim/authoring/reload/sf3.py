"""SMG and shotgun FRONT family, round 3: ten drafts SF21 to SF30 for picks 2 and 3, each a different technique
(no chops: round 2's SF13 low chop is pick 1). Takes A (Saratoga) and B (Zhuo), right hand, male V, empty reload.
Round 2's budget (sf2.BUDGET: A 72 frames, B 81, the same beats), part-frame map, stations, rig dive, racks and gate
additions; the magazine track is magtrack4 (inertia, strip, slide).

usage: sf3.py list | build [ids csv] [--takes A,B] [--jobs n] | stats [ids]
Output: <OUT>/clips/pma/<gun>_right_<id><take>_empty_reload.glb, .json, _track.json, _gate.json

Magazine rule (round 2): released on the move's fastest frame, it keeps the gun's velocity and spin (exit / gun
speed over the 3 frames up to the release 0.85 to 1.15). Where the gun is at rest at the release (it then jerks away,
or the magazine is caught on a rig edge, or slides out under its own weight) both speeds must be under 1.5 cm/f:
the magazine starts from rest, as the gun does. It lands before the fresh magazine appears.
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, prod, rgate, magtrack2, magtrack3, magtrack4, sf2
from sf2 import (BUDGET, GUNS, TAKES, CLIP, L, PUNCH, TL, bud, long_gun, exw, mag_point, aligned, peak_mag, opener,
                 seat_block, to_rig, rack, setup, part_frames, elbow_step, gone_height, stem)
from rlib import K
from glb import Glb
from fk import Clip, qrot

OUT = renv.OUT
REST = 1.5          # cm/f: below this the gun and the magazine count as at rest at the release


def stn(c, name): return sf2.STN_LONG.get(name, name) if long_gun(c) else name


def hook_on(c, tl, hook, rot, prof='drive'):
    """Dive to the rig right after the opener, arrive 6 frames before the stop beat, hold still 3 frames; returns the
    catch frame (3 before the stop beat)."""
    s = bud(c)['stop']; a = s - 6; tl.hold(bud(c)['cock'] + 1); tl.to(a, hook, rot, prof, rlag=0); tl.hold(a + 3); return a + 3


def mag_plan(c, r, mode, appear, **kw):
    d = {'release': int(r), 'mode': mode, 'appear': int(appear), 'seated': bud(c)['seat'], 'floor': 0.08, 'tumble': 2}
    d.update(kw); return {'mag': d}


def strike_along(c, tl, f_end, p0, rot, dist, n, prof='slam', kick=0.012):
    """One straight move along the well (no rotation) ending dead on f_end; returns the release (fastest frame)."""
    P = c.P; k = P['k']; e = exw(c, rot); f0 = f_end - n; tl.hold(f0)
    tl.to(f_end, np.array(p0, float) + e * dist, rot, prof, rlag=0); tl.kick(f_end, -e * kick * k, (0.5 * k, 0, 0), attack=0.5, release=2.5)
    tl.nodrag.append((f0 - 1, f_end + 1)); return peak_mag(c, tl, f0 + 1, f_end)


# ------------------------------------------------------------------------------------------------ drafts
def sf21(c, tl):
    """Press-and-drop. No wind-up: the gun is lifted a hand's width, level, then snapped down a short way and stopped
    dead in front of the chest; the magazine keeps going and drops out of the well in plain view. Belt rig; cocked
    back and punched forward on the home frame."""
    P = c.P; s = bud(c)['stop']; opener(c, tl, 'tug'); rot = (-4, 0, -2); p0 = np.array(P.get('p0', (0.0, 0.035, -0.01)))
    n = L(P, 3); tl.hold(s - n - 1 - L(P, 5)); tl.to(s - n - 1, p0, rot, 'ease', rlag=0); tl.hold(s - n)
    r = strike_along(c, tl, s, p0, rot, P.get('dist', 0.11), n); tl.mark('release', r)
    arr = to_rig(c, tl, 'belt'); rack(c, tl, 'punch')
    return mag_plan(c, r, 'inertia', arr + 2)


def sf22(c, tl):
    """Belt-edge strip. Straight down to the belt rig: the magazine's base catches on the rig's edge and the gun is
    pulled forward and up off it along the well; the magazine is left on the rig and drops. Onto the fresh magazine
    beside it; up, held out and yanked back on the home frame. All of it below the view."""
    P = c.P; s = bud(c)['stop']; se = bud(c)['seat']; opener(c, tl, 'tip')
    hook, rot = c.station(stn(c, 'belt')); r = hook_on(c, tl, hook, rot)
    po = r + L(P, 4); tl.to(po, hook - c.along(rot, c.v['exit'], 0.16), rot, PUNCH, rlag=0); tl.kick(po, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=2.5)
    tl.nodrag.append((r - 3, po + 1)); tl.mark('release', r)
    tl.hold(po + 2); arr = min(po + 2 + L(P, 5), se - 6); seat_block(c, tl, hook, rot, arr, se, d=0.12)
    rack(c, tl, 'yank')
    return mag_plan(c, r, 'strip', arr + 2, tumble=3, lead=5)


def sf23(c, tl):
    """Tilt and shake. The muzzle tips up and the gun is shaken short and hard along the well, three times: the
    first two work the magazine down, the third throws it out in front. Thigh rig; the muzzle is thrown down on the
    home frame."""
    P = c.P; k = P['k']; s = bud(c)['stop']; opener(c, tl, 'tug'); tr = (P.get('tilt', 26), 0, -4); b = np.array(P.get('base', (0.0, 0.0, 0.03)))
    t0 = s - L(P, 9); tl.hold(t0 - L(P, 4)); tl.to(t0, b, tr, 'drive', rlag=0); e = exw(c, tr)
    tl.to(t0 + 2, b + e * 0.03, tr, PUNCH, rlag=0); tl.kick(t0 + 2, -e * 0.005 * k, (0, 0, 0), attack=0.5, release=1.2)
    tl.to(t0 + 4, b, tr, 'snap', rlag=0); tl.to(t0 + 6, b + e * 0.035, tr, PUNCH, rlag=0); tl.kick(t0 + 6, -e * 0.005 * k, (0, 0, 0), attack=0.5, release=1.2)
    tl.to(s - 2, b - e * 0.01, tr, 'snap', rlag=0); tl.to(s, b + e * P.get('throw', 0.07), tr, 'slam', rlag=0); tl.kick(s, -e * 0.01 * k, (0.5 * k, 0, 0), attack=0.5, release=2.5)
    tl.nodrag.append((t0 - 1, s + 1)); r = peak_mag(c, tl, s - 1, s); tl.mark('loosen', t0 + 2); tl.mark('release', r)
    arr = to_rig(c, tl, P.get('rig', 'thigh')); rack(c, tl, 'nod')
    return mag_plan(c, r, 'inertia', arr + 2, loosen=[[t0 + 2, 0.01], [t0 + 6, 0.025]])


def sf24(c, tl):
    """Side fling. The gun is drawn in and rolled onto its left side so the well faces out; the arm swings it out to
    the right at chest height and stops dead at arm's length: the magazine flies on out to the right, level, and
    drops. Wide belt rig; held out and yanked back on the home frame."""
    P = c.P; s = bud(c)['stop']; opener(c, tl, 'tip'); r0 = P.get('r0', (2, -6, 58)); p0 = np.array(P.get('p0', (-0.07, -0.03, 0.02))); n = L(P, 4)
    tl.hold(s - n - 1 - L(P, 6)); tl.to(s - n - 1, p0, r0, 'drive', rlag=1); tl.hold(s - n)
    r = strike_along(c, tl, s, p0, r0, P.get('dist', 0.15), n); tl.mark('release', r)
    arr = to_rig(c, tl, 'belt_wide'); rack(c, tl, 'yank')
    return mag_plan(c, r, 'inertia', arr + 2)


def sf25(c, tl):
    """Stomach strip, show empty. The gun is pulled in to the stomach rig, the magazine's base catches on the rig
    edge and the gun is shoved out and up off it, on up into view, empty, for a beat; the magazine drops at the belly.
    Back down onto the fresh magazine on the same rig; up, cocked low, a rising punch on the home frame."""
    P = c.P; s = bud(c)['stop']; se = bud(c)['seat']; opener(c, tl, 'tug')
    hook, rot = c.station(stn(c, 'stomach')); r = hook_on(c, tl, hook, rot)
    po = r + L(P, 3); tl.to(po, hook - c.along(rot, c.v['exit'], 0.15), rot, PUNCH, rlag=0); tl.nodrag.append((r - 3, po + 1)); tl.mark('release', r)
    sh = po + L(P, 5); tl.to(sh, P.get('show', (0.03, -0.02, -0.06)), (2, 0, -12), 'drive', rlag=1); tl.kick(sh, (0, -0.006 * P['k'], 0), (-2, 0, 0), attack=0.5, release=2.0); tl.mark('show', sh)
    tl.hold(sh + 1); arr = se - 6; seat_block(c, tl, hook, rot, arr, se, d=0.11, reb=0.008)
    rack(c, tl, 'upper')
    return mag_plan(c, r, 'strip', arr + 2, tumble=3, lead=5)


def sf26(c, tl):
    """Release and let it fall. The gun is raised a little and turned in so the well hangs straight down, and held
    still: the thumb lets the magazine go and it slides out under its own weight and falls past the hand. Hip rig;
    held ready, the thumb drops the cocking piece and the gun jolts on the home frame."""
    P = c.P; s = bud(c)['stop']; opener(c, tl, 'tip'); r0 = P.get('r0', (-18, 8, -12)); p0 = P.get('p0', (0.0, 0.03, 0.0))
    r = s - L(P, 5); tl.hold(r - 4 - L(P, 6)); tl.to(r - 4, p0, r0, 'drive', rlag=0)
    tl.mark('release', r); tl.nodrag.append((r - 5, s + 2))
    arr = to_rig(c, tl, 'hip'); rack(c, tl, 'thumb')
    return mag_plan(c, r, 'slide', arr + 2)


def sf27(c, tl):
    """Pendulum backswing. The arm drops the gun beside the hip, tips the muzzle down, and swings it back along the
    thigh like a pendulum, stopping it dead beside the hip with the well facing back: the magazine flies on backward
    and falls behind the leg. Hip rig; swung forward and up, a rising punch on the home frame."""
    P = c.P; s = bud(c)['stop']; opener(c, tl, 'tip'); pos, rot = c.station('hip'); rs = P.get('rs', (-50, -10, 12))
    stop = np.array(pos) + np.array(P.get('above', (0.0, 0.10, 0.08))); n = L(P, 4); e = exw(c, rs); start = stop - e * P.get('swing', 0.20)
    tl.hold(bud(c)['cock'] + 1); tl.to(s - n - 2, start, rs, 'drive', rlag=1); tl.hold(s - n)        # down beside the hip first, muzzle tipped down
    r = strike_along(c, tl, s, start, rs, P.get('swing', 0.20), n, prof=(2.5, 1.0)); r = s; tl.mark('release', r)
    tl.hold(s + 3); se = bud(c)['seat']; arr = min(s + 3 + L(P, 6), se - 6); seat_block(c, tl, pos, rot, arr, se)
    rack(c, tl, 'upper')
    return mag_plan(c, r, 'inertia', arr + 2)


def sf28(c, tl):
    """Drop and catch. The arm lets go: the gun falls straight down, level, picking up speed like a dropped weight,
    and is caught dead beside the hip; the magazine keeps falling out of the well. Set onto the fresh magazine on the
    belt rig; up, cocked back, punched forward on the home frame."""
    P = c.P; s = bud(c)['stop']; opener(c, tl, 'tug'); rot = (-4, 0, 4); low = np.array(P.get('low', (0.07, -0.30, 0.12)))
    n = L(P, 7); top = low - exw(c, rot) * (0.5 * magtrack2.G_ACC * n * n * 1.05)      # the distance a dropped weight falls in n frames
    tl.hold(s - n - 1 - L(P, 4)); tl.to(s - n - 1, top, rot, 'ease', rlag=0); tl.hold(s - n)
    tl.to(s, low, rot, (2.0, 1.0), rlag=0); tl.kick(s, -exw(c, rot) * 0.014 * P['k'], (0, 0, 0), attack=0.5, release=2.5)   # Beta(2, 1): s = u^2, a free fall
    tl.nodrag.append((s - n - 1, s + 1)); r = peak_mag(c, tl, s - 2, s); tl.mark('release', r)
    arr = to_rig(c, tl, 'belt'); rack(c, tl, 'punch')
    return mag_plan(c, r, 'inertia', arr + 2)


def sf29(c, tl):
    """Jerk away. Rolled onto its left side so the well faces out and held still for a beat, then the gun is jerked
    in and up along the well and stopped: the magazine stays where it was, hangs for an instant beside the gun and
    drops on the right. Wide belt rig; the thumb drops the cocking piece on the home frame."""
    P = c.P; s = bud(c)['stop']; opener(c, tl, 'tip'); r0 = P.get('r0', (4, -4, 42)); p0 = np.array(P.get('p0', (0.05, 0.0, -0.02)))
    r = s - L(P, 5); tl.hold(r - 4 - L(P, 6)); tl.to(r - 4, p0, r0, 'drive', rlag=0); tl.hold(r)
    n = L(P, 2); e = exw(c, r0); tl.to(r + n, p0 - e * P.get('dist', 0.13), r0, 'snap', rlag=0); tl.kick(r + n, e * 0.008 * P['k'], (0, 0, 0), attack=0.5, release=2.5)
    tl.nodrag.append((r - 5, r + n + 1)); tl.mark('release', r)
    arr = to_rig(c, tl, 'belt_wide'); rack(c, tl, 'thumb')
    return mag_plan(c, r, 'inertia', arr + 2)


def sf30(c, tl):
    """Thigh strip. Down beside the thigh: the magazine's base catches on the thigh rig and the gun is pulled straight
    up off it; the magazine drops by the knee. Wound up over the fresh magazine on the same rig and slammed onto it.
    Up, cocked back, punched forward on the home frame."""
    P = c.P; k = P['k']; s = bud(c)['stop']; se = bud(c)['seat']; opener(c, tl, 'tug')
    hook, rot = c.station('thigh'); r = hook_on(c, tl, hook, rot, 'heavy')
    po = r + L(P, 4); tl.to(po, hook - c.along(rot, c.v['exit'], 0.16), rot, PUNCH, rlag=0); tl.kick(po, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=2.5)
    tl.nodrag.append((r - 3, po + 1)); tl.mark('release', r)
    tl.hold(po + 3); pre = hook + c.along(rot, c.v['enter'], 0.20); tl.to(se - 7, pre, rot, 'ease'); tl.hold(se - 5)
    tl.to(se, hook, rot, 'slam', rlag=0); tl.kick(se, c.along(rot, c.v['enter'], 0.02 * k), (-5 * k, 0, 0), attack=0.5, release=3.5)
    rack(c, tl, 'punch')
    return mag_plan(c, r, 'strip', se - 5, tumble=3, lead=5)


PICKS = {'SF21': ('Press-and-drop', sf21), 'SF22': ('Belt-edge strip', sf22), 'SF23': ('Tilt and shake', sf23), 'SF24': ('Side fling', sf24),
         'SF25': ('Stomach strip, show empty', sf25), 'SF26': ('Release and let it fall', sf26), 'SF27': ('Pendulum backswing', sf27),
         'SF28': ('Drop and catch', sf28), 'SF29': ('Jerk away', sf29), 'SF30': ('Thigh strip', sf30)}
DOC = {k: ' '.join((fn.__doc__ or '').split()) for k, (n, fn) in PICKS.items()}
PARAMS = {   # Zhuo: the long stock came within 17.3 to 19.8 cm of the eye: lower and further forward; thigh rig put the stock in the torso block
          'SF21B': {'p0': (0.0, 0.0, -0.05)}, 'SF24B': {'p0': (-0.07, -0.07, -0.02)}, 'SF26B': {'p0': (0.0, -0.02, -0.04)},
          'SF29B': {'p0': (0.06, -0.06, -0.05), 'dist': 0.11}, 'SF23B': {'rig': 'hip'}}


def mag_speed(gid, track, G):
    """As sf2.mag_speed, per mode. inertia: exit speed against the gun's speed over the 3 frames up to the release
    (ratio 0.85 to 1.15), or both under REST when the gun is still at the release. strip / slide: the gun is still at
    the release (under REST) and the magazine leaves from rest (first free step under REST)."""
    v = magtrack2.vanilla(gid, CLIP); cen = np.r_[v['centre'], 1]; S = v['seat']; r = track['release']; ff = track['free_from']
    C = [(magtrack2.m4(*G[f]) @ S @ cen)[:3] for f in range(r - 3, r + 1)]
    gun = max(float(np.linalg.norm(C[i + 1] - C[i])) for i in range(3)) * 100
    W = lambda f: (magtrack2.m4(*G[f]) @ np.array(track['frames'][f]['m']).reshape(4, 4) @ cen)[:3]
    f0 = r if track['plan']['mode'] == 'inertia' else ff - 1
    ex = float(np.linalg.norm(W(f0 + 1) - W(f0) - np.array([0, -magtrack2.G_ACC, 0]))) * 100
    mode = track['plan']['mode']
    if mode == 'inertia' and gun >= REST: ratio = ex / gun; ok = sf2.MAG_RATIO[0] <= ratio <= sf2.MAG_RATIO[1]
    elif mode == 'slide': ratio = None; ok = gun < REST            # slides out by its weight, from rest relative to a still gun
    else: ratio = None; ok = gun < REST and ex < REST
    return {'mode': mode, 'exit_cm_f': round(ex, 2), 'gun_cm_f': round(gun, 2), 'ratio': None if ratio is None else round(ratio, 2), 'ok': bool(ok)}


def build(pick, take, side='right', body='pma', out=None, quiet=False):
    gid = GUNS[take]; setup(gid); out = out or OUT + '/clips'; d = f'{out}/{body}'; os.makedirs(d, exist_ok=True); name = stem(pick, take, side)
    S = side.capitalize(); P = dict(TAKES[take]); P.update(PARAMS.get(pick + take, {})); c = prod.Ctx(gid, body, CLIP, P, S); tl = TL(c, P['lag'], P['drag'])
    m = PICKS[pick][1](c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    pf = part_frames(take, m['mag']['release'])
    spec = {'_draft': name, '_name': f'{PICKS[pick][0]}, take {take}', '_doc': DOC[pick], '_gun': gid, '_left_gun': gid, '_body': body, '_side': S,
            '_gun_clip': CLIP, '_pick': pick, '_take': take, '_timing': c.T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False, '_round': 'smg-front-3',
            '_part_frames': pf, 'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, ('Left' if S == 'Right' else 'Right'): [K(0)]},
            'shakes': {S: kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{name}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); G = [(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(c.N))]
    track = magtrack4.build(gid, CLIP, G, m['mag']); spec['_track'] = f'{d}/{name}_track.json'
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); o['elbow_step_deg'] = elbow_step(spec)
    if m['mag']['mode'] != 'inertia':
        o['mag_exit'] = {'off_axis_cm': o['exit_at_10cm'] if o['exit_at_10cm'] is not None else o['exit_off_axis_cm'], 'mode': m['mag']['mode']}
    o['mag_speed'] = mag_speed(gid, track, G); o['mag_gone_height_m'] = gone_height(gid, track, G)
    if not o['mag_speed']['ok']: o['fails'].append(f"magazine speed {o['mag_speed']['exit_cm_f']} cm/f against the gun's {o['mag_speed']['gun_cm_f']} ({o['mag_speed']['mode']})")
    if o['mag_gone_height_m'] is not None and o['mag_gone_height_m'] > 0.09: o['fails'].append(f"old magazine removed {o['mag_gone_height_m']} m above the ground")
    json.dump(o, open(f'{d}/{name}_gate.json', 'w'), indent=1)
    if not quiet: print(body, rgate.line(o), '| elbow', o['elbow_step_deg'], '| magv', o['mag_speed'], 'gone', o['mag_gone_height_m'], '| exit', o.get('mag_exit'), flush=True)
    return spec, o


def stats(ids):
    import motionstats
    rows = []; J = json.load(open(OUT + '/ref/motion_all.json')); rows += [(k, v) for k, v in J.items() if k.startswith('APPROVED')]
    R2 = common.mp('C:/Modding/anim-work/smg-shotgun/round2-front/clips/pma')
    for t in ('A', 'B'): rows.append((f'SF13{t} Low chop, pick 1 (round 2)', motionstats.stats(f'{R2}/{stem("SF13", t)}.glb', 'reload_draft', 'Right', 0.55 if t == 'A' else 0.6)))
    for p in ids:
        for t in ('A', 'B'):
            g = f'{OUT}/clips/pma/{stem(p, t)}.glb'
            if os.path.exists(g): rows.append((f'{p}{t} {PICKS[p][0]} ({GUNS[t]})', motionstats.stats(g, 'reload_draft', 'Right', 0.55 if t == 'A' else 0.6)))
    Tb = ['| clip | frames | peak cm/f | peak at | stop | jerks | still | whip | muzzle peak | big moves |', '|---|---|---|---|---|---|---|---|---|---|']
    for lab, s in rows: Tb.append(f"| {lab} | {s['frames']} | {s['peak_speed']} | {s['peak_at']} | {s['stop']} | {s['jerk_events']} | {int(s['hold_share'] * 100)} % | {s['whip']} | {s['peak_muzzle_speed']} | {s['big_moves']} |")
    os.makedirs(OUT + '/measure', exist_ok=True); open(OUT + '/measure/motion_round3.md', 'w').write('\n'.join(Tb) + '\n'); print('\n'.join(Tb))
    json.dump({l: s for l, s in rows}, open(OUT + '/measure/motion_round3.json', 'w')); motionstats.plot(rows, OUT + '/measure/motion_round3.png')


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
    else: raise SystemExit(__doc__)
