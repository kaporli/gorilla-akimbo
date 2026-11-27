"""Rules H1 and L1 (pfix3).

H1  handle part. The gun's cocking handle (or bolt, slider, lever) is a joint of the gun's own weapon set (base1 or rcv1), clip named as the
    reload slot; the game plays that clip on the same clock as our arm clip (not rebuilt, except by rpartset for the tube guns). Per handle joint:
    the frames in which it moves (per-frame change over `change_cm` in cm, 10 deg counted as 1 cm), none may be on a visible frame (outside
    hide_start..hide_end), and its state on our last frame equals the vanilla clip's last frame within `end_tol_cm`.
    Clock: the hidden window is stretched or cut by delta frames (TM1): frame f plays vanilla frame f before hide_start, f + delta after hide_end,
    linear in between; delta = hidden_avail_f - hidden_natural_f of the TM1 measure, 0 when there is none.
    built=True: the part set hpartset.py builds for the clip (every gun with a handle joint gets one in the build), computed in process.
    With part_set (a set built by hpartset.py) the curve is read from it, key f at clip frame f (the set has the arm clip's keys).
    Unverified in game: that the weapon clip runs on that clock.
L1  lowered end transition: the gun arrives at the lowered idle in one move, not a raised arrival and a long drift. In the last `window` frames:
    tail_frames (last frame with a speed of at least `frac` of the peak to the end) and slow_frames (frames after that with a speed between slow_lo and slow_hi cm/f).
usage: hfix.py <clip stem>... [--gun id]
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)).replace(chr(92), '/')
sys.path.insert(0, HERE + '/../reload'); sys.path.insert(0, HERE + '/..')
import renv, common, manifest, gungeo
import numpy as np
from glb import Glb
from fk import Clip
from wclip import TClip

FPS = 30.0
_cache = {}


def lim():
    return manifest.load()['checks']['draft']['h1']


def lim_l1():
    return manifest.load()['checks']['draft']['l1']


def slot_of(gid, pick, clip):
    g = next(x for x in manifest.load()['guns'] if x['id'] == gid); sl = list(g['reload'].get('slots') or g['reload'].get('picks') or [])
    if pick not in sl: return None      # the quick-drop fallback (FB) and guns without picks have no slot of their own
    i = sl.index(pick)
    return ('' if clip == 'reload' else 'empty_') + 'reload' + ('' if i == 0 else f'_0{i}')


def moving_parts(gid, slot):
    """The weapon-part joints that act after the magazine is seated, found by motion (timing.table: every joint of the gun's weapon sets that moves in the vanilla clip), not by name:
    the joint's motion window ends after seated + 5 and is not the magazine action (a window that starts at the release and ends by seated + 8 is the magazine lock or latch)."""
    import timing
    kind = 'reload' if slot.startswith('reload') else 'empty_reload'
    try: T = timing.table(gid, kind)
    except Exception: return set()
    se, out = T['seated'], T['out']; res = set()
    for n, p in T['parts'].items():
        a, b = p['window']
        if b > se + 5 and not (a >= out - 15 and b <= se + 8): res.add(n)
    return res


def curves(gid, slot):
    """{handle joint: displacement from its first frame (cm, 10 deg = 1 cm) per vanilla frame} for the gun's handle-like joints that move over `min_peak_cm`."""
    k = (gid, slot)
    if k in _cache: return _cache[k]
    L = lim(); gun = common.gun(gid); out = {}; cand = moving_parts(gid, slot)
    for kind in ('base1', 'rcv1'):
        p = gungeo.wanim(gun, kind)
        if not p: continue
        g = Glb(p)
        if slot not in [a['name'] for a in g.j.get('animations', [])]: continue
        c = TClip(g, slot)
        for i, n in enumerate(g.names):
            if n not in cand: continue
            t0, r0 = c.local(i, 0.0); d = []
            for f in range(c.frames):
                t, r = c.local(i, f / FPS); d.append(max(float(np.linalg.norm(t - t0)) * 100, float(np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(r, r0)))))) / 10)))
            d = np.array(d)
            if d.max() > L['min_peak_cm']: out[n] = d      # a candidate that moves less than min_peak_cm is not a part action
    _cache[k] = out
    return out


