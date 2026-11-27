"""Measurement survey of the reload clips for the owner's rules R1 to R6. Measures only: no limit, no pass or fail.

usage: survey.py run --out survey.json [--jobs 8] [--limit n] [--ref <folder>] [--manifest weapons.json]
       survey.py md survey.json SURVEY.md

Clips: every clip of checks/regen.py acceptance(include_parked=True) (shipped folders, or --ref, an earlier regen output with
the same layout). One row per clip. Every number is read from the clip's glb and its sidecars (spec .json, _track, _gate,
_inertia, _phys, _objects); nothing is regenerated. A number a clip's sidecars cannot give is None.

Definitions (units: cm and frames at 30 fps, grip = the Weapon<Side> bone, muzzle = a point 0.55 m in front of it):
 gun speed        grip position step per frame (motionstats.py). Rest frame: grip speed under 0.25 cm/f and turning under
                  0.5 deg/f. Acceleration frame: |change of the grip step| over 0.5 cm/f^2 or |change of the turning step|
                  over 1.0 deg/f^2, widened by 1 frame each side.
 R1               exit_cm_f: world speed of the magazine centre on the first free step (release to release + 1), gravity
                  taken off (sf2.mag_speed). gun_rel_cm_f: speed of the magazine seat point over the release step;
                  gun_max3_cm_f: the largest step over the 3 steps up to the release. ratio = exit / gun_rel, ratio3 =
                  exit / gun_max3 (sf2.mag_speed uses the latter). thrown: gun_rel_cm_f >= THROWN_GUN_CM_F, see SURVEY.md.
                  _inertia.json (mag.ratio, SF35 and SF40 only) and track phys exit_v_cm_f are copied for comparison.
 R2               per part, frames where it travels (relative to the gun) and, of those, frames where the gun is at rest
                  and frames outside every acceleration frame. magazine: steps in the well (states guided, loose, fresh_move)
                  over 0.3 cm/f; pump: spec _pump_cm step over 0.3 cm/f; barrels: _phys hinge_deg step over 1.0 deg/f;
                  shells: _objects (gun axes) steps over 0.3 cm/f that are not ballistic (world acceleration within
                  0.25 g of gravity). A falling magazine is ballistic and is not a part travel here.
 fresh approach   fresh_runs: per run of the new magazine going into the well, the distance it covers (gun axes) over the
                  run's frames (rate) against the mean step of the seated well point over the same frames (gun_cm_f); ratio = rate / gun_cm_f
                  (gun speed floored at 0.01 cm/f).
 R3               detached magazine (states guided, loose, falling, release + 1 to gone - 1): air frames, frames on screen
                  (gate mag_seen, which holds the first 40), the largest slowdown (cm/f^2: acceleration with gravity taken
                  off, component against the velocity) and the frames over 0.25 g of it; bounce frames excluded. mag_hang
                  is rgate's own count.
 R4               gate layout (length, mag_out, seated, handle, hide_start, hide_end) and the spec _timing marks.
 R5               motionstats big moves (grip path of 8 cm or more): peak cm/f, peak_at (0..1), stop (cm/f lost in the last
                  frames of the move, motionstats), muzzle peak over the move / grip peak, gaps between consecutive big
                  moves (frames, frames under 0.25 cm/f, fastest step).
 R10              peak swing speed of clavicle, shoulder, elbow and wrist (checks/armspeed.py)
R8               sustained speed: gun path (cm) and 90th percentile grip step (cm/f) over the whole clip and over the release phase (the gun first
                  leaving rest to release + 3; track release), `sustained()`.
 R6               gate start_cm, start_deg, end_cm, end_deg, end_step_cm (None where a clip has no gate file).
"""
import json, os, sys, math, time, traceback
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..', 'reload'))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import renv, common

REST_SP, REST_W = 0.25, 0.5          # cm/f, deg/f
ACC_A, ACC_W = 0.5, 1.0              # cm/f^2, deg/f^2
PART_CM, PART_DEG = 0.3, 1.0
THROWN_GUN_CM_F = 3.0                # 0.9 m/s; the survey values leave a gap between 1.9 and 3.2 cm/f (SURVEY.md)
G_CM = 9.81 / 900.0 * 100            # cm/f^2


def _clip_series(glb, clip, side, muzzle=0.55):
    """Grip position (m), rotation (xyzw) and muzzle position per frame."""
    import numpy as np
    from glb import Glb
    from wclip import TClip
    from fk import qrot
    c = TClip(Glb(glb), clip); i = c.names.index('Weapon' + side); G = []; Q = []; M = []
    for f in range(c.frames):
        t, q = c.wf(f)[i]; G.append(np.array(t, float)); Q.append(np.array(q, float)); M.append(t + qrot(q, np.array([0, 0, -muzzle])))
    return np.array(G), np.array(Q), np.array(M)


