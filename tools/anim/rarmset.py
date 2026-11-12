"""Builds a per-gun, per-hand rifle reload arm set (glb) from production clips (authoring/reload/prod.py), as topmag.py
does for the top-magazine sets: each clip glb holds one animation on the dual-wield rig and is stored under one of
the set's reload clip names with that name's metadata from the base set (fallback pose slots, no sound events, SIMD).

usage: rarmset.py <base glb> <out glb> <clip glb>=<name>[:<keys>] [...]
<keys>: pad the clip to this many keys by holding its last frame (the idle). WolvenKit's import keeps the key count
only for some lengths; the build pads to good_keys(n).
A clip longer than <keys> is an error.
Rotation tracks: author.py writes each frame's quaternion as it comes. Tracks that flip sign came back from the
import 2 to 46 cm off in the empty reload slots, and with sign continuity alone still up to 62 cm in some sets;
with w >= 0 on every key every slot comes back exact (production/research/slot_test*.txt). So: empty reload slots
get w >= 0 on every key (where a rotation passes w = 0 two neighbouring keys then differ in sign: printed as
crossings; whether the game interpolates across them cleanly needs a look in game); the reload slots, which came
back exact either way, keep one sign through the clip.
"""
import sys
import numpy as np
from glb import Glb

def good_keys(n):
    """The smallest key count >= n that WolvenKit's import keeps: it derives the frame count from the float32
    duration (n - 1) / 30, rounded up, so n survives only when that float is above the true value (tested on 34
    lengths from 80 to 208, production/import_length)."""
    while not float(np.float32((n - 1) / 30.0)) * 30.0 > (n - 1): n += 1
    return n


if __name__ == '__main__':
    BASE, OUT = sys.argv[1], sys.argv[2]
    g = Glb(BASE); base = Glb(BASE); anims = []
    for a in sys.argv[3:]:
        path, name = a.rsplit('=', 1); keys = None
        if ':' in name: name, keys = name.split(':'); keys = int(keys)
        c = Glb(path)
        if [n.get('name') for n in c.j['nodes']] != [n.get('name') for n in g.j['nodes']]:
            raise SystemExit(f'{path}: node list differs from the base set')
        src = c.j['animations'][0]; n = max(len(c.acc(s['input'])) for s in src['samplers'])
        if keys and n > keys: raise SystemExit(f'{path}: {n} keys, more than {keys}')
        samplers = []; crossings = 0
        for s in src['samplers']:
            t = np.asarray(c.acc(s['input']), np.float32).ravel(); v = np.asarray(c.acc(s['output']), np.float32)
            if v.ndim == 2 and v.shape[1] == 4:
                v = v.copy()
                if name.startswith('empty_reload'):      # every key with w >= 0
                    neg = v[:, 3] < 0; v[neg] = -v[neg]; crossings += int((np.sum(v[1:] * v[:-1], axis=1) < 0).sum())
                else:                                     # w >= 0 on the first key, no sign flip between keys
                    if v[0][3] < 0: v[0] = -v[0]
                    for k in range(1, len(v)):
                        if np.dot(v[k], v[k - 1]) < 0: v[k] = -v[k]
            if keys and len(t) == n and keys > n:      # animated track: hold the last key
                t = np.concatenate([t, np.arange(n, keys, dtype=np.float32) / 30.0]); v = np.concatenate([v, np.repeat(v[-1:], keys - n, 0)])
            samplers.append({'input': g.add_acc(t, 'SCALAR'), 'output': g.add_acc(v, c.j['accessors'][s['output']]['type']), 'interpolation': s.get('interpolation', 'LINEAR')})
        ex = dict(base.anim(name)['extras'])
        ex['animEvents'] = [e for e in ex.get('animEvents') or [] if e.get('type') != 'Sound']
        ex['fallbackFrameIndices'] = list(base.anim(name)['extras'].get('fallbackFrameIndices') or [])
        ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
        anims.append({'name': name, 'samplers': samplers, 'channels': [dict(ch) for ch in src['channels']], 'extras': ex})
        print(f'{name:18s} <- {path} ({n} keys' + (f', padded to {keys})' if keys and keys > n else ')') + (f', {crossings} sign crossings' if crossings else ''))
    g.j['animations'] = anims
    g.save(OUT); print('saved', OUT)
