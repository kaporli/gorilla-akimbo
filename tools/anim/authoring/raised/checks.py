"""Numeric checks of the raised poses (build.sh check, area "raised"). Limits: weapons.json checks.raised.

Per raised pose and body, from the clip files (paths.raised_clips) and the reload sets the build made (WORK/tmp_reload):
  metric     per gun that uses the pose (a gun that shares the variable too): screen cover at or under the family
             target, eye distance, reach, wrist, gun-to-gun gap (the pair, and the gun beside one in the game pose),
             muzzle direction and hand on the grip against the game clip, idle and aim
  pose clips a clip that starts or ends in the idle in the game starts or ends in the raised idle; the other arm and
             the body are the game clip's
  reload     the six reload clips of the gun's own set start and end in the raised idle; equip ends there, unequip
             starts there, melee does both
  partner    top-magazine clips with the gun as partner: the partner arm starts and ends in the raised idle, the
             frames inside checks.raised.topmag_window and the other arm are the source clip's

usage: checks.py [--guns id,id] [--bodies pma,pwa] [--work <build work folder>]
"""
import concurrent.futures, math, os, sys
import rpose as R
from rpose import common
import numpy as np
from lpose import FPS

sys.path.insert(0, common.ANIM)
import raisedsets, topmagsets

T = R.RULES
RELOADS = ('reload', 'reload_01', 'reload_02', 'empty_reload', 'empty_reload_01', 'empty_reload_02')


def diff(ra, La, rb, Lb, names):
    """Max world position (cm) and rotation (deg) difference over the named joints of two poses (two rigs)."""
    WA, WB = ra.world(La), rb.world(Lb); dp = dr = 0.0
    for n in names:
        a, b = WA[ra.idx[n]], WB[rb.idx[n]]
        dp = max(dp, 100 * float(np.linalg.norm(a[0] - b[0])))
        dr = max(dr, math.degrees(2 * math.acos(min(1.0, abs(float(np.dot(a[1], b[1])))))))
    return dp, dr


def arm_names(rig, S):
    return [rig.names[j] for j in R.arm_joints(S)] + [f'Weapon{S}']


def other_names(rig, S):
    mine = set(arm_names(rig, S))
    # fingers and the gun's children follow the hand: everything under this side's shoulder moves with it
    under = set(); par = rig.par
    for i, n in enumerate(rig.names):
        j = i
        while j in par:
            if rig.names[j] in mine: under.add(n); break
            j = par[j]
    return [n for n in rig.names if n not in mine and n not in under and n != 'Armature']


def frames_of(rig, clip):
    return int(round(rig.duration(clip) * FPS)) + 1


