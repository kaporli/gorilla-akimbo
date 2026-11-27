"""Owner rules on reload clips, round pvan2 (2026-11-24): speed caps, dead pause, fling, hidden-phase leak, two-gun clearance.

series(glb, clip, side)   -> dict of per-frame arrays: G grip (cm), Q gun rotation (xyzw), H hand joint (cm), A arm joints (cm: ForeArm, Hand), 30 fps from the keys (wclip.TClip)
layout(stem)              -> release, free_from, seated, hide_start, hide_end, hit (from <stem>_track.json and <stem>_gate.json), None where the clip has no such file
features(S, L)            -> the measures below, per clip, from a series and a layout. Units cm and frames.

Measures (frame f = step arriving at f):
  R2 speed caps   post-seat window seat..end: peak gun speed (cm/f), peak gun acceleration (cm/f^2, |v[f]-v[f-1]|), peak hand speed (Hand joint, cm/f);
                  the same three over the whole clip are reported (whole_*), not gated: the release drive is as fast as the rise in shipped clips.
  R3 dead pause   longest run of consecutive near-still gun frames (grip step under STILL_CM and turn under STILL_DEG) inside release..hide_start (the discard phase).
  R4 fling        release phase, the frames from the cue (the gun first leaves rest) to release + 3: straightness (chord / path of the grip), longest run of frames
                  at constant speed (within CONST_BAND of the window peak), largest acceleration spike at the start and at the stop of the drive.
  R1 leak         (needs the gun mesh, series_vis): gun turn speed and the angle from the end pose on the frames after the hidden window in which any gun vertex is in the frame.
  R5 clearance    (needs the gun mesh) the clip mirrored onto the other hand (x negated about the body mid plane): minimum distance between the gun+arm points of the two guns on
                  every frame, and the lateral extent of the gun+arm points (outward max |x| and inward min |x|, cm).
"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..', 'reload')); sys.path.insert(0, os.path.join(HERE, '..'))
import renv
import numpy as np
from glb import Glb
from wclip import TClip
from fk import qmul, qinv

STILL_CM = 0.5        # near-still gun: grip step under this (cm/f) ...
STILL_DEG = 1.0       # ... and turn under this (deg/f)
CONST_BAND = 0.15     # constant-speed run: speed within this share of the window's peak


def series(glb, clip, side):
    c = TClip(Glb(glb), clip); nm = c.names; gi = nm.index('Weapon' + side); hi = nm.index(side + 'Hand'); fi = nm.index(side + 'ForeArm')
    G, Q, H, A = [], [], [], []
    for f in range(c.frames):
        W = c.wf(f); G.append(np.array(W[gi][0], float) * 100); Q.append(np.array(W[gi][1], float)); H.append(np.array(W[hi][0], float) * 100)
        A.append(np.array([W[fi][0], W[hi][0]], float) * 100)
    return {'G': np.array(G), 'Q': np.array(Q), 'H': np.array(H), 'A': np.array(A), 'n': c.frames}


def layout(stem):
    L = {}
    try:
        t = json.load(open(stem + '_track.json')); L['release'] = t.get('release'); L['free_from'] = t.get('free_from')
    except OSError: pass
    try:
        g = json.load(open(stem + '_gate.json'))['layout']; L.update(seated=g.get('seated'), hide_start=g.get('hide_start'), hide_end=g.get('hide_end'), hit=g.get('handle'), mag_out=g.get('mag_out'))
    except OSError: pass
    return L


def turn_deg(q0, q1):
    d = qmul(qinv(np.asarray(q0)), np.asarray(q1)); return math.degrees(2 * math.atan2(float(np.linalg.norm(d[:3])), abs(float(d[3]))))


def steps(S):
    G = S['G']; n = len(G); v = np.zeros((n, 3)); v[1:] = G[1:] - G[:-1]
    sp = np.linalg.norm(v, axis=1); acc = np.zeros(n); acc[2:] = np.linalg.norm(v[2:] - v[1:-1], axis=1)
    rot = np.array([0.0] + [turn_deg(S['Q'][f - 1], S['Q'][f]) for f in range(1, n)])
    hs = np.zeros(n); hs[1:] = np.linalg.norm(S['H'][1:] - S['H'][:-1], axis=1)
    return v, sp, acc, rot, hs


def longest_run(flags):
    best = cur = 0
    for x in flags:
        cur = cur + 1 if x else 0; best = max(best, cur)
    return best


def cue_frame(sp, rot):
    """First frame the gun leaves rest (survey.REST_SP / REST_W)."""
    import survey
    return next((f for f in range(1, len(sp)) if not (sp[f] < survey.REST_SP and rot[f] < survey.REST_W)), None)


def features(S, L):
    v, sp, acc, rot, hs = steps(S); n = S['n']; R = L.get('release'); st = L.get('seated'); out = {'n': n, 'whole_peak_sp': float(sp.max()), 'whole_peak_acc': float(acc.max()), 'whole_peak_hs': float(hs.max())}
    if st is not None and st < n - 1:
        w = slice(st, n); out.update(post_sp=float(sp[w].max()), post_acc=float(acc[w].max()), post_hs=float(hs[w].max()), post_rot=float(rot[w].max()))
    hsx = L.get('hide_start')
    if R is not None:
        end = hsx if hsx else min(n - 1, (L.get('free_from') or R) + 12)
        still = [bool(sp[f] < STILL_CM and rot[f] < STILL_DEG) for f in range(R + 1, max(R + 1, end))]
        out['still_run'] = longest_run(still); out['still_window'] = [R + 1, end - 1]
        cue = cue_frame(sp, rot); e = min(R + 3, n - 1)
        if cue is not None and e > cue + 1:
            a = max(cue, 1); P = S['G'][a - 1:e + 1]; path = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum()); chord = float(np.linalg.norm(P[-1] - P[0]))
            w = sp[a:e + 1]; pk = float(w.max()); out.update(fl_cue=a, fl_straight=round(chord / path, 4) if path else None, fl_const_run=longest_run([abs(x - pk) <= CONST_BAND * pk for x in w]) if pk else 0, fl_peak=round(pk, 3))
            dv = np.linalg.norm(v[a:e + 1] - v[a - 1:e], axis=1); out['fl_acc_start'] = round(float(dv[:2].max()), 3); out['fl_acc_stop'] = round(float(dv[-3:].max()), 3)
    return out


# ------------------------------------------------------------------------------------------------ needs the gun mesh (Warden) and the game camera
ARM_R = 4.0          # cm: radius of the forearm and hand polyline in the clearance
GUN_STRIDE = 12


def series_vis(clips, body, side, pick, nm='empty_reload'):
    """Per frame, from a built clip folder (<clips>/<body>/warden_<side>_<pick>_<nm>.glb): gun and magazine vertices in the game-camera frame, the gun turn, and the
    clearance of the clip against its own mirror image on the other hand. Warden only (lift.cloud). Returns arrays and the clip's layout."""
    import lift, visibility as V
    from scipy.spatial import cKDTree
    s = lift.stem(clips, body, side, pick, nm); trk = json.load(open(s + '_track.json')); lay = layout(s)
    r, Lp = V.poses(s + '.glb', 'reload_draft', None, side, 'raised'); S = 'Right' if side == 'right' else 'Left'; eye, hh = V.camera(body)
    hj = [r.idx[n] for n in r.names if n.startswith(S + 'Hand')]; ei = r.idx[S + 'ForeArm']; hi = r.idx[S + 'Hand']; n = len(Lp)
    cl = lift.cloud(); gun = cl['gun'][::GUN_STRIDE]; sg = 1.0 if side == 'right' else -1.0
    out = {'n': n, 'gun_in': [], 'gun_in_n': [], 'hand_in': [], 'mag_in': [], 'turn': [], 'idle_turn': [], 'clear_cm': [], 'out_x': [], 'in_x': [], 'sr': None}
    q0 = None; sr = lift.series2(clips, body, side, pick, nm); out['sr'] = {'R': sr['R'], 'F': sr['F']}
    for f in range(n):
        W = r.world(Lp[f]); wt = (np.array(W[r.idx['Weapon' + S]][0], float), tuple(W[r.idx['Weapon' + S]][1]))
        G = V.R.place(wt, cl['gun']); m = V.margin(G, eye, hh); H = np.array([W[j][0] for j in hj]); mh = V.margin(H, eye, hh)
        out['gun_in_n'].append(int((m > 0).sum())); out['gun_in'].append(float(m.max())); out['hand_in'].append(int((mh > 0).sum()))
        # whole arm: elbow, wrist and fingers
        elbow = np.array(W[ei][0], float); wrist = np.array(W[hi][0], float); seg = np.array([elbow + (wrist - elbow) * t for t in np.linspace(0, 1, 6)])
        mp = lift.mag_pts(sr, f) if f < len(sr['trk']['frames']) else None; out['mag_in'].append(0 if mp is None else int((V.margin(mp, eye, hh) > 0).sum()))
        out['hand_in'][-1] = int((V.margin(np.vstack([H, seg]), eye, hh) > 0).sum())
        q = np.array(wt[1], float)
        if q0 is None: q0 = q
        out['turn'].append(0.0 if f == 0 else turn_deg(prevq, q)); out['idle_turn'].append(turn_deg(q0, q)); prevq = q
        Gs = V.R.place(wt, gun); parts = [Gs]      # the gun with its seated magazine; the discarded one is a loose part, not an envelope of the arm and gun
        pts = np.vstack(parts + [H, seg]); out['out_x'].append(float((pts[:, 0] * sg).max() * 100)); out['in_x'].append(float((pts[:, 0] * sg).min() * 100))
        P = np.vstack(parts); rad_g = np.zeros(len(P)); A = np.vstack([H, seg]); Pm = P * np.array([-1, 1, 1]); Am = A * np.array([-1, 1, 1])
        d = np.inf
        for X, rx in ((P, 0.0), (A, ARM_R / 100)):
            tr = cKDTree(X)
            for Y, ry in ((Pm, 0.0), (Am, ARM_R / 100)):
                d = min(d, float(tr.query(Y)[0].min()) - rx - ry)
        out['clear_cm'].append(round(d * 100, 2))
    out['layout'] = lay
    return out


