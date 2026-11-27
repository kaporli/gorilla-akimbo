"""The pose rule (build.sh check, area "pose"): the lowered and raised family of every gun with a mesh equals what the
measures give. No category, no hand length: only the assembled gun.

  lowered   the length gives the preferred family: v1d when the assembled gun (parts and seated standard magazine, every vertex,
            z extent, authoring/lowered/guns.py length_cm) is longer than checks.lowered.v1d_over_cm, else v1. It applies only
            if a tune passes every lowered check (lowered/fit.py), else the other family. A gun in the preferred family is
            taken as passing (area lowered checks its clips); a gun in the other family must be shown to have no passing tune
            in the preferred one (every footprint-fit tune is run through the checks: slow, only for such guns)
  raised    C when the idle screen cover in the game's raised pose (both bodies, the larger) is over checks.raised.limit_pct,
            else none (the game pose)
A gun without a model variable of its own follows the gun whose variable it uses (same mesh or same arm set: Umbra with
Copperhead, Kyubi with Ajax, the generic double-barrel shotgun with Satara); its own measure must give that family too.
The per-gun tune (autotune.py) and s (rautotune.py) are not checked here: those tools exit 1 when weapons.json differs.

usage: checks.py [--guns id,id] [--bodies pma,pwa]
"""
import concurrent.futures, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import common
if HERE not in sys.path: sys.path.insert(0, HERE)     # the worker processes import posemeasure by name
import posemeasure

M = common.manifest.load()
LIM_LEN = M['checks']['lowered']['v1d_over_cm']
LIM_COVER = M['checks']['raised']['limit_pct']


def source(g, every):
    """The gun that owns the model variable g uses (g itself when it has one)."""
    if g.get('vars') or not g.get('mesh'): return g
    for o in every:
        if o is not g and o.get('vars') and o.get('mesh') and (o['mesh'] == g['mesh'] or (o.get('arm_set') and o.get('arm_set') == g.get('arm_set'))):
            return o
    return g


def other(g, fam):
    """[(tune, failures)] of every footprint-fit tune of family fam for the gun, through the lowered checks (main process)."""
    import autotune, fit
    c = [x[1] for x in autotune.candidates(g['mesh'], fam) if x[2]['eye'] >= autotune.EYE_MIN and x[2]['wrist'] <= autotune.WRIST_MAX]
    return fit.search(g['id'], fam, c)


def run(guns=None, bodies=None, jobs=None):
    bodies = bodies or common.BODIES; jobs = jobs or int(os.environ.get('JOBS', '4'))
    every = common.manifest.guns(all_=True)
    mine = [g for g in (guns or common.manifest.arm_guns()) if g.get('mesh')]
    meshes = sorted({g['mesh'] for g in mine})
    with concurrent.futures.ProcessPoolExecutor(jobs) as ex:
        got = {m: (L, c) for m, L, c in ex.map(posemeasure.measure, [(m, bodies) for m in meshes])}
    rows = []

    def add(check, item, v, thr, unit, ok, note=''):
        rows.append({'check': check, 'item': item, 'value': v, 'threshold': thr, 'unit': unit, 'ok': bool(ok), 'note': note})
    for g in sorted(mine, key=lambda g: g['id']):
        L, cov = got[g['mesh']]; c = max(cov.values()); s = source(g, every)
        low = s.get('lowered') or {}; ra = s.get('raised') or {}
        want_l = common.lowered_family(L); have_l = low.get('family')
        ok_l, why = have_l == want_l, ''
        if not ok_l and have_l in ('v1', 'v1d'):
            if s is g:
                tries = other(g, want_l)
                ok_l = not any(not f for _, f in tries)
                why = f'; {want_l} tried {len(tries)} tunes, ' + ('none passes every lowered check' if ok_l else 'one passes: the rule gives ' + want_l)
            else:   # shares another gun's pose: fine when that gun is itself in its other family
                ok_l = have_l != common.lowered_family(got[s['mesh']][0]); why = '; the gun it shares is in its other family' if ok_l else ''
        add('pose: lowered family = the length band, or the other one when no tune passes every lowered check', g['id'], L, LIM_LEN, 'cm', ok_l,
            f'rule {want_l}, weapons.json {have_l}' + (f' (via {s["id"]})' if s is not g else '') + why)
        if have_l in ('v1', 'v1d') and s is g:
            add('pose: lowered v1 or v1d has a tune and its own pose', g['id'], 0 if ('tune' in low and low.get('pose') == f'{have_l}_{g["mesh"].split("__")[1]}') else 1, 0, 'missing',
                'tune' in low and low.get('pose') == f'{have_l}_{g["mesh"].split("__")[1]}', f'pose {low.get("pose")}')
        want_r = common.raised_family(c); have_r = ra.get('family') or 'none'
        add('pose: raised family = C over the cover limit, else none', g['id'], c, LIM_COVER, '%', have_r == want_r,
            f'rule {want_r}, weapons.json {have_r}' + (f' (via {s["id"]})' if s is not g else ''))
        if have_r == 'C' and s is g:
            ok = all((ra.get('s') or {}).get(b) for b in bodies) and ra.get('pose') == f'C_{g["mesh"].split("__")[1]}'
            add('pose: raised C has s for both bodies and its own pose', g['id'], 0 if ok else 1, 0, 'missing', ok, f'pose {ra.get("pose")}')
    return rows


if __name__ == '__main__':
    argv = sys.argv[1:]
    picked = common.opt(argv, '--guns')
    rows = run(common.gun_list(picked) if picked else None, common.body_list(common.opt(argv, '--bodies')))
    bad = 0
    for r in rows:
        bad += not r['ok']
        print(f'{"pass" if r["ok"] else "FAIL"}  {r["check"]}: {r["item"]} {r["value"]} {r["unit"]} (limit {r["threshold"]}) {r["note"]}')
    sys.exit(1 if bad else 0)