def _pose(a):
    pose, body, fam, s, gun_ids = a
    rows = []; rig, _ = R.base(body); cg = R.rig_of(R.clip_glb(pose, body)); f = R.FAM[fam]
    tag = f'{body} {pose}'

    def add(check, item, v, thr, unit, ok, note=''):
        rows.append({'check': check, 'item': f'{tag} {item}'.strip(), 'value': v, 'threshold': thr, 'unit': unit, 'ok': bool(ok), 'note': note})
    # ---- metric, from the clips
    for name, clip in (('idle', R.IDLE), ('aim', R.AIM)):
        G0 = rig.sample(clip, 0.0); both = list(G0); one = {'Right': list(G0), 'Left': list(G0)}
        for S, c in (('Right', clip), ('Left', clip + '_l')):
            X = cg.sample(c, 0.0)
            for j in R.arm_joints(S): both[j] = X[j]; one[S][j] = X[j]
        for gid in gun_ids:
            G = common.gun(gid)['mesh']
            m = R.measure(body, both, {'Right': G, 'Left': G}, G0); g0 = R.measure(body, G0, {'Right': G, 'Left': G}, G0)
            for S in ('Right', 'Left'):
                r = m[S]
                add(f'raised: muzzle direction against the game pose, {name}', f'{gid} {S}', r['muzzle'], f'<= {T["muzzle_max_deg"]}', 'deg', r['muzzle'] <= T['muzzle_max_deg'])
                add(f'raised: hand on the grip, {name}', f'{gid} {S}', r['grip'], f'<= {T["grip_max_cm"]}', 'cm', r['grip'] <= T['grip_max_cm'])
                if name == 'idle':
                    lim = f['target'] + T['cover_over_target_max_pct']
                    add('raised: screen cover, idle (one gun)', f'{gid} {S}', r['cover'], f'<= {lim:.1f} (family target)', '%', r['cover'] <= lim + 1e-9, f'game pose {g0[S]["cover"]}')
                    e = min(T['eye_min_cm'], g0[S]['eye'])
                    add('raised: eye distance, idle', f'{gid} {S}', r['eye'], f'>= {e}', 'cm', r['eye'] >= e, f'game pose {g0[S]["eye"]}')
                    add('raised: reach (shoulder to wrist over arm length), idle', f'{gid} {S}', r['reach'], f'<= {T["reach_max"]}', '', r['reach'] <= T['reach_max'])
                    add('raised: wrist bend from the bind pose, idle', f'{gid} {S}', r['wrist'], f'<= {T["wrist_max_deg"]}', 'deg', r['wrist'] <= T['wrist_max_deg'], 'game pose 43')
                    add('raised: wrist change against the game pose, idle', f'{gid} {S}', r['wrist_vs_game'], f'<= {T["wrist_vs_game_max_deg"]}', 'deg', r['wrist_vs_game'] <= T['wrist_vs_game_max_deg'])
                else:
                    add('raised: screen cover, aim (one gun)', f'{gid} {S}', r['cover'], 'none', '%', True, f'for information; game pose {g0[S]["cover"]}')
            if name == 'idle':
                lim = min(T['gap_min_cm'], g0['gap'])
                add('raised: gun gap, the pair, idle', gid, m['gap'], f'>= {lim}', 'cm', m['gap'] >= lim, f'game pose {g0["gap"]}')
                for S in ('Right', 'Left'):
                    mm = R.measure(body, one[S], {'Right': G, 'Left': G}, G0)
                    add('raised: gun gap beside the same gun in the game pose, idle', f'{gid} {S}', mm['gap'], f'>= {lim}', 'cm', mm['gap'] >= lim)
            else:
                add('raised: gun gap, the pair, aim', gid, m['gap'], 'none', 'cm', True, f'for information; game pose {g0["gap"]}')
    # ---- pose clips: ends against the raised idle where the game clip ends in the game idle; the rest untouched
    I0 = rig.sample(R.IDLE, 0.0)
    for n in raisedsets.POSE_CLIPS:
        for S, suf in (('Right', ''), ('Left', '_l')):
            c = n + suf; names = arm_names(rig, S); RI = cg.sample(R.IDLE + suf, 0.0)
            nf = frames_of(rig, c)
            for t, where in ((0.0, 'start'), (rig.duration(c), 'end')):
                miss = diff(rig, rig.sample(c, t), rig, I0, names)[0]
                if n not in (R.IDLE,) and miss > 0.5: continue          # the game clip is not at the idle there
                got = diff(cg, cg.sample(c, min(t, cg.duration(c))), cg, RI, names)[0]
                add('raised: pose clip starts or ends in the raised idle', f'{c} {where}', round(got - miss, 4), f'<= {T["pose_clip_extra_cm"]} over the game clip', 'cm',
                    got <= miss + T['pose_clip_extra_cm'], f'game clip misses its idle by {miss:.3f}')
            oth = other_names(rig, S); w = 0.0
            for k in range(nf):
                w = max(w, diff(cg, cg.sample(c, min(k / FPS, cg.duration(c))), rig, rig.sample(c, k / FPS), oth)[0])
            add('raised: pose clip leaves the other arm and the body as the game clip', c, round(w, 4), '<= 0.001', 'cm', w <= 0.001)
    return rows


def _reload(a):
    pose, body, work = a
    rows = []; cg = R.rig_of(R.clip_glb(pose, body)); tag = f'{body} {pose}'

    def add(check, item, v, thr, unit, ok, note=''):
        rows.append({'check': check, 'item': f'{tag} {item}'.strip(), 'value': v, 'threshold': thr, 'unit': unit, 'ok': bool(ok), 'note': note})
    for S, side, suf in (('Right', 'right', ''), ('Left', 'left', '_l')):
        name = common.manifest.raised_reload_set(body, side, pose); glb = f'{work}/tmp_reload/{name}/{name}.glb'
        if not os.path.exists(glb):
            add('raised: the gun\'s own reload set is built', name, 1, '0 missing', 'sets', False, 'build.sh reload'); continue
        rg = R.rig_of(glb); names = arm_names(rg, S); RI = cg.sample(R.IDLE + suf, 0.0)
        for c in RELOADS:
            for t, where in ((0.0, 'first frame'), (rg.duration(c + suf), 'last frame')):
                dp, dr = diff(rg, rg.sample(c + suf, t), cg, RI, names)
                add(f'raised: reload clip {where} = raised idle, position', f'{name} {c + suf}', round(dp, 4), f'<= {T["end_max_cm"]}', 'cm', dp <= T['end_max_cm'])
                add(f'raised: reload clip {where} = raised idle, rotation', f'{name} {c + suf}', round(dr, 4), f'<= {T["end_max_deg"]}', 'deg', dr <= T['end_max_deg'])
        hand = [f'Weapon{S}', f'{S}Hand']
        for c, ends in (('equip', ('end',)), ('unequip', ('start',)), ('melee', ('start', 'end'))):
            for where in ends:
                t = 0.0 if where == 'start' else rg.duration(c + suf)
                dp, _ = diff(rg, rg.sample(c + suf, t), cg, RI, hand)
                add('raised: equip end, unequip start, melee ends against the raised idle (hand and gun)', f'{name} {c + suf} {where}', round(dp, 3),
                    f'<= {T["hand_clip_end_max_cm"]} (baseline: the game clips against the game idle)', 'cm', dp <= T['hand_clip_end_max_cm'])
    return rows


