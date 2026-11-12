"""The pose a reload clip starts and ends in: each hand in the raised idle of its own gun.

A tuned gun (raised family C) has its raised clips in <RAISED>/<body>/raised_C_<gun>.glb: idlepose_shoulder carries the
right arm, idlepose_shoulder_l the left arm. An untuned gun keeps the game's idlepose_shoulder of the dual-wield base
set. make(right gun, left gun, body) writes one glb with the clip "idle" (4 equal keys, every joint) that has the
right arm of the right gun's idle and the left arm of the left gun's idle; author.py takes it as src / template.

usage: rest.py <right gun id> <left gun id> [--body pma] [--out file.glb]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import Clip


def raised_entry(gid):
    """The gun's "raised" entry of weapons.json, or that of the gun whose arm sets it plays (shared model variable)."""
    g = common.gun(gid)
    if g.get('raised'): return g['raised']
    for o in common.manifest.guns(all_=True):
        if o['id'] != gid and o.get('arm_set') == g.get('arm_set') and o.get('raised'): return o['raised']
    return {'family': 'none'}


def idle_source(gid, body):
    """(glb, right clip, left clip, tuned?) of a gun's raised idle, from the manifest: guns[].raised.pose names the
    clip file <paths.raised_clips>/<body>/raised_<pose>.glb (the raised-pose production); the phase 1 draft
    raised_C_<gun>.glb is the fallback while that file is missing; family none = the game's dual-wield base set."""
    r = raised_entry(gid)
    if r.get('family', 'none') != 'none':
        p = f"{common.path('raised_clips')}/{body}/raised_{r['pose']}.glb"
        if os.path.exists(p): return p, 'idlepose_shoulder', 'idlepose_shoulder_l', True
        p = f'{renv.RAISED}/{body}/raised_C_{gid}.glb'
        if os.path.exists(p): return p, 'idlepose_shoulder', 'idlepose_shoulder_l', True
        raise SystemExit(f'{gid}: no raised idle clip for {body} ({r["pose"]})')
    return common.need(common.idle_glb(body)), 'idlepose_shoulder', 'idlepose_shoulder_l', False


def left_nodes(g):
    """Indices of the left arm: LeftShoulder and below, and the left arm IK helper joints."""
    nodes = g.j['nodes']; idx = {n: i for i, n in enumerate(g.names)}; out = set()

    def sub(i):
        out.add(i)
        for c in nodes[i].get('children', []): sub(c)
    sub(idx['LeftShoulder'])
    for n in ('arm_left_ik', 'Torso_World_LeftArm_Hand_IK_JNT', 'Torso_World_LeftArm_PoleVector_JNT', 'Torso_LeftArm_Hand_IK_JNT', 'Torso_LeftArm_PoleVector_JNT'):
        if n in idx: sub(idx[n])
    return out


def make(right, left, body='pma', out=None):
    out = out or f'{renv.OUT}/production/rest/{body}/rest_{right}_R__{left}_L.glb'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pr, cr, _, tr = idle_source(right, body); pl, _, cl, tl = idle_source(left, body)
    info = {'right_tuned': tr, 'left_tuned': tl, 'right_src': pr, 'left_src': pl}
    if os.path.exists(out) and os.path.getmtime(out) > max(os.path.getmtime(pr), os.path.getmtime(pl)): return out, info
    g = Glb(pr); R = Clip(g, cr); gl = Glb(pl); L = Clip(gl, cl)
    ln = left_nodes(g); a = g.anim(cr)
    animated = sorted({c['target']['node'] for c in a['channels']} | ln)
    tin = g.add_acc(np.arange(4) / 30.0, 'SCALAR'); samplers, channels = [], []
    for i in animated:
        if g.names[i] == 'Armature': continue
        if i in ln: t, r = L.local(gl.names.index(g.names[i]), 0)
        else: t, r = R.local(i, 0)
        if r[3] < 0: r = -r
        for path, v, kind in (('translation', t, 'VEC3'), ('rotation', r, 'VEC4')):
            samplers.append({'input': tin, 'output': g.add_acc(np.repeat(np.asarray(v, float)[None], 4, 0), kind), 'interpolation': 'LINEAR'})
            channels.append({'sampler': len(samplers) - 1, 'target': {'node': i, 'path': path}})
    a = dict(a); a['name'] = 'idle'; a['samplers'], a['channels'] = samplers, channels
    g.j['animations'] = [a]; g.save(out)
    return out, {'right_tuned': tr, 'left_tuned': tl, 'right_src': pr, 'left_src': pl}


if __name__ == '__main__':
    argv = sys.argv[1:]; body = common.opt(argv, '--body') or 'pma'; o = common.opt(argv, '--out')
    p, info = make(argv[0], argv[1], body, o); print('saved', p, info)
    g = Glb(p); W = Clip(g, 'idle').world(0)
    for n in ('WeaponRight', 'WeaponLeft', 'RightArm', 'LeftArm', 'RightHand', 'Hips', 'RightUpLeg', 'LeftUpLeg', 'RightLeg', 'Spine3', 'Head', 'RightForeArm', 'LeftForeArm', 'LeftHand'):
        print(f'  {n:14s}', np.round(W[g.names.index(n)][0], 3))
