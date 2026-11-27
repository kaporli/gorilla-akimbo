"""Shell and pump geometry of a tube shotgun from its game files (tube1.py reads it as <OUT>/ref/<gun>_geometry.json).
Recovered from round 1's carnage_geometry.json (no script was kept); this reproduces that file exactly:
  chamber      shell mesh matrix (mag_slot x shell joint x inverse bind, gun axes) on the empty reload's frame where
               the fresh shell is in the chamber (Carnage f76)
  port, tube   the reload clip's shell 6 frames before it is in, and when it is in (Carnage f18, f24)
  pump_point   the fore-end joint (Carnage cocking_handle, Tactician foreend) on frame 0, gun axes
  pump_curve   [gun frame, travel m] of the empty reload's opening stroke, quarter frames, from 2 frames before it
               moves to 0.25 f after it is fully back
  shell_centre the shell mesh's bounding-box centre (mesh axes)
usage: tubegeo.py check | <gun id> [--chamber f] [--tube f] [--port f]
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, gungeo
import numpy as np
from glb import Glb
from wclip import TClip
from magtrack2 import m4

PUMP = {'carnage': 'cocking_handle', 'tactician': 'foreend'}
# the Tactician's anim sets are named after w_shotgun__constitutional_arms_tactician, not its mesh stem (phase 1 probe)
WANIM = {'tactician': {k: common.mp(f'C:/Modding/_tools/gamefiles/ga-reloads/wanim/w_shotgun__constitutional_arms_tactician__{k}.anims.glb') for k in ('base1', 'mag_std')}}


def wanim(gid, kind):
    return WANIM[gid][kind] if gid in WANIM else gungeo.wanim(common.gun(gid), kind)


def shell_mats(gid, clip):
    gun = common.gun(gid); b = Glb(wanim(gid, 'base1')); m = Glb(wanim(gid, 'mag_std'))
    mp = common.find('weapon_meshes', gun['mesh'] + '__mag_std_01.glb'); sk = Glb(mp); s = sk.j['skins'][0]; leaf = sk.names[s['joints'][0]]
    ibm = np.asarray(sk.acc(s['inverseBindMatrices']), float).reshape(-1, 4, 4)[0].T
    tb = TClip(b, clip); tm = TClip(m, clip); S = m4(*tb.wf(0)[b.names.index('mag_slot')])
    return [S @ m4(*tm.wf(f)[m.names.index(leaf)]) @ ibm for f in range(tm.frames)], mp


def geometry(gid, chamber_f, tube_f, port_back=6):
    E, mp = shell_mats(gid, 'empty_reload'); Rl, _ = shell_mats(gid, 'reload'); b = Glb(wanim(gid, 'base1'))
    tb = TClip(b, 'empty_reload'); i = b.names.index(PUMP[gid]); t0 = tb.local(i, 0.0)[0]
    d = np.array([float(np.linalg.norm(tb.local(i, f / 120.0)[0] - t0)) for f in range(tb.frames * 4)])      # quarter frames
    mx = d.max(); st = int(np.argmax(d > 0.0005 * 10)); en = int(np.argmax(d >= mx - 1e-5))
    f0 = max(st - 8, 0); curve = [[k / 4.0, round(float(d[k]), 5)] for k in range(f0, en + 2)]
    V = gungeo.verts(mp); cen = (V.min(0) + V.max(0)) / 2
    pw = tb.wf(0)[i][0]
    return {'chamber': E[chamber_f].tolist(), 'port': Rl[tube_f - port_back].tolist(), 'tube': Rl[tube_f].tolist(), 'pump_point': [round(float(x), 4) for x in pw],
            'pump_curve': curve, 'pump_max': round(float(mx), 4), 'pump_dir': [0.0, -1.0, 0.0], 'shell_centre': [round(float(x), 4) for x in cen],
            '_source': {'chamber': f'empty_reload f{chamber_f}', 'port': f'reload f{tube_f - port_back}', 'tube': f'reload f{tube_f}', 'pump': PUMP[gid]}}


def check():
    ref = json.load(open(renv.OUT + '/ref/carnage_geometry.json')); g = geometry('carnage', 76, 24)
    for k in ('chamber', 'port', 'tube'): print(k, 'max element difference', round(float(np.abs(np.array(ref[k]) - np.array(g[k])).max()), 6))
    print('pump_point', ref['pump_point'], g['pump_point'], 'shell_centre', ref['shell_centre'], g['shell_centre'])
    rc = np.array(ref['pump_curve']); gc = np.array(g['pump_curve']); print('pump curve ref', rc[0], rc[-1], len(rc), 'new', gc[0], gc[-1], len(gc))
    common_f = [f for f in rc[:, 0] if f in gc[:, 0]]; print('curve max diff on common frames', max(abs(float(rc[rc[:, 0] == f][0, 1] - gc[gc[:, 0] == f][0, 1])) for f in common_f))


if __name__ == '__main__':
    argv = sys.argv[1:]
    if argv[0] == 'check': check()
    else:
        gid = argv[0]; o = lambda n: common.opt(argv, n); g = geometry(gid, int(o('--chamber')), int(o('--tube')), int(o('--port') or 6))
        json.dump(g, open(f'{renv.OUT}/ref/{gid}_geometry.json', 'w'), indent=1); print('wrote', g['_source'], g['pump_point'], g['pump_max'], g['shell_centre'])