def _partner(a):
    body, src, pose, S = a
    rows = []; glb = topmagsets.raised_clip(src, pose); item = f'{body} {os.path.basename(glb)}'

    def add(check, v, thr, unit, ok, note=''):
        rows.append({'check': check, 'item': item, 'value': v, 'threshold': thr, 'unit': unit, 'ok': bool(ok), 'note': note})
    if not os.path.exists(glb):
        add('raised: top-magazine clip with the raised partner exists', 1, '0 missing', 'clips', False, 'authoring/raised/rmakeclips.py'); return rows
    rg, rs = R.rig_of(glb), R.rig_of(src); cg = R.rig_of(R.clip_glb(pose, body))
    c = rg.g.j['animations'][0]['name']; cs = rs.g.j['animations'][0]['name']; n = frames_of(rs, cs)
    names = arm_names(rg, S); RI = cg.sample(R.IDLE + ('' if S == 'Right' else '_l'), 0.0)
    for f, where in ((0, 'first frame'), (n - 1, 'last frame')):
        dp, dr = diff(rg, rg.sample(c, f / FPS), cg, RI, names)
        add(f'raised: top-magazine clip, partner arm {where} = raised idle, position', round(dp, 4), f'<= {T["end_max_cm"]}', 'cm', dp <= T['end_max_cm'])
        add(f'raised: top-magazine clip, partner arm {where} = raised idle, rotation', round(dr, 4), f'<= {T["end_max_deg"]}', 'deg', dr <= T['end_max_deg'])
    a0, b0 = T['topmag_window']; w = o = 0.0; oth = other_names(rg, S)
    for f in range(n):
        if a0 <= f <= b0: w = max(w, diff(rg, rg.sample(c, f / FPS), rs, rs.sample(cs, f / FPS), names)[0])
        o = max(o, diff(rg, rg.sample(c, f / FPS), rs, rs.sample(cs, f / FPS), oth)[0])
    add(f'raised: top-magazine clip, partner arm inside frames {a0} to {b0} = source clip', round(w, 4), '<= 0.001', 'cm', w <= 0.001)
    add('raised: top-magazine clip, the other arm and the body = source clip', round(o, 4), '<= 0.001', 'cm', o <= 0.001)
    add('raised: top-magazine clip length = source clip', frames_of(rg, c) - n, '0', 'frames', frames_of(rg, c) == n)
    return rows


def run(guns=None, bodies=None, work=None, jobs=None):
    """-> [{'check', 'item', 'value', 'threshold', 'unit', 'ok', 'note'}]"""
    bodies = bodies or common.BODIES; jobs = jobs or int(os.environ.get('JOBS', '4'))
    work = work or (common.manifest.path('work') + ('/test' if common.manifest.with_test() else ''))
    want = {g['id'] for g in guns} if guns else None
    pj, rj, tj = [], [], []; rows = []; seen = set()
    for g, ra in R.raised_guns():
        if want is not None and not ({o['id'] for o in R.sharers(g)} & want): continue
        if ra['pose'] in seen: continue
        seen.add(ra['pose'])
        for body in bodies:
            if not all(os.path.exists(R.clip_glb(ra['pose'], body, k)) for k in ('', '_hands')):
                rows.append({'check': 'raised: clips present', 'item': f'{body} {ra["pose"]}', 'value': 1, 'threshold': '0 missing', 'unit': 'poses', 'ok': False,
                             'note': 'authoring/raised/rmakeclips.py'}); continue
            pj.append((ra['pose'], body, ra['family'], ra['s'][body], [o['id'] for o in R.sharers(g)]))
            rj.append((ra['pose'], body, work))
    tj = [(b, src, pose, S) for b, src, pose, S in topmagsets.raised_sources(common.path('clips')) if b in bodies and pose in seen]
    with concurrent.futures.ProcessPoolExecutor(jobs) as ex:
        for fn, js in ((_pose, pj), (_reload, rj), (_partner, tj)):
            for r in ex.map(fn, js): rows += r
    if not rows:
        rows.append({'check': 'raised: guns with a raised pose in this build', 'item': 'none', 'value': 0, 'threshold': 'none', 'unit': 'poses', 'ok': True,
                     'note': 'nothing to check'})
    return rows


if __name__ == '__main__':
    argv = sys.argv[1:]
    work = common.opt(argv, '--work'); picked = common.opt(argv, '--guns')
    rows = run(common.gun_list(picked) if picked else None, common.body_list(common.opt(argv, '--bodies')), work=work)
    by = {}
    for r in rows: by.setdefault(r['check'], []).append(r)
    bad = 0
    for check, rs in by.items():
        fails = [r for r in rs if not r['ok']]; bad += len(fails)
        num = [r for r in rs if isinstance(r['value'], (int, float))]
        w = fails[0] if fails else max(num, key=lambda r: r['value']) if '<=' in rs[0]['threshold'] or rs[0]['threshold'] in ('none', '0') else min(num, key=lambda r: r['value'])
        print(f'{"FAIL" if fails else "pass"}  {check}: {w["value"]} {w["unit"]} ({w["threshold"]}) worst: {w["item"]}  [{len(rs)} items{", " + str(len(fails)) + " fail" if fails else ""}] {w["note"]}')
    sys.exit(1 if bad else 0)
