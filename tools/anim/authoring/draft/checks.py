"""Gate area `draft` (build.sh check --only draft): the owner's reload rules (R1 to R14, rules.json) on every reload clip of the manifest,
shipped and parked (rules, data and limits: authoring/checks/draftcheck.py, weapons.json checks.draft). No WolvenKit.

run(guns, bodies, jobs) -> rows as authoring/checks/gate.py prints them, one check per rule item, the worst clip shown.
GA_CLIPS_ROOT=<folder> checks <folder>/clips and <folder>/fallback instead of the manifest's folders (ga produce --out).
Per clip output: WORK/check/draft/<folder>/<clip>_draft.json (the shipped folders are not written), WORK/check/draft/summary.json.
A named baseline (weapons.json checks.draft.baselines) passes and is marked in the note.
"""
import os, sys, json, concurrent.futures
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..', 'checks')); sys.path.insert(0, os.path.join(HERE, '..', 'reload')); sys.path.insert(0, os.path.join(HERE, '..'))
import renv, common, manifest

UNITS = {'pump_outside_accel': 'frames', 'pump_closing_x_mean_peak': 'of peak gun speed', 'magazine_flight_off_g': 'frames', 'shell_flight_off_g': 'frames', 'fresh_moving_no_contact': 'frames', 'length': 'frames', 'keys': 'keys',
         'grip_pace_per_f': '1/frame', 'grip_peak_cm_f': 'cm/frame', 'stop_loss_max_cm_f': 'cm/frame', 'start_pose': 'cm or deg', 'end_pose': 'cm or deg', 'end_step_cm': 'cm', 'finger_torque_nm': 'N m', 'gun_path_cm': 'cm', 'gun_v90_cm_f': 'cm/frame', 'release_path_cm': 'cm', 'release_v90_cm_f': 'cm/frame',
         'discard_hand_margin_min': 'share of the half frame', 'discard_well_in_frame_share': 'of the release frames', 'post_gun_speed_cm_f': 'cm/frame', 'post_gun_accel_cm_f2': 'cm/frame^2', 'post_hand_speed_cm_f': 'cm/frame',
         'whole_gun_speed_cm_f': 'cm/frame', 'whole_gun_accel_cm_f2': 'cm/frame^2', 'whole_hand_speed_cm_f': 'cm/frame', 'still_run_frames': 'frames', 'hidden_frames_visible': 'frames', 'spin_peak_deg_f': 'deg/frame',
         'spin_at_entry_deg': 'deg', 'lift_offset_cm': 'cm', 'gun_cover_pct': '% of the screen', 'lift_pitch_deg': 'deg', 'inward_reach_min_cm': 'cm', 'lateral_reach_max_cm': 'cm'}


def lowered_items():
    """The lowered-stance variant clips of every gun with reload.lowered_variant (root 'lowered' or 'raised': <GA_CLIPS_ROOT>/<stance>/clips, else the folder of the manifest path key), same rules as the shipped clips."""
    out = []
    for g in manifest.load()['guns']:
        r = g.get('reload') or {}; lv = r.get('lowered_variant')
        if not lv or r.get('parked'): continue
        for stance, ent in (('lowered', lv), ('raised', r.get('raised_variant'))):
            if not ent: continue
            d = manifest.path(ent['clips']).rstrip('/')
            for body in manifest.bodies():
                for side in ('right', 'left'):
                    for clip in ('empty_reload', 'reload'):
                        for pk in lv['layout']:
                            if 'picks' in ent and pk[:-1] not in ent['picks'] + (ent.get('stance_only') or []): continue      # per-pick wiring: the other slots are the shipped clips (stance-only picks are checked too)
                            f = f'{d}/{body}/{g["id"]}_{side}_{pk}_{clip}.glb'
                            if not os.path.exists(f) and not os.path.exists(f[:-4] + '.json'): continue      # a gun whose two clips are one file (hercules, masamune) has no second name
                            out.append(dict(family=r['category'], gun=g['id'], body=body, side=side, pick=pk[:-1], take=pk[-1], clip=clip, kind='reload', shipped=f, rel=f'clips/{body}/{os.path.basename(f)}', parked=False, root=stance))
    return out


def run(guns=None, bodies=None, jobs=4):
    import regen, draftcheck
    items = regen.acceptance(regen.load_manifest(), os.environ.get('GA_PARKED') == '1') + lowered_items()      # parked clips are not shipped: checked only with GA_PARKED=1
    root = os.environ.get('GA_CLIPS_ROOT')      # ga produce --out: check the clips made in <root>/clips and <root>/fallback, not the shipped ones
    if root:
        for i in items: i['shipped'] = root.replace('\\', '/').rstrip('/') + '/' + i['root'] + '/' + i['rel']
    # a gun whose raised variant is wired plays it in the active stance: its shipped base clips are frozen inputs (approved.json), not outputs, and are not gated (rule V2)
    wired = {g['id'] for g in manifest.load()['guns'] if (lambda rv: rv.get('layout') and 'picks' not in rv)((g.get('reload') or {}).get('raised_variant') or {})}
    items = [i for i in items if not (i['root'] == 'clips' and i['gun'] in wired)]
    if guns: items = [i for i in items if i['gun'] in {g['id'] for g in guns}]
    if bodies: items = [i for i in items if i['body'] in bodies]
    out = manifest.path('work') + ('/test' if manifest.with_test() else '') + '/check/draft'; os.makedirs(out, exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(jobs) as ex: res = list(ex.map(draftcheck.check_pair, items, chunksize=4))
    rows = []; summary = []
    for it, r in res:
        d = f"{out}/{it['root']}/{it['body']}"; os.makedirs(d, exist_ok=True); json.dump(r, open(f"{d}/{r['clip']}_draft.json", 'w'), indent=1)
        summary.append({'clip': f"{it['root']}/{it['rel']}", 'family': r.get('family'), 'fails': r['fails'], 'baselines': r['baselines']})
        nm = (it['root'] + '/' if it['root'] in ('lowered', 'raised') else '') + r['clip']
        if not r.get('rules'): rows.append({'check': 'draft: clip measured', 'item': nm, 'value': 1, 'threshold': 0, 'unit': 'errors', 'ok': False, 'note': '; '.join(r['fails'])}); continue
        for rule, blk in r['rules'].items():
            for i in blk['items']:
                if i.get('skipped'): continue
                if i.get('not_measurable'):
                    rows.append({'check': f"draft {rule}: {i['name']} (not measurable)", 'item': nm, 'value': 0, 'threshold': 0, 'unit': '', 'ok': False, 'note': 'not measurable: ' + i['not_measurable']}); continue
                kind = i.get('kind', 'max'); note = (f"baseline {i['baseline']} ({i['baseline_value']})" if i.get('baseline') else i.get('note') or '')
                rows.append({'check': f"draft {rule}: {i['name']} ({'at most' if kind == 'max' else 'at least'})", 'item': nm, 'value': i['value'], 'threshold': i['limit'],
                             'unit': UNITS.get(i['name'], ''), 'ok': i['ok'], 'note': note})
    bl = [(s['clip'], s['baselines']) for s in summary if s['baselines']]
    if bl: rows.append({'check': 'draft: clips on a named baseline (weapons.json checks.draft.baselines)', 'item': bl[0][0], 'value': len(bl), 'threshold': 0, 'unit': 'clips', 'ok': True, 'note': bl[0][1][0]})
    json.dump(summary, open(out + '/summary.json', 'w'), indent=1)
    return rows