def leak(o, thr=0.01):
    """R1 from series_vis: the frames after the hidden window in which the gun comes back into the frame. e1 = first frame at or after hide_start with a gun, hand or arm point in the frame.
    literal: gun, hand or arm points in the frame between hide_start and the rise beat (seat + 1), counted in frames (0 = never visible).
    spin_peak: largest gun turn (deg/f) over the frames from e1 on in which any gun vertex is in the frame, to the frame the turn is under 5 deg/f.
    spin_at_entry: angle of the gun from the end pose (deg) on the first frame with at least `thr` of the gun vertices in the frame."""
    L = o['layout']; hs = L.get('hide_start'); st = L.get('seated'); n = min(o['n'], 77); tot = max(o['gun_in_n'][0], 1)
    if hs is None: return {'hidden': None}
    lit = sum(1 for f in range(hs, min(st + 2, n)) if o['gun_in_n'][f] > 0 or o['hand_in'][f] > 0)
    e1 = next((f for f in range(hs, n) if o['gun_in_n'][f] > 0 or o['hand_in'][f] > 0), None)
    if e1 is None or e1 <= st: return {'hidden': lit, 'e1': e1, 'spin_peak': 0.0, 'spin_at_entry': 0.0}
    vis = [f for f in range(e1, n) if o['gun_in_n'][f] > 0]; pk = 0.0
    for f in vis:
        pk = max(pk, o['turn'][f])
        if f > e1 and o['turn'][f] < 5.0: break
    fe = next((f for f in range(e1, n) if o['gun_in_n'][f] >= thr * tot), e1)
    return {'hidden': lit, 'e1': e1, 'spin_peak': round(pk, 1), 'spin_at_entry': round(o['idle_turn'][fe], 1), 'spin_entry_frame': fe}