def _turn(q0, q1):
    """Rotation vector (deg) from q0 to q1, in the frame of q0."""
    import numpy as np
    from fk import qmul, qinv
    r = qmul(qinv(q0), q1)
    if r[3] < 0: r = -r
    s = float(np.linalg.norm(r[:3]))
    if s < 1e-12: return np.zeros(3)
    return np.array(r[:3]) / s * math.degrees(2 * math.atan2(s, r[3]))


def _dilate(a, k):
    n = len(a); return [any(a[max(0, f - k):f + k + 1]) for f in range(n)]


def gun_frames(G, Q):
    """(rest, accel, sp) per frame. sp: grip step cm/f arriving at the frame."""
    import numpy as np
    n = len(G); V = np.zeros((n, 3)); W = np.zeros((n, 3))
    for f in range(1, n): V[f] = (G[f] - G[f - 1]) * 100; W[f] = _turn(Q[f - 1], Q[f])
    sp = np.linalg.norm(V, axis=1); wn = np.linalg.norm(W, axis=1)
    acc = [False] * n
    for f in range(1, n):
        a = float(np.linalg.norm(V[f] - V[f - 1])) if f > 1 else 0.0; b = float(np.linalg.norm(W[f] - W[f - 1])) if f > 1 else 0.0
        acc[f] = a > ACC_A or b > ACC_W
    rest = [bool(sp[f] < REST_SP and wn[f] < REST_W) for f in range(n)]
    return rest, _dilate(acc, 1), sp


def travel_block(moving, rest, accel):
    """moving[f]: the part steps into frame f. -> counts."""
    mv = [f for f in range(len(moving)) if moving[f]]
    return {'travel_frames': len(mv), 'travel_at_rest': sum(1 for f in mv if rest[f]), 'travel_outside_accel': sum(1 for f in mv if not accel[f])}


def r5(glb, clip, side, upto=None):
    """upto: only the big moves that end by this frame count (a lowered variant: the motion before hide_end, identical to its source; its visible rise is governed by the arm bounds, L1 and the smoothness diagnostics: the approved lowered rises stop softly, stop loss 0.7 to 3.4)."""
    import numpy as np
    import motionstats
    s = motionstats.stats(glb, clip, side, 0.55); sp = np.array(s['speed']); ms = np.array(s['muzzle_speed']); big = [m for m in s['moves'] if m['dist'] >= 8 and (upto is None or m['end'] <= upto)]
    mv = []
    for m in big:
        gp = float(sp[m['start']:m['end'] + 1].max()); mp = float(ms[m['start']:m['end'] + 1].max())
        mv.append({'start': m['start'], 'end': m['end'], 'dist': m['dist'], 'grip_peak': m['peak'], 'peak_at': m['peak_at'], 'stop': m['stop'], 'muzzle_peak': round(mp, 1), 'muz_over_grip': round(mp / gp, 2) if gp > 0 else None})
    gaps = []
    for a, b in zip(big, big[1:]):
        seg = sp[a['end'] + 1:b['start']]
        gaps.append({'after': a['end'], 'frames': int(len(seg)), 'still': int((seg < REST_SP).sum()), 'max_speed': round(float(seg.max()), 2) if len(seg) else 0.0})
    out = {'big_moves': len(big), 'moves': mv, 'gaps': gaps, 'hold_share': s['hold_share'], 'peak_speed': s['peak_speed'], 'mean_peak_at': s['peak_at'], 'mean_stop': s['stop'], 'whip': s['whip']}
    if mv:
        gpk = max(m['grip_peak'] for m in mv); mpk = max(m['muzzle_peak'] for m in mv); k = max(mv, key=lambda m: m['grip_peak'])
        lg = max(mv, key=lambda m: m['dist'])      # the longest big move: its peak grip speed per cm of its length, 1 / frames of a minimum-jerk move of that peak (plift4)
        out.update({'grip_peak': gpk, 'peak_at': k['peak_at'], 'stop_max': max(m['stop'] for m in mv), 'stop_min': min(m['stop'] for m in mv), 'stop_last': mv[-1]['stop'],
                    'muz_over_grip': round(mpk / gpk, 2) if gpk > 0 else None, 'pace': round(lg['grip_peak'] / lg['dist'], 4), 'pace_dist': lg['dist']})
    if gaps:
        out.update({'gap_min_frames': min(g['frames'] for g in gaps), 'gap_min_still': min(g['still'] for g in gaps), 'gap_max_speed': max(g['max_speed'] for g in gaps)})
    return out


