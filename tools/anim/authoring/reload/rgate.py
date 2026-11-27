"""Gate checks of the production rifle reload clips (arm clip + its magazine track), either hand, either body.
Limits: weapons.json checks.rreload. Camera: the raised-pose fit.

gate(spec, track) -> dict
  start/end pose   first and last frame against the gun's raised idle (rest glb), own arm and gun
  layout           hide_start, hide_end: the longest run of frames that holds the seated frame and in which the gun,
                   its hand and forearm and every magazine are off screen in first person; mag_out, seated, length,
                   handle (frame of the handle, bolt or latch hit, None when the clip has none), keys (padded length)
  hidden rules     the window is at least hidden_min_frames long, the handle hit is not inside it, and a magazine
                   thrown in view is off screen before hide_start (so the fast-forward never shows it)
  magazine         mag_hang (frames in the air and not in free fall), release_dv (jump of its world velocity where
                   the slide ends, gravity taken off), exit and insertion off the well axis, fresh magazine drift
  body             eye distance while the gun is on screen (rule, or the gun's idle distance less 1 cm where that is nearer), screen cover,
                   wrist (all frames from the idle / while the hand or forearm is on screen from the bind pose), reach, shoulder
                   pull, body blocks, gap to the other gun
usage: rgate.py <spec.json>       (reads its _track)
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, manifest
import numpy as np
from glb import Glb
from fk import Clip, qmul, qinv, qrot
import rchecks, magtrack2, magtrack3, gungeo, motionstats, rarmset

LIM = manifest.load()['checks']['rreload']
HAND = ['Hand', 'HandThumb1', 'HandThumb2', 'HandIndex1', 'HandIndex2', 'HandIndex3', 'HandMiddle1', 'HandMiddle2', 'HandMiddle3', 'HandRing1', 'HandRing2', 'HandRing3',
        'HandPinky1', 'HandPinky2', 'HandPinky3']
_sph = None


# Family profiles. Each family was gated by its own copy of this file; the differences are the knobs below. A profile
# lists only what differs from DEFAULT. A clip's gate file reads as it did when the clip was made.
#   hang_next_falling   a hanging frame also needs the next frame to be falling (guard against the release frame); on for every family
#   offaxis_near_only   the off-axis check counts only frames within 0.10 m of the seat in every direction; on for every family
#                       (both were bug fixes made in the SMG round 1 copy; every other family now gets them, 2b)
#   axis_check_plan     the exit-at-distance check uses the track plan's axis_check_m (default 0.10 m)
#   second_mag_visible  the old magazine still falling while the fresh one exists counts for the screen test
#   series              adds vis_gun, vis_arm, vis_mag, wrist_series, wrist_view_at, shoulder_at to the gate file
DEFAULT = {'hang_next_falling': True, 'offaxis_near_only': True, 'axis_check_plan': False, 'second_mag_visible': False, 'series': False}
_SMG_R1 = {'axis_check_plan': True, 'second_mag_visible': True}
PROFILES = {'front': {}, 'masamune': {}, 'hercules': {}, 'grip': _SMG_R1, 'bullpup': _SMG_R1, 'top': _SMG_R1, 'smg_front': {}, 'tube': {}, 'break': {'series': True}, 'fallback': {}}
_PICK_FAMILY = (('FB', 'fallback'), ('SG', 'grip'), ('SB', 'bullpup'), ('ST', 'top'), ('SF', 'smg_front'), ('TU', 'tube'), ('BR', 'break'), ('F', 'front'), ('M', 'masamune'), ('H', 'hercules'))


def family(spec):
    """The family of a clip, from the pick id (FB, FBloop: the quick-drop clips) and the manifest category of its gun;
    a gun without a manifest category falls back to the pick's prefix (SG, SB, ST, SF, TU, BR, F, M, H)."""
    pick = str(spec.get('_pick') or '')
    if pick in ('FB', 'FBloop'): return 'fallback'
    cat = next(((g.get('reload') or {}).get('category') for g in manifest.load()['guns'] if g['id'] == spec.get('_gun')), None)
    if cat in PROFILES: return cat
    return next((f for p, f in _PICK_FAMILY if pick.startswith(p)), None)


