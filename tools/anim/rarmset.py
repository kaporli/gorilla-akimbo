"""Builds a per-gun, per-hand rifle reload arm set (glb) from production clips (authoring/reload/prod.py), as topmag.py
does for the top-magazine sets: each clip glb holds one animation on the dual-wield rig and is stored under one of
the set's reload clip names with that name's metadata from the base set (fallback pose slots, no sound events, SIMD).

usage: rarmset.py <base glb> <out glb> <clip glb>[#<animation>]=<name>[:<keys>] [...] [--phases]
#<animation>: that animation of the glb instead of its first (a fallback-only gun's reload clip, from the base set's glb).
<keys>: pad the clip to this many keys by holding its last frame (the idle). WolvenKit's import keeps the key count
only for some lengths; the build pads to good_keys(n).
A clip longer than <keys> is an error. A name the base set lacks (reload_start, reload_loop: the dual-wield graph's
shell-loop slots the quick-drop fallback plays in) takes the metadata of the base set's reload clip.
--phases: the reload clips (reload, reload_l) get the phase events the graph's shell-loop End state plays: Loop on all
but the last two keys, LoopEnd on the last two (the idle), so after a fallback the End state plays two idle frames.
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

# fields of a Phase event as WolvenKit exports them (the game's Carnage arm set)
PHASE_KEYS = ('type', 'eventName', 'startFrame', 'durationInFrames', 'switches', 'params', 'paramCurves', 'dynamicParams', 'metadataContext',
              'onlyPlayOn', 'dontPlayOn', 'playerGenderAlt', 'emitterName', 'effectName', 'sequenceShift', 'breakAllLoopsOnStop', 'eventValue',
              'actionName', 'boneName', 'facialAnimName', 'leg', 'footPhase', 'voContext', 'isQuest', 'side', 'customEvent', 'workspotActions')


def good_keys(n):
    """The smallest key count >= n that WolvenKit's import keeps: it derives the frame count from the float32
    duration (n - 1) / 30, rounded up, so n survives only when that float is above the true value (tested on 34
    lengths from 80 to 208, production/import_length)."""
    while not float(np.float32((n - 1) / 30.0)) * 30.0 > (n - 1): n += 1
    return n


if __name__ == '__main__':
    argv = sys.argv[1:]; PHASES = '--phases' in argv
    if PHASES: argv.remove('--phases')
    BASE, OUT = argv[0], argv[1]
    g = Glb(BASE); base = Glb(BASE); anims = []; have = {a['name'] for a in base.j['animations']}
    for a in argv[2:]:
        path, name = a.rsplit('=', 1); keys = None
        if ':' in name: name, keys = name.split(':'); keys = int(keys)
        path, _, which = path.partition('#'); c = Glb(path)
        if [n.get('name') for n in c.j['nodes']] != [n.get('name') for n in g.j['nodes']]:
            raise SystemExit(f'{path}: node list differs from the base set')
        src = c.anim(which) if which else c.j['animations'][0]; n = max(len(c.acc(s['input'])) for s in src['samplers'])
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
        src_name = name if name in have else ('reload_l' if name.endswith('_l') else 'reload')
        ex = dict(base.anim(src_name)['extras'])
        ex['animEvents'] = [e for e in ex.get('animEvents') or [] if e.get('type') != 'Sound' and src_name == name]
        ex['fallbackFrameIndices'] = list(base.anim(src_name)['extras'].get('fallbackFrameIndices') or [])
        if PHASES and name in ('reload', 'reload_l'):
            kn = keys or n; ev = dict.fromkeys(PHASE_KEYS)
            ex['animEvents'] = [e for e in ex['animEvents'] if e.get('type') != 'Phase'] + [
                dict(ev, type='Phase', eventName='Loop', startFrame=0, durationInFrames=kn - 2),
                dict(ev, type='Phase', eventName='LoopEnd', startFrame=kn - 2, durationInFrames=2)]
        ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
        anims.append({'name': name, 'samplers': samplers, 'channels': [dict(ch) for ch in src['channels']], 'extras': ex})
        print(f'{name:18s} <- {path} ({n} keys' + (f', padded to {keys})' if keys and keys > n else ')') + (f', {crossings} sign crossings' if crossings else ''))
    g.j['animations'] = anims
    g.save(OUT); print('saved', OUT)
