"""Round 2: the owner's five picks re-authored, two takes each (A snappy, B heavy), each with its own magazine track.

usage: round2.py [take ids csv] [--clip empty_reload] [--out dir]      takes: F02A F02B F09A F09B M02A M02B M03A M03B H02A H02B
Output per take in <out>/<pick>/: <take>.json (spec: one key per frame, kicks, marks, magazine plan), <take>.glb,
<take>_track.json (magazine track), <take>_checks.json, gen_<take>.py.

Every move is a tl.to(frame, pose, profile): see rlib2.py. Frames come from the gun's own clip (seat, handle, bolt,
latch); the release of the old magazine is the draft's own (its track is ours). Rules of the motion, from the
measured shipped clips: big moves at 8 to 11 cm/frame peak with the peak past the middle and a dead stop; a stop
at a contact gets a rebound kick; before a big move a short counter move; the muzzle trails the hand (drag) and the
rotation ends a frame or two after the translation; stillness between moves instead of drifting.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, rlib, rlib2, magtrack2, rchecks2
from fk import qrot

OUT = renv.OUT + '/round2'
# take parameters: w stretches the big moves, drag and lag set how far the muzzle trails, k scales kicks, a anticipation
TAKES = {'A': {'w': 1.0, 'drag': 0.8, 'lag': 1, 'k': 1.0, 'a': 0.05}, 'B': {'w': 1.15, 'drag': 1.3, 'lag': 2, 'k': 1.4, 'a': 0.09}}
PROF_PUNCH = (1.5, 1.5)      # starts and ends abruptly: an impulse


def qw(c, rot): return author.qmul(c.q0, author.qeuler(*rot))
def along(c, rot, axis, d): return qrot(qw(c, rot), np.asarray(axis, float)) * d
def L(P, n): return int(round(n * P['w']))


def seat_block(c, tl, P, pos, rot, arrive, se, d=0.13, slam=5, reb=0.012):
    """Down to the place the fresh magazine stands, held clear of it along the well; then driven onto it, dead stop
    on the gun's seated frame, rebound."""
    en = magtrack2.vanilla(c.gun, c.clip)['enter']; pre = np.array(pos) + along(c, rot, en, d)
    tl.to(arrive, pre, rot, 'heavy', antic=P['a']); tl.kick(arrive, along(c, rot, en, -0.006), (-2, 0, 0), release=2.5)
    tl.hold(se - slam); tl.to(se, pos, rot, 'slam', rlag=0)
    tl.kick(se, along(c, rot, en, reb * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=3.0)
    tl.mark('arrive', arrive); tl.mark('seated', se)
    return pre


def punch(c, tl, P, f_start, f_stop, back=0.06, fwd=0.08, up_to=None):
    """Cocked back before, thrown forward f_start..f_stop, dead stop and rebound, then settle into the idle."""
    tl.hold(f_start); tl.to(f_stop, (0, 0.02, -fwd), (1, 0, 0), PROF_PUNCH, rlag=0)
    tl.kick(f_stop, (0, 0.004, 0.018 * P['k']), (5 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.hold(f_stop + 3 + (1 if P['w'] > 1 else 0)); tl.to(f_stop + 3 + L(P, 8), (0, 0, 0), (0, 0, 0), 'settle')
    tl.kick(f_stop + 3 + L(P, 8), (0, -0.004, 0.004), (-1.5, 0, 0), release=3.0)


def f02(c, tl):
    """Side flick, punch rack. Counter roll, then a hard outward wrist roll that stops dead: the magazine is thrown
    out sideways and falls. Down to the belt, driven onto the fresh magazine there. Up, cocked back, and a forward
    punch racks the handle on the gun's handle frame."""
    P = c.P; T = c.T; se = T['seated']; h0 = T['handle'][0] if T.get('handle') else se + 16; r = T['out'] - 1; R = P.get('roll', 85)
    tl.hold(r - 5 - L(P, 4)); tl.to(r - 5, (-0.02, -0.012, 0.0), (0, 4, -14), 'ease')
    tl.to(r, (0.085, 0.03, -0.01), (4, -12, R), 'drive', rlag=0); tl.kick(r, (0.01, 0, 0), (0, -3, -10 * P['k']), attack=0.5, release=2.5); tl.mark('release', r)
    tl.hold(r + 5)
    dip = P.get('dip', (0.03, -0.24, 0.11)); drot = c.natural(dip, P.get('dip_rot', (-28, -4, 0)), span=12, twist_w=0.15)
    seat_block(c, tl, P, dip, drot, r + 5 + L(P, 7), se)
    tl.hold(se + 3); cf = se + 3 + L(P, 7); tl.to(cf, (0.012, -0.022, 0.035), (0, 0, -4), 'rise', antic=P['a'] * 0.6); tl.kick(cf, (0, 0.012 * P['k'], -0.004), (-2, 0, 0), release=3.0)
    punch(c, tl, P, h0 - 1, h0 + 3)
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.16, 'tumble': 9, 'appear': r + 5 + L(P, 7) + 2, 'seated': se}}


def f09(c, tl):
    """Chest tuck. A short dip, then the rifle is snapped upward and canted: the magazine stays behind and drops out.
    Pulled back to the stomach rig and pressed onto the fresh magazine there. Pushed out, cocked, short punch for
    the handle."""
    P = c.P; T = c.T; se = T['seated']; h0 = T['handle'][0] if T.get('handle') else se + 16; r = T['out'] - 3
    tl.hold(r - 3 - L(P, 3)); tl.to(r, (0.0, -0.035, 0.012), (-4, 0, -10), 'ease'); tl.mark('release', r)
    tl.to(r + 3, (0.02, 0.05, 0.0), (7, 0, -34), PROF_PUNCH, rlag=1); tl.kick(r + 3, (0, -0.012 * P['k'], 0), (-3, 0, 5), attack=0.5, release=2.5)
    tl.hold(r + 8)
    ch = c.off(P.get('chest', (0.14, 1.17, -0.16))); rot = c.natural(ch, P.get('chest_rot', (-36, 8, 0)), span=14, twist_w=0.15)
    seat_block(c, tl, P, ch, rot, r + 8 + L(P, 7), se, d=0.11, reb=0.008)
    tl.hold(se + 3); cf = se + 3 + L(P, 7); tl.to(cf, (0.01, -0.012, 0.035), (0, 0, -4), 'rise', antic=P['a'] * 0.6); tl.kick(cf, (0, 0.01 * P['k'], -0.004), (-2, 0, 0), release=3.0)
    punch(c, tl, P, h0 - 1, h0 + 3, fwd=0.07)
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.15, 'tumble': 5, 'appear': r + 8 + L(P, 7) + 2, 'seated': se}}


