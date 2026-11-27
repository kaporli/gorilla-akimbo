"""Guns that get a lowered stance (weapons.json: mesh, lowered.family) and their mesh points for the checks.

A gun's body is assembled as the Blender scene draws it (part_names): the manifest `parts` list (else <mesh>__base1_01.glb;
it can name another gun's receiver) plus, when present, the receiver (__rcv1_01), a fixed stock (__rcv1_01_stock_01)
and the parts named in its mesh_parts; the standard magazine sits on the weapon's mag_slot (weapon anim set
<mesh>__base1.anims.glb, or the gun's weapon_anim stem). Mesh and weapon anim glbs are WolvenKit exports found in the
folders of paths.weapon_meshes and paths.weapon_anims.

usage: guns.py [--guns id,id]   -> one line per model variable: family, mesh, extents in weapon bone space
  --guns   these guns (any gun with a mesh, lowered entry or not): mesh, extents, length in cm (every vertex)
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


def part_names(G):
    """Mesh part names (no .glb) of a gun body: the one assembly every measure and tune tool uses. The manifest `parts`
    (the scene's list), else <G>__base1_01; plus rcv1_01, rcv1_01_stock_01 and mesh_parts when their glb exists."""
    g = _gun(G); names = list(g.get('parts') or [G + '__base1_01'])
    for part in ['rcv1_01', 'rcv1_01_stock_01'] + list(g.get('mesh_parts', [])):
        n = f'{G}__{part}'
        if find(n + '.glb') and n not in names: names.append(n)
    return names


def assembled(G):
    """All vertices of the body and the seated standard magazine in weapon bone space (magazine on its slot when the
    weapon anims are known)."""
    P = [mesh(common.need(find(n + '.glb'))) for n in part_names(G)]
    mp = find(G + '__mag_std_01.glb')
    if mp and wanim(G):
        gw = Glb(wanim(G)); an = [x['name'] for x in gw.j['animations']]
        W0 = Clip(gw, 'reload' if 'reload' in an else an[0]).world(0)
        if 'mag_slot' in gw.names:
            st, sq = W0[gw.names.index('mag_slot')]; P.append(np.array([st + qrot(sq, x) for x in mesh(mp)]))
    return np.concatenate(P)


def length_cm(G):
    """Length of the assembled gun (z extent of assembled(G), every vertex), cm: the measure of the lowered family rule
    (checks.lowered.v1d_over_cm)."""
    z = assembled(G)[:, 2]
    return round(float(z.max() - z.min()) * 100, 1)


def verts(G, n=4000):
    """assembled(G), thinned to about n points."""
    if G in _cache: return _cache[G]
    P = assembled(G); P = P[::max(1, len(P) // n)]; _cache[G] = P
    return P


if __name__ == '__main__':
    _picked = common.opt(sys.argv, '--guns')
    if _picked:
        for _g in common.gun_list(_picked):
            G = _g.get('mesh')
            if not G: print(f'{_g["id"]:14s} (no mesh)'); continue
            P = verts(G); print(f'{_g["id"]:14s} {G:40s} x {P[:,0].min():+.2f}..{P[:,0].max():+.2f} y {P[:,1].min():+.2f}..{P[:,1].max():+.2f} z {P[:,2].min():+.2f}..{P[:,2].max():+.2f} length {length_cm(G)} cm')
        sys.exit(0)
    for var, (G, fam) in GUNS.items():
        if not G: print(f'{var:40s} {fam} (no mesh)'); continue
        P = verts(G); print(f'{var:40s} {fam} {G:40s} x {P[:,0].min():+.2f}..{P[:,0].max():+.2f} y {P[:,1].min():+.2f}..{P[:,1].max():+.2f} z {P[:,2].min():+.2f}..{P[:,2].max():+.2f}')