def profile(spec):
    """The knobs of a clip's family: DEFAULT with the family's differences."""
    return dict(DEFAULT, **PROFILES.get(family(spec), {}))


def sphere(r):
    global _sph
    if _sph is None:
        d = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1], [0.58, 0.58, 0.58], [-0.58, 0.58, 0.58], [0.58, -0.58, 0.58], [0.58, 0.58, -0.58],
                      [-0.58, -0.58, 0.58], [-0.58, 0.58, -0.58], [0.58, -0.58, -0.58], [-0.58, -0.58, -0.58]]); _sph = d
    return _sph * r


def arm_points(W, ix, S):
    """Points on the hand and forearm of one side (joint spheres), world."""
    P = []
    for n in HAND:
        if S + n in ix: P.append(W[ix[S + n]][0] + sphere(0.028))
    a, b = W[ix[S + 'ForeArm']][0], W[ix[S + 'Hand']][0]
    for t in np.linspace(0.0, 1.0, 9): P.append(a + (b - a) * t + sphere(0.05 - 0.012 * t))
    return np.concatenate(P)


def exit_at(track, gid, clip, at=0.10):
    """Sideways offset (cm) of the leaving magazine from the well axis where it is `at` metres out along the axis,
    interpolated between frames (gun axes). The off-axis check below samples only frames inside the first 10 cm, and
    a fast magazine can pass them in one frame (a Hercules draft left 23 deg off the axis and passed). None when it
    never gets that far out (it stays on the rig)."""
    v = magtrack2.vanilla(gid, clip); cen = np.r_[v['centre'], 1]; s0 = (v['seat'] @ cen)[:3]; ex = np.array(track['exit_gun_axes'], float); ex /= np.linalg.norm(ex)
    prev = (0.0, 0.0)
    for f in range(track['release'] + 1, len(track['frames'])):
        row = track['frames'][f]
        if row['state'] not in ('guided', 'falling') or row['s'] < 0.5: break
        d = (np.array(row['m']).reshape(4, 4) @ cen)[:3] - s0; al = float(d @ ex); lat = float(np.linalg.norm(d - al * ex))
        if al >= at:
            t = (at - prev[0]) / max(al - prev[0], 1e-9); return round((prev[1] + t * (lat - prev[1])) * 100, 2)
        prev = (al, lat)
    return None


