"""Handle part set (rule H1): the gun's own weapon set (base1 or rcv1, the set that holds the cocking handle, bolt, slider or lever) with one clip per reload slot,
same slot names and key counts as the arm set (as rpartset.py does for the tube guns), so it plays in step with the arm clip on the runtime clock (the hidden-window
stretch of ClipSpeed moves both).

Per clip, from its spec and gate file (`<stem>.json`, `<stem>_gate.json`): every joint holds the gun's vanilla clip of that slot, frame f at key f (what the game plays today,
unmapped), except the handle joints (hfix.curves): their vanilla stroke [a, b] (first and last frame in which the joint moves) is played inside the hidden window,
a at hide_start + 1 and b at hide_end - 1, linear between; before it the joint holds the vanilla frame a (the state the gun starts in), after it the frame b (the
vanilla end state). The visible frames carry no handle change and the last frame is the vanilla end state.
Frames past the vanilla clip hold its last frame. Keys past the clip's frames hold the last.

usage: hpartset.py <base set glb> <out glb> --gun <id> <stem>=<slot>:<keys> [...] [--report <json>]
                   (<base set glb>: the gun's base1 or rcv1 glb that holds the handle)
Exit 1 when a handle joint changes on a visible frame or ends off the vanilla end state (check() rebuilds every frame from the written keys).
check(): handle change frames against the hidden window, handle end state against the vanilla end, every other joint against the vanilla clip (cm).
"""
import sys, os, json, copy, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'authoring', 'reload'))
sys.path.insert(0, os.path.join(HERE, 'authoring', 'checks'))
import numpy as np
from glb import Glb
from wclip import TClip
import hfix

FPS = 30.0


def stroke(d, thr):
    """(first, last) vanilla frame in which a handle curve changes by more than thr per frame, None when it does not."""
    ch = [f for f in range(1, len(d)) if abs(d[f] - d[f - 1]) > thr]
    return (ch[0] - 1, ch[-1]) if ch else None


def gun_frame(f, a, b, w0, w1):
    """Vanilla frame played at key f by a handle joint with the stroke [a, b] hidden in the clip frames [w0, w1]."""
    if f <= w0: return float(a)
    if f >= w1: return float(b)
    return a + (f - w0) / (w1 - w0) * (b - a)


def window(gate):
    L = (gate or {}).get('layout') or {}; hs, he = L.get('hide_start'), L.get('hide_end')
    if hs is None or he - hs < 3: raise ValueError(f'no hidden window ({hs}, {he})')
    return hs + 1, he - 1


def build(base_glb, out_glb, items, gid):
    gb = Glb(base_glb); anims = []; rep = []; thr = hfix.lim()['change_cm']
    for stem, slot, keys in items:
        sp = json.load(open(stem + '.json')); gate = json.load(open(stem + '_gate.json')); n = sp['frames']; w0, w1 = window(gate)
        cv = hfix.curves(gid, slot)
        if slot not in [a['name'] for a in gb.j['animations']]: raise ValueError(f'{slot} not in {base_glb}')
        c = TClip(gb, slot); nv = c.frames; ti = gb.add_acc((np.arange(keys) / FPS).astype(np.float32), 'SCALAR'); samplers, channels = [], []
        strokes = {nm: stroke(d, thr) for nm, d in cv.items()}
        for k, nd in enumerate(gb.j['nodes']):
            nm = nd.get('name')
            if nm == 'Armature': continue
            T, Q = [], []
            for f in range(keys):
                fc = min(f, n - 1)
                g = gun_frame(fc, *strokes[nm], w0, w1) if strokes.get(nm) else float(min(fc, nv - 1))
                t, q = c.local(k, min(g, nv - 1) / FPS); q = np.asarray(q, float)
                if (Q and np.dot(q, Q[-1]) < 0) or (not Q and q[3] < 0): q = -q
                T.append(t); Q.append(q)
            for path, arr, kind in (('translation', np.array(T, np.float32), 'VEC3'), ('rotation', np.array(Q, np.float32), 'VEC4')):
                samplers.append({'input': ti, 'output': gb.add_acc(arr, kind), 'interpolation': 'LINEAR'}); channels.append({'sampler': len(samplers) - 1, 'target': {'node': k, 'path': path}})
        v0 = next(a for a in gb.j['animations'] if a['name'] == slot); ex = copy.deepcopy(v0.get('extras', {})); ex.pop('trackKeys', None); ex.pop('constTrackKeys', None)
        anims.append({'name': slot, 'samplers': samplers, 'channels': channels, 'extras': ex})
        rep.append({'slot': slot, 'stem': os.path.basename(stem), 'frames': n, 'keys': keys, 'window': [w0, w1], 'strokes': {k: v for k, v in strokes.items() if v}})
        print(f"{slot:16s} <- {os.path.basename(stem)} ({n} frames, {keys} keys, window {w0}-{w1}, handle {sorted(k for k, v in strokes.items() if v)})")
    gb.j['animations'] = anims; gb.save(out_glb)
    return rep