def mag_rows(spec, track, G, Q, rest, accel):
    """R1, R3 and the magazine part of R2. None-valued dict when the clip has no detachable magazine."""
    import numpy as np
    import magtrack2
    st = [x['state'] for x in track['frames']]; sc = [x['s'] for x in track['frames']]; n = len(st); r = track['release']
    if not any(s == 'falling' for s in st) or r + 1 >= n: return None
    gid, gc = spec['_gun'], spec['_gun_clip']
    v = magtrack2.vanilla(gid, gc); cen = np.r_[v['centre'], 1]; Seat = v['seat']; GW = [magtrack2.m4(G[f], Q[f]) for f in range(n)]
    Mm = [None if x.get('m') is None else np.array(x['m']).reshape(4, 4) for x in track['frames']]
    C = [None if Mm[f] is None else (GW[f] @ Mm[f] @ cen)[:3] for f in range(n)]
    seat = [(GW[f] @ Seat @ cen)[:3] for f in range(n)]
    gv = np.array([0, -magtrack2.G_ACC, 0])
    exit_ = float(np.linalg.norm(C[r + 1] - C[r] - gv)) * 100
    gun_rel = float(np.linalg.norm(seat[r] - seat[r - 1])) * 100 if r >= 1 else 0.0
    gun3 = max(float(np.linalg.norm(seat[i + 1] - seat[i])) for i in range(max(r - 3, 0), r)) * 100 if r >= 1 else 0.0
    gun_seat_v = (seat[r] - seat[r - 1]) * 100 if r >= 1 else np.zeros(3)
    out = {'release': r, 'free_from': track['free_from'], 'gone': track['gone'], 'exit_cm_f': round(exit_, 2), 'gun_rel_cm_f': round(gun_rel, 2), 'gun_max3_cm_f': round(gun3, 2),
           'ratio': round(exit_ / gun_rel, 3) if gun_rel > 0.05 else None, 'ratio3': round(exit_ / gun3, 3) if gun3 > 0.05 else None,
           'phys_exit_cm_f': (track.get('phys') or {}).get('exit_v_cm_f'), 'mode': (track.get('plan') or {}).get('mode'), 'thrown': bool(gun_rel >= THROWN_GUN_CM_F)}
    # the world velocity direction against the gun's: cosine (a thrown magazine goes with the gun)
    vx = (C[r + 1] - C[r] - gv) * 100; nv = float(np.linalg.norm(vx)); ng = float(np.linalg.norm(gun_seat_v))
    out['exit_dir_cos_gun'] = round(float(vx @ gun_seat_v) / (nv * ng), 2) if nv > 1e-6 and ng > 0.05 else None
    # R3: the detached magazine
    bt = [b['t'] for b in ((track.get('phys') or {}).get('bounces') or [])]
    air = [f for f in range(r + 1, min(track['gone'], n)) if st[f] in ('guided', 'loose', 'falling') and sc[f] > 0.5 and C[f] is not None]
    dec = 0.0; dec_at = None; decn = 0
    for f in air:
        if st[f] != 'falling' or f == track['free_from'] or f + 1 >= n or C[f + 1] is None or st[f + 1] not in ('falling',) or f < 1 or C[f - 1] is None: continue
        if any(abs(f - t) <= 1.0 for t in bt): continue
        a = (C[f + 1] - 2 * C[f] + C[f - 1]) - gv; vel = C[f + 1] - C[f - 1]; nvl = float(np.linalg.norm(vel))
        if nvl < 1e-9: continue
        d = -float(a @ vel) / nvl * 100
        if d > dec: dec, dec_at = d, f
        if d > 0.25 * G_CM: decn += 1
    out.update({'air_frames': len(air), 'decel_max_cm_f2': round(dec, 3), 'decel_at': dec_at, 'decel_frames': decn,
                'slide_frames': (track['free_from'] - r) if track['free_from'] > r else 0})
    # hanging: falling frames above 0.15 m whose acceleration is not gravity (rgate's mag_hang with hang_next_falling; frames next to a
    # bounce are the hit, as sf4.bounce_hang counts them)
    hang = 0
    for f in range(1, n - 1):
        if st[f] != 'falling' or sc[f] <= 0.5 or f in (track['free_from'], track['gone'] - 1) or st[f + 1] != 'falling' or st[f - 1] not in ('falling', 'guided') or C[f - 1] is None or C[f] is None or C[f + 1] is None: continue
        if any(abs(f - t) <= 1.01 for t in bt): continue
        A = C[f + 1] - 2 * C[f] + C[f - 1]
        if C[f][1] > 0.15 and (abs(A[1] + magtrack2.G_ACC) > 0.25 * magtrack2.G_ACC or float(np.linalg.norm(A[[0, 2]])) > 0.25 * magtrack2.G_ACC): hang += 1
    out['hang_frames'] = hang
    ff = track['free_from']      # rgate's release_dv: jump of the world velocity where the slide ends, gravity taken off (the gate file's number may be refined by the generator)
    out['release_dv_raw_cm_f'] = round(float(np.linalg.norm((C[ff] - C[ff - 1] - gv) - (C[ff - 1] - C[ff - 2]))) * 100, 2) if ff >= 2 and ff < n and all(C[i] is not None for i in (ff, ff - 1, ff - 2)) else 0.0
    # R2, fresh magazine: approach to the well. A run = consecutive frames in state fresh or fresh_move; distance = gun-local centre
    # from the run's first frame (the frame before it) to the seated position (else the run's last frame); gun speed = mean step
    # of the seated well point over the run frames.
    loc = [None if Mm[f] is None else (Mm[f] @ cen)[:3] for f in range(n)]; runs, cur = [], []
    for f in range(1, n):
        if st[f] in ('fresh', 'fresh_move') and loc[f] is not None and loc[f - 1] is not None: cur.append(f)
        else:
            if cur: runs.append(cur); cur = []
    if cur: runs.append(cur)
    fr = []
    for run in runs:
        a, b = run[0], run[-1]; e = loc[b + 1] if b + 1 < n and st[b + 1] == 'seated' and loc[b + 1] is not None else loc[b]
        d = float(np.linalg.norm(loc[a] - e)) * 100; wm = float(np.mean([np.linalg.norm(seat[f] - seat[f - 1]) for f in run])) * 100
        fr.append({'first': a, 'last': b, 'frames': len(run), 'dist_cm': round(d, 2), 'rate_cm_f': round(d / len(run), 3), 'gun_cm_f': round(wm, 3), 'ratio': round(d / len(run) / max(wm, 0.01), 2)})
    out['fresh_runs'] = fr
    # R2, magazine: steps in the well
    well = [False] * n
    for f in range(1, n):
        if st[f] in ('guided', 'loose', 'fresh_move') and C[f] is not None and C[f - 1] is not None and st[f - 1] in ('guided', 'loose', 'fresh_move', 'seated'):
            Mp = np.linalg.norm(Mm[f][:3, 3] - Mm[f - 1][:3, 3]) * 100
            well[f] = bool(Mp > PART_CM)
    out['r2'] = travel_block(well, rest, accel)
    out['r2_states'] = {k: travel_block([well[f] and st[f] == k for f in range(n)], rest, accel) for k in ('guided', 'loose', 'fresh_move')}
    return out


