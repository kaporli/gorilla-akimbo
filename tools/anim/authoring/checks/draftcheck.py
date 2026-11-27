"""The `draft` check: the owner's reload rules on a reload clip (an arm clip with its magazine track and sidecars).
Limits: weapons.json checks.draft (each with its source in "_notes"). Measures: checks/survey.py (one row per clip), checks/physmeasure.py
(free parts), the gate file of rgate.py (start and end pose). Nothing is regenerated.

  Physics gates (checks.draft.phys_floor, the float-rounding floor, measured: see its note). A measure within the floor is zero.
  R3  free flight at g   a detached magazine in the air, and every shell outside contact that is not carried, moves at g with
                         constant spin (per-frame acceleration and spin change within the floors). Hand frames (loading and
                         ejection near the hands) are not judged; their count is in the note.
  R4a fresh part         a fresh magazine with no contact is still or in free flight at g; it does not move by itself.
  Reported, not gated (R1 block): release linear impulse (cm/f) and angular impulse (deg/f) of the first free step against the
                         carrier, and the carrier-energy bound (exit speed against the largest well-point step up to the release).
                         The model has no catch spring, friction or wall contact, so these are not limits.
  R2  loose parts        a part moves only while the gun drives it: frames where it travels outside every acceleration frame
                         of the gun (widened by 1 frame each side, which holds a magazine's slide out of the well after the
                         release). Gated: the pump, none. The magazine in the well, barrels (hinge) and shells are reported (the magazine and shells are judged by R3 and R4a).
                         The fresh magazine's approach speed over the gun's speed is reported.
  R2b pump closes while the gun moves   every closing run of the pump (cut from its own track, first to last moving frame) has a mean gun
                         speed of at least 0.16 of the clip's peak grip speed (weapons.json checks.draft.r2b_pump_closing_x_mean_min). Only
                         the pump closing is gated; every other part and direction is exempt (see the note in weapons.json). The median over the
                         peak and the share of run frames under 1 cm/f are reported in the R2b block, not gated.
  R4  timing budget      clip length and key count per family and take.
  R5  weight             grip pace (peak grip speed of the longest big move per cm of its length) and the speed lost in the hardest stop: lower bounds per family. No upper bounds.
  R6  start and end      first and last frame in the idle the game returns to (gate start/end, limits checks.rreload).
  R7  finger torque      net applied finger torque (I alpha minus the gravity moment, gun mass and inertia from the mesh, checks/fingertorque.py) on the
                         in-hand turn frames only (the gun turning relative to the hand, over 0.5 deg/f); at most checks.draft.finger_torque_nm. Arm-driven
                         turns are not judged. A spin the generator slowed to fit is listed in the R7 report (spec _finger).

  R8  sustained speed    lower bounds on the gun path (cm) and the 90th percentile gun speed (cm/f), over the whole clip and over the release phase (the gun
                         first leaving rest to release + 3), per family and take (checks.draft.r8_min; shipped approved clips, worst x 0.9). R5 bounds one frame;
                         this bounds how long the gun keeps moving (a slow clip with one fast frame fails).

  R10 arm swing speed    peak swing speed (deg/f) of each arm joint (clavicle, shoulder, elbow, wrist; checks/armspeed.py) at most checks.draft.r10_swing_max_deg_f
                         (worst of the 396 shipped and parked clips x 1.1). A joint that turns faster than any shipped clip in one frame reads as a snap, not an arm.

usage: draftcheck.py [--family f] [--take A|B] [--out dir] <clip.json | clip.glb | folder> ...
       (build.sh check --only draft runs every clip of the manifest through authoring/draft/checks.py)
A clip is named by its spec (.json) or glb; the glb, _track, _gate, _phys, _objects sit beside it. Writes <clip>_draft.json
next to the clip, or into --out. Exit code 1 when a clip fails a rule that is not a named baseline.
"""
import os, sys, json, fnmatch, glob
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..', 'reload'))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import renv, common, manifest

