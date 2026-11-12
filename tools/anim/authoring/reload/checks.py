"""Gate area `rreload` (build.sh check --only rreload --with-test): the production rifle reload clips and their sets.

run(bodies, jobs) -> rows as authoring/checks/gate.py prints them. Per clip (rgate.py): start and end pose against
the gun's raised idle, the hidden window (present, long enough, handle hit outside, no magazine on screen after
hide_start), no magazine hanging in the air, release velocity continuity, exit and insertion on the well axis, eye
distance, cover, wrist, reach, shoulder pull, body, gap to the other gun. Per built set (rreload.py round trip, when
WORK/rreload/roundtrip.txt exists): key count kept by the import, SIMD buffer, path against the source glb.
"""
import os, sys, json, concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, manifest


def _one(a):
    import rgate
    gid, pick, take, clip, side, body = a; d = manifest.path('rreload_clips'); p = f'{d}/{body}/{gid}_{side}_{pick}{take}_{clip}.json'
    if not os.path.exists(p): return (f'{body}/{gid}_{side}_{pick}{take}_{clip}', None)
    return (f'{body}/{gid}_{side}_{pick}{take}_{clip}', rgate.gate(p))


def run(bodies=None, jobs=4):
    import prod, rgate
    L = rgate.LIM; rows = []; row = lambda c, i, v, t, u, ok, n='': rows.append({'check': c, 'item': i, 'value': v, 'threshold': t, 'unit': u, 'ok': bool(ok), 'note': n})
    pl = prod.plan(bodies=list(bodies) if bodies else None)
    with concurrent.futures.ProcessPoolExecutor(jobs) as ex: res = list(ex.map(_one, pl))
    for item, o in res:
        if o is None: row('rreload: clip built', item, 0, 1, 'file', False); continue
        Lr = o['layout']; emin = min(L['eye_min_cm'], o['eye_idle_cm'] - 1.0)
        row('rreload: start pose', item, max(o['start_cm'], o['start_deg']), L['end_max_cm'], 'cm or deg', max(o['start_cm'], o['start_deg']) <= L['end_max_cm'])
        row('rreload: end pose', item, max(o['end_cm'], o['end_deg']), L['end_max_cm'], 'cm or deg', max(o['end_cm'], o['end_deg']) <= L['end_max_cm'])
        row('rreload: hidden window', item, o['hidden_frames'], L['hidden_min_frames'], 'frames', o['hidden_frames'] >= L['hidden_min_frames'], f"f{Lr['hide_start']}-{Lr['hide_end']}")
        row('rreload: window rules (hit outside, no magazine after hide_start)', item, len([f for f in o['fails'] if 'hidden' in f or 'after hide_start' in f]), 0, 'faults', not [f for f in o['fails'] if 'hidden' in f or 'after hide_start' in f])
        row('rreload: magazine hangs in the air', item, o['mag_hang'], L['mag_hang_frames'], 'frames', o['mag_hang'] <= L['mag_hang_frames'])
        row('rreload: release velocity jump', item, o['release_dv_cm_f'], L['release_dv_max_cm_f'], 'cm/frame', o['release_dv_cm_f'] <= L['release_dv_max_cm_f'])
        row('rreload: exit off the well axis', item, o['exit_off_axis_cm'], L['off_axis_max_cm'], 'cm', o['exit_off_axis_cm'] <= L['off_axis_max_cm'])
        row('rreload: insertion off the well axis', item, o['insert_off_axis_cm'], L['off_axis_max_cm'], 'cm', o['insert_off_axis_cm'] <= L['off_axis_max_cm'])
        row('rreload: eye distance (below the rule and the idle less 1 cm)', item, o['eye_cm'][0], round(emin, 1), 'cm', o['eye_cm'][0] >= emin, f"f{o['eye_cm'][1]}")
        row('rreload: screen cover', item, o['cover_peak'][0], L['cover_max_pct'], '%', o['cover_peak'][0] <= L['cover_max_pct'])
        row('rreload: wrist', item, o['wrist'][0], L['wrist_max_deg'], 'deg', o['wrist'][0] <= L['wrist_max_deg'])
        row('rreload: wrist with the hand on screen', item, o['wrist_view'], L['wrist_view_max_deg'], 'deg', o['wrist_view'] <= L['wrist_view_max_deg'])
        row('rreload: reach', item, o['reach'][0], L['reach_max'], 'ratio', o['reach'][0] <= L['reach_max'])
        row('rreload: shoulder pull', item, o['shoulder_pull_cm'], L['shoulder_pull_max_cm'], 'cm', o['shoulder_pull_cm'] <= L['shoulder_pull_max_cm'])
        row('rreload: gun inside the body blocks', item, o['body_cm'][0], L['body_min_cm'], 'cm', o['body_cm'][0] >= L['body_min_cm'])
        row('rreload: gap to the other gun', item, o['guns_gap_cm'][0], 0.5, 'cm', o['guns_gap_cm'][0] > 0.5)
    rt = manifest.path('work') + ('/test' if manifest.with_test() else '') + '/rreload/roundtrip.txt'
    if os.path.exists(rt):
        lines = [l for l in open(rt).read().splitlines() if l.strip()]; bad = [l for l in lines if l.startswith('BAD')]
        row('rreload: built sets round trip (keys kept, SIMD, path)', bad[0][4:90] if bad else f'{len(lines)} clips', len(bad), 0, 'bad clips', not bad)
    else:
        row('rreload: built sets round trip', 'not built: build.sh rreload --with-test', 1, 0, 'missing', False)
    return rows