def pump_closing_runs(spec, sp):
    """R2b data: the closing runs of the pump, cut from its own track (_pump_cm). A run is a stretch of frames in which the pump
    steps over PART_CM, gaps of one frame merged, from the first to the last moving frame; closing when the pump ends lower than it
    started. Per run: the mean gun grip speed over its moving frames (cm/f) and as a fraction of the clip's peak grip speed (x_mean),
    the median over the peak, and the share of its frames in which the gun moves under 1 cm/f. None when the clip has no pump."""
    if '_pump_cm' not in spec: return None
    import numpy as np
    p = spec['_pump_cm']; n = min(len(p), len(sp)); peak = float(max(sp[:n])) if n else 0.0
    runs = []; cur = []
    for f in range(1, n):
        if abs(p[f] - p[f - 1]) <= PART_CM: continue
        if cur and f - cur[-1] - 1 > 1: runs.append(cur); cur = []
        cur.append(f)
    if cur: runs.append(cur)
    out = []
    for r in runs:
        if p[r[-1]] - p[r[0] - 1] > 0: continue
        v = np.array([float(sp[f]) for f in r])
        out.append({'first': r[0], 'last': r[-1], 'frames': len(r), 'mean_gun_cm_f': round(float(v.mean()), 3), 'x_mean_peak': round(float(v.mean()) / peak, 3) if peak > 0 else None,
                    'median_peak': round(float(np.median(v)) / peak, 3) if peak > 0 else None, 'share_under_1cm_f': round(float((v < 1.0).mean()), 3)})
    return {'peak_cm_f': round(peak, 2), 'closing': out}


def r2_parts(spec, base, G, Q, rest, accel):
    import numpy as np
    out = {}
    if '_pump_cm' in spec:
        p = spec['_pump_cm']; out['pump'] = travel_block([False] + [abs(p[f] - p[f - 1]) > PART_CM for f in range(1, len(p))], rest, accel)
    h = spec.get('_hinge_deg')       # break round 1 drafts keep the hinge in the spec
    if os.path.exists(base + '_phys.json'):
        ph = json.load(open(base + '_phys.json')); h = ph.get('hinge_deg')
    if h: out['barrels'] = travel_block([False] + [abs(h[f] - h[f - 1]) > PART_DEG for f in range(1, len(h))], rest, accel)
    if os.path.exists(base + '_objects.json'):
        J = json.load(open(base + '_objects.json')); n = len(G)
        import magtrack2
        GW = [magtrack2.m4(G[f], Q[f]) for f in range(n)]; per = []
        for nm, v in J['joints'].items():
            for tr in (v.values() if isinstance(v, dict) else [v]): per.append(tr)
        mv = [False] * n
        for tr in per:
            P = [None if (f >= len(tr) or tr[f] is None) else (GW[f] @ np.array(tr[f]).reshape(4, 4))[:3, 3] for f in range(n)]
            for f in range(1, n - 1):
                if P[f] is None or P[f - 1] is None: continue
                step = float(np.linalg.norm(np.array(tr[f]).reshape(4, 4)[:3, 3] - np.array(tr[f - 1]).reshape(4, 4)[:3, 3])) * 100 if tr[f - 1] is not None else 0
                if step <= PART_CM: continue
                if P[f + 1] is not None:
                    a = P[f + 1] - 2 * P[f] + P[f - 1] - np.array([0, -9.81 / 900.0, 0])
                    if float(np.linalg.norm(a)) < 0.25 * 9.81 / 900.0: continue      # ballistic
                mv[f] = True
        if per: out['shells'] = travel_block(mv, rest, accel)
    return out


