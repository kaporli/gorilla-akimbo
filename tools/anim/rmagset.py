"""Builds a rifle's dual-wield magazine set (glb) from the magazine tracks of its production reload clips, as
magtrack.py does for the Shingen: one set per gun (model variable owner), body and hand, holding reload, reload_01,
reload_02 and empty_reload, _01, _02; each clip name carries the track of the arm clip in the same slot of the arm
set, so the variant the graph picks plays its own track.

usage: rmagset.py <vanilla magazine set glb> <weapon set glb with mag_slot> <magazine mesh glb> <out glb>
                  <track json>=<clip name>:<keys> [...]

A track (authoring/reload/magtrack2.py) gives per frame the 4x4 of the magazine MESH in gun axes, a scale and a
state. The rifles' appearance has two animated components on this set, Magazine (mesh on mag_std, child of the
joint `magazine`) and MagazineReload (mesh on mag_stdr, child of `magazine_reload`). As in the game's own clips:
  empty reload   the leaving magazine is `magazine_reload` when the game's clip moves that joint, the fresh one
                 `magazine`; a gun whose clip moves one joint only (Hercules) gets both on `magazine`, one after the
                 other
  reload         both on `magazine`, one after the other; `magazine_reload` keeps the game's own track
A magazine that is gone or not there yet is at its seat with scale 0.001. Other joints keep the game's track.
Keys beyond the gun's own clip hold the last frame.
"""
import sys, os, json, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'authoring', 'reload'))
from glb import Glb

FPS = 30.0; SMALL = 0.001
EMPTY = ('empty_reload', 'empty_reload_01', 'empty_reload_02')
OLD = ('seated0', 'loose', 'guided', 'falling')


def m4(t, q):
    x, y, z, w = np.asarray(q, float) / np.linalg.norm(q); M = np.eye(4)
    M[:3, :3] = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    M[:3, 3] = t
    return M


def quat(R):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_matrix(R).as_quat()


def build(vanilla_glb, weapon_glb, mesh_glb, out, items):
    from wclip import TClip
    MG = Glb(vanilla_glb); gw = Glb(weapon_glb); an = [a['name'] for a in gw.j['animations']]
    SLOT = m4(*TClip(gw, 'reload' if 'reload' in an else an[0]).world(0)[gw.names.index('mag_slot')])
    sk = Glb(mesh_glb); s = sk.j['skins'][0]; leaf = sk.names[s['joints'][0]]; IBM = np.asarray(sk.acc(s['inverseBindMatrices']), float).reshape(-1, 4, 4)[0].T
    names = MG.names; par = {}
    for i, n in enumerate(MG.j['nodes']):
        for c in n.get('children', []): par[c] = i
    anims = []
    for track_path, name, keys in items:
        tr = json.load(open(track_path)); rows = tr['frames']; nt = len(rows); c = TClip(MG, name if name in [a['name'] for a in MG.j['animations']] else tr['clip'])
        cg = TClip(MG, tr['clip'])          # the gun's own clip of this kind: joint roles and the other joints' tracks
        W0 = cg.wf(0); two = 'magazine_reload' in names and 'mag_stdr' in names and 'magazine_reload' in cg.moved() and name in EMPTY and leaf != 'magazine'
        st = [r['state'] for r in rows]; rel = tr['release']
        role = ['seated0' if (st[f] == 'seated' and f < rel) else st[f] for f in range(nt)]
        seat = np.array(rows[-1]['m']).reshape(4, 4)
        # inverse bind of the second mesh joint: the two meshes coincide when both joints are at their seat (frame 0)
        Wl = m4(*W0[names.index(leaf if leaf in names else 'magazine')])
        IBM2 = np.linalg.inv(m4(*W0[names.index('mag_stdr')])) @ Wl @ IBM if 'mag_stdr' in names else IBM
        tracks = {}
        for k, node in enumerate(MG.j['nodes']):
            nm = node.get('name')
            if nm == 'Armature': continue
            T, Q, Sc = [], [], []
            for f in range(keys):
                ff = min(f, nt - 1, cg.frames - 1); t, q = cg.local(k, ff / FPS); sc = 1.0; M = None
                if nm == 'magazine':
                    r = role[min(f, nt - 1)]
                    if two:
                        if r in ('fresh', 'seated'): M = np.array(rows[min(f, nt - 1)]['m']).reshape(4, 4)
                        elif r == 'seated0' and np.linalg.norm(cg.local(k, ff / FPS)[0] - cg.local(k, 0.0)[0]) < 0.005: M = seat     # as the game: there until its clip takes it away
                        else: M = seat; sc = SMALL
                    else:
                        M = np.array(rows[min(f, nt - 1)]['m']).reshape(4, 4); sc = 1.0 if rows[min(f, nt - 1)]['s'] > 0.5 else SMALL
                    Wj = np.linalg.inv(SLOT) @ M @ np.linalg.inv(IBM) @ (np.linalg.inv(m4(*cg.local(names.index(leaf), 0.0))) if leaf != 'magazine' else np.eye(4))
                elif nm == 'magazine_reload' and two:
                    r = role[min(f, nt - 1)]
                    if r in OLD: M = np.array(rows[min(f, nt - 1)]['m']).reshape(4, 4)
                    else: M = seat; sc = SMALL
                    Wj = np.linalg.inv(SLOT) @ M @ np.linalg.inv(IBM2) @ np.linalg.inv(m4(*cg.local(names.index('mag_stdr'), 0.0)))
                if M is not None:
                    P = m4(*cg.wf(ff)[par[k]]) if k in par else np.eye(4); Lm = np.linalg.inv(P) @ Wj; t, q = Lm[:3, 3], quat(Lm[:3, :3])
                if Q and np.dot(q, Q[-1]) < 0: q = -np.asarray(q)
                T.append(t); Q.append(q); Sc.append([sc, sc, sc])
            tracks[k] = (np.array(T, np.float32), np.array(Q, np.float32), np.array(Sc, np.float32))
        ti = MG.add_acc((np.arange(keys) / FPS).astype(np.float32), 'SCALAR'); samplers, channels = [], []
        for k, (T, Q, Sc) in tracks.items():
            for path, arr, kind in (('translation', T, 'VEC3'), ('rotation', Q, 'VEC4'), ('scale', Sc, 'VEC3')):
                samplers.append({'input': ti, 'output': MG.add_acc(arr, kind), 'interpolation': 'LINEAR'}); channels.append({'sampler': len(samplers) - 1, 'target': {'node': k, 'path': path}})
        van = MG.anim(name) if name in [a['name'] for a in MG.j['animations']] else MG.anim(tr['clip'])
        ex = copy.deepcopy(van.get('extras', {})); ex['trackKeys'] = [x for x in ex.get('trackKeys') or [] if x['time'] < keys / FPS - 1e-4]
        ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
        anims.append({'name': name, 'samplers': samplers, 'channels': channels, 'extras': ex})
        print(f'{name:16s} <- {os.path.basename(track_path)} ({nt} frames, {keys} keys, {"two joints" if two else "one joint"})')
    MG.j['animations'] = anims; MG.save(out); print('saved', out)


if __name__ == '__main__':
    items = []
    for a in sys.argv[5:]:
        p, rest = a.rsplit('=', 1); name, keys = rest.split(':'); items.append((p, name, int(keys)))
    build(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], items)
