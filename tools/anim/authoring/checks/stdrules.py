"""Standard rules R9 and R11 to R14 of a reload clip (the owner's 2026-11-24 standard, rules.json): measures and verdicts.

  R9   discard visible    from the release to the frame the magazine has left the well (track release .. free_from), every joint of the reloading hand is inside the
                          game camera frame (margin >= checks.draft.std.r9_hand_min) and the magazine well point is inside it on at least checks.draft.std.r9_well_share_min
                          of those frames. Game camera: checks/visibility.py. Generic: needs the gun's mag_slot and the clip's track only. The clip is read alone
                          (an absolute pose; the 0.2 s blend from the stance idle ends before the release).
  R12  speed caps         post-seat gun speed, gun acceleration and hand speed, and the same over the whole clip (checks/reloadrules.py features), at most the
                          limit of the clip's family set (top: the approved Warden set x 1.1; every other family: all shipped clips and the vanilla reloads x 1.1).
  R13  no dead pause      longest run of near-still gun frames between the release and hide_start at most checks.draft.std.still_run_max.
  R14  hidden phase       (Warden mesh) no gun, hand or arm point in the frame from hide_start to the rise beat; gun spin on the visible frames after it and the
                          angle from the end pose at entry capped.
  R11  two-gun clearance  (Warden mesh) the clip mirrored onto the other hand: inward reach (min x) and lateral reach (max x) of the gun and arm points.
Limits: weapons.json checks.draft.std (each with its source in _notes).
"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..', 'reload')); sys.path.insert(0, os.path.join(HERE, '..')); sys.path.insert(0, HERE)
import renv, common, manifest


def std():
    return manifest.load()['checks']['draft']['std']


def parse_stem(stem):
    """<root>/<body>/<gun>_<side>_<pick>_<name> -> (root, body, gun, side, pick, name) or None."""
    import re
    d, f = os.path.split(stem.replace('\\', '/')); r, body = os.path.split(d)
    m = re.match(r'^(?P<gun>[a-z0-9]+)_(?P<side>right|left)_(?P<pick>.+?)_(?P<nm>empty_reload|reload)$', f)
    if not m or body not in ('pma', 'pwa'): return None
    return r, body, m['gun'], m['side'], m['pick'], m['nm']


def is_variant(stem, spec, root=None):
    """A discard-visible variant: a clip of a lowered or raised variant folder, with a lift record (_lift or _lowered in its spec), or a vanilla-round draft (_draft SV..)."""
    if spec.get('_stance_only'): return False      # lowered idle at both ends, no lift (reload/stance.py): there is no discard to show, R9 and R18 do not apply
    return root in ('lowered', 'raised') or '/lowered/' in stem.replace(chr(92), '/') or '/raised/' in stem.replace(chr(92), '/') or '_lift' in spec or '_lowered' in spec or str(spec.get('_draft') or spec.get('_pick') or '').startswith('SV')


def lift_of(spec):
    """(offset cm, pitch deg) the variant needed to bring the discard into view (the solved offset of _lift: stop_m or move_m), or None."""
    L = spec.get('_lift')
    if not isinstance(L, dict): return None
    v = L.get('stop_m') or L.get('move_m')
    if not v: return None
    import math
    return round(100.0 * math.sqrt(sum(x * x for x in v)), 2), round(abs(L.get('pitch_deg') or 0.0), 2)


def fresh_visible(stem, gun, spec, frames):
    """Of the frames in which the fresh magazine moves without contact (R4a), those in which it can be seen: any magazine vertex inside the game camera frame on that frame or the one before (the step
    arrives at the frame). Same camera and margin as R9 (visibility.py); the magazine points come from the track (lift.mag_pts). -> ([visible frames], None) or ([], error text)."""
    import visibility as V, numpy as np, lift
    p = parse_stem(stem)
    if p is None: return list(frames), 'clip name does not follow <gun>_<side>_<pick>_<clip>: all frames counted'
    try:
        lift.GUN = gun; lift._cloud.clear(); V._rigs.clear(); trk = json.load(open(stem + '_track.json'))
        r, L = V.poses(stem + '.glb', spec.get('clip', 'reload_draft'), None, p[3], 'raised'); S = 'Right' if p[3] == 'right' else 'Left'; eye, hh = V.camera(p[1])
        wt = [(np.array(r.world(q)[r.idx['Weapon' + S]][0], float), tuple(r.world(q)[r.idx['Weapon' + S]][1])) for q in L]; sr = {'trk': trk, 'wt': wt}; out = []
        for f in frames:
            for g in (f - 1, f):
                if 0 <= g < min(len(wt), len(trk['frames'])):
                    P = lift.mag_pts(sr, g)
                    if P is not None and float(V.margin(P, eye, hh).max()) > 0: out.append(f); break
        V._rigs.clear(); return out, None
    except Exception:
        import traceback; V._rigs.clear(); return list(frames), 'visibility measure failed, all frames counted: ' + traceback.format_exc()[-160:]


def gun_cover(gun):
    """Screen cover (%) of the gun in the raised game pose, the larger of the two bodies (posemeasure, the pose rule's measure)."""
    sys.path.insert(0, os.path.join(HERE, '..', 'pose')); import posemeasure
    mesh = common.gun(gun)['mesh']; _, L, cov = posemeasure.measure((mesh, ('pma', 'pwa')))
    return round(max(cov.values()), 2)


def r9(stem, gun, spec):
    """{'hand_min', 'well_share', 'window', 'n'} or {'skipped': why} or {'error': text}."""
    import visibility as V, numpy as np, gungeo
    p = parse_stem(stem); trk = json.load(open(stem + '_track.json')) if os.path.exists(stem + '_track.json') else None
    if p is None: return {'skipped': 'clip name does not follow <gun>_<side>_<pick>_<clip> in <body>/'}
    if not trk or trk.get('release') is None or trk.get('free_from') is None: return {'skipped': 'no magazine release and free frame in the track (no detachable magazine)'}
    _, body, _, side, _, _ = p
    try:
        V._rigs.clear()
        r, L = V.poses(stem + '.glb', spec.get('clip', 'reload_draft'), None, side, 'raised'); S = 'Right' if side == 'right' else 'Left'
        eye, hh = V.camera(body); R, F = int(trk['release']), int(trk['free_from'])
        if R > len(L) - 1: return {'skipped': 'the release frame is outside the clip (quick-drop fallback)'}
        try: seat = V.seat(common.gun(gun))
        except TypeError: return {'skipped': 'the gun has no weapon anim set with a mag_slot (no detachable magazine well)'}
        hj = [r.idx[n] for n in r.names if n.startswith(S + 'Hand')]; well = []; hand = []
        for f in range(R, min(F, len(L) - 1) + 1):
            W = r.world(L[f]); well.append(float(V.margin(V.R.place(W[r.idx['Weapon' + S]], seat[None]), eye, hh).min()))
            hand.append(float(V.margin(np.array([W[j][0] for j in hj]), eye, hh).min()))
        V._rigs.clear()
        return {'hand_min': round(min(hand), 3), 'well_share': round(sum(1 for w in well if w > 0) / len(well), 3), 'well_min': round(min(well), 3), 'window': [R, F], 'n': len(well)}
    except Exception as e:
        import traceback; V._rigs.clear(); return {'error': traceback.format_exc()[-300:]}


def motion(stem, spec):
    """R12 and R13 measures from reloadrules.features: {'F': {...}, 'layout': {...}} or {'error'}."""
    import reloadrules as RR
    try:
        S = RR.series(stem + '.glb', spec['clip'], spec.get('_side', 'Right')); L = RR.layout(stem)
        return {'F': RR.features(S, L), 'layout': {k: L.get(k) for k in ('release', 'seated', 'hide_start', 'hide_end')}}
    except Exception as e:
        import traceback; return {'error': traceback.format_exc()[-300:]}


def warden_vis(stem):
    """R14 and R11 measures (the Warden gun mesh): reloadrules.series_vis, leak. {'leak', 'in_min', 'out_max'} or {'error'}."""
    import reloadrules as RR, lift
    p = parse_stem(stem)
    try:
        lift.GUN = 'warden'; lift._cloud.clear()
        o = RR.series_vis(p[0], p[1], p[3], p[4], p[5]); lk = RR.leak(o); n = min(o['n'], 77)
        import visibility as V; V._rigs.clear()
        return {'leak': lk, 'in_min': round(min(o['in_x'][:n]), 2), 'out_max': round(max(o['out_x'][:n]), 1), 'clear_min_cm': min(o['clear_cm'][:n])}
    except Exception as e:
        import traceback; return {'error': traceback.format_exc()[-300:]}


def measure(stem, spec, gun, family, variant=True):
    out = {'r9': r9(stem, gun, spec) if variant else {'skipped': 'not a discard-visible variant: R9 gates only variants that are made (the shipped clip stays where the lift is not natural)'}, 'motion': motion(stem, spec), 'lift': lift_of(spec), 'cover': gun_cover(gun) if variant else None}
    if gun == 'warden' and parse_stem(stem) and os.path.exists(stem + '_track.json'): out['warden'] = warden_vis(stem)
    return out