def handle_glb(gid, slot='empty_reload'):
    """The weapon set glb (base1 or rcv1) that holds the gun's handle joints for the slot, None when the gun has none."""
    gun = common.gun(gid); L = lim()
    for kind in ('base1', 'rcv1'):
        p = gungeo.wanim(gun, kind)
        if not p: continue
        g = Glb(p)
        if slot in [a['name'] for a in g.j.get('animations', [])] and curves(gid, slot): return p
    return None


def slots_of(glb):
    """Clip names of a weapon set glb."""
    return [a['name'] for a in Glb(glb).j.get('animations', [])]


def clock(f, hs, he, d):
    if f <= hs: return float(f)
    if f >= he: return float(f + d)
    return hs + (f - hs) * (1 + d / max(he - hs, 1))


def part_curves(set_glb, slot, names):
    """{joint: displacement per key (cm, 10 deg = 1 cm)} of the handle joints in a built handle part set (hpartset.py): keyed like our arm clip, no clock shift."""
    g = Glb(set_glb); c = TClip(g, slot); out = {}
    for n in names:
        i = g.names.index(n); t0, r0 = c.local(i, 0.0); d = []
        for f in range(c.frames):
            t, r = c.local(i, f / FPS); d.append(max(float(np.linalg.norm(t - t0)) * 100, float(np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(r, r0)))))) / 10)))
        out[n] = np.array(d)
    return out


def handle(spec, gate, delta=0.0, part_set=None, built=False):
    """-> {joint: {visible_change_f: [...], end_state_cm, end_vs_vanilla_cm, change: [first, last]}} for the handle joints of the clip's slot; {} when the gun has none."""
    L = lim(); gid = spec['_gun']; N = spec['frames']; lay = (gate or {}).get('layout') or {}; hs, he = lay.get('hide_start'), lay.get('hide_end')
    slot = slot_of(gid, spec['_pick'], spec['_gun_clip']); out = {}
    if slot is None: return out
    van = curves(gid, slot); bc = part_curves(part_set, slot, list(van)) if part_set else None
    for n, d in van.items():
        if built and hs is not None and he - hs >= 3:      # the handle part set hpartset.py builds for this clip (rreload.handle_plan), computed in process: the stroke inside the hidden window
            import hpartset; st = hpartset.stroke(d, L['change_cm']); w0, w1 = hpartset.window(gate)
            s = np.array([d[int(round(min(hpartset.gun_frame(f, *st, w0, w1) if st else f, len(d) - 1)))] for f in range(N)])
        elif bc is not None: bd = bc[n]; s = np.array([bd[min(f, len(bd) - 1)] for f in range(N)])      # a built set plays key f at clip frame f
        else: s = np.array([d[int(round(min(clock(f, hs, he, delta) if hs is not None else f, len(d) - 1)))] for f in range(N)])
        ch = [f for f in range(1, N) if abs(s[f] - s[f - 1]) > L['change_cm']]
        vis = [f for f in ch if not (hs is not None and hs <= f <= he)]
        out[n] = {'change': [ch[0], ch[-1]] if ch else None, 'visible_change_f': vis, 'end_state_cm': round(float(s[-1]), 2), 'vanilla_end_cm': round(float(d[-1]), 2), 'end_vs_vanilla_cm': round(abs(float(s[-1] - d[-1])), 2)}
    return out


def end_transition(stem, side):
    """L1 numbers of a clip (stem without .glb): the gun's last move to the idle."""
    L = lim_l1(); g = Glb(stem + '.glb'); sp = json.load(open(stem + '.json')); c = Clip(g, sp['clip']); ix = {n: i for i, n in enumerate(g.names)}; N = sp['frames']
    P = np.array([np.array(c.world(f)[ix['Weapon' + side]][0]) * 100 for f in range(N)]); v = np.r_[0, np.linalg.norm(np.diff(P, axis=0), axis=1)]
    w0 = max(0, N - L['window']); tail = v[w0:]; pk = float(tail.max()); fe = max(f for f in range(w0, N) if v[f] >= L['frac'] * pk)
    slow = int(sum(1 for f in range(fe + 1, N) if L['slow_lo'] < v[f] < L['slow_hi']))
    return {'tail_frames': N - 1 - fe, 'slow_frames': slow, 'peak_cm_f': round(pk, 2), 'tail_path_cm': round(float(v[fe + 1:].sum()), 2)}


if __name__ == '__main__':
    for a in sys.argv[1:]:
        print(a, json.dumps(end_transition(a, 'Left' if '_left_' in a else 'Right')))
