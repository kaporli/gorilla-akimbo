"""Numeric checks of the lowered stance clips, per gun and body (build.sh check runs these).

Per gun with a mesh, three pairs through the preview sequence (seq.py): the gun right with the reference gun left
(weapons.json checks.lowered.pair_reference, a long gun in v2), the reference right with the gun left, and two of
the gun. Checked: loop seam and clip ends against the idle's first frame, closest gun point to the eye in the lowered
idle, how much nearer than the game's raised pose the guns come anywhere, the gap between the guns, and the wrist
bend read from the clips (hand against forearm, relative to idlepose_shoulder).

usage: checks.py [--guns id,id] [--bodies pma,pwa] [--clips <dir>] [--out <dir>]
  --clips  <body>/lowered_<pose>.glb (default: paths.low_clips, then paths.low_clips_test)
  --out    also writes each pair's check file there (<body>_<right>_R__<left>_L_checks.txt)
"""
import concurrent.futures, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
CLIPS = ('friendly_idlepose', 'safe_action', 'equip_safe')
# Sequence labels whose frames are these clips alone (no blend with the game's raised pose).
OWN = ('lowered idle', 'safe_action', 'safe_action (fire pressed in safe zone)', 'equip_safe (draw)', 'Ready/Safe blend 0.3 s')


def clip_of(pose, body, clips=None):
    for d in ([clips] if clips else [common.path('low_clips'), common.path('low_clips_test')]):
        if os.path.exists(f'{d}/{body}/lowered_{pose}.glb'):
            return f'{d}/{body}/lowered_{pose}.glb'
    return None


def wrists(glb, body):
    """{clip: {'Right'|'Left': max wrist bend in degrees}}: the side's own clip (_l for the left)."""
    from lpose import Rig, Glb, FPS
    from fk import qmul, qinv
    r = Rig(Glb(glb)); b = Rig(Glb(common.need(common.idle_glb(body))))
    W0 = b.world(b.sample('idlepose_shoulder', 0))
    out = {}
    for clip in CLIPS:
        out[clip] = {}
        for S in ('Right', 'Left'):
            name = clip + ('_l' if S == 'Left' else '')
            fa, hd = r.idx[f'{S}ForeArm'], r.idx[f'{S}Hand']
            rel0 = qmul(qinv(W0[b.idx[f'{S}ForeArm']][1]), W0[b.idx[f'{S}Hand']][1])
            worst = 0.0
            for i in range(int(round(r.duration(name) * FPS)) + 1):
                W = r.world(r.sample(name, i / FPS))
                rel = qmul(qinv(W[fa][1]), W[hd][1])
                worst = max(worst, math.degrees(2 * math.acos(min(1, abs(float(np.dot(rel, rel0)))))))
            out[clip][S] = worst
    return out


def _pair(a):
    import seq
    rglb, lglb, rg, lg, body, out = a
    res = seq.run(rglb, lglb, rg, lg, body, out, write=False)
    res.pop('lines')
    return a, res


def _wr(a):
    return a, wrists(*a)


