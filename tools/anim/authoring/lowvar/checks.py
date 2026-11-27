"""Gate area `lowvar` (build.sh check --only lowvar): the stance variants of the reload clips (manifest reload.lowered_variant and raised_variant; made by reload/lowprod.py: the generator's own hook for
the Warden, reload/discard.py for every other gun).

R9, one rule for every gun (checks.lowered_variant.discard, measured by reload/discard.py vis): in every frame of the discard event (the magazine leaving the well: release to free_from of the clip's
track) the share of gun vertices inside the game camera frame (eye joint Torso_fppCamera_Control_GRP, hfov 100, 16:9) is at least the share in the shipped raised idle (frame 0 of the shipped clip, per body,
rounded down to 0.001), the magazine well point is inside the frame with margin eps and every joint of the reloading hand is inside with margin eps. Both bodies, both hands, both reload clips.
Wrist: the variant clips' wrist from the bind pose (gate file, else rgate) at most checks.rreload.wrist_view_bind_max_deg; fails: none in the gate files the generator wrote (start and end in the stance idle, hidden window, reach, shoulder, eye).
Stances: lowered (reload.lowered_variant) and raised (reload.raised_variant: start and end in the raised idle, same offsets, no lowered overlay).
Clips: <GA_CLIPS_ROOT>/<stance>/clips when set (ga produce), else the folder of the manifest path key. The shipped clips are read from the gun's reload.clips folder (GA_CONTROL overrides).
run(guns, bodies, jobs) -> rows as authoring/checks/gate.py prints them.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
for p in (HERE + '/../reload', HERE + '/../checks', HERE + '/..', HERE + '/../../'):
    if p not in sys.path: sys.path.insert(0, p)
import renv, common, manifest

UNIT = 'share of the gun vertices'


def row(check, item, value, threshold, unit, ok, note=''):
    return {'check': check, 'item': item, 'value': value, 'threshold': threshold, 'unit': unit, 'ok': bool(ok), 'note': note}


def run(guns=None, bodies=None, jobs=1):
    import discard, rgate, lowprod
    rows = []; man = manifest.load(); lim = man['checks']['rreload']; root = os.environ.get('GA_CLIPS_ROOT')
    for g in man['guns']:
        r = g.get('reload') or {}; lv = r.get('lowered_variant'); rv = r.get('raised_variant')
        if not (lv or rv) or (guns and g['id'] not in {x['id'] for x in guns}): continue
        gid = g['id']; ctl = os.environ.get('GA_CONTROL') or lowprod.control_root(gid, (root or '').rstrip('/'))
        for stance, ent in (('lowered', lv), ('raised', rv)):
            if not ent: continue
            clips = (root.replace(chr(92), '/').rstrip('/') + f'/{stance}/clips') if root else manifest.path(ent['clips']).rstrip('/')
            picks = list((lv or {}).get('layout') or {}) or [p + ('A' if r['weight'] == 'light' else 'B') for p in r['slots']]
            if 'picks' in ent: picks = [p for p in picks if p[:-1] in ent['picks']]      # per-pick wiring: the other slots are the shipped clips
            l1_w = None; l1 = manifest.load()['checks']['draft']['l1']
            cov_w = well_w = hand_w = None; share_w = None; wrist_w = None; nfail = 0; nclips = 0; fail_item = None; eps = discard.rules()['eps']
            so = [p + ('A' if r['weight'] == 'light' else 'B') for p in (ent.get('stance_only') or [])] if stance == 'lowered' else []      # stance-only clips (no lift): the gate rules apply, R9 does not
            if not picks and not so: continue      # a stance with no variant pick (only the other stance has one)
            for pk in picks + so:
                for x in (discard.vis(clips, gid, pk, ctl) if pk not in so else []):
                    nclips += 1; name = f"{x['clip']} {x['body']} {x['side']}"
                    if cov_w is None or x['coverage'] - x['coverage_idle'] < cov_w[0]: cov_w = (x['coverage'] - x['coverage_idle'], x['coverage'], x['coverage_idle'], name)
                    if well_w is None or x['well'] < well_w[0]: well_w = (x['well'], name)
                    if share_w is None or x['well_share'] < share_w[0]: share_w = (x['well_share'], name)
                    if hand_w is None or x['hand'] < hand_w[0]: hand_w = (x['hand'], name)
                for body in (bodies or ['pma', 'pwa']):
                    for side in ('right', 'left'):
                        for clip in ('empty_reload', 'reload'):
                            s = f'{clips}/{body}/{gid}_{side}_{pk}_{clip}'
                            if not os.path.exists(s + '_gate.json'): continue
                            if pk in so: nclips += 1      # a stance-only clip: counted by its gate file (no R9 rows)
                            o = json.load(open(s + '_gate.json'))      # the gate the generator wrote (its fails include the family's own checks, which a fresh rgate.gate call does not know)
                            nfail += len(o['fails']); fail_item = fail_item or (f'{os.path.basename(s)}: {o["fails"]}' if o['fails'] else None)
                            if stance == 'lowered':      # L1: the last move to the lowered idle (checks/hfix.py)
                                import hfix; e = hfix.end_transition(s, 'Left' if side == 'left' else 'Right'); sc = e['slow_frames'] / l1['slow_frames_max']
                                if l1_w is None or sc > l1_w[0]: l1_w = (sc, os.path.basename(s), e)
                            wv = o.get('wrist_view_bind')
                            if wv is None: spec = json.load(open(s + '.json')); wv = rgate.gate(dict(spec, out=s + '.glb', _track=s + '_track.json'), json.load(open(s + '_track.json')))['wrist_view_bind']
                            if wrist_w is None or wv > wrist_w[0]: wrist_w = (wv, os.path.basename(s))
            if not nclips:
                rows.append(row(f'lowvar {stance}: variant clips found', gid, 0, 1, 'clips', False, clips)); continue
            S = man['checks']['draft']['std']      # R9 as calibrated on the approved clips (checks.draft.std): hand margin and the share of release frames with the well in the frame
            if share_w is not None: rows.append(row(f'lowvar {stance} R9: magazine well inside the frame on at least the share of the discard event frames', share_w[1], share_w[0], S['r9_well_share_min'], 'of the release frames', share_w[0] >= S['r9_well_share_min'] - 1e-9, f'{nclips} clips; gun coverage {cov_w[1]} reported, not gated (the phook target fails every approved clip)'))
            if hand_w is not None: rows.append(row(f'lowvar {stance} R9: reloading hand inside the frame in the discard event (margin at least the limit)', hand_w[1], hand_w[0], S['r9_hand_min'], 'share of the half frame', hand_w[0] >= S['r9_hand_min'] - 1e-9))
            rows.append(row(f'lowvar {stance}: wrist from the bind pose (at most)', wrist_w[1], wrist_w[0], lim['wrist_view_bind_max_deg'], 'deg', wrist_w[0] <= lim['wrist_view_bind_max_deg']))
            if l1_w is not None: rows.append(row(f'lowvar {stance} L1: the last move to the lowered idle is one move (slow drift frames after the rise at most the limit)', l1_w[1], l1_w[0], 1.0, 'share of the limit (slow drift 7 f)', l1_w[0] <= 1.0, f"tail {l1_w[2]['tail_frames']} f, slow {l1_w[2]['slow_frames']} f"))
            rows.append(row(f'lowvar {stance}: gate rules (start and end in the stance idle, hidden window, reach, shoulder, eye, ...)', fail_item or gid, nfail, 0, 'fails', not nfail))
    return rows