def shakes(c, tl, P, f0, R, base=(0.05, 0.03, -0.01), amp=(0.05, 0.075)):
    """Rolled onto its side at f0-?; two outward jerks that stop dead. Returns (loosen frame, release frame)."""
    b = np.array(base); s1 = f0 + 2; tl.to(s1, b + (amp[0], 0, 0), (3, -12, R + 6), PROF_PUNCH, rlag=0); tl.to(s1 + 2, b, (3, -8, R - 3), PROF_PUNCH, rlag=0)
    tl.hold(s1 + 4 + (1 if P['w'] > 1 else 0)); s2 = tl.f + 2
    tl.to(s2, b + (amp[1], 0.005, 0), (3, -14, R + 9), PROF_PUNCH, rlag=0); tl.kick(s2, (-0.008, 0, 0), (0, 2, -6 * P['k']), attack=0.5, release=2.0)
    tl.to(s2 + 3, b, (3, -8, R - 4), 'settle'); tl.mark('loosen', s1); tl.mark('release', s2)
    return s1, s2


def m02(c, tl):
    """Shake loose, punch. Counter roll, the rifle is rolled onto its side and jerked outward twice: the first jerk
    works the magazine loose, the second throws it out. Down to the belt and onto the fresh magazine. Up, cocked
    back, and a forward punch that stops dead on the bolt frame sends the bolt home."""
    P = c.P; T = c.T; se = T['seated']; b = T['handle'][0] if T.get('handle') else se + 18; R = P.get('roll', 78); o = T['out']
    tl.hold(o - 11 - L(P, 2)); tl.to(o - 7, (-0.02, -0.012, 0), (0, 4, -14), 'ease'); tl.to(o - 2, (0.05, 0.03, -0.01), (3, -8, R), 'drive', rlag=0)
    tl.kick(o - 2, (0.008, 0, 0), (0, -2, -8 * P['k']), attack=0.5, release=2.5); tl.hold(o)
    s1, s2 = shakes(c, tl, P, o, R); tl.hold(s2 + 6)
    dip = P.get('dip', (0.03, -0.20, 0.10)); drot = c.natural(dip, P.get('dip_rot', (-28, -4, 0)), span=12, twist_w=0.15)
    arr = s2 + 6 + L(P, 7); seat_block(c, tl, P, dip, drot, arr, se)
    tl.hold(se + 3); cf = se + 3 + L(P, 7); tl.to(cf, (0.012, -0.022, 0.035), (0, 0, -4), 'rise', antic=P['a'] * 0.6); tl.kick(cf, (0, 0.012 * P['k'], -0.004), (-2, 0, 0), release=3.0)
    punch(c, tl, P, b - 4, b)
    return {'mag': {'release': s2, 'loosen': [[s1, 0.03]], 'mode': 'throw', 'slide': 3, 'travel': 0.17, 'tumble': 8, 'appear': arr + 2, 'seated': se}}


