"""Builds the glb for one raised-pose set: authored clips stored with the metadata of the same clips in the game's
dual-wield base set (float tracks, fallback pose slots, events without sounds, SIMD buffers). As lowset.py, for any
clip names.

usage: raisedset.py <base set glb> <authored glb> <out glb> <right|left> <name,name,...>
right keeps the plain names, left the _l names."""
import sys
from glb import Glb

BASE, SRC, OUT, SIDE, NAMES = sys.argv[1:6]
NAMES = NAMES.split(',')
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
    ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
    anims.append({'name': name, 'samplers': samplers, 'channels': [dict(ch) for ch in src['channels']], 'extras': ex})
g.j['animations'] = anims
g.save(OUT)
print('saved', OUT, ', '.join(NAMES))
