"""Regression: production clip (right, pma, empty reload) against the reviewed draft: gun path, every arm joint and
the magazine track per frame. usage: regress.py (writes ../../../../work/regress.txt)"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import Clip
D = common.mp('C:/Modding/anim-work/smg-shotgun')
CASES = [('senkoh', 'SG08A', 'round2-grip'), ('senkoh', 'SG13A', 'round2-grip'), ('senkoh', 'SG12A', 'round2-grip'), ('pulsar', 'SB43A', 'round3-bullpup'), ('pulsar', 'SB39A', 'round3-bullpup'),
         ('pulsar', 'SB38A', 'round3-bullpup'), ('warden', 'ST38B', 'round3-top'), ('warden', 'ST40B', 'round3-top'), ('warden', 'ST32B', 'round3-top')]
out = []
for gid, pk, rnd in CASES:
    a = f'{D}/production/clips/pma/{gid}_right_{pk}_empty_reload'; b = f'{D}/{rnd}/clips/pma/{gid}_right_{pk}_empty_reload'
    if not os.path.exists(a + '.glb'): continue
    ga, gb = Glb(a + '.glb'), Glb(b + '.glb'); ca, cb = Clip(ga, 'reload_draft'), Clip(gb, 'reload_draft'); N = json.load(open(b + '.json'))['frames']
    names = [n for n in gb.names if n and (n.startswith('Right') or n == 'WeaponRight') and 'Leg' not in n]
    dj = max(float(np.linalg.norm(np.array(ca.world(f)[ga.names.index(n)][0]) - np.array(cb.world(f)[gb.names.index(n)][0]))) for f in range(N) for n in names) * 100
    ta, tb = json.load(open(a + '_track.json')), json.load(open(b + '_track.json'))
    dm = max(float(np.abs(np.array(ra['m']) - np.array(rb['m'])).max()) for ra, rb in zip(ta['frames'], tb['frames']))
    s = f'{gid} {pk}: frames {N} / {ca.frames} keys; worst joint difference {dj:.4f} cm; worst track matrix element difference {dm:.6f}'
    print(s); out.append(s)
open(f'{D}/production/work/regress.txt', 'w').write('\n'.join(out) + '\n')
