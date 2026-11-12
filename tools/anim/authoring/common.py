"""Paths and tables for the authoring tools. Everything comes from weapons.json through manifest.py; no script
holds a path or a gun list.

Scripts in the subfolders start with:
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    import common
which also puts tools/anim on sys.path (manifest, glb, fk).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
ANIM = os.path.dirname(HERE)
for _p in (ANIM, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import manifest

path, paths, find = manifest.path, manifest.paths, manifest.find
BODIES = manifest.bodies()
SIDES = ('right', 'left')


def need(p):
    if not p or not os.path.exists(p):
        raise SystemExit(f'missing {p}: see weapons.json paths (game files: tools/anim/build.sh extract)')
    return p


def source(key, **kw):
    """glb export of a game file named in weapons.json game_files (reload_source, lowered_base)."""
    return manifest.gamefile(manifest.depot(manifest.load()['game_files'][key].format(**kw)), '.glb')


def idle_glb(body):
    """The dual-wield base set: idlepose_shoulder is the pose the graph returns to after a reload."""
    return source('lowered_base', body=body)


def reload_glb(body, side='right'):
    """The Lexington dual-wield set of one hand: the rig and template of the arm clips."""
    return source('reload_source', body=body, side=side)


def arm_mesh(body, side):
    """V's arm mesh glb, side 'l' or 'r'."""
    return find('arm_meshes', f'a0_000_{body}_base_hq__{side}.glb')


def anim_work(*parts):
    """A file of the authoring data folder (specs, drafts, renders; outside the repo, never deleted)."""
    return '/'.join((path('anim_work'),) + parts)


def work(*parts):
    """A folder for new authoring output (outside the repo); created."""
    d = '/'.join((path('authoring_work'),) + parts)
    os.makedirs(d, exist_ok=True)
    return d


def gun(key):
    """A gun by id, mesh stem or model variable; all guns, whatever their status."""
    for g in manifest.guns(all_=True):
        if key in (g['id'], g.get('mesh')) or key in manifest.gun_vars(g):
            return g
    raise SystemExit(f'weapons.json: no gun {key}')


def gun_list(arg=None, arm_only=True):
    """Guns of this build (GA_TEST=1 includes test content), or the comma separated ids given."""
    if arg:
        return [gun(i) for i in arg.split(',')]
    return manifest.arm_guns() if arm_only else manifest.guns()


def body_list(arg=None):
    return tuple(arg.split(',')) if arg else BODIES


def opt(argv, name, default=None):
    """Value of '--name value' in argv, removed from it."""
    if name in argv:
        i = argv.index(name); v = argv[i + 1]; del argv[i:i + 2]
        return v
    return default


def rifle_mag(key):
    """(vertices, triangles) of a rifle's standard magazine seated on its mag_slot (frame 0 of the weapon's reload),
    gun-local, as lowered/guns.py places it; None for other types or when a file is missing."""
    import numpy as np
    from glb import Glb
    from fk import Clip, qrot
    try:
        g = gun(key)
    except SystemExit:
        return None
    if g.get('type') != 'rifle' or not g.get('mesh'):
        return None
    mp = find('weapon_meshes', g['mesh'] + '__mag_std_01.glb')
    wa = find('weapon_anims', (g.get('weapon_anim') or g['mesh']) + '__base1.anims.glb')
    if not (mp and wa):
        return None
    gw = Glb(wa)
    if 'mag_slot' not in gw.names:
        return None
    an = [a['name'] for a in gw.j['animations']]
    t, q = Clip(gw, 'reload' if 'reload' in an else an[0]).world(0)[gw.names.index('mag_slot')]
    m = Glb(mp); V, T = [], []; n = 0
    for me in m.j['meshes']:
        for pr in me['primitives']:
            v = m.acc(pr['attributes']['POSITION']); i = m.acc(pr['indices']).astype(int).reshape(-1, 3)
            V.append(np.array([t + qrot(q, x) for x in v])); T.append(i + n); n += len(v)
    return np.vstack(V), np.vstack(T)