def sustained(G, Q, release):
    """R8 measures from the grip series (m) and the release frame: gun path (cm) and 90th percentile gun speed (cm/f) over the whole clip and over the release phase.
    Release phase = the frame the gun first leaves rest (cue) to release + 3; the cue is read from the motion, not from a mark, so it cannot be moved. Steps: grip position
    change arriving at each frame, frames 1 to n-1."""
    import numpy as np
    rest, accel, sp = gun_frames(G, Q); n = len(G); st = sp[1:]
    out = {'path_cm': round(float(st.sum()), 2), 'v90_cm_f': round(float(np.percentile(st, 90)), 3), 'frames': n}
    cue = next((f for f in range(1, n) if not rest[f]), None)
    if release is not None and cue is not None and release + 3 > cue:
        w = sp[cue:min(release + 3, n - 1) + 1]
        out.update(cue=cue, release=int(release), rel_path_cm=round(float(w.sum()), 2), rel_v90_cm_f=round(float(np.percentile(w, 90)), 3), rel_frames=int(len(w)))
    return out


def one(item):
    """One survey row. Errors are kept in the row ('error') so one clip never stops the run."""
    import rgate
    b = item['shipped'][:-4]; row = {'clip': item['rel'], 'family': None, 'gun': item['gun'], 'pick': item['pick'], 'take': item['take'], 'body': item['body'], 'side': item['side'],
                                     'kind': item['clip'] if item['kind'] == 'reload' else item['kind'], 'parked': item['parked'], 'shipped_glb': item['shipped'], 'missing': [], 'error': None}
    try:
        if not os.path.exists(b + '.json'): row['missing'].append('spec'); return row
        spec = json.load(open(b + '.json')); row['family'] = item.get('family') or rgate.family(dict(spec, _pick=spec.get('_pick') or item['pick'], _gun=spec.get('_gun') or item['gun']))
        if 'clip' not in spec:      # FBloop: a held idle, no clip name, no track
            row['frames'] = spec.get('frames'); row['r4'] = {'length': spec.get('frames')}; row['missing'] += ['clip name', 'gate', 'track', 'inertia', 'phys', 'objects']; row['note'] = 'idle hold after the fallback'; return row
        S = spec.get('_side', 'Right'); row['frames'] = spec.get('frames')
        G, Q, M = _clip_series(item['shipped'], spec['clip'], S); rest, accel, sp = gun_frames(G, Q); n = len(G)
        if n != spec.get('frames'): row['frames_glb'] = n
        _up = json.load(open(b + '_gate.json'))['layout']['hide_end'] if (spec.get('_lowered') and os.path.exists(b + '_gate.json')) else None
        row['r5'] = r5(item['shipped'], spec['clip'], S, _up); row['r5_pre_hide'] = _up is not None      # a lowered variant: the motion before hide_end, against the floors calibrated on that scope (checks.draft.r5_min_lowered)
        import armspeed; row['r10'] = armspeed.measure(item['shipped'], spec['clip'], S)
        gate = json.load(open(b + '_gate.json')) if os.path.exists(b + '_gate.json') else None
        if gate is None: row['missing'].append('gate')
        track = json.load(open(b + '_track.json')) if os.path.exists(b + '_track.json') else None
        if track is None: row['missing'].append('track')
        for k in ('_inertia', '_phys', '_objects'):
            if not os.path.exists(b + k + '.json'): row['missing'].append(k[1:])
        T = spec.get('_timing') or {}; mk = spec.get('_marks') or {}
        row['r4'] = {'length': spec.get('frames'), 'timing_out': T.get('out'), 'timing_seated': T.get('seated'), 'timing_handle': (T.get('handle') or [None])[0] if isinstance(T.get('handle'), list) else T.get('handle'), 'marks': mk}
        if gate:
            L = gate['layout']; row['r4'].update({'mag_out': L['mag_out'], 'seated': L['seated'], 'handle': L['handle'], 'hide_start': L['hide_start'], 'hide_end': L['hide_end'], 'hidden_frames': gate.get('hidden_frames')})
            row['r6'] = {k: gate.get(k) for k in ('start_cm', 'start_deg', 'end_cm', 'end_deg', 'end_step_cm')}
            row['gate_fails'] = gate['fails']; row['mag_hang_gate'] = gate.get('mag_hang'); row['mag_seen_frames'] = len(gate.get('mag_seen') or [])
        row['rest_frames'] = sum(rest); row['accel_frames'] = sum(accel)
        row['r8'] = sustained(G, Q, (track or {}).get('release', mk.get('release')))
        r2 = r2_parts(spec, b, G, Q, rest, accel)
        if track:
            mg = mag_rows(spec, track, G, Q, rest, accel)
            row['mag'] = mg
            if mg:
                r2['magazine'] = mg.pop('r2'); row['r2_states'] = mg.pop('r2_states')
                if gate: mg['on_screen_frames'] = sum(1 for f in (gate.get('mag_seen') or []) if track['frames'][f]['state'] in ('guided', 'loose', 'falling') and f > track['release'])
        row['r2'] = r2
        row['r2b'] = pump_closing_runs(spec, sp)
        if os.path.exists(b + '_inertia.json'):
            I = json.load(open(b + '_inertia.json')); row['inertia_mag'] = I.get('mag')
    except Exception:
        row['error'] = traceback.format_exc()[-700:]
    return row


