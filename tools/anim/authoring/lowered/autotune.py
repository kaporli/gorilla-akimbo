"""Per-gun tuning of the lowered family the pose rule gives. The length gives the preferred family (v1d when the assembled gun
is longer than checks.lowered.v1d_over_cm, else v1); it applies only if a tune passes every lowered check
(fit.py: the checks of build.sh check --only lowered, both bodies), else the other family is tried. Within a family the tune
is the footprint fit: the gun's top edge on screen near -0.78 (the bottom 11 % of the view, as the Saratoga + Shingen pair tested
in game), at least 25 cm from the eye, wrist bend at most 20 deg, best fit first; the first tune that passes the checks wins.

Prints, per gun with a mesh, the family, the tune found and the tune in weapons.json (lowered.tune). The result is entered in
weapons.json by hand: "lowered": {"family": "v1", "pose": "v1_<name>", "tune": [0, dy, dz]} (v1d: pose "v1d_<name>").
Target and limits: weapons.json checks.lowered (v1d_over_cm, autotune_top_edge, eye_min_cm, wrist_idle_max_deg and the check limits).

usage: autotune.py [--guns id,id] [--all] [--family v1|v1d] [--no-gate] [--out <json>]
  --family  tune for this family only, whatever the rule gives
  --no-gate footprint fit only (eye, wrist, top edge), no lowered checks: fast, not the rule
  --out     also writes {gun: {mesh, family, preferred, length_cm, tune, footprint, score, passes, failures, weapons_json}} there
            (passes: the checks are met; failures: what the best tune of the preferred family misses when another family was taken)
  without --guns: every v1 or v1d gun of this build (GA_TEST=1 includes test guns); --all also tunes the guns of another
  family (v2).
"""
import os, sys, itertools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from tune import footprint
from guns import length_cm
import fit as fitmod

T = common.manifest.load()['checks']['lowered']
TARGET, EYE_MIN, WRIST_MAX = T['autotune_top_edge'], T['eye_min_cm'], T['wrist_idle_max_deg']


def candidates(G, fam):
    """[(score, tune, footprint)] best first: eye and wrist limits met, top edge on screen."""
    out = []
    for ddy, ddz in itertools.product(np.arange(-0.06, 0.101, 0.01), (0.0, -0.03, -0.06)):
        t = {'d': [0, round(float(ddy), 3), ddz]}
        f = footprint(fam, G, t)
        if f['box'] is None: continue
        sc = abs(f['box'][3] - TARGET) + (10 if f['eye'] < EYE_MIN else 0) + (10 if f['wrist'] > WRIST_MAX else 0) + abs(ddz) * 0.5 + abs(ddy) * 0.3
        out.append((sc, t['d'], f))
    return sorted(out, key=lambda x: x[0])


def tune(G, fam='v1'):
    c = candidates(G, fam)
    return (c[0][0], {'d': c[0][1]}, c[0][2])


def fit(gid, G, fam, gate=True):
    """-> (score, tune, footprint, failures) of the best tune of the family that passes the checks, else of the best fit (failures of it)."""
    c = candidates(G, fam)
    ok = [x for x in c if x[2]['eye'] >= EYE_MIN and x[2]['wrist'] <= WRIST_MAX]
    if not gate or not ok: return c[0] + ([],)
    for tune_, f in fitmod.search(gid, fam, [x[1] for x in ok], first=True):
        if not f:
            x = next(x for x in ok if x[1] == tune_); return x + ([],)
    return c[0] + (fitmod.failures(gid, fam, ok[0][1]),)


if __name__ == '__main__':
    every = '--all' in sys.argv
    picked = common.opt(sys.argv, '--guns'); outj = common.opt(sys.argv, '--out'); force = common.opt(sys.argv, '--family'); gate = '--no-gate' not in sys.argv
    if not gate: sys.argv.remove('--no-gate')
    if force not in (None, 'v1', 'v1d'): sys.exit('autotune: --family is v1 or v1d')
    done, bad, res = set(), 0, {}
    for g in common.gun_list(picked):
        G, low = g.get('mesh'), g.get('lowered') or {}
        if not G or G in done or (low.get('family') not in ('v1', 'v1d') and not (every or picked)): continue
        done.add(G)
        length = length_cm(G); pref = force or common.lowered_family(length)
        order = [pref] if force else [pref] + [x for x in ('v1d', 'v1') if x != pref]
        chosen, pref_fail = None, []
        for fam in order:
            sc, t, f, fails = fit(g['id'], G, fam, gate)
            ok = not fails and f['eye'] >= EYE_MIN and f['wrist'] <= WRIST_MAX
            if fam == pref: pref_fail = fails
            if ok: chosen = (fam, sc, t, f); break
        passes = chosen is not None
        if not passes:   # no family passes: the preferred family's best fit, with what it misses
            sc, t, f, _ = fit(g['id'], G, pref, False); chosen = (pref, sc, t, f)
        fam, sc, t, f = chosen
        have = low.get('tune') if low.get('family') == fam else None
        same = have is not None and np.allclose(have, t)
        bad += have is not None and not same
        res[g['id']] = {'mesh': G, 'family': fam, 'preferred': pref, 'length_cm': length, 'tune': t, 'footprint': f, 'score': round(float(sc), 3), 'passes': passes,
                        'failures': pref_fail, 'weapons_json': have}
        print(f'{g["id"]:14s} {G:40s} {fam} ({length} cm, rule {pref}{"" if fam == pref else ", " + pref + " misses " + "; ".join(f"{n} {v} vs {l}" for n, v, l in pref_fail)}) tune {t} {f} score {sc:.3f}'
              f'{"" if passes else "  NO FAMILY PASSES"}  weapons.json: '
              f'{have if have is not None else "none (" + low.get("family", "no lowered entry") + ")"}{"" if same or have is None else "  DIFFERENT"}')
    if outj:
        import json
        json.dump(res, open(outj, 'w'), indent=1)
    sys.exit(1 if bad else 0)
