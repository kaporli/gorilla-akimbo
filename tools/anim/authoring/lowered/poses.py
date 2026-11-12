"""Lowered-stance specs: a family (weapons.json lowered_families: template, right-hand offset and angles, clavicle)
plus a per-gun tune. The right-hand pose is given and mirrored for the left hand.
v1 low ready: SMGs and short guns. v2 high port: long guns; hands 10 cm higher and 2 cm nearer the body than its
template, muzzles 40 deg up, clavicles 20 deg forward and 15 deg down (wrist bend 55-57 deg -> about 14 deg)."""
import json, copy, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common

FAMILY = common.manifest.load()['lowered_families']


def mirror(o): return [-o[0], o[1], o[2]]
def mrot(e): return [e[0], -e[1], -e[2]]


def spec(family, body, out, tune=None):
    """tune: {'d': [dx,dy,dz] added to the right-hand offset, 'e': [p,y,r] added, 'clav': [..] replaces}"""
    f = FAMILY[family]; s = copy.deepcopy(json.load(open(os.path.join(common.ANIM, f['template']))))
    o = list(f['offset']); e = list(f['angles']); c = list(f['clavicle'])
    if tune:
        o = [a + b for a, b in zip(o, tune.get('d', [0, 0, 0]))]; e = [a + b for a, b in zip(e, tune.get('e', [0, 0, 0]))]
        c = tune.get('clav', c)
    s['lowered'] = {'Right': [o, e], 'Left': [mirror(o), mrot(e)]}
    s['clavicle'] = {'Right': c, 'Left': list(c)}  # the clavicle joints' local frames are already mirrored
    s['base'] = common.need(common.idle_glb(body)); s['out'] = out; s['id'] = f'{family}_{body}'
    s['tune'] = tune or {}
    return s


def production():
    """{pose: (family, tune or None)} of the guns of this build (weapons.json lowered.pose, family, tune)."""
    out = {}
    for g in common.manifest.arm_guns():
        low = g.get('lowered')
        if not low: continue
        t = {'d': low['tune']} if 'tune' in low else None
        if out.setdefault(low['pose'], (low['family'], t)) != (low['family'], t):
            raise SystemExit(f'weapons.json: pose {low["pose"]} has two definitions (gun {g["id"]})')
    return out
