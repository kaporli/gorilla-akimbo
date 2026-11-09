"""Builds the glb for one lowered (safe) stance set (see lowsets.py): the authored clips stored with the metadata of the
same clips in the game's dual-wield base set: fallback pose slots, events without sounds, SIMD buffers.

usage: lowset.py <base set glb> <authored glb> <out glb> <right|left>
right keeps the plain names, left the _l names."""
import sys
from glb import Glb

BASE, SRC, OUT, SIDE = sys.argv[1:5]
NAMES = ['friendly_idlepose', 'safe_action', 'equip_safe']
NAMES = NAMES if SIDE == 'right' else [n + '_l' for n in NAMES]
g = Glb(BASE); base = Glb(BASE); c = Glb(SRC)
if [n.get('name') for n in c.j['nodes']] != [n.get('name') for n in g.j['nodes']]:
    raise SystemExit(f'{SRC}: node list differs from the base set')
anims = []
for name in NAMES:
    src = c.anim(name); samplers = []
    for s in src['samplers']:
        a_in, a_out = c.j['accessors'][s['input']], c.j['accessors'][s['output']]
        samplers.append({'input': g.add_acc(c.acc(s['input']), a_in['type']), 'output': g.add_acc(c.acc(s['output']), a_out['type']),
                         'interpolation': s.get('interpolation', 'LINEAR')})
    ex = dict(base.anim(name)['extras'])
    ex['animEvents'] = [e for e in ex.get('animEvents') or [] if e.get('type') != 'Sound']
    ex['fallbackFrameIndices'] = list(base.anim(name)['extras'].get('fallbackFrameIndices') or [])
    # SIMD buffers, as flick.py and topmag.py: WolvenKit's compressed buffer breaks the first-person camera.
    ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
    anims.append({'name': name, 'samplers': samplers, 'channels': [dict(ch) for ch in src['channels']], 'extras': ex})
g.j['animations'] = anims
g.save(OUT)
print('saved', OUT, ', '.join(NAMES))
