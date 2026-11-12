"""Guns that get a lowered stance (weapons.json: mesh, lowered.family) and their mesh points for the checks.

A gun's body is <mesh>__base1_01.glb plus, when present, the receiver (__rcv1_01), a fixed stock (__rcv1_01_stock_01)
and the parts named in its mesh_parts; the standard magazine sits on the weapon's mag_slot (weapon anim set
<mesh>__base1.anims.glb, or the gun's weapon_anim stem). Mesh and weapon anim glbs are WolvenKit exports found in the
folders of paths.weapon_meshes and paths.weapon_anims.

usage: guns.py   -> one line per model variable: family, mesh, extents in weapon bone space
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import Clip, qrot

# model variable: (mesh stem or None, family)
GUNS = common.manifest.lowered_guns()


def find(name):
    return common.find('weapon_meshes', name)


def wanim(G):
    g = _gun(G)
    return common.find('weapon_anims', (g.get('weapon_anim') or G) + '__base1.anims.glb')


def _gun(G):
    for g in common.manifest.guns(all_=True):
        if g.get('mesh') == G:
            return g
    return {}


def mesh(path):
    g = Glb(path)
    return np.concatenate([g.acc(pr['attributes']['POSITION']) for m in g.j['meshes'] for pr in m['primitives']])


_cache = {}


def verts(G, n=4000):
    """Body + standard magazine vertices in weapon bone space (magazine on its slot when the weapon anims are known)."""
    if G in _cache: return _cache[G]
    P = [mesh(common.need(find(G + '__base1_01.glb')))]
    for part in ['rcv1_01', 'rcv1_01_stock_01'] + list(_gun(G).get('mesh_parts', [])):
        if find(f'{G}__{part}.glb'): P.append(mesh(find(f'{G}__{part}.glb')))
    mp = find(G + '__mag_std_01.glb')
    if mp and wanim(G):
        gw = Glb(wanim(G)); an = [x['name'] for x in gw.j['animations']]
        W0 = Clip(gw, 'reload' if 'reload' in an else an[0]).world(0)
        if 'mag_slot' in gw.names:
            st, sq = W0[gw.names.index('mag_slot')]; P.append(np.array([st + qrot(sq, x) for x in mesh(mp)]))
    P = np.concatenate(P); P = P[::max(1, len(P) // n)]; _cache[G] = P
    return P


if __name__ == '__main__':
    for var, (G, fam) in GUNS.items():
        if not G: print(f'{var:40s} {fam} (no mesh)'); continue
        P = verts(G); print(f'{var:40s} {fam} {G:40s} x {P[:,0].min():+.2f}..{P[:,0].max():+.2f} y {P[:,1].min():+.2f}..{P[:,1].max():+.2f} z {P[:,2].min():+.2f}..{P[:,2].max():+.2f}')
