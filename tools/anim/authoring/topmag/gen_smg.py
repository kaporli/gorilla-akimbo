"""Arm clips of the single picks (flip, doubletap, uppercut) and of the pairs (overunder, scissor, clap).
usage: gen_smg.py [--picks flip,doubletap,uppercut] [--sides left,right] [--bodies pma,pwa] [--cats name,name]
                  [--pairs overunder,scissor,clap | --nopairs] [--out dir] [--nobuild]
A single pick is one spec per hand (data/picks: v10 v09 v06 = top-magazine gun left, m10 m09 m06 = right), made with
the Saratoga as partner. Per partner category (data/categories.json) the striking gun gets one smooth translation
("bump") along the striking feature's outward axis, so the category's guns meet the magazine at the contact frames
like the Saratoga did. Rotations, timing, the top-magazine gun's path and everything after f40 stay the pick's.
Female clips are the same specs on the female body.
Writes <out>/specs/smg/<name>.json and <out>/clips/<body>/shingen_<side>_<pick>[_<category>].glb, pair_SS_<pick>.glb
(out defaults to the topmag work folder). Run checks.py on <out>/clips after."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common, manifest
import geo
from geo import load_spec, gunM, pick_spec, PICKS, PAIRS, SIDES, DATA

# which columns of a family's shift_cm belong to which pick (table order: see partner.FAM)
COLS = {'v09': [0, 1], 'm09': [2, 3], 'v06': [0], 'm06': [1], 'v10': [0], 'm10': [1]}
# shifting axis: outward normal of the striking feature. doubletap: grip butt (gun -y), uppercut: receiver top
# (gun +y), flip: opposite of the mean push-out direction over all partners (data/axis_<pick>.json, world)
AX = {'v09': ('local', [0, -1, 0]), 'm09': ('local', [0, -1, 0]), 'v06': ('local', [0, 1, 0]), 'm06': ('local', [0, 1, 0]),
      'v10': ('world', [-x for x in json.load(open(DATA + 'axis_v10.json'))]),
      'm10': ('world', [-x for x in json.load(open(DATA + 'axis_m10.json'))])}
# bump windows [ramp in from, full at, full until, ramp out to]: full over the approach, contact(s) and follow-through
WIN = {'v10': [8, 15, 31, 40], 'm10': [8, 15, 31, 40], 'v09': [5, 12, 28, 38], 'm09': [5, 12, 28, 38],
       'v06': [9, 18, 28, 36], 'm06': [9, 18, 28, 36]}
# doubletap: follow-through 3 cm further out and up (f25..37, zero at the contact) so long stocks and the Dian
# clear the other forearm at f28-29
FT = {'v09': [0.03, 0.03, 0.0], 'm09': [-0.03, 0.03, 0.0]}


def axis(pid, ns=None):
    """world unit axis of a pick's bump (mean over its contact frames)"""
    side, _, frames, _ = PICKS[pid]; st = SIDES[side][1]
    ns = ns or load_spec(pick_spec(pid))
    kind, v = AX[pid]; v = np.array(v, float); v /= np.linalg.norm(v)
    axes = [gunM(ns, st, c)[:3, :3] @ v if kind == 'local' else v for c in frames]
    a = np.mean(axes, 0)
    return a / np.linalg.norm(a)


def category_spec(pid, cat, body='pma'):
    """the pick's spec with the category's bump. cat: an entry of data/categories.json"""
    side, _, _, fam = PICKS[pid]; st = SIDES[side][1]
    a = axis(pid)
    s = np.mean([cat['shift_cm'][i] for i in COLS[pid]]) / 100        # + = penetrates: move the gun back out
    spec = pick_spec(pid, body)
    spec['bumps'] = {st: [{'f': WIN[pid], 'move': [round(float(x), 4) for x in -s * a]}]}
    if pid in FT: spec['bumps'][st].append({'f': [25, 28, 31, 37], 'move': FT[pid]})
    spec['_partner'] = {'category': cat['name'], 'shift_cm': round(s * 100, 2), 'axis_world': np.round(a, 3).tolist(),
                        'members': cat['members']}
    return spec


def categories():
    return json.load(open(DATA + 'categories.json'))


if __name__ == '__main__':
    a = sys.argv[1:]
    picked = common.opt(a, '--picks')
    picks = (picked or ','.join(manifest.PICKS)).split(',')
    sides = (common.opt(a, '--sides') or 'left,right').split(',')
    bodies = common.body_list(common.opt(a, '--bodies'))
    only = common.opt(a, '--cats')
    pairs = common.opt(a, '--pairs')
    out = (common.opt(a, '--out') or common.work('topmag')).replace('\\', '/')
    build = '--nobuild' not in a
    top = common.gun(geo.TOPGUN)['topmag']
    os.makedirs(out + '/specs/smg', exist_ok=True)
    cats = categories()
    jobs = []                                                   # (clip name, pick id, category or None)
    for pid, (side, pick, _, fam) in PICKS.items():
        if pick not in picks or side not in sides:
            continue
        name = f'{top["clip_name"]}_{side}_{pick}'
        if not only:
            jobs.append((name, pid, None))
        for c in cats[fam]['cats']:
            if not only or c['name'] in only.split(','):
                jobs.append((f'{name}_{c["name"]}', pid, c))
    if '--nopairs' not in a and (pairs or not (only or picked)):    # pairs: on request, or in a full run
        for pid, pick in PAIRS.items():
            if not pairs or pick in pairs.split(','):
                jobs.append((f'pair_{top["pair_code"] * 2}_{pick}', pid, None))
    for name, pid, c in jobs:
        for body in bodies:
            spec = category_spec(pid, c, body) if c else pick_spec(pid, body)
            json.dump(spec, open(f'{out}/specs/smg/{name}_{body}.json', 'w'), indent=1)
            if build:
                geo.build(spec, f'{out}/clips/{body}/{name}.glb')
            b = (spec.get('bumps') or {})
            mv = next(iter(b.values()))[0]['move'] if b else [0, 0, 0]
            print(f'{body} {name:40s} bump cm {[round(x * 100, 2) for x in mv]}')