def run(guns=None, bodies=None, thresholds=None, clips=None, out=None, jobs=None):
    """-> [{'check', 'item', 'value', 'threshold', 'unit', 'ok', 'note'}], one row per check with the worst item."""
    T = dict(common.manifest.load()['checks']['lowered']); T.update(thresholds or {})
    guns = guns or common.gun_list()
    bodies = bodies or common.BODIES
    ref = common.gun(T['pair_reference'])
    jobs = jobs or int(os.environ.get('JOBS', '4'))
    pairs, wjobs, skipped, seen = [], set(), [], set()
    for g in guns:
        low = g.get('lowered')
        if not low: continue
        for body in bodies:
            glb = clip_of(low['pose'], body, clips); rglb = clip_of(ref['lowered']['pose'], body, clips) or clip_of(ref['lowered']['pose'], body)
            if not glb:
                skipped.append(f'{body} {g["id"]} (no lowered_{low["pose"]}.glb)'); continue
            wjobs.add((glb, body))
            if not g.get('mesh') or (g['mesh'], low['pose'], body) in seen: continue
            seen.add((g['mesh'], low['pose'], body))
            tag = lambda r, l: f'{out}/{body}_{r}_R__{l}_L' if out else None
            pairs += [(glb, rglb, g['id'], ref['id'], body, tag(g['id'], ref['id'])),
                      (rglb, glb, ref['id'], g['id'], body, tag(ref['id'], g['id'])),
                      (glb, glb, g['id'], g['id'], body, tag(g['id'], g['id']))]
    if out: os.makedirs(out, exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(jobs) as ex:
        pres = list(ex.map(_pair, pairs)); wres = list(ex.map(_wr, sorted(wjobs)))

    def name(a): return f'{a[4]} {a[2]} R + {a[3]} L'
    rows = []

    def row(check, worst, value, thr, unit, ok, note=''):
        rows.append({'check': check, 'item': worst, 'value': value, 'threshold': thr, 'unit': unit, 'ok': bool(ok), 'note': note})

    n = f'{len(pres)} pairs'
    if pres:
        a, v = max(((a, max(max(s[0], s[1]) for s in r['seam'].values())) for a, r in pres), key=lambda x: x[1])
        row('lowered: seam and clip ends against the idle', name(a), v, f'<= {T["seam_max"]}', 'cm or deg', v <= T['seam_max'], n)
        a, v = min(((a, r['labels']['lowered idle']['eye']) for a, r in pres), key=lambda x: x[1])
        row('lowered: eye distance, lowered idle', name(a), v, f'>= {T["eye_min_cm"]}', 'cm', v >= T['eye_min_cm'], n)
        # Under eye_min_cm the guns may come only a little nearer than the game's own raised pose does.
        a, v = max(((a, r['raised_eye'] - r['eye'] if r['eye'] < T['eye_min_cm'] else 0.0) for a, r in pres), key=lambda x: x[1])
        row(f'lowered: nearer to the eye than the raised pose (where under {T["eye_min_cm"]} cm)', name(a), v,
            f'<= {T["eye_closer_than_raised_max_cm"]} (baseline)', 'cm', round(v, 2) <= T['eye_closer_than_raised_max_cm'], n)
        # Gap: never under gun_gap_min_cm, or under the gap the pair has in the game's raised pose.
        a, v = max(((a, min(r['raised_apart'], T['gun_gap_min_cm']) - r['apart']) for a, r in pres), key=lambda x: x[1])
        row(f'lowered: gun gap under {T["gun_gap_min_cm"]} cm and under the raised pose gap', name(a), v, '<= 0', 'cm', round(v, 2) <= 0, n)
        a, v = min(((a, min(r['labels'][k]['apart'] for k in r['labels'] if k in OWN)) for a, r in pres), key=lambda x: x[1])
        row('lowered: gun gap, lowered idle and clips', name(a), v, 'none', 'cm', True, 'for information')
        a, v = min(((a, r['raised_apart']) for a, r in pres), key=lambda x: x[1])
        row('lowered: gun gap, game raised pose', name(a), v, 'none', 'cm', True, 'for information: the game pose')
    if wres:
        a, v = max((((os.path.basename(a[0]), a[1], S), w['friendly_idlepose'][S]) for a, w in wres for S in w['friendly_idlepose']), key=lambda x: x[1])
        row('lowered: wrist bend, lowered idle', f'{a[1]} {a[0]} {a[2]}', v, f'<= {T["wrist_idle_max_deg"]}', 'deg', round(v, 1) <= T['wrist_idle_max_deg'], f'{len(wres)} clips')
        a, v = max((((os.path.basename(a[0]), a[1], S, c), w[c][S]) for a, w in wres for c in w for S in w[c]), key=lambda x: x[1])
        row('lowered: wrist bend, any clip', f'{a[1]} {a[0]} {a[3]} {a[2]}', v, f'<= {T["wrist_max_deg"]} (baseline)', 'deg', round(v, 1) <= T['wrist_max_deg'], f'{len(wres)} clips')
    if skipped:
        row('lowered: clips present', skipped[0], len(skipped), '0 missing', 'clips', False, '; '.join(skipped[:6]))
    return rows


if __name__ == '__main__':
    argv = sys.argv[1:]
    guns = common.gun_list(common.opt(argv, '--guns'))
    rows = run(guns, common.body_list(common.opt(argv, '--bodies')), clips=common.opt(argv, '--clips'), out=common.opt(argv, '--out'))
    for r in rows:
        print(f'{"pass" if r["ok"] else "FAIL"}  {r["check"]}: {r["value"]:.3f} {r["unit"]} ({r["threshold"]}) worst: {r["item"]}  {r["note"]}')
    sys.exit(0 if all(r['ok'] for r in rows) else 1)