def m03(c, tl):
    """Thigh slam, hip bump. A short lift, then the rifle swings muzzle-down beside the leg and its magazine catches
    on the thigh rig; the rifle is ripped up off it and the magazine drops. Held high over the fresh magazine, then
    slammed down onto it. The butt is knocked back on the hip on the bolt frame, and the rifle comes up."""
    P = c.P; T = c.T; se = T['seated']; b = T['handle'][0] if T.get('handle') else se + 18; r = T['out']; v = magtrack2.vanilla(c.gun, c.clip)
    th = c.off(P.get('thigh', (0.31, 1.13, -0.03))); rot = c.natural(th, P.get('thigh_rot', (-50, -8, 0)), span=14, twist_w=0.15)
    tl.hold(r - 10 - L(P, 3)); tl.to(r - 10, (0, 0.025, 0.0), (5, 0, 0), 'ease'); tl.to(r, th, rot, 'heavy'); tl.kick(r, (0, -0.01 * P['k'], 0), (-3, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r)
    up = np.array(th) - along(c, rot, v['exit'], 0.17); tl.to(r + 5, up, rot, PROF_PUNCH, rlag=0); tl.kick(r + 5, along(c, rot, v['exit'], 0.01), (2, 0, 0), release=3.0)
    tl.hold(r + 5 + 8); pre = np.array(th) + along(c, rot, v['enter'], P.get('windup', 0.20)); tl.to(r + 5 + 8 + L(P, 5), pre, rot, 'ease')
    tl.hold(se - 5); tl.to(se, th, rot, 'slam', rlag=0); tl.kick(se, along(c, rot, v['enter'], 0.02 * P['k']), (-5 * P['k'], 0, 0), attack=0.5, release=3.5); tl.mark('seated', se)
    tl.hold(se + 5)
    hb = np.array(th) + (-0.02, 0.03, -0.02); hrot = [rot[0] + 12, rot[1] + 2, rot[2] + 2]
    tl.to(b - 4, hb, hrot, 'heavy'); tl.to(b, hb + (0.0, 0.0, 0.05), [hrot[0] + 4, hrot[1], hrot[2]], 'slam', rlag=0)
    tl.kick(b, (0, 0.004, -0.02 * P['k']), (-4 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.hold(b + 3); e = b + 3 + L(P, 13); tl.to(e - 3, (0.004, -0.03, -0.03), (-3, 0, 0), 'rise', antic=P['a']); tl.to(e + 2, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0.004, 0.008, -0.024), (-1.5, 0, 1), release=3.5)
    return {'mag': {'release': r, 'mode': 'hook', 'slide': 5, 'tumble': 3, 'appear': r + 5 + 8 + L(P, 5) + 2, 'seated': se}}


def h02(c, tl):
    """Flip and shake, punch. A wrist flick that stops dead on the latch frame pops the latch. Counter roll, the rifle
    is rolled onto its left side and jerked outward twice: the cassette comes loose, then flies out. Down to the
    belt and onto the fresh cassette. Up, cocked back, and a punch that stops dead on the latch frame shuts it."""
    P = c.P; T = c.T; se = T['seated']; g = T['parts'].get('magazine_grabber', {}).get('window', [19, 140]); Lf, C = g[0], g[1]; R = P.get('roll', 78); o = T['out']
    tl.hold(Lf - 7 - L(P, 2)); tl.to(Lf - 4, (0, -0.004, 0), (0, 0, 8), 'ease'); tl.to(Lf, (0.02, 0.02, 0), (3, -3, -30), 'drive', rlag=0)
    tl.kick(Lf, (0.008, 0.004, 0), (0, -2, -7 * P['k']), attack=0.5, release=2.5); tl.hold(Lf + 4); tl.to(Lf + 4 + L(P, 6), (0, 0, 0), (0, 0, 0), 'settle')
    tl.hold(o - 9 - L(P, 2)); tl.to(o - 5, (-0.02, -0.012, 0), (0, 4, -14), 'ease'); tl.to(o, (0.05, 0.03, -0.01), (3, -8, R), 'drive', rlag=0)
    tl.kick(o, (0.008, 0, 0), (0, -2, -8 * P['k']), attack=0.5, release=2.5); tl.hold(o + 2)
    s1, s2 = shakes(c, tl, P, o + 2, R); tl.hold(s2 + 6)
    dip = P.get('dip', (0.03, -0.20, 0.10)); drot = c.natural(dip, P.get('dip_rot', (-28, -4, 0)), span=12, twist_w=0.15)
    arr = s2 + 6 + L(P, 7); seat_block(c, tl, P, dip, drot, arr, se)
    tl.hold(se + 3); cf = se + 3 + L(P, 7); tl.to(cf, (0.012, -0.022, 0.035), (0, 0, -4), 'rise', antic=P['a'] * 0.6); tl.kick(cf, (0, 0.012 * P['k'], -0.004), (-2, 0, 0), release=3.0)
    punch(c, tl, P, C - 4, C)
    return {'mag': {'release': s2, 'loosen': [[s1, 0.03]], 'mode': 'throw', 'slide': 3, 'travel': 0.18, 'tumble': 6, 'appear': arr + 2, 'seated': se}}


PICKS = {'F02': ('Side flick, punch rack', 'copperhead', f02, 'front'), 'F09': ('Chest tuck', 'copperhead', f09, 'front'), 'M02': ('Shake loose, punch', 'masamune', m02, 'masamune'),
         'M03': ('Thigh slam, hip bump', 'masamune', m03, 'masamune'), 'H02': ('Flip and shake, punch', 'hercules', h02, 'hercules')}
GEN = '''"""{tid} {name}, take {take} ({kind}). Rebuilds the clip, its magazine track and its checks."""
import sys
sys.path.insert(0, 'C:/Modding/gg-work/reloads/tools/anim/authoring/reload')
import round2
PARAMS = {params}
if __name__ == '__main__':
    round2.one('{tid}', PARAMS, clip=(sys.argv[1] if len(sys.argv) > 1 else '{clip}'))
'''


def one(tid, params=None, clip='empty_reload', out=None, quiet=False):
    pick, take = tid[:3], tid[3]; name, gun, fn, cat = PICKS[pick]; P = dict(TAKES[take]); P.update(params or {}); out = out or OUT
    d = f'{out}/{pick}'; stem = tid + ('' if clip == 'empty_reload' else f'_{clip}')
    spec, glb, ctx = rlib2.build(stem, gun, fn, P, d, clip=clip)
    spec['_name'] = f'{name}, take {take}'; spec['_doc'] = ' '.join((fn.__doc__ or '').split()); spec['_take'] = take; spec['_pick'] = pick; spec['_category'] = cat
    G = rchecks2.gun_world(spec); track = magtrack2.build(gun, clip, [(np.array(t), np.array(q)) for t, q in G], spec['_mag'])
    json.dump(track, open(f'{d}/{stem}_track.json', 'w')); spec['_track'] = f'{d}/{stem}_track.json'
    json.dump(spec, open(f'{d}/{stem}.json', 'w'), indent=1)
    c = rchecks2.check(spec, track); c['name'] = spec['_name']; json.dump(c, open(f'{d}/{stem}_checks.json', 'w'), indent=1)
    if clip == 'empty_reload':
        open(f'{d}/gen_{tid}.py', 'w').write(GEN.format(tid=tid, name=name, take=take, kind='snappy' if take == 'A' else 'heavy', params=json.dumps(params or {}), clip=clip))
    en = magtrack2.vanilla(gun, clip)['enter']; gq = G[spec['_timing']['seated']][1]; c['fresh_side'] = [round(float(x), 2) for x in -qrot(gq, en)]
    json.dump(c, open(f'{d}/{stem}_checks.json', 'w'), indent=1)
    if not quiet: print(summary(c), 'fresh magazine stands toward', c['fresh_side'])
    return spec, c


def summary(c):
    v = lambda k: c[k][0] if isinstance(c.get(k), list) else c.get(k); m = c['motion']
    return (f"{c['draft']:5s} end {c['end_cm']:.3f}/{c['end_deg']:.3f} eye {v('eye_cm')} cover {v('cover_peak')} wrist {v('wrist_swing')}/{c['wrist_view']} reach {v('reach')} sh {c['shoulder_pull_cm']} "
            f"body {v('body_cm')}@{c['body_cm'][1]} guns {v('guns_gap_cm')} | mag rel f{c['release']} acc {c['release_grip_acc']} seen {c['mag_seen_fpp']} hang {c['mag_hang']} fall {c['mag_fall_frames']} gone {c['mag_gone']} "
            f"fresh {c['fresh_frames']} seen {c['fresh_seen_fpp']} offaxis {c['fresh_off_axis_cm']}/{c['guided_off_axis_cm']} | peak {m['peak_speed']} p90 {m['p90_speed']} at {m['peak_at']} stop {m['stop']} "
            f"jerks {m['jerk_events']} still {m['hold_share']} whip {m['whip']} | FAILS {c['fails']}")


if __name__ == '__main__':
    argv = sys.argv[1:]; clip = common.opt(argv, '--clip') or 'empty_reload'; out = common.opt(argv, '--out')
    ids = argv[0].split(',') if argv else [p + t for p in PICKS for t in 'AB']
    for tid in ids: one(tid, None, clip, out)