def gate(spec, track=None):
    if isinstance(spec, str): spec = json.load(open(spec))
    if track is None: track = json.load(open(spec['_track']))
    gid, clip = spec['_gun'], spec['_gun_clip']; N = spec['frames']; T = spec['_timing']; S = spec.get('_side', 'Right'); O = 'Left' if S == 'Right' else 'Right'
    g = Glb(spec['out']); c = Clip(g, spec['clip']); nm = g.names; ix = {n: i for i, n in enumerate(nm)}
    r = Glb(common.mp(spec.get('_idle') or spec['src'])); R0 = Clip(r, 'idle').world(0); rix = {n: i for i, n in enumerate(r.names)}
    PG, PO = rchecks.gun_points(gid), rchecks.gun_points(spec['_left_gun'] if S == 'Right' else gid, 5000)
    v = magtrack2.vanilla(gid, clip); cen = np.r_[v['centre'], 1]; seat = v['seat']
    V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb'))[::5]; V1 = np.c_[V, np.ones(len(V))]
    Ms = [np.array(x['m']).reshape(4, 4) for x in track['frames']]; sc = [x['s'] for x in track['frames']]; st = [x['state'] for x in track['frames']]
    W = [c.world(f) for f in range(N)]; out = {'clip': spec['_draft'], 'gun': gid, 'side': S, 'body': spec['_body'], 'gun_clip': clip, 'frames': N, 'fails': []}; P = profile(spec)
    own = [n for n in nm if n.startswith(S) and any(k in n for k in ('Shoulder', 'Arm', 'ForeArm', 'Hand')) and 'Leg' not in n] + ['Weapon' + S]

    def pose_err(f):
        dc = dd = 0.0
        for n in own:
            t, q = W[f][ix[n]]; t0, q0 = R0[rix[n]]; rel = qmul(qinv(q0), q)
            dc = max(dc, float(np.linalg.norm(t - t0)) * 100); dd = max(dd, math.degrees(2 * math.atan2(float(np.linalg.norm(rel[:3])), abs(float(rel[3])))))
        return dc, dd
    s0, s1 = pose_err(0), pose_err(N - 1)
    out['start_cm'], out['start_deg'], out['end_cm'], out['end_deg'] = round(s0[0], 4), round(s0[1], 4), round(s1[0], 4), round(s1[1], 4)
    hq0, fq0 = R0[rix[S + 'Hand']][1], R0[rix[S + 'ForeArm']][1]; sh0 = R0[rix[S + 'Arm']][0]
    shw = None
    if (spec.get('_judge') or {}).get('low_w'):      # variant clips (discard.py): the shoulder is judged against the stance blend of the two idles (raised idle the author's IK works from, lowered idle weighted by low_w per frame), not against the lowered idle alone (its own shoulder sits 5 to 6 cm from the raised one)
        _r = Glb(common.mp(spec['src'])); sh_r = Clip(_r, 'idle').world(0)[{n: i for i, n in enumerate(_r.names)}[S + 'Arm']][0]; shw = [np.array(sh_r) + w * (np.array(sh0) - np.array(sh_r)) for w in spec['_judge']['low_w']]
    # bind pose (every joint at its node rotation): the wrist bend in view is measured from it, not from the idle (plift4: the idle's own wrist is 32.7 deg from the bind pose)
    RB = Clip(r, 'idle').world(0, local={i: (np.array(n.get('translation', [0, 0, 0]), float), np.array(n.get('rotation', [0, 0, 0, 1]), float)) for i, n in enumerate(r.j['nodes'])})
    hqb, fqb = RB[rix[S + 'Hand']][1], RB[rix[S + 'ForeArm']][1]; wrb = []
    hip, sp3 = W[0][ix['Hips']][0], W[0][ix['Spine3']][0] + np.array([0, 0.12, 0]); legs = [(W[0][ix[f'{s}UpLeg']][0], W[0][ix[f'{s}Leg']][0]) for s in ('Left', 'Right')]
    belt = (hip + np.array([-0.17, -0.02, 0]), hip + np.array([0.17, -0.02, 0]))
    cov = []; eye = []; gun_on = []; arm_on = []; mag_on = []; wr = []; reach = []; shp = []; body = []; gap = []; C = []
    for f in range(N):
        Wf = W[f]; G = Wf[ix['Weapon' + S]]; GP = rchecks.place(G, PG); cv = rchecks.cover(GP); cov.append(cv); gun_on.append(cv > 0)
        eye.append(float(np.linalg.norm(GP - rchecks.EYE, axis=1).min()) * 100)
        arm_on.append(bool(rchecks.screen(arm_points(Wf, ix, S))[2].any()))
        if sc[f] > 0.5:
            MP = rchecks.place(G, (V1 @ Ms[f].T)[:, :3]); mag_on.append(bool(rchecks.screen(MP)[2].any()))
        else: mag_on.append(False)
        row = track['frames'][f]
        if P['second_mag_visible'] and row.get('s2', 0) > 0.5:   # round1 grip/bullpup/top: the old magazine still falling while the fresh one exists
            M2 = np.array(row['m2']).reshape(4, 4); on2 = bool(rchecks.screen(rchecks.place(G, (V1 @ M2.T)[:, :3]))[2].any()); mag_on[-1] = mag_on[-1] or on2
        C.append(rchecks.place(G, (Ms[f] @ cen)[None, :3])[0])
        hp, hq = Wf[ix[S + 'Hand']]; ep, fq = Wf[ix[S + 'ForeArm']]; sp = Wf[ix[S + 'Arm']][0]; uf = (hp - ep) / np.linalg.norm(hp - ep)
        rel = qmul(hq, qinv(qmul(fq, qmul(qinv(fq0), hq0))))
        wr.append(2 * math.degrees(math.acos(min(1.0, math.sqrt(rel[3] ** 2 + np.dot(rel[:3], uf) ** 2)))))
        relb = qmul(hq, qinv(qmul(fq, qmul(qinv(fqb), hqb)))); wrb.append(2 * math.degrees(math.acos(min(1.0, math.sqrt(relb[3] ** 2 + np.dot(relb[:3], uf) ** 2)))))
        reach.append(float(np.linalg.norm(hp - sp) / (np.linalg.norm(ep - sp) + np.linalg.norm(hp - ep)))); shp.append(float(np.linalg.norm(sp - (sh0 if shw is None else shw[f]))) * 100)
        d = np.minimum.reduce([rchecks.seg_dist(GP, hip, sp3) - 0.15, rchecks.seg_dist(GP, *belt) - 0.12] + [rchecks.seg_dist(GP, *l) - 0.085 for l in legs]); body.append(float(d.min()) * 100)
        a, b = GP[::6], rchecks.place(Wf[ix['Weapon' + O]], PO)[::4]; gap.append(float(np.sqrt(((a[:, None] - b[None]) ** 2).sum(2)).min()) * 100)
    C = np.array(C); am = lambda a: int(np.argmax(a)); an = lambda a: int(np.argmin(a))
    # ---- layout: the hidden run around the seated frame
    se = T['seated']; vis = [gun_on[f] or arm_on[f] or mag_on[f] for f in range(N)]
    if vis[se]: hs = he = None
    else:
        hs = he = se
        while hs > 0 and not vis[hs - 1]: hs -= 1
        while he < N - 1 and not vis[he + 1]: he += 1
    h = T.get('handle'); gw = T['parts'].get('magazine_grabber', {}).get('window')
    hit = spec.get('_marks', {}).get('hit'); keys = rarmset.good_keys(N)
    out['layout'] = {'hide_start': hs, 'hide_end': he, 'mag_out': track['release'], 'seated': se, 'length': N, 'handle': hit, 'keys': keys}
    out['hidden_frames'] = (he - hs + 1) if hs is not None else 0
    out['gun_hidden'] = [next((f for f in range(N) if not gun_on[f]), None), max([f for f in range(N) if not gun_on[f]] or [None])]
    out['mag_seen'] = [f for f in range(N) if mag_on[f] and st[f] not in ('seated',)][:40]; out['arm_only_seen_in_gun_hidden'] = int(sum(1 for f in range(N) if arm_on[f] and not gun_on[f]))
    if P['series']: out['vis_gun'] = [f for f in range(N) if gun_on[f]]; out['vis_arm'] = [f for f in range(N) if arm_on[f]]; out['vis_mag'] = [f for f in range(N) if mag_on[f]]     # round 3: what keeps the opening visible
    if hs is None: out['fails'].append('not hidden at the seated frame')
    else:
        if out['hidden_frames'] < LIM['hidden_min_frames']: out['fails'].append(f"hidden only {out['hidden_frames']} f")
        if hit is not None and hs <= hit <= he:
            if hit > se + 8:   # a hit made out of view on purpose (hip bump): the window to fast-forward ends before it
                he = hit - 4; out['layout']['hide_end'] = he; out['hidden_frames'] = he - hs + 1; out['hit_hidden'] = True
            else: out['fails'].append(f'handle hit f{hit} inside the hidden window')
        late = [f for f in range(hs, N) if mag_on[f] and st[f] in ('falling', 'guided', 'fresh')]
        if late: out['fails'].append(f'magazine on screen after hide_start (f{late[0]})')
    # ---- magazine
    A = np.zeros((N, 3)); A[1:-1] = C[2:] - 2 * C[1:-1] + C[:-2]; g0 = magtrack2.G_ACC; ff = track['free_from']; gone = track['gone']
    det = [f for f in range(N) if sc[f] > 0.5 and st[f] in ('guided', 'falling')]
    fall = [f for f in det if st[f] == 'falling']
    hang = [f for f in fall if 0 < f < N - 1 and f not in (ff, gone - 1) and (not P['hang_next_falling'] or st[f + 1] == 'falling') and C[f][1] > 0.15 and (abs(A[f][1] + g0) > 0.25 * g0 or np.linalg.norm(A[f][[0, 2]]) > 0.25 * g0)]
    out['mag_hang'] = len(hang); out['mag_fall'] = [fall[0], fall[-1]] if fall else None; out['mag_gone'] = gone
    if len(fall) >= 2 and ff - 2 >= 0:
        vg = C[ff - 1] - C[ff - 2]; vf = C[ff] - C[ff - 1] - np.array([0, -g0, 0]); out['release_dv_cm_f'] = round(float(np.linalg.norm(vf - vg)) * 100, 2)
    else: out['release_dv_cm_f'] = 0.0
    fresh = [f for f in range(N) if st[f] == 'fresh' and sc[f] > 0.5]
    out['fresh'] = [fresh[0], fresh[-1]] if fresh else None; out['fresh_drift_cm'] = round(float(max(np.linalg.norm(C[f] - C[fresh[-1]]) for f in fresh)) * 100, 2) if fresh else 0.0

    def off_axis(frames, axis):
        worst = 0.0
        for f in frames:
            dv = (Ms[f] @ cen)[:3] - (seat @ cen)[:3]; al = float(dv @ axis)
            if abs(al) < 0.10 and (not P['offaxis_near_only'] or np.linalg.norm(dv) < 0.10): worst = max(worst, float(np.linalg.norm(dv - al * axis)))
        return round(worst * 100, 2)
    ex = np.array(track['exit_gun_axes']); out['insert_off_axis_cm'] = off_axis(fresh, v['enter']); out['exit_off_axis_cm'] = off_axis([f for f in det if st[f] == 'guided'], ex)
    if out['mag_hang'] > LIM['mag_hang_frames']: out['fails'].append(f"magazine hangs {out['mag_hang']} f")
    if out['release_dv_cm_f'] > LIM['release_dv_max_cm_f']: out['fails'].append(f"release velocity jumps {out['release_dv_cm_f']} cm/f")
    if out['insert_off_axis_cm'] > LIM['off_axis_max_cm']: out['fails'].append(f"insertion {out['insert_off_axis_cm']} cm off axis")
    if out['exit_off_axis_cm'] > LIM['off_axis_max_cm']: out['fails'].append(f"exit {out['exit_off_axis_cm']} cm off axis")
    out['exit_at_10cm'] = exit_at(track, gid, clip, track.get('plan', {}).get('axis_check_m', 0.10) if P['axis_check_plan'] else 0.10)   # round2 TOP: a 3 cm rail, checked over 4 cm
    if out['exit_at_10cm'] is not None and out['exit_at_10cm'] > LIM['off_axis_max_cm']: out['fails'].append(f"exit {out['exit_at_10cm']} cm off axis at 10 cm out")
    if track.get('plan', {}).get('mode') == 'inertia':   # free from the release frame on: it must still leave along the well
        out['mag_exit'] = magtrack3.exit_check(track, gid, clip)
        if out['mag_exit']['off_axis_cm'] > LIM['off_axis_max_cm'] or out['mag_exit']['into_gun_cm'] > 0.5: out['fails'].append(f"magazine leaves the well {out['mag_exit']['off_axis_cm']} cm off its axis")
    if out['fresh_drift_cm'] > 0.1: out['fails'].append(f"fresh magazine drifts {out['fresh_drift_cm']} cm")
    # the last frames settle into the idle: a big last step is a jump the end-pose check cannot see (the author forces
    # the last key to the idle; seen 2026-11-12 when the settle move of M03 was commented out by mistake)
    gp = [np.array(W[f][ix['Weapon' + S]][0]) for f in range(N - 3, N)]
    out['end_step_cm'] = round(float(max(np.linalg.norm(gp[k + 1] - gp[k]) for k in range(2))) * 100, 2)
    if out['end_step_cm'] > LIM.get('end_step_max_cm', 0.5): out['fails'].append(f"gun moves {out['end_step_cm']} cm in the last frames")
    # ---- body
    view = [f for f in range(N) if arm_on[f]]     # the wrist counts while the hand or forearm is on screen
    eyev = [eye[f] if gun_on[f] else 9e9 for f in range(N)]; out['eye_any_cm'] = [round(min(eye), 1), an(eye)]     # the rule is for the gun on screen
    if P['series']: out['wrist_series'] = [round(x, 1) for x in wr]
    out['eye_cm'] = [round(min(eyev), 1), an(eyev)]; out['cover_peak'] = [round(max(cov), 1), am(cov)]; out['wrist'] = [round(max(wr), 1), am(wr)]
    out['wrist_view'] = round(max([wr[f] for f in view] or [0]), 1); out['wrist_view_bind'] = round(max([wrb[f] for f in view] or [0]), 1); jd = spec.get('_judge') or {}; rf = jd.get('reach_frames') or [0, N - 1]      # _judge (discard.py variants): reach and shoulder are judged where the author's IK arm is in effect, not on the lowered idle's own arm; eye_idle_cm: the shipped raised idle's
    ro = [reach[f] for f in range(N) if not rf[0] <= f <= rf[1]]      # the frames outside the judged window (the end overlay, the lowered idle): no frame straighter than the clip's own last frame (the idle) by more than 0.003
    if ro and jd.get('reach_frames') and max(ro) > max(LIM['reach_max'], reach[N - 1]) + 0.003: out['fails'].append(f"arm straighter than the idle: reach {round(max(ro), 3)} (idle {round(reach[N - 1], 3)})")
    rr = reach[rf[0]:rf[1] + 1]; ss = shp[rf[0]:rf[1] + 1]; out['reach'] = [round(max(rr), 3), am(rr) + rf[0]]; out['shoulder_pull_cm'] = round(max(ss), 1)
    if P['series']: out['wrist_view_at'] = max(view, key=lambda f: wr[f]) if view else None; out['shoulder_at'] = am(shp)     # break-2: frames of the worst values
    out['body_cm'] = [round(min(body), 1), an(body)]; out['guns_gap_cm'] = [round(min(gap), 1), an(gap)]
    if max(out['start_cm'], out['end_cm']) > LIM['end_max_cm'] or max(out['start_deg'], out['end_deg']) > LIM['end_max_deg']: out['fails'].append('start or end pose')
    eye0 = jd.get('eye_idle_cm') or eye[0]; out['eye_idle_cm'] = round(eye0, 1); emin = min(LIM['eye_min_cm'], eye0 - 1.0)   # a gun whose idle is nearer than the rule may come 1 cm nearer than its idle
    if out['eye_cm'][0] < emin: out['fails'].append(f"eye {out['eye_cm'][0]} cm (idle {out['eye_idle_cm']})")
    if out['cover_peak'][0] > LIM['cover_max_pct']: out['fails'].append(f"cover {out['cover_peak'][0]} %")
    if out['wrist'][0] > LIM['wrist_max_deg']: out['fails'].append(f"wrist {out['wrist'][0]} deg")
    if out['wrist_view_bind'] > LIM['wrist_view_bind_max_deg']: out['fails'].append(f"wrist in view {out['wrist_view_bind']} deg from the bind pose")      # wrist_view (from the idle) is reported, not gated
    if out['reach'][0] > LIM['reach_max']: out['fails'].append(f"reach {out['reach'][0]}")
    if out['shoulder_pull_cm'] > LIM['shoulder_pull_max_cm']: out['fails'].append(f"shoulder pulled {out['shoulder_pull_cm']} cm")
    if out['body_cm'][0] < LIM['body_min_cm']: out['fails'].append(f"gun {-out['body_cm'][0]} cm inside the body")
    if out['guns_gap_cm'][0] <= 0.5: out['fails'].append('guns touch')
    s = motionstats.stats(spec['out'], spec['clip'], S, 0.55)
    out['motion'] = {k: s[k] for k in ('peak_speed', 'p90_speed', 'peak_at', 'stop', 'jerk_events', 'hold_share')}
    return out


def line(o):
    L = o['layout']; m = o['motion']
    return (f"{o['clip']:44s} start {o['start_cm']:.3f}/{o['start_deg']:.3f} end {o['end_cm']:.3f}/{o['end_deg']:.3f} hide {L['hide_start']}-{L['hide_end']} out {L['mag_out']} seat {L['seated']} len {L['length']} hit {L['handle']} "
            f"| eye {o['eye_cm'][0]} cover {o['cover_peak'][0]} wrist {o['wrist'][0]}/{o['wrist_view']} reach {o['reach'][0]} sh {o['shoulder_pull_cm']} body {o['body_cm'][0]} gap {o['guns_gap_cm'][0]} "
            f"| hang {o['mag_hang']} dv {o['release_dv_cm_f']} axis {o['exit_off_axis_cm']}/{o['insert_off_axis_cm']} gone {o['mag_gone']} | peak {m['peak_speed']} stop {m['stop']} | FAILS {o['fails']}")


if __name__ == '__main__':
    o = gate(sys.argv[1]); print(line(o))
