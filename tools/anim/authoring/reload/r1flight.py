"""Flight of the old magazine per draft: world velocity at release (x right, y up, z back), frames until it leaves the
first-person view, where it is gone. usage: r1flight.py <family module>"""
import os, sys, json, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, r1lib, rchecks, gungeo, common
import numpy as np
from glb import Glb
from fk import Clip
from magtrack2 import m4
F = importlib.import_module(sys.argv[1]); out = {}
for p in F.PICKS:
    s = json.load(open(f'{renv.OUT}/clips/pma/{r1lib.stem(F, p)}.json')); t = json.load(open(s['_track'])); g = Glb(s['out']); c = Clip(g, 'reload_draft'); i = g.names.index('WeaponRight')
    v = r1lib.magtrack2.vanilla(F.GUN, 'empty_reload'); cen = np.r_[v['centre'], 1]; V = gungeo.verts(common.find('weapon_meshes', common.gun(F.GUN)['mesh'] + '__mag_std_01.glb'))[::5]; V1 = np.c_[V, np.ones(len(V))]
    r = t['release']; seen = 0; P = []
    for f in range(r, s['frames']):
        row = t['frames'][f]; M = row.get('m2') if 'm2' in row else (row['m'] if row['state'] in ('seated', 'loose', 'falling') and f <= r + 40 else None)
        if M is None or (row['state'] == 'gone'): break
        G = c.world(f)[i]; W = m4(*G) @ np.array(M).reshape(4, 4); P.append((W @ cen)[:3])
        on = rchecks.screen(rchecks.place(G, (V1 @ np.array(M).reshape(4, 4).T)[:, :3]))[2].any()
        if f > r and on: seen = f - r
    vel = (P[1] - P[0]) * 100
    out[p] = {'vel_cm_f': [round(float(x), 1) for x in vel], 'seen_frames_after_release': seen}
    print(p, F.PICKS[p][0], 'velocity cm/f', out[p]['vel_cm_f'], 'in view for', seen, 'frames after the release')
json.dump(out, open(f'{renv.OUT}/measure/flight_round1.json', 'w'), indent=1)