def check(base_glb, out_glb, items, gid):
    """H1 on the written set: per slot the handle change frames outside the window, the end state against the vanilla end, the other joints against the vanilla clip."""
    g0 = Glb(base_glb); g1 = Glb(out_glb); thr = hfix.lim()['change_cm']; res = []
    for stem, slot, keys in items:
        sp = json.load(open(stem + '.json')); gate = json.load(open(stem + '_gate.json')); n = sp['frames']; hs, he = gate['layout']['hide_start'], gate['layout']['hide_end']
        c0 = TClip(g0, slot); c1 = TClip(g1, slot); cv = hfix.curves(gid, slot); r = {'slot': slot, 'handle': {}, 'other_worst_cm': 0.0}
        for k, nm in enumerate(g1.names):
            if nm == 'Armature': continue
            if nm in cv:
                t0, q0 = c0.local(k, 0.0); d = []
                for f in range(keys):
                    t, q = c1.local(k, f / FPS); d.append(max(float(np.linalg.norm(t - t0)) * 100, float(np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(q, q0)))))) / 10)))
                d = np.array(d); ch = [f for f in range(1, keys) if abs(d[f] - d[f - 1]) > thr]
                r['handle'][nm] = {'change': [ch[0], ch[-1]] if ch else None, 'visible_change_f': [f for f in ch if not (hs <= f <= he)], 'end_vs_vanilla_cm': round(abs(float(d[-1]) - float(cv[nm][-1])), 3)}
            else:
                for f in range(min(n, keys)):
                    a = c0.local(k, min(f, c0.frames - 1) / FPS)[0]; b = c1.local(k, f / FPS)[0]; r['other_worst_cm'] = max(r['other_worst_cm'], float(np.linalg.norm(a - b)) * 100)
        r['other_worst_cm'] = round(r['other_worst_cm'], 4); res.append(r)
    return res


def roundtrip_clip(src, back, slot, keys, deg_tol=0.1):
    """Every joint of the set as written (src glb) against the set exported back (back glb), every key and halfway between.
    deg_tol: 0.1, or 0.5 for a clip in the game's compressed format with its own rotation compression (Dian 0.16 deg)."""
    a, b = TClip(src, slot), TClip(back, slot); names = [n for n in src.names if n != 'Armature']
    missing = sorted(set(names) - set(back.names)); cm = deg = 0.0
    for n in names:
        if n in missing: continue
        i, j = src.names.index(n), back.names.index(n)
        for f in np.arange(0, keys - 0.5, 0.5):
            at, aq = a.local(i, f / FPS); bt, bq = b.local(j, f / FPS)
            cm = max(cm, float(np.linalg.norm(at - bt)) * 100)
            deg = max(deg, float(np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(aq, bq)) / (np.linalg.norm(aq) * np.linalg.norm(bq))))))))
    ok = not missing and b.frames == keys and cm < 0.01 and deg < deg_tol
    return dict(ok=ok, joints=len(names), keys=keys, back_frames=b.frames, cm=round(cm, 5), deg=round(deg, 4), missing=missing)


if __name__ == '__main__':
    argv = sys.argv[1:]; rep = None; gid = None
    for flag in ('--report', '--gun'):
        if flag in argv:
            i = argv.index(flag); v = argv[i + 1]; del argv[i:i + 2]
            if flag == '--report': rep = v
            else: gid = v
    items = []
    for a in argv[2:]:
        s, rest = a.rsplit('=', 1); p = rest.split(':'); items.append((s, p[0], int(p[1])))
    r = build(argv[0], argv[1], items, gid)
    chk = check(argv[0], argv[1], items, gid)
    bad = [(c['slot'], k, v) for c in chk for k, v in c['handle'].items() if v['visible_change_f'] or v['end_vs_vanilla_cm'] > hfix.lim()['end_tol_cm']]
    print('handle fails:', len(bad), bad[:3], 'other joints worst', max(c['other_worst_cm'] for c in chk), 'cm')
    if rep: json.dump({'slots': r, 'check': chk}, open(rep, 'w'), indent=1)
    sys.exit(1 if bad else 0)