RULES = ('R1', 'R2', 'R2b', 'R3', 'R4', 'R4a', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R18', 'TM1', 'H1', 'H2')


def limits():
    return manifest.load()['checks']['draft']


def gate_of(base, spec):
    """The gate numbers of a clip: its _gate.json, else rgate.gate on the clip (needs the paths of its spec to exist); None if neither."""
    p = base + '_gate.json'
    if os.path.exists(p): return json.load(open(p))
    try:
        import rgate
        s = dict(spec, out=base + '.glb', _track=base + '_track.json')
        return rgate.gate(s)
    except Exception as e:
        return {'_error': f'{type(e).__name__}: {e}'[:200]}


def _lim(table, family, default=None):
    return table.get(family, default) if isinstance(table, dict) else table


def evaluate(row, gate, L=None):
    """-> {'rules': {R: {ok, items: [{name, value, limit, ok, baseline?}]}}, 'fails': [...], 'baselines': [...]} for one survey row."""
    L = L or limits(); fam = row.get('family'); take = row.get('take'); name = os.path.basename(row['shipped_glb'])[:-4]
    mg = row.get('mag'); r2 = row.get('r2') or {}; r5 = row.get('r5') or {}
    base_pat = [(pat, v) for pat, v in L.get('baselines', {}).items() if fnmatch.fnmatch(name, pat)]
    out = {r: {'items': []} for r in RULES}

    def add(rule, item, value, limit, kind='max', note=None):
        if value is None or limit is None: out[rule]['items'].append({'name': item, 'value': value, 'limit': limit, 'ok': True, 'skipped': True, 'note': note or 'no value'}); return
        ok = value <= limit if kind == 'max' else value >= limit; it = {'name': item, 'value': value, 'limit': limit, 'kind': kind, 'ok': bool(ok)}
        if not ok:
            for pat, v in base_pat:
                if item in v and (value <= v[item] if kind == 'max' else value >= v[item]): it.update(ok=True, baseline=pat, baseline_value=v[item])
        out[rule]['items'].append(it)
    def not_measurable(rule, item, why, limit=None):
        """A rule that applies to this family but cannot be measured on this clip: a failing verdict, never a silent pass."""
        out[rule]['items'].append({'name': item, 'value': None, 'limit': limit, 'ok': False, 'not_measurable': why})
    # R1: reported, not gated (see the docstring)
    ph = row.get('phys') or {}; pm = ph.get('mag') or {}; rel = pm.get('release') or {}
    out['R1']['report'] = {'mechanism': (mg or {}).get('mode'), 'thrown': (mg or {}).get('thrown'), 'exit_cm_f': (mg or {}).get('exit_cm_f'), 'gun_at_well_cm_f': (mg or {}).get('gun_rel_cm_f'), 'exit_over_gun': (mg or {}).get('ratio'),
                           'release_linear_impulse_cm_f': rel.get('linear_cm_f'), 'release_angular_impulse_deg_f': rel.get('angular_deg_f'), 'guided_frames': rel.get('guided_frames'),
                           'carrier_energy': {k: rel.get(k) for k in ('exit_cm_f', 'carrier_max_cm_f', 'carrier_margin_cm_f')} if rel.get('carrier_margin_cm_f') is not None else None}
    # R2
    ex = L['r2_outside_accel_max']
    if 'pump' in r2: add('R2', 'pump_outside_accel', r2['pump']['travel_outside_accel'], ex['pump'])
    out['R2']['report'] = {'magazine_outside_accel': (r2.get('magazine') or {}).get('travel_outside_accel'), 'barrels_outside_accel': (r2.get('barrels') or {}).get('travel_outside_accel'), 'shells_outside_accel': (r2.get('shells') or {}).get('travel_outside_accel'),
                           'fresh_approach_over_gun': max([r['ratio'] for r in mg['fresh_runs']], default=None) if mg and mg.get('fresh_runs') else None}
    # R2b: the pump slides home while the gun drives it, not after the gun has come to rest
    rb = row.get('r2b'); lim_b = L.get('r2b_pump_closing_x_mean_min'); pumped = fam in L.get('r2b_pump_families', [])
    if rb is not None:
        out['R2b']['report'] = {'pump_closing_runs': rb['closing'], 'peak_cm_f': rb['peak_cm_f']}
        if rb['closing'] and lim_b is not None: add('R2b', 'pump_closing_x_mean_peak', min(r['x_mean_peak'] for r in rb['closing']), lim_b, 'min')
        elif pumped: not_measurable('R2b', 'pump_closing_x_mean_peak', 'no pump closing run in the clip', lim_b)
    elif pumped: not_measurable('R2b', 'pump_closing_x_mean_peak', 'no pump track (_pump_cm) in the clip', lim_b)
    # R3 and R4a: physics gates on the free parts (checks/physmeasure.py)
    if row.get('phys_error'):
        for rule, item in (('R3', 'free_flight_off_g'), ('R4a', 'fresh_moving_no_contact')):
            if (rule == 'R3' and (mg or r2.get('shells'))) or (rule == 'R4a' and mg): not_measurable(rule, item, 'physics measure failed: ' + row['phys_error'][-120:])
    else:
        if pm.get('flight') is not None: add('R3', 'magazine_flight_off_g', pm['flight']['off_g'], 0)
        po = ph.get('objects')
        if po is not None and po.get('objects'):
            add('R3', 'shell_flight_off_g', po['flight_off_g'], 0)
            out['R3']['report'] = {'worst_x_floor_magazine': (pm.get('flight') or {}).get('worst_x_floor'), 'worst_x_floor_shells': po['worst_x_floor'], 'shell_frames_off_g': po['flight_frames'],
                                   'hand_frames_not_judged': po['hand_frames']}
            out['R3']['items'][-1]['note'] = f"{po['hand_frames']} hand frames (loading, ejection) not judged"
        if pm.get('fresh') is not None:
            fv = row.get('fresh_vis'); add('R4a', 'fresh_moving_no_contact', len(fv['visible_frames']) if fv else pm['fresh']['moving'], 0)      # frames with the magazine in the game frame
            out['R4a']['report'] = {'moving_frames_all': pm['fresh']['moving'], 'moving_frames_visible': (fv or {}).get('visible_frames'), 'visibility_note': (fv or {}).get('note'), 'frames': pm['fresh']['frames'], 'no_contact': pm['fresh']['no_contact'], 'moving_frames': pm['fresh']['moving_frames'], 'max_step_cm_f': pm['fresh']['max_step_cm_f']}
    # R4
    bud = (L['r4_budget'].get(fam) or {}).get(take or '')
    if bud:
        add('R4', 'length', row.get('frames'), bud['length'])
        keys = ((gate or {}).get('layout') or {}).get('keys')
        if keys is None:
            try: import rarmset; keys = rarmset.good_keys(row['frames'])
            except Exception: keys = None
        add('R4', 'keys', keys, bud['keys'])
    elif fam == 'fallback': out['R4']['items'].append({'name': 'budget', 'value': None, 'limit': None, 'ok': True, 'skipped': True, 'note': 'quick-drop fallback clip, no budget'})
    else: not_measurable('R4', 'budget', f'no budget for {fam} take {take}')
    # TM1: the hidden window absorbs the stat time (timing.py)
    tm = row.get('tm1'); T = L.get('tm1') or {}
    if tm is not None and str(tm.get('note', '')).startswith('TM1 not measured'): not_measurable('TM1', 'hidden_avail_f', tm['note'])      # an error is a failing verdict, never a silent pass
    elif tm is not None and tm.get('note'): out['TM1']['items'].append({'name': 'hidden_avail_f', 'value': None, 'limit': None, 'ok': True, 'skipped': True, 'note': tm['note']})
    elif tm is not None:
        add('TM1', 'hidden_avail_f', tm['hidden_avail_f'], T['hidden_min_frames'], 'min'); add('TM1', 'hidden_cut_rate', tm['hidden_cut_rate'], T['max_speed'])
        add('TM1', 'visible_identical', tm['visible_identical'], 0, note='no control clip')
        out['TM1']['report'] = {k: tm[k] for k in ('state_f', 'settle_f', 'hide_start', 'hide_end', 'hidden_natural_f')}
    # H1: the handle part changes only while hidden and ends as the vanilla reload leaves it (hfix.py)
    h1 = row.get('h1'); T1 = L.get('h1') or {}
    hg = next((x for x in manifest.load()['guns'] if x['id'] == row.get('gun')), None)      # a gun with reload.handle_set ships handle sets: H1 applies
    if not manifest.load()['checks']['rreload'].get('handle_sets', True) and not ((hg or {}).get('reload') or {}).get('handle_set'): out['H1']['items'].append({'name': 'handle_visible_change_f', 'value': None, 'limit': 0, 'ok': True, 'skipped': True, 'note': 'handle sets disabled (checks.rreload.handle_sets false)'})
    elif h1 is not None and h1.get('error'): not_measurable('H1', 'handle_visible_change_f', h1['error'])
    elif h1:
        add('H1', 'handle_visible_change_f', max(len(v['visible_change_f']) for v in h1.values()), 0); add('H1', 'handle_end_vs_vanilla_cm', max(v['end_vs_vanilla_cm'] for v in h1.values()), T1['end_tol_cm'])
        out['H1']['report'] = {n: {k: v[k] for k in ('change', 'visible_change_f', 'end_state_cm', 'vanilla_end_cm')} for n, v in h1.items()}
    # H2: the break-open hinge opens once, stays open while the shells change, closes once (breakphys.hinge_stats)
    h2 = row.get('h2'); T2 = L.get('h2') or {}
    if h2 is not None:
        add('H2', 'hinge_opens', h2['opens'], T2.get('opens_max', 1)); add('H2', 'hinge_closes', h2['closes'], T2.get('closes_max', 1)); add('H2', 'hinge_dip_deg', h2['dip_deg'], T2.get('dip_max_deg', 3.0))
        out['H2']['report'] = {k: h2[k] for k in ('max_deg',)}
    # R5
    lb = (L.get('r5_min_lowered') or {}).get(fam) if row.get('r5_pre_hide') else L['r5_min'].get(fam)
    if lb and r5.get('grip_peak') is not None:
        add('R5', 'grip_pace_per_f', r5.get('pace'), lb['grip_pace_per_f'], 'min'); add('R5', 'stop_loss_max_cm_f', r5.get('stop_max'), lb['stop_loss_cm_f'], 'min')
        out['R5']['report'] = {'grip_peak_cm_f': r5['grip_peak'], 'longest_move_cm': r5.get('pace_dist')}
    elif fam != 'fallback': out['R5']['items'].append({'name': 'grip_peak', 'value': r5.get('grip_peak'), 'limit': None, 'ok': True, 'skipped': True, 'note': 'no big move or no family bound'})
    # R8: sustained speed (survey.sustained)
    r8 = row.get('r8'); lb8 = ((L.get('r8_min') or {}).get(fam) or {}).get(take or '')
    if lb8:
        names = (('gun_path_cm', 'path_cm', 'path_cm'), ('gun_v90_cm_f', 'v90_cm_f', 'v90_cm_f'), ('release_path_cm', 'rel_path_cm', 'rel_path_cm'), ('release_v90_cm_f', 'rel_v90_cm_f', 'rel_v90_cm_f'))
        for item, key, lim in names:
            if r8 is None or r8.get(key) is None: not_measurable('R8', item, 'no gun series or no release frame in the clip', lb8.get(lim))
            else: add('R8', item, r8[key], lb8.get(lim), 'min')
        out['R8']['report'] = {k: (r8 or {}).get(k) for k in ('cue', 'release', 'rel_frames', 'frames')}
    # R10: arm swing speed (checks/armspeed.py)
    r10 = row.get('r10'); lim10 = L.get('r10_swing_max_deg_f')
    if lim10 is not None and r10:
        for jn, v in r10['peak_deg_f'].items(): add('R10', 'swing_' + jn + '_deg_f', v, lim10.get(jn))
        out['R10']['report'] = {'peak_frame': r10['peak_frame']}
    elif lim10 is not None and 'clip name' in (row.get('missing') or []): out['R10']['items'].append({'name': 'swing_deg_f', 'value': None, 'limit': None, 'ok': True, 'skipped': True, 'note': 'held idle after the fallback: no clip to measure'})
    elif lim10 is not None: not_measurable('R10', 'swing_deg_f', 'no arm swing measure for the clip')
    # R7: finger torque of the in-hand turn frames (checks/fingertorque.py)
    fg = row.get('finger'); lim7 = L.get('finger_torque_nm')
    if row.get('finger_error'):
        if lim7 is not None: not_measurable('R7', 'finger_torque_nm', 'finger torque measure failed: ' + row['finger_error'][-120:], lim7)
    elif fg is not None and fg.get('skipped'): out['R7']['items'].append({'name': 'finger_torque_nm', 'value': None, 'limit': lim7, 'ok': True, 'skipped': True, 'note': fg['skipped']})
    elif fg is not None:
        add('R7', 'finger_torque_nm', round(fg['peak_nm'], 4), lim7)
        if fg.get('arm_driven_peak_nm') is not None and L.get('arm_driven_torque_nm') is not None: add('R7', 'arm_driven_torque_nm', fg['arm_driven_peak_nm'], L['arm_driven_torque_nm'], note='held frames where the gun does not turn in the hand: arm-driven, shipped Zhuo SF40B reaches 101.7 N m (prel: limit raised from 100, pwa right measures 101.675)')
        out['R7']['report'] = {k: fg.get(k) for k in ('turn_frames', 'turn_first', 'turn_last', 'peak_frame', 'peak_inertial_nm', 'mass_kg')}
        out['R7']['report']['generator'] = row.get('finger_spec')
        if not fg['turn_frames']: out['R7']['items'][-1]['note'] = 'no in-hand turn frames (arm-driven or none)'
    # R9, R11 to R14: the 2026-11-24 standard (checks/stdrules.py, weapons.json checks.draft.std)
    sd = row.get('std')
    if sd is not None and 'std' in L:
        S = L['std']; r9 = sd.get('r9') or {}; mo = sd.get('motion') or {}; F = mo.get('F') or {}; lay = mo.get('layout') or {}
        if r9.get('error'): not_measurable('R9', 'discard_hand_margin_min', 'visibility measure failed: ' + r9['error'][-120:])
        elif r9.get('skipped'): out['R9']['items'].append({'name': 'discard_visible', 'value': None, 'limit': None, 'ok': True, 'skipped': True, 'note': r9['skipped']})
        else:
            add('R9', 'discard_hand_margin_min', r9['hand_min'], S['r9_hand_min'], 'min'); add('R9', 'discard_well_in_frame_share', r9['well_share'], S['r9_well_share_min'], 'min')
            out['R9']['report'] = {'window': r9['window'], 'well_min_margin': r9.get('well_min')}
        if mo.get('error'):
            for rule, item in (('R12', 'post_gun_speed_cm_f'), ('R13', 'still_run_frames')): not_measurable(rule, item, 'motion measure failed: ' + mo['error'][-120:])
        else:
            fam_lim = S['speed_family'].get(fam) or S['speed_global']
            for item, key, lk in (('post_gun_speed_cm_f', 'post_sp', 'post_sp'), ('post_gun_accel_cm_f2', 'post_acc', 'post_acc'), ('post_hand_speed_cm_f', 'post_hs', 'post_hs'),
                                  ('whole_gun_speed_cm_f', 'whole_peak_sp', 'whole_peak_sp'), ('whole_gun_accel_cm_f2', 'whole_peak_acc', 'whole_peak_acc'), ('whole_hand_speed_cm_f', 'whole_peak_hs', 'whole_peak_hs')):
                v = F.get(key)
                if v is None: out['R12']['items'].append({'name': item, 'value': None, 'limit': fam_lim[lk], 'ok': True, 'skipped': True, 'note': 'no seated frame in the gate layout' if key.startswith('post') else 'no value'})
                else: add('R12', item, round(float(v), 3), fam_lim[lk])
            out['R12']['report'] = {'limit_set': 'family ' + fam if S['speed_family'].get(fam) else 'global'}
            if F.get('still_run') is not None: add('R13', 'still_run_frames', F['still_run'], S['still_run_max']); out['R13']['report'] = {'window': F.get('still_window')}
            else: out['R13']['items'].append({'name': 'still_run_frames', 'value': None, 'limit': S['still_run_max'], 'ok': True, 'skipped': True, 'note': 'no release frame in the track'})
        if sd.get('cover') is not None: add('R18', 'gun_cover_pct', sd['cover'], S['lift_max_cover_pct'])
        lf = sd.get('lift')
        if lf is not None: add('R18', 'lift_offset_cm', lf[0], S['lift_max_offset_cm']); add('R18', 'lift_pitch_deg', lf[1], S['lift_max_pitch_deg'])
        else: out['R18']['items'].append({'name': 'lift_offset_cm', 'value': None, 'limit': S['lift_max_offset_cm'], 'ok': True, 'skipped': True, 'note': 'no lift record (not a variant, or the vanilla round)'})
        wv = sd.get('warden'); W = S['warden_only']
        if wv is None:
            for rule, item in (('R14', 'hidden_frames_visible'), ('R11', 'inward_reach_min_cm')): out[rule]['items'].append({'name': item, 'value': None, 'limit': None, 'ok': True, 'skipped': True, 'note': 'Warden mesh limits: not applied to this gun'})
        elif wv.get('error'):
            for rule, item in (('R14', 'hidden_frames_visible'), ('R11', 'inward_reach_min_cm')): not_measurable(rule, item, 'Warden visibility measure failed: ' + wv['error'][-120:])
        else:
            lk = wv['leak']
            if lk.get('hidden') is not None:
                add('R14', 'hidden_frames_visible', lk['hidden'], W['hidden_frames_visible']); add('R14', 'spin_peak_deg_f', lk['spin_peak'], W['spin_peak_deg_f']); add('R14', 'spin_at_entry_deg', lk['spin_at_entry'], W['spin_at_entry_deg'])
            else:
                out['R14']['items'].append({'name': 'hidden_frames_visible', 'value': None, 'limit': W['hidden_frames_visible'], 'ok': True, 'skipped': True, 'note': 'no hidden window in the gate layout'})
            add('R11', 'inward_reach_min_cm', wv['in_min'], W['inward_min_cm'], 'min'); add('R11', 'lateral_reach_max_cm', wv['out_max'], W['lateral_max_cm'])
            out['R11']['report'] = {'clear_min_cm': wv.get('clear_min_cm')}
    # R6: the limits of the gate area rreload
    import rgate
    E = rgate.LIM
    if gate and 'start_cm' in gate:
        add('R6', 'start_pose', max(gate['start_cm'], gate['start_deg']), E['end_max_cm']); add('R6', 'end_pose', max(gate['end_cm'], gate['end_deg']), E['end_max_deg'])
        if gate.get('end_step_cm') is not None: add('R6', 'end_step_cm', gate['end_step_cm'], E.get('end_step_max_cm', 0.5))
    else: out['R6']['items'].append({'name': 'start_end_pose', 'value': None, 'limit': None, 'ok': True, 'skipped': True, 'note': (gate or {}).get('_error', 'no gate numbers')})
    import rules as RULES_MANIFEST      # every item this check emits is a row of rules.json: a rule that is not in the manifest does not run
    reg = RULES_MANIFEST.registered(); unreg = sorted({(r, i['name']) for r in RULES for i in out[r]['items'] if (r, i['name']) not in reg})
    if unreg: raise RuntimeError(f'draft items not registered in rules.json: {unreg}')
    if row.get('clip_kind') == 'cycle':      # a per-shot cycle clip (toss-cock): the rules whose applies_to lacks 'cycle' are reload-only and do not run on it
        scope = {x['id']: x.get('applies_to', ['reload']) for x in RULES_MANIFEST.load()}
        for r in RULES:
            if 'cycle' not in scope.get(r, ['reload']): out[r] = {'items': [{'name': 'scope', 'value': None, 'limit': None, 'ok': True, 'skipped': True, 'note': 'out of scope: reload clips only (rules.json applies_to)'}]}
    fails = []; bl = []
    for r in RULES:
        out[r]['ok'] = all(i['ok'] for i in out[r]['items'])
        for i in out[r]['items']:
            if i.get('not_measurable'): fails.append(f"{r} not measurable: {i['not_measurable']}")
            elif not i['ok']: fails.append(f"{r} {i['name']} {i['value']} {'<=' if i.get('kind', 'max') == 'max' else '>='} {i['limit']}")
            if i.get('baseline'): bl.append(f"{r} {i['name']} {i['value']} (baseline {i['baseline']})")
    return {'clip': name, 'family': fam, 'take': take, 'gun': row.get('gun'), 'pick': row.get('pick'), 'frames': row.get('frames'), 'rules': out, 'fails': fails, 'baselines': bl,
            'missing': row.get('missing'), 'error': row.get('error')}


def item_of(path, family=None, take=None):
    """A survey item for a clip given by its spec or glb (a draft outside the manifest)."""
    b = os.path.splitext(path)[0]; spec = json.load(open(b + '.json'))
    pick = spec.get('_pick') or spec.get('_draft') or ''; kind = spec.get('_gun_clip', 'reload')
    d = os.path.dirname(os.path.abspath(path)).replace('\\', '/')
    return dict(family=family, gun=spec.get('_gun'), body=spec.get('_body', 'pma'), side=spec.get('_side', 'Right').lower(), pick=pick, take=take or spec.get('_take') or (pick[-1] if pick[-1:] in 'AB' and len(pick) > 2 else None),
                clip=kind, kind='reload', shipped=b.replace('\\', '/') + '.glb', rel=os.path.basename(b) + '.glb', parked=False, root=os.path.basename(d))


def check_item(item, L=None):
    import survey
    row = survey.one(item); b = item['shipped'][:-4]
    L = L or limits()
    if row.get('error') or row.get('missing') and 'spec' in row['missing']:
        return {'clip': os.path.basename(b), 'family': row.get('family'), 'rules': {}, 'fails': ['could not measure: ' + str(row.get('error') or row.get('missing'))[:200]], 'baselines': [], 'error': row.get('error')}
    spec = json.load(open(b + '.json')); row['clip_kind'] = spec.get('_clip_kind', 'reload')
    if 'clip' in spec:
        try:
            import physmeasure; row['phys'] = physmeasure.measure(b, spec, L['phys_floor'])
        except Exception:
            import traceback; row['phys_error'] = traceback.format_exc()
    if 'clip' in spec:
        try:
            import fingertorque; row['finger'] = fingertorque.measure(b, spec); row['finger_spec'] = spec.get('_finger')
        except Exception:
            import traceback; row['finger_error'] = traceback.format_exc()
    if 'clip' in spec and os.path.exists(b + '.glb'):
        try:
            import stdrules; row['std'] = stdrules.measure(b, spec, spec.get('_gun') or row.get('gun'), row.get('family'), stdrules.is_variant(b, spec, item.get('root')))
        except Exception:
            import traceback; row['std'] = {'r9': {'error': traceback.format_exc()}, 'motion': {'error': traceback.format_exc()}}
    fm = ((row.get('phys') or {}).get('mag') or {}).get('fresh')
    if fm and fm.get('moving'):      # R4a counts only the frames in which the magazine can be seen
        import stdrules; vis, err = stdrules.fresh_visible(b, spec.get('_gun') or row.get('gun'), spec, fm.get('moving_all') or [])
        row['fresh_vis'] = {'visible_frames': vis, 'all_frames': fm.get('moving_all'), 'note': err}
    g = gate_of(b, spec) if os.path.exists(b + '_track.json') or os.path.exists(b + '_gate.json') else None
    try:      # TM1 needs the gun's stats; a clip of a gun without a reload entry has none
        import tm1 as timing; gid = spec.get('_gun') or row.get('gun'); gg = next((x for x in manifest.load()['guns'] if x['id'] == gid), None); stats = ((gg or {}).get('reload') or {}).get('stats')
        cf = None; root = item.get('root')
        if gg and (gg.get('reload') or {}).get('slots') and root in ('lowered', 'raised'):      # a variant: the control is the shipped clip of the same name
            import lowprod; sp_ = f"{lowprod.ship_root(gid)}/clips/{spec.get('_body', 'pma')}/{os.path.basename(b)}.json"
            cf = json.load(open(sp_))['frames'] if os.path.exists(sp_) else None
        elif gg: cf = spec['frames']
        if gg: row['tm1'] = timing.measure(b + '.glb', g, gid, spec.get('_gun_clip', 'reload'), spec['frames'], stats, L['tm1'], cf)
    except Exception as e: row['tm1'] = {'note': f'TM1 not measured: {type(e).__name__}: {e}'[:160]}
    try:      # H1: the handle joint of the gun's weapon set on our clip's clock (hfix.py); a gun without one has no row
        import hfix; tm = row.get('tm1') or {}; dl = (tm.get('hidden_avail_f') or 0) - (tm.get('hidden_natural_f') or 0) if tm.get('hidden_avail_f') is not None else 0.0
        row['h1'] = hfix.handle(dict(spec, _gun=spec.get('_gun') or row.get('gun'), _pick=spec.get('_pick') or '', frames=spec['frames']), g, dl, built=True) if spec.get('_pick') and spec.get('_gun_clip') else None
    except Exception as e: row['h1'] = {'error': f'H1 not measured: {type(e).__name__}: {e}'[:160]}
    if spec.get('_hinge_deg'):      # H2: break-open guns keep the hinge angle in the spec
        try:
            import breakphys; row['h2'] = breakphys.hinge_stats(spec['_hinge_deg'])
        except Exception as e: row['h2'] = None; row['h2_error'] = f'{type(e).__name__}: {e}'[:160]
    return evaluate(row, g, L)


def check_pair(item):
    """check_item for a process pool: (item, result)."""
    return item, check_item(item)


def clips_in(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for q in sorted(glob.glob(p.rstrip('/\\') + '/**/*.json', recursive=True)):
                n = os.path.basename(q)
                if not n.endswith(('_gate.json', '_track.json', '_objects.json', '_phys.json', '_prims.json', '_inertia.json', '_ik.json', '_checks.json', '_draft.json')) and os.path.exists(q[:-5] + '.glb'):
                    out.append(q)
        else: out.append(os.path.splitext(p)[0] + '.json')
    return out


def write(res, item, out):
    if out is None: path = item['shipped'][:-4] + '_draft.json'
    else:
        os.makedirs(out, exist_ok=True); path = f"{out}/{os.path.basename(item['shipped'])[:-4]}_draft.json"
    json.dump(res, open(path, 'w'), indent=1); return path


def line(r):
    return f"{r['clip']:46s} {r.get('family')}/{r.get('take')} " + ('pass' if not r['fails'] else 'FAIL ' + '; '.join(r['fails'])) + (('  [baseline: ' + '; '.join(r['baselines']) + ']') if r['baselines'] else '')


def main(argv):
    out = common.opt(argv, '--out'); fam = common.opt(argv, '--family'); take = common.opt(argv, '--take')
    if not argv: raise SystemExit(__doc__)
    bad = 0
    for p in clips_in(argv):
        it = item_of(p, fam, take); r = check_item(it); write(r, it, out); print(line(r), flush=True); bad += bool(r['fails'])
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
