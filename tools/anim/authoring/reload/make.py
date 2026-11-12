"""Builds reload drafts of a category and checks them.

usage: make.py <category> [draft ids csv] [--gun id] [--left id] [--clip empty_reload|reload] [--body pma]
               [--params '{"F01": {"hop": 0.05}}'] [--out dir] [--tag name]
Categories: front (front.py, default gun copperhead), masamune (masa.py), hercules (herc.py).
Output per draft: <out>/<category>/<id>/<id>[_tag].json (spec), .glb (clip), _ik.json, _checks.json, gen.py
(the call that rebuilds it, with its parameters), and a line in <out>/<category>/builds.log.
"""
import os, sys, json, importlib, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import rlib, rchecks

CATS = {'front': ('front', 'copperhead'), 'masamune': ('masa', 'masamune'), 'hercules': ('herc', 'hercules')}
GEN = '''"""{did} {name}: {doc}
Rebuilds this draft. Parameters of the motion are in PARAMS (empty = the defaults in {mod}.py)."""
import sys
sys.path.insert(0, 'C:/Modding/gg-work/reloads/tools/anim/authoring/reload')
import make
PARAMS = {params}
if __name__ == '__main__':
    make.one('{cat}', '{did}', PARAMS, gun='{gun}', left='{left}', clip=(sys.argv[1] if len(sys.argv) > 1 else '{clip}'), body='{body}')
'''


def summary(c):
    v = lambda k: c[k][0] if isinstance(c.get(k), list) else c.get(k)
    return (f"{c['draft']:4s} end {c['end_cm']:.3f}cm/{c['end_deg']:.3f}deg eye {v('eye_cm')} cover {v('cover_peak')}@{c['cover_peak'][1]} hidden {c['hidden']} "
            f"magfloat {c.get('mag_float')} insert {c.get('mag_insert_seen')} handle_seen {c.get('handle_seen')} wrist {v('wrist_swing')}/{c['wrist_view']} twist {v('wrist_twist')} "
            f"reach {v('reach')} sh {c['shoulder_pull_cm']} hands {v('hands_gap_cm')} guns {v('guns_gap_cm')}@{c['guns_gap_cm'][1]} body {v('body_cm')}@{c['body_cm'][1]} "
            f"spd {v('speed_cm_f')} L eye {v('left_eye_cm')} cover {v('left_cover_peak')} FAILS {c['fails']}")


def one(cat, did, params=None, gun=None, left=None, clip='empty_reload', body='pma', out=None, tag=None, quiet=False):
    mod, dgun = CATS[cat]; M = importlib.import_module(mod); name, fn = M.DRAFTS[did]
    gun = gun or dgun; left = left or gun; out = out or renv.OUT
    d = f'{out}/{cat}/{did}'; stem = did + (f'_{tag}' if tag else '') + ('' if clip == 'empty_reload' else f'_{clip}') + ('' if gun == dgun else f'_{gun}') + ('' if body == 'pma' else f'_{body}')
    spec, glb = rlib.build(did, gun, fn, params or {}, d, clip=clip, left=left, body=body, name=stem)
    spec['_name'] = name; spec['_doc'] = ' '.join((fn.__doc__ or '').split()); json.dump(spec, open(f'{d}/{stem}.json', 'w'), indent=1)
    c = rchecks.check(spec); c['name'] = name; json.dump(c, open(f'{d}/{stem}_checks.json', 'w'), indent=1)
    if stem == did:
        open(f'{d}/gen.py', 'w').write(GEN.format(did=did, name=name, doc=spec['_doc'], mod=mod, params=json.dumps(params or {}), cat=cat, gun=gun, left=left, clip=clip, body=body))
    with open(f'{out}/{cat}/builds.log', 'a') as f:
        f.write(json.dumps({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'stem': stem, 'params': params or {}, 'fails': c['fails']}) + '\n')
    if not quiet: print(summary(c))
    return spec, c


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n, d=None: common.opt(argv, n, d)
    gun, left, clip, body, out, tag = o('--gun'), o('--left'), o('--clip', 'empty_reload'), o('--body', 'pma'), o('--out'), o('--tag')
    params = json.loads(o('--params', '{}')); cat = argv[0]
    M = importlib.import_module(CATS[cat][0]); saved = getattr(M, 'PARAMS', {})
    ids = argv[1].split(',') if len(argv) > 1 else list(M.DRAFTS)
    for did in ids:
        p = dict(saved.get(did, {})); p.update(params.get(did, {}))
        one(cat, did, p, gun, left, clip, body, out, tag)
