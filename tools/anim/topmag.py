"""Builds a top-magazine reload anim set (glb) from authored two-handed clips.

Each clip glb holds one animation (any name) on the dual-wield rig. They are stored under the game's reload clip
names (reload, reload_01, ...) with that name's metadata from the base set: its fallback pose slots (other slots
crash the game when sampled) and no sound events (the script plays each weapon's own reload sounds).

--phases: the reload clip gets the phase events the dual-wield graph's shell-loop End state plays (Loop on all but the
last two keys, LoopEnd on the last two), as rarmset.py --phases: a top-magazine gun's one-handed quick-drop fallback
(GorillaAkimboSmgShotgun) ends in that state, which plays this set's reload clip. The two-handed reload plays the whole
clip (phases unused).

usage: topmag.py <base glb> <out glb> <clip glb>=<name> [<clip glb>=<name> ...] [--phases]
"""
import sys
import numpy as np
from glb import Glb
from rarmset import PHASE_KEYS

argv = sys.argv[1:]; PHASES = '--phases' in argv
if PHASES: argv.remove('--phases')
BASE, OUT = argv[0], argv[1]
pairs = [a.rsplit('=', 1) for a in argv[2:]]

g = Glb(BASE)
base = Glb(BASE)
anims = []
for path, name in pairs:
    c = Glb(path)
    if [n.get('name') for n in c.j['nodes']] != [n.get('name') for n in g.j['nodes']]:
        raise SystemExit(f'{path}: node list differs from the base set')
    src = c.j['animations'][0]
    samplers = []
    for s in src['samplers']:
        a_in, a_out = c.j['accessors'][s['input']], c.j['accessors'][s['output']]
        samplers.append({'input': g.add_acc(c.acc(s['input']), a_in['type']),
                         'output': g.add_acc(c.acc(s['output']), a_out['type']),
                         'interpolation': s.get('interpolation', 'LINEAR')})
    ex = dict(base.anim(name)['extras'])
    ex['animEvents'] = [e for e in ex.get('animEvents') or [] if e.get('type') != 'Sound']
    ex['fallbackFrameIndices'] = list(base.anim(name)['extras'].get('fallbackFrameIndices') or [])
    # SIMD buffers, as flick.py: WolvenKit's compressed buffer with raw rotations breaks the first-person camera.
    ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
    frames = max(len(c.acc(s['input'])) for s in src['samplers'])
    if PHASES and name == 'reload':
        ev = dict.fromkeys(PHASE_KEYS)
        ex['animEvents'] = [e for e in ex['animEvents'] if e.get('type') != 'Phase'] + [
            dict(ev, type='Phase', eventName='Loop', startFrame=0, durationInFrames=frames - 2),
            dict(ev, type='Phase', eventName='LoopEnd', startFrame=frames - 2, durationInFrames=2)]
    anims.append({'name': name, 'samplers': samplers, 'channels': [dict(ch) for ch in src['channels']], 'extras': ex})
    print(f'{name:16s} <- {path} ({frames} frames)')
g.j['animations'] = anims
g.save(OUT)
print('saved', OUT)
