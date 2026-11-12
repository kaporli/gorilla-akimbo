"""Gun geometry in gun axes (x = right, y = up, z = back; the muzzle is at the lowest z): body extents, magazine seat
and extents, where the hand holds it. Tells a front magazine from a bullpup.

usage: gungeo.py <gun id> ...       (weapon mesh and anim folders: WMESH, WANIM of weapons.json / the environment)
module: geo(gun id) -> dict
"""
import os, sys, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import Clip, qrot, qinv
from wclip import TClip

BODY_PARTS = ['base1_01', 'base1_02', 'rcv1_01', 'rcv1_01_stock_01', 'base_01']


def verts(path):
    g = Glb(path); out = []
    for m in g.j['meshes']:
        for pr in m['primitives']: out.append(np.asarray(g.acc(pr['attributes']['POSITION']), float))
    return np.concatenate(out)


def wanim(gun, kind):
    """Path of the gun's weapon anim glb: kind base1 (gun parts and mag_slot) or mag_std. Shared sets as fallback."""
    stem = gun.get('weapon_anim') or gun['mesh']
    names = [f'{stem}__{kind}.anims.glb']
    fam = stem.split('__')[0]
    if kind == 'mag_std': names += [f"{gun['mesh']}__mag_std.anims.glb", f'{fam}__mag_std.anims.glb']
    if kind == 'rcv1': names = [f'{stem}__rcv1.anims.glb', f'{fam}__rcv1.anims.glb']
    over = (gun.get('reload_anim') or {}).get(kind)
    if over: names.insert(0, over)
    for n in names:
        p = common.find('weapon_anims', n)
        if p: return p
    return None


def hand_in_gun(body='pma'):
    """Wrist joint and middle finger root of the right hand in gun axes (same for every gun: the weapon bone)."""
    g = Glb(common.need(common.idle_glb(body))); c = Clip(g, 'idlepose_shoulder'); W = c.world(0)
    gi = g.names.index('WeaponRight'); out = {}
    for n in ('RightHand', 'RightHandMiddle1', 'RightHandIndex1'):
        t = W[g.names.index(n)][0]; out[n] = [round(float(x), 3) for x in qrot(qinv(W[gi][1]), t - W[gi][0])]
    return out


def geo(gid):
    gun = common.gun(gid); G = gun['mesh']; out = {'id': gid, 'mesh': G}
    V = []
    for p in BODY_PARTS:
        f = common.find('weapon_meshes', f'{G}__{p}.glb')
        if f: V.append(verts(f))
    V = np.concatenate(V); out['body_min'] = V.min(0).round(3).tolist(); out['body_max'] = V.max(0).round(3).tolist()
    out['length'] = round(float(V[:, 2].max() - V[:, 2].min()), 3)
    b = wanim(gun, 'base1')
    if b and 'mag_slot' not in Glb(b).names: b = wanim(gun, 'rcv1')
    if b and 'mag_slot' in Glb(b).names:
        gb = Glb(b); an = [a['name'] for a in gb.j['animations']]
        c = TClip(gb, 'reload' if 'reload' in an else an[0]); st, sq = c.world(0)[gb.names.index('mag_slot')]
        out['slot'] = st.round(3).tolist()
        mf = common.find('weapon_meshes', f'{G}__mag_std_01.glb')
        if mf:
            M = np.array([st + qrot(sq, v) for v in verts(mf)[::7]])
            out['mag_min'] = M.min(0).round(3).tolist(); out['mag_max'] = M.max(0).round(3).tolist()
            out['mag_centre'] = ((M.min(0) + M.max(0)) / 2).round(3).tolist()
    out['hand'] = hand_in_gun()
    return out


if __name__ == '__main__':
    for gid in sys.argv[1:]:
        o = geo(gid); print(gid)
        for k, v in o.items(): print('   ', k, v)