def _init():
    pass


def run(argv):
    import regen
    opts = {n: common.opt(argv, n) for n in ('--manifest', '--out', '--jobs', '--limit', '--ref')}
    o = opts.get
    man = regen.load_manifest(o('--manifest')); items = regen.acceptance(man, True)
    if o('--ref'):
        for i in items: i['shipped'] = os.path.abspath(o('--ref')).replace(chr(92), '/') + '/' + i['root'] + '/' + i['rel']
    if o('--limit'): items = items[::max(1, len(items) // int(o('--limit')))][:int(o('--limit'))]
    t0 = time.time()
    with ProcessPoolExecutor(int(o('--jobs') or 8)) as ex: rows = list(ex.map(one, items, chunksize=4))
    json.dump({'thresholds': {'rest_sp': REST_SP, 'rest_w': REST_W, 'acc_a': ACC_A, 'acc_w': ACC_W, 'part_cm': PART_CM, 'part_deg': PART_DEG, 'thrown_gun_cm_f': THROWN_GUN_CM_F}, 'rows': rows},
              open(o('--out'), 'w'), indent=1)
    err = [r for r in rows if r['error']]
    print(f'{len(rows)} clips, {len(err)} errors, {time.time() - t0:.0f} s -> {o("--out")}')
    for r in err[:5]: print(r['clip'], r['error'][-300:])
    return 1 if err else 0


# ---------- SURVEY.md

NUMS = [  # (label, rule, getter)
    ('R1 exit speed cm/f', lambda r: (r.get('mag') or {}).get('exit_cm_f')),
    ('R1 gun speed at release cm/f', lambda r: (r.get('mag') or {}).get('gun_rel_cm_f')),
    ('R1 ratio exit / gun, thrown only', lambda r: (r.get('mag') or {}).get('ratio') if (r.get('mag') or {}).get('thrown') else None),
    ('R1 ratio exit / gun, dropped only', lambda r: (r.get('mag') or {}).get('ratio') if r.get('mag') and not r['mag'].get('thrown') else None),
    ('R1 ratio exit / gun, all', lambda r: (r.get('mag') or {}).get('ratio')),
    ('R1 thrown (1) or dropped (0)', lambda r: None if not r.get('mag') else int(bool(r['mag'].get('thrown')))),
    ('R1 sidecar ratio (_inertia mag.ratio)', lambda r: (r.get('inertia_mag') or {}).get('ratio')),
    ('R1 ratio exit / gun max 3 steps', lambda r: (r.get('mag') or {}).get('ratio3')),
    ('R2 magazine travel frames at rest', lambda r: ((r.get('r2') or {}).get('magazine') or {}).get('travel_at_rest')),
    ('R2 pump travel frames at rest', lambda r: ((r.get('r2') or {}).get('pump') or {}).get('travel_at_rest')),
    ('R2 barrels travel frames at rest', lambda r: ((r.get('r2') or {}).get('barrels') or {}).get('travel_at_rest')),
    ('R2 shells travel frames at rest', lambda r: ((r.get('r2') or {}).get('shells') or {}).get('travel_at_rest')),
    ('R2 parts travel frames outside accel (all parts)', lambda r: sum(v['travel_outside_accel'] for v in (r.get('r2') or {}).values()) if r.get('r2') else None),
    ('R3 decel max cm/f^2', lambda r: (r.get('mag') or {}).get('decel_max_cm_f2')),
    ('R3 decel frames over 0.25 g', lambda r: (r.get('mag') or {}).get('decel_frames')),
    ('R3 on screen frames, detached', lambda r: (r.get('mag') or {}).get('on_screen_frames')),
    ('R4 length', lambda r: (r.get('r4') or {}).get('length')),
    ('R4 mag_out', lambda r: (r.get('r4') or {}).get('mag_out')),
    ('R4 seated', lambda r: (r.get('r4') or {}).get('seated')),
    ('R4 handle', lambda r: (r.get('r4') or {}).get('handle')),
    ('R4 hide_start', lambda r: (r.get('r4') or {}).get('hide_start')),
    ('R4 hide_end', lambda r: (r.get('r4') or {}).get('hide_end')),
    ('R5 grip peak cm/f', lambda r: (r.get('r5') or {}).get('grip_peak')),
    ('R5 peak_at', lambda r: (r.get('r5') or {}).get('peak_at')),
    ('R5 stop loss max cm/f', lambda r: (r.get('r5') or {}).get('stop_max')),
    ('R5 stop loss min cm/f', lambda r: (r.get('r5') or {}).get('stop_min')),
    ('R5 muzzle / grip peak', lambda r: (r.get('r5') or {}).get('muz_over_grip')),
    ('R5 gap min frames', lambda r: (r.get('r5') or {}).get('gap_min_frames')),
    ('R5 gap max speed cm/f', lambda r: (r.get('r5') or {}).get('gap_max_speed')),
    ('R5 hold share', lambda r: (r.get('r5') or {}).get('hold_share')),
    ('R6 start cm', lambda r: (r.get('r6') or {}).get('start_cm')),
    ('R6 end cm', lambda r: (r.get('r6') or {}).get('end_cm')),
    ('R6 start deg', lambda r: (r.get('r6') or {}).get('start_deg')),
    ('R6 end deg', lambda r: (r.get('r6') or {}).get('end_deg')),
]
ORDER = ['front', 'masamune', 'hercules', 'grip', 'bullpup', 'top', 'smg_front', 'tube', 'break', 'fallback']


def _name(r):
    return r['clip'].rsplit('/', 1)[-1].replace('.glb', '')


def stat(rows, get):
    v = [(get(r), r) for r in rows]; v = [(x, r) for x, r in v if x is not None]
    if not v: return None
    xs = sorted(x for x, _ in v); lo = min(v, key=lambda t: t[0]); hi = max(v, key=lambda t: t[0])
    med = xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2
    return len(v), lo[0], med, hi[0], _name(lo[1]), _name(hi[1])


def f(x):
    return f'{x:.3g}' if isinstance(x, float) else str(x)


def md(argv):
    D = json.load(open(argv[0])); rows = D['rows']; out = []
    groups = {}
    for r in rows:
        groups.setdefault((r['family'], r['take']), []).append(r)
    out += ['# Survey of the reload clips (Phase 2a)', '', f'{len(rows)} clips ({sum(1 for r in rows if not r["parked"])} shipped, {sum(1 for r in rows if r["parked"])} parked); rows: `survey.json`; script: `tools/anim/authoring/checks/survey.py`.',
            'Measures only. Definitions are in the docstring of survey.py. Thresholds: ' + ', '.join(f'{k} {v}' for k, v in D['thresholds'].items()) + '.', '',
            'Cell format: min / median / max (n clips). The clip at each extreme is in the per-group tables below.', '']
    fams = [k for k in ORDER if any(g[0] == k for g in groups)]
    # headline: per family (takes merged)
    out += ['## Headline per family', '']
    heads = [('R1 ratio exit / gun', 'R1 ratio'), ('R5 grip peak cm/f', 'R5 grip peak'), ('R5 stop loss max cm/f', 'R5 stop loss'), ('R2 parts at rest (magazine, pump, barrels, shells)', 'R2'), ('R4 length', 'R4 length'), ('R4 mag_out', 'R4 mag_out'), ('R4 seated', 'R4 seated')]
    num = dict(NUMS)
    out += ['| family | clips | R1 ratio, thrown only (n) | R5 grip peak | R5 stop loss max | R2 at rest (frames) | R4 length | R4 mag_out | R4 seated |', '|---|---|---|---|---|---|---|---|---|']
    for fam in fams:
        rr = [r for r in rows if r['family'] == fam]; cells = []
        for key in ('R1 ratio exit / gun, thrown only', 'R5 grip peak cm/f', 'R5 stop loss max cm/f'):
            s = stat(rr, num[key]); cells.append('-' if s is None else f'{f(s[1])} / {f(s[2])} / {f(s[3])} ({s[0]})')
        parts = []
        for k, lab in (('R2 magazine travel frames at rest', 'mag'), ('R2 pump travel frames at rest', 'pump'), ('R2 barrels travel frames at rest', 'barrels'), ('R2 shells travel frames at rest', 'shells')):
            s = stat(rr, num[k])
            if s: parts.append(f'{lab} {f(s[1])} / {f(s[2])} / {f(s[3])} ({s[0]})')
        cells.append('; '.join(parts) or '-')
        for key in ('R4 length', 'R4 mag_out', 'R4 seated'):
            s = stat(rr, num[key]); cells.append('-' if s is None else f'{f(s[1])} / {f(s[2])} / {f(s[3])} ({s[0]})')
        out.append(f'| {fam} | {len(rr)} | ' + ' | '.join(cells) + ' |')
    out.append('')
    mg = [r for r in rows if r.get('mag')]; dr = [r['mag']['gun_rel_cm_f'] for r in mg if not r['mag']['thrown']]; th = [r['mag']['gun_rel_cm_f'] for r in mg if r['mag']['thrown']]
    out += ['## R1: thrown or dropped', '',
            f'Proposed definition: a magazine is thrown when the gun moves at the release step, gun_rel_cm_f >= {D["thresholds"]["thrown_gun_cm_f"]} cm/f (0.9 m/s); otherwise it is dropped (it leaves by gravity or the well slide).',
            f'Data: {len(mg)} clips with a detachable magazine, {len(th)} thrown, {len(dr)} dropped. Largest dropped gun speed {max(dr):.2f}, smallest thrown {min(th):.2f} cm/f: no clip lies between 2 and 3 cm/f, so the cut is not sensitive inside that gap.',
            'Per family (thrown / dropped): ' + '; '.join(f'{fam} {sum(1 for r in mg if r["family"] == fam and r["mag"]["thrown"])} / {sum(1 for r in mg if r["family"] == fam and not r["mag"]["thrown"])}' for fam in fams if any(r['family'] == fam for r in mg)) + '.',
            'Exit speed is measured on the first free step with gravity taken off (sf2.mag_speed); ratio3 uses the largest seat-point step of the 3 steps before the release, as sf2.mag_speed and inertia.mag_stats do. A chop that stops at the release gives a ratio3 well below the ratio. `_inertia.json` ratio (SF35, SF40) uses the contact speed where the draft hits the magazine.', '']
    out += ['## Per family and take', '']
    for (fam, take) in sorted(groups, key=lambda k: (ORDER.index(k[0]) if k[0] in ORDER else 99, str(k[1]))):
        rr = groups[(fam, take)]
        out += [f'### {fam}, take {take or "-"} ({len(rr)} clips)', '', '| number | n | min | median | max | min clip | max clip |', '|---|---|---|---|---|---|---|']
        for lab, g in NUMS:
            s = stat(rr, g)
            if s: out.append(f'| {lab} | {s[0]} | {f(s[1])} | {f(s[2])} | {f(s[3])} | {s[4]} | {s[5]} |')
        out.append('')
    out += ['## Numbers that cannot be computed, per family', '']
    kinds = ('gate', 'track', 'inertia', 'phys', 'objects')
    for fam in fams:
        rr = [r for r in rows if r['family'] == fam]; n = len(rr)
        have = {k: sum(1 for r in rr if k not in r['missing']) for k in kinds}
        no = [lab for lab, g in NUMS if not any(g(r) is not None for r in rr)]
        part = [lab for lab, g in NUMS if 0 < sum(1 for r in rr if g(r) is not None) < n and not lab.startswith(('R1 ratio exit / gun, dropped', 'R1 ratio exit / gun, thrown', 'R2 parts'))]
        err = sum(1 for r in rr if r['error'])
        out.append(f'- {fam} ({n} clips): sidecars present ' + ', '.join(f'{k} {v}' for k, v in have.items()) + '; no value for any clip: ' + (', '.join(no) or 'none')
                   + '; value for some clips only: ' + (', '.join(part) or 'none') + (f'; errors {err}' if err else ''))
    out += ['', 'Reasons:',
            '- No detachable magazine (tube, break, fallback): the track holds a seated dummy, so R1 and R3 have no value. Tube loads shells, break loads shells into barrels.',
            '- R2 pump: only tube specs carry `_pump_cm`. R2 barrels: only break `_phys.json` (`hinge_deg`). R2 shells: only `_objects.json` (tube, break; break guns without shell meshes have an empty one). R2 magazine: clips with a track that has a falling magazine.',
            '- R2 for the cocking handle or bolt of the SMG, rifle and shotgun clips is not computed: the spec holds the game animation time of the part (`_part_frames`), not a displacement, and the game animation is not read here.',
            '- `_inertia.json` exists only for SF35 and SF40 (round 4 generator); `_phys.json` and `_prims.json` only for break. The R1 sidecar ratio therefore exists for the 80 smg_front files of SF35 and SF40.',
            '- FBloop (56 files) is a 10 frame idle hold: spec holds only `frames`, no clip name, track or gate. Only its length is surveyed.',
            '- R4 handle is None where the clip has no handle, bolt or latch hit (break, fallback).',
            '- R6 comes from the gate files only; the 56 FBloop clips have none.', '']
    open(argv[1], 'w').write('\n'.join(out) + '\n')
    print('wrote', argv[1])


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('run', 'md'): raise SystemExit(__doc__)
    sys.exit(run(sys.argv[2:]) if sys.argv[1] == 'run' else md(sys.argv[2:]))
