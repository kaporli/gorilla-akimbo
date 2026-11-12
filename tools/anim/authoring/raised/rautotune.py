"""Per-gun tuning of a raised family: the smallest s (5 mm steps) whose idle cover is at or under the family target,
while the arm rules of checks.raised hold (reach, wrist, eye distance, gun gap). A gun that shares its model variable
(Umbra with the Copperhead) is tuned together with the gun that owns it: the larger s serves both.

Prints, per gun, the s found and the s in weapons.json; the result is entered by hand:
  "raised": {"family": "C", "pose": "C_<name>", "s": {"pma": 0.145, "pwa": 0.145}}
Guns without a raised entry and guns with family "none" are only measured in the game pose (over the limit or not).

usage: rautotune.py [--guns id,id] [--family C] [--bodies pma,pwa] [--out <json>]
  --family  tune the guns given with --guns for this family, whatever weapons.json says
  GA_TEST=1 includes test guns. Exit code 1 if a tuned s differs from weapons.json.
"""
import json, os, sys
import rpose as R
from rpose import common
import numpy as np

RULES = R.RULES


def evaluate(body, G, fam, s):
    rig, _ = R.base(body); out = {}
    for name, clip, aim in (('idle', R.IDLE, False), ('aim', R.AIM, True)):
        L0 = rig.sample(clip, 0.0); L = R.pose(body, L0, fam, s, aim=aim)[0] if fam and s > 0 else L0
        out[name] = R.measure(body, L, {'Right': G, 'Left': G}, L0)
    return out


def failures(m, game):
    r = m['idle']['Right']; bad = []
    if r['reach'] > RULES['reach_max']: bad.append('reach')
    if r['wrist'] > RULES['wrist_max_deg'] or r['wrist_vs_game'] > RULES['wrist_vs_game_max_deg']: bad.append('wrist')
    if r['eye'] < min(RULES['eye_min_cm'], game['idle']['Right']['eye']): bad.append('eye')
    if m['idle']['gap'] < min(RULES['gap_min_cm'], game['idle']['gap']): bad.append('gap')
    return bad


def tune(body, G, fam):
    """-> (s, metrics at s, note, game pose metrics)"""
    f = R.FAM[fam]; game = evaluate(body, G, None, 0.0)
    best = (0.0, game, 'no passing s'); s = RULES['step']
    if game['idle']['Right']['cover'] <= f['target']:
        return 0.0, game, 'at the target in the game pose', game
    while s <= f['s_max'] + 1e-9:
        m = evaluate(body, G, fam, s); bad = failures(m, game)
        if bad:
            return best[0], best[1], f'stopped by {",".join(bad)} at {s:.3f}, target not reached', game
        best = (round(s, 3), m, 'target reached')
        if m['idle']['Right']['cover'] <= f['target']: return best + (game,)
        s += RULES['step']
    return best[0], best[1], 's_max, target not reached', game


def line(m):
    r = m['Right']
    return (f"cover {r['cover']:5.1f} top {r['top']:5.2f} eye {r['eye']:5.1f} muzzle {r['muzzle']:.2f} grip {r['grip']:.2f} "
            f"wrist {r['wrist']:4.1f} ({r['wrist_vs_game']:+5.1f}) elbow {r['elbow']:3.0f} reach {r['reach']:.3f} gap {m['gap']:5.1f}")


if __name__ == '__main__':
    argv = sys.argv[1:]
    picked = common.opt(argv, '--guns'); force = common.opt(argv, '--family'); out = common.opt(argv, '--out')
    bodies = common.body_list(common.opt(argv, '--bodies'))
    res = {b: {} for b in bodies}; bad = 0
    for g in common.gun_list(picked):
        if not g.get('mesh') or not g.get('vars'): continue          # sharers are tuned with their owner
        ra = g.get('raised') or {}; fam = force or (ra.get('family') if ra.get('family') != 'none' else None)
        for body in bodies:
            if not fam:
                for o in R.sharers(g):
                    m = evaluate(body, o['mesh'], None, 0.0); c = m['idle']['Right']['cover']
                    why = 'family none (kept on purpose)' if ra.get('family') == 'none' else 'no raised entry'
                    print(f'{body} {o["id"]:11s} game pose  idle {line(m["idle"])}  [{why}; {"OVER" if c > RULES["limit_pct"] else "under"} the limit {RULES["limit_pct"]}]')
                    res[body][o['id']] = {'s': 0.0, 'family': None, 'game': m, 'note': why}
                continue
            rows = [(o,) + tune(body, o['mesh'], fam) for o in R.sharers(g)]
            s = max(r[1] for r in rows)
            for o, so, m, note, game in rows:
                if so != s: m = evaluate(body, o['mesh'], fam, s); note += f'; shares the variable: s {s:.3f} of the larger gun'
                print(f'{body} {o["id"]:11s} game pose  idle {line(game["idle"])}'); print(f'{"":15s} game pose  aim  {line(game["aim"])}')
                print(f'{"":15s} {fam} s={s:.3f} idle {line(m["idle"])}  [{note}]'); print(f'{"":15s} {fam}         aim  {line(m["aim"])}')
                res[body][o['id']] = {'s': s, 'family': fam, 'note': note, 'idle': m['idle'], 'aim': m['aim'], 'game': game,
                                      'delta_idle': R.delta(fam, s), 'delta_aim': R.delta(fam, s, True)}
            have = (ra.get('s') or {}).get(body)
            if not force and have is not None and abs(have - s) > 1e-9:
                print(f'{"":15s} weapons.json has s {have}: DIFFERENT'); bad += 1
            elif not force and have is None:
                print(f'{"":15s} weapons.json has no s for {body}'); bad += 1
    if out:
        for b in bodies:
            p = out.replace('{body}', b); os.makedirs(os.path.dirname(p) or '.', exist_ok=True); json.dump(res[b], open(p, 'w'), indent=1)
    sys.exit(1 if bad else 0)
