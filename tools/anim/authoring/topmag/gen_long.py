"""Arm clips of the three long partner picks (lupper, axe, hang): top-magazine gun in one hand, a long gun in the other.
usage: gen_long.py [--picks lupper,axe,hang] [--sides left,right] [--bodies pma,pwa] [--guns id,id] [--out dir]
                   [--share id:id[+id],...] [--nobuild] [--jobs n]
Default guns: every gun of weapons.json that is its own long_partner. Guns fitted in one run may share a clip
(bumps within 3 mm), so a run with --guns for one new gun gives that gun its own fit and leaves the others alone.
Writes <out>/specs/<pick>/<side>_<body>_<gun>.json and <out>/clips/<body>/shingen_<side>_<pick>_<gun>.glb
(out defaults to the topmag work folder). Prints the contact per clip; run checks.py on <out>/clips after.
--share copperhead:umbra: one clip, named after the first gun, for guns that share a model variable (and so its sets).
Each gun is fitted alone, then the striking gun's bump is moved along the line between the fits to the point where
the worse of (depth / depth limit, miss / miss limit) over the guns is smallest (checks.py contact, hand included)."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common

PICKS = ('lupper', 'axe', 'hang')


LIM = {'depth': 0.005, 'miss': 0.010}   # checks.py contact_depth_long_cm, contact_miss_long_cm (m)


def contact(sp, side, gun):
    """signed depth (m, + penetration) of the gun and V's hand in the seated magazine box at the hit frame, as checks.py"""
    import numpy as np, geo
    sh, st = geo.SIDES[side]; ns = geo.load_spec(sp); f = 25
    P = np.vstack([geo.load(gun)['all'], geo.hand(sp['body'], st)])
    return float(geo.box_signed(geo.app(np.linalg.inv(geo.magJ(ns, sh, f)) @ geo.gunM(ns, st, f), P)).max())


def score(d):
    return max(d / LIM['depth'], -d / LIM['miss'])


def shared_fit(specs, side, main, others):
    """one spec for main and others: the bump on the line between their own fits that minimises the worst score"""
    import json as _j, numpy as np, geo
    st = geo.SIDES[side][1]
    def mv(sp): b = (sp.get('bumps') or {}).get(st); return np.array(b[0]['move']) if b else np.zeros(3)
    def win(): 
        for sp in specs.values():
            b = (sp.get('bumps') or {}).get(st)
            if b: return b[0]['f']
        return None
    w = win(); grp = [main] + others
    if w is None:
        sp = _j.loads(_j.dumps(specs[main]))
        sp['_share'] = {'guns': grp, 'contact_mm': {g: round(contact(sp, side, g) * 1000, 1) for g in grp}}
        return sp
    def at(m):
        sp = _j.loads(_j.dumps(specs[main])); sp.setdefault('bumps', {})
        if np.linalg.norm(m) > 1e-5: sp['bumps'][st] = [{'f': w, 'move': [round(float(x), 4) for x in m]}]
        else: sp['bumps'].pop(st, None)
        return sp
    best = None
    for o in others:
        a, b = mv(specs[main]), mv(specs[o])
        for t in np.linspace(-0.2, 1.2, 57):
            sp = at(a + t * (b - a)); c = {g: contact(sp, side, g) for g in grp}
            sc = max(score(v) for v in c.values())
            if best is None or sc < best[0]: best = (sc, sp, c, float(t))
    sc, sp, c, t = best
    sp['_share'] = {'guns': grp, 't': round(t, 3), 'score': round(sc, 3), 'contact_mm': {g: round(v * 1000, 1) for g, v in c.items()}}
    return sp


def run(job):
    pick, side, body, guns, out, build, share = job
    import importlib, geo
    mod = importlib.import_module('long_' + pick)
    res = mod.specs(side, body, guns)
    for main, others in share.items():
        if main in res:
            res[main] = shared_fit(res, side, main, [o for o in others if o in res])
            for o in others: res.pop(o, None)
    lines = []
    for g, sp in res.items():
        d = f'{out}/specs/{pick}'; os.makedirs(d, exist_ok=True)
        json.dump(sp, open(f'{d}/{side}_{body}_{g}.json', 'w'), indent=1)
        clip = f'{out}/clips/{body}/{geo.TOPGUN}_{side}_{pick}_{g}.glb'
        if build:
            geo.build(sp, clip)
        b = sp.get('bumps') or {}
        mv = next(iter(b.values()))[0]['move'] if b else [0, 0, 0]
        lines.append(f'{body} {side:5s} {pick:6s} {g:10s} bump mm {[round(x * 1000, 1) for x in mv]} {sp.get("_share") or sp.get("_bump", "")}')
    return lines


if __name__ == '__main__':
    a = sys.argv[1:]
    picks = (common.opt(a, '--picks') or ','.join(PICKS)).split(',')
    sides = (common.opt(a, '--sides') or 'left,right').split(',')
    bodies = common.body_list(common.opt(a, '--bodies'))
    guns = common.opt(a, '--guns')
    out = common.opt(a, '--out') or common.work('topmag')
    jobs = int(common.opt(a, '--jobs') or 6)
    share = {}
    for x in (common.opt(a, '--share') or '').split(','):
        if x: m, o = x.split(':'); share[m] = o.split('+')
    import geo
    guns = guns.split(',') if guns else geo.long_guns()
    guns = guns + [o for v in share.values() for o in v if o not in guns]
    todo = [(p, s, b, guns, out.replace('\\', '/'), '--nobuild' not in a, share) for p in picks for b in bodies for s in sides]
    if jobs > 1 and len(todo) > 1:
        from multiprocessing import Pool
        with Pool(min(jobs, len(todo))) as pool:
            res = pool.map(run, todo)
    else:
        res = [run(t) for t in todo]
    for lines in res:
        for l in lines:
            print(l)
