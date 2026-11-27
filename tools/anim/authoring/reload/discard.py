"""Discard-visible stance variants for every reload family (one layer over the clips a generator already wrote).

Input per clip: the generator's own files next to the glb (spec json with the author keys, _track.json with release, free_from, gone and the part matrices in
gun axes, _gate.json). Nothing is read from a family module. The clip is re-authored (author.build) from its own keys with
  bump     one world offset d of the reloading gun (the hand follows, the arm is solved by the author's IK): minimum jerk in over frames 0 .. f1, held to f2, out over
           f2 .. f3. f1 = release - lead_frames (checks.lowered_variant.discard.lead_frames). f2 = the track's `gone` frame (the part no longer exists).
           f3 = the frame the fresh magazine's rig needs the gun on its shipped path (lift.station_frame), at most the last frame. Held through the flight, the part's track
           (gun axes) stays a free fall at g shifted by d; only the shipped track is used.
  lowered  (lowered stance only) the key path plus the lowered gun pose (lowover.gun_pose) faded out over frames 0 .. f1 and faded back in from the seated frame to the
           last frame (the post-seat gesture scaled by s about the lowered pose, s from the reach and shoulder limits, as lowprod's bisection); lowover.overlay then trades the
           arm for the lowered set's own arm at both ends. Frame 0 and the last frame are the lowered idle exactly.
  raised   (raised stance) the bump only: frame 0 and the last frame stay the shipped raised idle.

Discard event (the frames the offset must show), from the track:
  magazine families   the magazine leaving the well: release R .. free_from F of the track (F = the first frame the magazine is out of the well and free).
  tube and break      the spent hulls / shells leaving the gun (<stem>_objects.json, 'spent' joints, matrices in gun axes): R = the first frame the part is more than 1 cm from its frame 0
                      position, F = the first frame it is more than 5 cm away (object_event). Not used by produce: tube and break are parked.
Target (R9, one rule for every gun; checks.lowered_variant.discard): in every frame R .. F, with the offset,
  coverage   the share of gun vertices (assembled mesh, every 20th vertex) inside the game camera frame is at least the share of the shipped raised idle (frame 0 of the
             shipped clip, per body, rounded down to 0.001),
  well       the magazine well point (mag_slot) is inside the frame with margin eps from R to F,
  hand       every joint of the reloading hand is inside the frame with margin eps,
  and the rgate eye distance (no gun point nearer than checks.rreload.eye_min_cm to the eye) and the arm reach (hand within reach_max of the arm length) hold.
d is the smallest offset (norm) that meets all of it on both bodies, both hands, both reload clips. No hand numbers, no per-family code.

usage: discard.py plan <gun> [--control <root>]       the event and the target per clip, no solve
       discard.py solve <gun> --out <dir> [--control <root>] [--picks ..]
       discard.py produce <gun> --root <dir> [--control <root>] [--jobs n]   (writes <root>/lowered, <root>/raised: clips, solve, layout.json, magsets, report.json)
"""
import os, sys, json, math, copy, shutil, glob, time, concurrent.futures
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, HERE)
import renv, common, manifest, lift, lowover
import numpy as np
import visibility as V

BODIES = ('pma', 'pwa'); SIDES = ('right', 'left'); CLIPS = ('reload', 'empty_reload')
MIR_P = np.array([-1.0, 1.0, 1.0]); MIR_R = np.array([1.0, -1.0, -1.0])
PY = [sys.executable, '-B']


def rules():
    return manifest.load()['checks']['lowered_variant']['discard']


# ------------------------------------------------------------------------------------------------ clips and event
def setup(gid, pick, ctl, clear=True):
    """Point lift.py's module state at the gun, its idle pick and the control clips (no family module needed)."""
    if lift.GUN != gid and not clear: lift._cloud.clear()
    lift.GUN = gid; lift.IDLE_PICK = pick; lift.CONTROL = ctl + '/clips'
    try:      # no magazine well in the weapon set: the discard point is where the spent part starts (frame 0, gun axes)
        import numpy as _np
        sp = json.load(open(clip_base(ctl, 'pma', gid, 'right', pick, 'empty_reload') + '_objects.json'))['joints'].get('spent'); sp = sp if isinstance(sp, list) else list(sp.values())[0]
        V.SEAT_FALLBACK[gid] = _np.array(next(m for m in sp if m is not None), float).reshape(4, 4)[:3, 3]
    except Exception: pass
    if clear: lift._cloud.clear()
    V._rigs.clear()      # the rig cache keeps every glb read (about 50 MB each): a gun's solve and checks read hundreds


def clip_base(ctl, body, gid, side, pick, clip):
    """Path without extension of the clip (a gun whose two clips are the same has one file, named after either)."""
    import rreload
    return rreload.clip_file(ctl + '/clips', body, gid, side, pick[:-1], pick[-1], clip)[:-4]


def files_of(ctl, gid, pick):
    """[(body, side, clip, base)] of the distinct clip files of a pick."""
    out = []; seen = set()
    for body in BODIES:
        for side in SIDES:
            for clip in CLIPS:
                b = clip_base(ctl, body, gid, side, pick, clip)
                if b in seen or not os.path.exists(b + '.glb'): continue
                seen.add(b); out.append((body, side, os.path.basename(b)[len(f'{gid}_{side}_{pick}_'):], b))
    return out


def object_event(base):
    """Discard event of a tube or break clip (lift.object_event): (R, F) of the spent part, or None."""
    return lift.object_event(base)


def entries(gid, pick, ctl):
    """Per clip file: the control series (gun transforms, hand joints, track, spec), the event (R, F, w1) and the camera, for the solver and the check."""
    setup(gid, pick, ctl); out = []
    for body, side, clip, base in files_of(ctl, gid, pick):
        sr = lift.series2(ctl + '/clips', body, side, pick, clip)
        eye, hh = V.camera(body); s0, L = lift.arm(sr['spec'], side)
        out.append(dict(body=body, side=side, clip=clip, base=base, sr=sr, eye=eye, hh=hh, s0=s0, L=L, m=MIR_P if side == 'left' else np.ones(3)))
    return out


def sub():
    """Every 20th vertex of the assembled gun (weapon bone space)."""
    return lift.cloud()['gun'][::int(rules()['vertex_step'])]


def idle_cov(body, gid, pick, ctl):
    """Share of gun vertices inside the frame in the shipped raised idle (frame 0 of the shipped clip), rounded down to 0.001."""
    setup(gid, pick, ctl, clear=False)
    b = clip_base(ctl, body, gid, 'right', pick, 'empty_reload'); r, L = V.poses(b + '.glb', 'reload_draft', None, 'right', 'raised'); eye, hh = V.camera(body)
    W = r.world(L[0]); m = V.margin(V.R.place(W[r.idx['WeaponRight']], sub()), eye, hh)
    return math.floor(float((m > 0).mean()) * 1000) / 1000


def station(trk, n):
    try: return min(int(lift.station_frame(trk['plan'])), n - 1)
    except Exception: return n - 1


# ------------------------------------------------------------------------------------------------ target and solve
def frame_cache(e, f, G, Ep, seat):
    """World points of frame f of the control (gun vertices, eye-rule points, well point), cached on the entry."""
    c = e.setdefault('_c', {})
    if f not in c: sr = e['sr']; c[f] = (V.R.place(sr['wt'][f], G), V.R.place(sr['wt'][f], Ep), V.R.place(sr['wt'][f], seat[None]))
    return c[f]


def slacks(z, E, cov, w1, eps, reach, eye_min, Ep, seat, G, Epf=None):
    """Constraint slacks (>= 0 ok) of the offset z (right hand; a left clip gets x negated) over every entry and frame R .. w1."""
    out = []; eyep = lift.rchecks_eye(); Epf = Ep if Epf is None else Epf
    for e in E:
        sr = e['sr']; d = z * e['m']; p = 1.0 - cov[e['body']]; R, F = sr['R'], sr['F']
        for f in range(R, w1[id(e)] + 1):
            P0, E0, W0 = frame_cache(e, f, G, Ep, seat)      # R9 as calibrated on the approved clips (checks.draft.std): no coverage target (it fails every approved clip), hand and well below
            out.append(float(V.margin(sr['hand'][f] + d, e['eye'], e['hh']).min()) - eps)
            if f <= F: out.append(float(V.margin(W0 + d, e['eye'], e['hh']).min()) - eps)
            out.append(float(np.linalg.norm(E0 + d - eyep, axis=1).min()) - eye_min)
            out.append(reach * e['L'] - float(np.linalg.norm(sr['hand'][f][0] + d - e['s0'])))
        lead = rules()['lead_frames']; trk = sr['trk']; f_lo = max(0, R - lead); f_hi = min(int(trk.get('gone') or F), sr['n'] - 1)
        for f in range(f_lo, f_hi + 1):      # the rgate eye rule holds on every frame the gun is on screen: all gun points, from the rise to the part's flight
            if R <= f <= w1[id(e)]: continue      # counted above
            E0f = V.R.place(sr['wt'][f], Epf); out.append(float(np.linalg.norm(E0f + d - eyep, axis=1).min()) - eye_min)
    return np.array(out)


def solve(gid, pick, ctl, quiet=True):
    """(d, info): the smallest offset meeting the target, or (None, info) with the best achievable worst slack."""
    from scipy.optimize import minimize
    rl = rules(); mc = rl.get('max_cover_pct')
    if mc:      # size: a gun covering more of the screen than the approved Warden x 1.1 is too big to raise (owner 2026-11-24): no variant
        import stdrules; cv = stdrules.gun_cover(gid)
        if cv > mc: return None, {'feasible': False, 'too_large': True, 'cover_pct': cv, 'max_cover_pct': mc, 'error': f'gun cover {cv} % over {mc} %: too big to raise, no variant'}
    E = entries(gid, pick, ctl); rl = rules(); eps = rl['eps']; reach = manifest.load()['checks']['rreload']['reach_max']
    cov = {b: idle_cov(b, gid, pick, ctl) for b in BODIES}; G = sub(); Ep, eye_min = lift.eye_pts(); import rchecks; Ep = np.array(rchecks.gun_points(gid));      # every gun point, as rgate measures (lift.eye_pts is every 4th, shared with the Warden hooks)
    seat = V.seat(common.gun(gid))
    w1 = {id(e): e['sr']['F'] for e in E}; best = None; info = {'cov_idle': cov}      # the discard event: release R .. free_from F (the magazine has left the well)
    fn = lambda z: slacks(z, E, cov, w1, eps, reach, eye_min, Ep, seat, G); bound = [(-1.2, 1.2)] * 3
    for x0 in ([0, 0.1, 0], [0, 0.3, -0.2], [0.1, 0.4, -0.1], [-0.1, 0.4, -0.1], [0, 0.2, 0.2]):
        r = minimize(lambda z: float(z @ z), np.array(x0, float), constraints=[{'type': 'ineq', 'fun': fn}], bounds=bound, method='SLSQP', options={'maxiter': 80, 'ftol': 1e-10})
        sl = float(fn(r.x).min())
        if not quiet: print('  start', x0, '->', np.round(r.x, 3), 'cost', round(r.fun, 5), 'min slack', round(sl, 4), flush=True)
        if sl >= -1e-6 and (best is None or r.fun < best.fun): best = r
    if best is None:      # nothing feasible: report the offset that maximises the worst slack
        r = minimize(lambda v: -v[3], np.array([0, 0.3, -0.2, -1.0]), constraints=[{'type': 'ineq', 'fun': lambda v: fn(v[:3]) - v[3]}], bounds=bound + [(-50, 5)], method='SLSQP', options={'maxiter': 100})
        info.update(feasible=False, best_worst_slack=round(float(fn(r.x[:3]).min()), 3), best_offset_m=[round(float(v), 3) for v in r.x[:3]]); return None, info
    z = np.array([round(float(v), 4) for v in best.x])
    mx = rl.get('max_offset_cm')      # natural lift (checks.lowered_variant.discard, from the approved Warden variants x 1.1): a larger lift is not made; the shipped clip stays in the stance
    if mx and 100.0 * float(np.linalg.norm(z)) > mx:
        info.update(feasible=False, too_large=True, needed_offset_cm=round(100.0 * float(np.linalg.norm(z)), 1), max_offset_cm=mx); return None, info
    # nudge to the feasible side after the rounding to 0.1 mm
    for _ in range(40):
        if float(slacks(z, E, cov, w1, eps, reach, eye_min, Ep, seat, G).min()) >= 0: break
        z = z + np.array([0, 1e-4, -1e-4])
    info.update(feasible=True, window=sorted({(e['sr']['R'], w1[id(e)]) for e in E}), min_slack=round(float(slacks(z, E, cov, w1, eps, reach, eye_min, Ep, seat, G).min()), 4))
    info['w1'] = {f"{e['body']}_{e['side']}_{e['clip']}": w1[id(e)] for e in E}
    return z, info


# ------------------------------------------------------------------------------------------------ build
def window(spec_trk, lead, w1, n, ev=None, hide=None):
    if ev:      # tube and break: the spent hull leaves at ev[0] (spec_trk release is a placeholder): rise complete lead frames before it leaves but over at least 2 frames (it leaves within the first frames), hold one frame past the event (the hull has left the gun), back to the shipped path while hidden
        f1 = max(2, ev[0] - lead); f2 = ev[1] + 1; f3 = min(f2 + 6, max(f2 + 1, hide['seated'] - 1), n - 1)
        return [0, f1, f2, f3]
    R = spec_trk['release']; f1 = max(1, R - lead); f2 = max(int(spec_trk.get('gone') or 0), spec_trk['free_from']); f3 = min(max(station(spec_trk, n), f2 + 4), n - 1)
    return [0, f1, f2, f3]


def extend_flight(gid, trk, GG, limit=0.09, max_extra=8):
    """The old magazine of a family that checks its removal height (smg_front: gate mag_gone_height_m at most 0.09 m) falls from the offset gun: the flight is continued at g (position of the part origin
    carried on at its last velocity, rotation at its last per-frame turn, gun axes re-derived from the gun pose GG) until the removal height is within the limit. Edits trk in place (rows and `gone`);
    returns the number of frames added."""
    import magtrack2, sf2
    fr = trk['frames']; drawn = [f for f, row in enumerate(fr) if row['state'] in ('falling', 'guided', 'loose') and row.get('s', 1.0) > 0.5]
    if len(drawn) < 2: return 0
    W = lambda f: magtrack2.m4(*GG[f]) @ np.array(fr[f]['m'], float).reshape(4, 4)
    cen = np.array(magtrack2.vanilla(gid, 'empty_reload')['centre'], float)      # the part turns about its centre: the centre is the ballistic point (as sf2.gone_height and rgate measure it)
    A, B = W(drawn[-2]), W(drawn[-1]); v = (B[:3, :3] @ cen + B[:3, 3]) - (A[:3, :3] @ cen + A[:3, 3]); dR = B[:3, :3] @ A[:3, :3].T; n = 0; last = drawn[-1]; c = B[:3, :3] @ cen + B[:3, 3]
    while n < max_extra:
        h = sf2.gone_height(gid, trk, GG)
        if h is None or h <= limit: break
        f = last + 1 + n
        if f >= len(fr) or f >= len(GG): break
        v = v + np.array([0.0, -magtrack2.G_ACC, 0.0]); c = c + v; Wn = np.eye(4); Wn[:3, :3] = dR @ B[:3, :3]; Wn[:3, 3] = c - Wn[:3, :3] @ cen
        rel = np.linalg.inv(magtrack2.m4(*GG[f])) @ Wn; fr[f] = {'m': [round(float(x), 6) for x in rel.reshape(-1)], 's': 1.0, 'state': 'falling'}; B = Wn; n += 1
    if n: trk['gone'] = last + 1 + n
    return n


def retarget(keys, orig, rs, gid, take, spec, seat_f, frac, extra=0):
    """The last rise after the hidden window regenerated (retarget, not an overlay). The shipped rise motion is dropped and rebuilt in two parts:
    reconfigure  while the gun is out of view, from two frames after the seat to the frame before the rise: first it moves the fraction `frac` of the way along the rise line (clear of the body; the search in
                 build_clip takes the smallest fraction that keeps the body gate and the shipped hidden window), then it turns to the lowered pose's orientation (minimum jerk), so the arm is in the lowered-pose
                 configuration before it is seen (the clavicle turn of the reach cap is reached in the same frames and held: spec clav_plan, author.py);
    rise         the shipped rise's own speed profile (its cumulative path fraction over its frames: the same peak speed and the same stop) applied to the shorter path from the waypoint to the lowered idle.
                 The shorter path takes fewer frames: the rise starts later and ends on the shipped frame r1; before it the gun is held at the waypoint (the hidden or held part). `extra` frames more: the rise starts earlier (the search in build_clip; the visible rise takes more frames, the hidden window gets shorter by the same frames, never under 12: only hidden time is retimed).
    After the rise the shipped gesture residual (the keys relative to their rise-end pose, the shipped settle and kicks) is added. The arm is solved by the author's IK from these keys."""
    r0, r1 = rs; s0 = max(r0 - 2, 0); N = len(keys); q0f = seat_f + 2
    assert [int(k[0]) for k in keys] == list(range(N)), 'one key per frame expected'
    P = np.array([k[1] for k in keys], float); R = np.array([k[2] for k in keys], float); R1 = R[r1].copy(); R2 = R.copy()
    O = np.array([k[1] for k in orig], float); P1 = P[r1]
    Pw = P[s0] + frac * (P1 - P[s0]); P2 = P.copy(); mid = (q0f + s0) // 2
    for f in range(q0f, s0 + 1):
        wp = lowover.mj((f - q0f) / float(max(mid - q0f, 1))); wr = lowover.mj((f - mid) / float(max(s0 - mid, 1)))
        P2[f] = P[f] + wp * (Pw - P[f]); R2[f] = R[f] + wr * (R1 - R[f])
    seg = np.linalg.norm(np.diff(O[s0:r1 + 1], axis=0), axis=1); cum = np.r_[0.0, np.cumsum(seg)]; Lship = float(cum[-1]); u = cum / max(Lship, 1e-9)      # the shipped rise: path fraction per frame
    Lnew = float(np.linalg.norm(P1 - Pw)); span = r1 - s0; nfr = int(math.ceil(span * Lnew / max(Lship, 1e-9) - 1e-9)) + int(extra); k = nfr / float(span); start = r1 - nfr
    out = []
    for f, key in enumerate(keys):
        if f < s0:
            rot = R2[f] if f >= q0f else R[f]; pos = P2[f] if f >= q0f else P[f]
        elif f <= r1:
            tau = (f - start) / max(k, 1e-9); uu = 0.0 if tau <= 0 else float(np.interp(tau, np.arange(span + 1), u)); pos = Pw + (P1 - Pw) * uu; rot = R1
        else:
            pos = P1 + (P[f] - P1); rot = R1 + (R[f] - R[r1])
        out.append([int(f), [round(float(x), 4) for x in pos], [round(float(x), 2) for x in rot]] + list(key[3:]))
    spec['_retarget'] = {'frac': frac, 'extra_frames': int(extra), 'reconfigure': [q0f, s0], 'rise_frames': [start, r1], 'shipped_rise': [s0, r1], 'path_cm': [round(Lship * 100, 1), round(Lnew * 100, 1)]}
    spec['clav_plan'] = {'ramp': [q0f, s0]}
    return out, (q0f, s0)


def FOLLOW():
    """GA_FOLLOW_RISE=1 (stance.py --follow-rise): lowered clips reach the lowered pose in their own last rise (L1)."""
    v = os.environ.get('GA_FOLLOW_RISE')      # 1: the lowered pose faded in over the shipped rise (overlay); gen: the rise regenerated as one move to the lowered idle (retarget)
    return {'follow_rise': 'gen' if v == 'gen' else True} if v else {}


def rise_span(base, side, he, frac=0.25):
    """(r0, r1): the first rise after the hidden window (L1). The peak gun speed from hide_end - 2 on; r1 = the first frame after the peak below frac of it, r0 = the start of the run
    of frames before the peak with at least frac / 2.5 of it. None when the span is under 4 frames."""
    from glb import Glb
    from fk import Clip
    g = Glb(base + '.glb'); c = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + side); n = json.load(open(base + '.json'))['frames']
    P = np.array([np.array(c.world(f)[i][0]) * 100 for f in range(n)]); v = np.r_[0, np.linalg.norm(np.diff(P, axis=0), axis=1)]
    a = max(he - 2, 1); pf = a + int(np.argmax(v[a:])); pk = float(v[pf]); r1 = next((f for f in range(pf + 1, n) if v[f] < frac * pk), None)
    if r1 is None: return None
    r0 = pf
    while r0 - 1 >= a and v[r0 - 1] >= frac / 2.5 * pk: r0 -= 1
    return (r0, r1) if r1 - r0 >= 4 else None


def build_clip1(gid, pick, body, side, clip, base, ctl, outdir, d, w1, low=None, quiet=True, retime=None):
    """One clip file of the variant into outdir (glb, json, _track.json, _gate.json). low: None (raised) or dict(s, ...)."""
    import author, rgate, smgprod, r2lib, rarmset
    from glb import Glb
    from fk import Clip
    spec = json.load(open(base + '.json')); trk = json.load(open(base + '_track.json')); gate0 = json.load(open(base + '_gate.json'))
    if retime:      # only the off-screen window is stretched or cut (retime.py): the visible start and end stay frame-identical
        import retime as RT, copy as _cp
        if os.path.exists(base + '_objects.json') or 'mag_gone_height_m' in gate0: raise RuntimeError(f'{os.path.basename(base)}: retime is not supported for clips with an objects track or a removal-height gate')
        L0 = gate0['layout']; m_ = RT.Map(L0['hide_start'] if retime.get('hs') is None else retime['hs'], L0['hide_end'] if retime.get('he') is None else retime['he'], retime['delta'])
        spec = RT.spec(spec, m_); trk = RT.track(trk, m_); gate0 = _cp.deepcopy(gate0); L1 = gate0['layout']
        for k_ in ('hide_end', 'seated', 'length', 'keys', 'mag_out', 'handle'):
            if isinstance(L1.get(k_), (int, float)): L1[k_] = L1[k_] + m_.delta if k_ in ('length', 'keys') else m_.fi(L1[k_])
    S = spec['_side']; O = 'Left' if S == 'Right' else 'Right'; N = spec['frames']; name = os.path.basename(base); rl = rules()
    os.makedirs(outdir, exist_ok=True); out = f'{outdir}/{name}.glb'; spec['out'] = out
    if spec.get('_slot_cm_max'): raise RuntimeError(f'{name}: in-hand slot offsets (tl.slot) are not stored in the spec; the layer cannot re-apply them')
    mv = np.array(d, float) * (MIR_P if S == 'Left' else 1.0); nx = 0
    if 'mag_gone_height_m' in gate0:      # the family limits the height the old magazine is removed at: continue its flight from the offset gun
        g0 = Glb(base + '.glb'); c0 = Clip(g0, 'reload_draft'); i0 = g0.names.index('Weapon' + S)
        GG0 = [(np.array(t) + mv, np.array(q)) for t, q in (c0.world(f)[i0] for f in range(N))]; trk = copy.deepcopy(trk); nx = extend_flight(gid, trk, GG0)
    ev = lift.object_event(base); fw = window(trk, rl['lead_frames'], w1, N, ev, gate0['layout'])
    spec['bumps'] = {S: [{'f': fw, 'move': [round(float(x), 5) for x in mv], 'profile': 'minjerk'}]}
    spec['_lift'] = {'layer': 'discard', 'move_m': [round(float(x), 4) for x in d], 'frames': fw, 'release': trk['release'], 'free_from': trk['free_from'], 'gone': trk.get('gone'), 'flight_frames_added': nx}
    lowd = None
    if low:
        gun = common.gun(gid); lowglb = f"{common.path('low_clips')}/{body}/lowered_{gun['lowered']['pose']}.glb"
        Lp, Lr = lowover.gun_pose(common.mp(spec['src']), lowglb, 'Right'); seat_f = int(gate0['layout']['seated']); e_ = N - 1; s = low['s']
        a = fw[1]; b = seat_f; mp, mr = (MIR_P, MIR_R) if S == 'Left' else (1.0, 1.0)
        rs = rise_span(base, S, int(gate0['layout']['hide_end'])) if low.get('follow_rise') else None      # follow_rise: the lowered pose is reached in the clip's own first rise after the hidden window (the key path and the arm), not faded in over the frames from the seat to the end
        if rs: b, e_ = rs[0], rs[1]
        keys = []; orig_keys = [list(k) for k in spec['keys'][S]]
        for k in spec['keys'][S]:
            f = k[0]; ws = lowover.w_start(f, 0, a); we = lowover.w_end(f, b, e_); sc = 1.0 - (1.0 - s) * we
            pos = np.array(k[1], float) * sc + (ws + we) * Lp * mp; rot = np.array(k[2], float) * sc + (ws + we) * Lr * mr
            keys.append([int(f), [round(float(x), 4) for x in pos], [round(float(x), 2) for x in rot]] + list(k[3:]))
        if rs and low.get('follow_rise') == 'gen':
            keys, (b, e_) = retarget(keys, orig_keys, rs, gid, 'A' if common.gun(gid)['reload']['weight'] == 'light' else 'B', spec, seat_f, (low.get('follow_opt') or {}).get('frac', 0.0), (low.get('follow_opt') or {}).get('extra', 0))      # the arm trade (lowover.overlay) takes place in the hidden reconfiguration
        spec['keys'][S] = keys; lowd = dict(h=0, a=a, b=b if (rs and low.get('follow_rise') != 'gen') else N - 1 - manifest.load()['checks']['lowered_variant']['return_frames'], e=(e_ if low.get('follow_rise') != 'gen' else N - 1), s=s, low=lowglb)
        if rs: lowd['rise'] = list(rs)
    author.build(spec, out)
    if spec.get('_spins'):
        spins = [(sp, np.asarray(a_, float)) for sp, a_ in spec['_spins']]; smgprod.apply_spins_side(out, 'reload_draft', spins, None, S)
    if lowd:
        lr = f'{os.path.dirname(os.path.dirname(outdir))}/rest_low/{body}/rest_low_{gid}.glb'; os.makedirs(os.path.dirname(lr), exist_ok=True)
        lowover.rest(common.mp(spec['src']), lowd['low'], lr)
        lowover.overlay(out, 'reload_draft', lowd['low'], S, N, lowd['h'], lowd['a'], lowd['b'], lowd['e'], lowover.arm_joints(common.mp(spec['src']), lowd['low']))
        spec['_idle'] = lr; spec['_lowered'] = lowd; spec['_stance_only'] = bool(low.get('stance_only'))
        spec['_judge'] = {'reach_frames': [lowd['a'], lowd['b']], 'eye_idle_cm': gate0.get('eye_idle_cm'), 'low_w': [round(lowover.w_start(f, 0, a) + lowover.w_end(f, b, e_), 5) for f in range(N)]}      # rgate: reach and shoulder on the frames between the start fade and the end overlay; the eye rule against the shipped raised idle
    g = Glb(out); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); io = g.names.index('Weapon' + O)
    GG = [(np.array(t), np.array(q)) for t, q in (cl.world(f)[i] for f in range(N))]; GO = [cl.world(f)[io] for f in range(N)]
    trk2 = dict(trk); trk2['clip'] = clip; trk2['side'] = S; trk2['body'] = body
    spec['_track'] = f'{outdir}/{name}_track.json'; json.dump(trk2, open(spec['_track'], 'w')); json.dump(spec, open(f'{outdir}/{name}.json', 'w'), indent=1)
    o = rgate.gate(spec, trk2)
    # rgate measures the magazine against the well axes the family's generator set up (magtrack2 state the layer does not have); those measures come from the gun-axes track, which a held offset does not change:
    # the control's values and verdicts are carried over
    TRACK = ('exit_at_10cm', 'insert_off_axis_cm', 'exit_off_axis_cm', 'mag_exit', 'mag_hang', 'release_dv_cm_f'); PRE = ('insertion ', 'exit ', 'magazine leaves the well', 'magazine speed', 'fresh magazine meets', 'magazine hangs', 'release velocity jumps')      # hang and release velocity: world accelerations of the magazine, which a constant offset does not change; rgate re-measured here lacks the generator's axes and reads 2 frames where the generator's own gate read 0
    for k in TRACK:
        if k in gate0: o[k] = gate0[k]
    o['fails'] = [x for x in o['fails'] if not x.startswith(PRE)] + [x for x in gate0['fails'] if x.startswith(PRE)]
    for k in ('mag_exit', 'mag_speed', 'mag_view_frames', 'insert_rel_cm', 'inertia', 'in_hand'):
        if k in gate0: o[k] = gate0[k]      # engine-specific, unchanged by an offset held through the discard (copied from the control)
    if 'mag_gone_height_m' in gate0:      # smg_front: re-measured on the offset clip with the family's own functions
        import sf2; o['mag_gone_height_m'] = sf2.gone_height(gid, trk2, GG)
        if o['mag_gone_height_m'] is not None and o['mag_gone_height_m'] > 0.09: o['fails'].append(f"old magazine removed {o['mag_gone_height_m']} m above the ground")
    if 'other_gun' in gate0:
        import frontprod; o['other_gun'] = th = frontprod.through_other(gid, trk2, GG, GO)
        if th['inside_other_mag_frames']: o['fails'].append(f"old magazine passes through the other gun's magazine (f{th['inside_other_mag_frames'][:5]})")
    try: o['elbow_step_deg'] = r2lib.elbow_step(spec)
    except Exception: o['elbow_step_deg'] = gate0.get('elbow_step_deg')
    if o['elbow_step_deg'] and o['elbow_step_deg'] > 45: o['fails'].append(f"elbow swings {o['elbow_step_deg']} deg in one frame")
    o['flight'] = smgprod.flight(spec, trk2, GG, GO)
    if o['flight']['other_gun_min_cm'] < 5.0: o['fails'].append(f"old magazine {o['flight']['other_gun_min_cm']} cm from the other gun")
    o['end_transition'] = et = smgprod.end_transition(spec)
    if et['last3_step_cm'] > 0.5 or et['last_vs_idle_cm'] > 0.02 or et['last_vs_idle_deg'] > 0.02: o['fails'].append(f"end transition {et}")
    keys_n = max(rarmset.good_keys(N), int(gate0['layout'].get('keys') or 0)); o['layout']['keys'] = keys_n
    smgprod.pad(out, 'reload_draft', keys_n); spec['_keys'] = keys_n; json.dump(spec, open(f'{outdir}/{name}.json', 'w'), indent=1)
    json.dump(o, open(f'{outdir}/{name}_gate.json', 'w'), indent=1)
    return o


# ------------------------------------------------------------------------------------------------ check
def vis(clips, gid, pick, ctl):
    """R9 (the target above) on a built clips folder: per clip file the worst coverage, well and hand margins from R to the frame the part has left the frame in the shipped clip (offset 0)."""
    setup(gid, pick, ctl); G = sub(); seat = V.seat(common.gun(gid)); rows = []
    cov = {b: idle_cov(b, gid, pick, ctl) for b in BODIES}; eps = rules()['eps']
    for body in BODIES:
        eye, hh = V.camera(body)
        for side in SIDES:
            for clip in CLIPS:
                b = f'{clips}/{body}/' + os.path.basename(clip_base(ctl, body, gid, side, pick, clip))
                if not os.path.exists(b + '.glb') or any(r['file'] == os.path.basename(b) and r['body'] == body for r in rows): continue
                V._rigs.clear(); nm = os.path.basename(b)[len(f'{gid}_{side}_{pick}_'):]; sr = lift.series2(clips, body, side, pick, nm); R, F = sr['R'], sr['F']; w1 = F
                c = min(float((V.margin(V.R.place(sr['wt'][f], G), eye, hh) > 0).mean()) for f in range(R, w1 + 1))      # reported
                h = min(float(V.margin(sr['hand'][f], eye, hh).min()) for f in range(R, w1 + 1))
                wl = [float(V.margin(V.R.place(sr['wt'][f], seat[None]), eye, hh).min()) for f in range(R, F + 1)]; w = min(wl); share = sum(1 for x in wl if x > 0) / len(wl); S = manifest.load()['checks']['draft']['std']
                rows.append({'file': os.path.basename(b), 'clip': f'{pick}_{clip}', 'body': body, 'side': side, 'window': [R, w1], 'coverage': round(c, 3), 'coverage_idle': cov[body], 'well': round(w, 3), 'well_share': round(share, 3), 'hand': round(h, 3),
                             'pass': share >= S['r9_well_share_min'] - 1e-9 and h >= S['r9_hand_min'] - 1e-9})
    return rows


# ------------------------------------------------------------------------------------------------ hold pick: R9 and R8 together
def hold_probe(gid, pick, ctl, d, work):
    """R8 measures (survey.sustained) of the generator's own hold pick built with the hold offset d (smgprod --lift, one clip: pma, right, empty_reload)."""
    import smgprod, survey, subprocess
    out = f'{work}/probe_{abs(hash(tuple(round(float(x), 4) for x in d))) % 10**8}'; os.makedirs(out + '/work', exist_ok=True); ctl_r = ctl
    for b in BODIES:
        os.makedirs(f'{out}/rest/{b}', exist_ok=True); n = f'rest_{gid}_R__{gid}_L.glb'
        if not os.path.exists(f'{out}/rest/{b}/{n}'): shutil.copyfile(f'{ctl_r}/rest/{b}/{n}', f'{out}/rest/{b}/{n}')
    base = f'{ctl}/clips/pma/{gid}_right_{pick}_empty_reload'; trk = json.load(open(base + '_track.json')); lj = out + '/lift.json'
    json.dump({pick[:-1]: {'stop_m': [round(float(x), 4) for x in d], 'pitch_deg': 0.0, 'roll_deg': 0.0, 'drop_m': 0.0, 'lead': 0, 'release': trk['release'], 'free_from': trk['free_from'], 'objective': 'hold', 'from': lift.ARRIVE}}, open(lj, 'w'))
    env = dict(os.environ, ROUND_OUT=out, WORK=out + '/work', AUTHORING=out + '/work', PYTHONDONTWRITEBYTECODE='1'); env.pop('GA_TEST', None)
    r = subprocess.run(PY + [HERE + '/smgprod.py', 'build', smgprod.family_of(pick[:-1]), '--picks', pick[:-1], '--clips', 'empty_reload', '--sides', 'right', '--bodies', 'pma', '--lift', lj], env=env, capture_output=True, text=True)
    g = f'{out}/clips/pma/{gid}_right_{pick}_empty_reload'
    if not os.path.exists(g + '.glb'): raise RuntimeError('probe build failed: ' + (r.stdout + r.stderr)[-400:])
    spec = json.load(open(g + '.json')); t = json.load(open(g + '_track.json')); G, Q, M = survey._clip_series(g + '.glb', spec['clip'], spec['_side'])
    return survey.sustained(G, Q, t['release'])


R8_KEYS = ('path_cm', 'v90_cm_f', 'rel_path_cm', 'rel_v90_cm_f')


def solve_hold_r8(gid, pick, ctl, work, margin=0.01, step=0.03, rounds=6):
    """Hold pick (the gun turns in the fingers; the generator moves the hold position by d): the smallest d meeting the R9 target (geometry, as solve) AND the R8 lower bounds
    (checks.draft.r8_min), R8 measured on the built clip. Model: R8 measure(d) = measure(z0) + g . (d - z0), g from builds at +step on each axis, the constant re-anchored on every built
    candidate (secant). Candidates are built (smgprod, one clip) until all four bounds hold with `margin` (share of the bound). Returns (d, info)."""
    from scipy.optimize import minimize
    lb = lift.r8_limits(gid, pick); E = entries(gid, pick, ctl); rl = rules(); eps = rl['eps']; reach = manifest.load()['checks']['rreload']['reach_max']
    cov = {b: idle_cov(b, gid, pick, ctl) for b in BODIES}; G = sub(); Ep, eye_min = lift.eye_pts(); seat = V.seat(common.gun(gid)); w1 = {id(e): e['sr']['F'] for e in E}
    fn = lambda z: slacks(z, E, cov, w1, eps, reach, eye_min, Ep, seat, G); info = {'cov_idle': cov, 'r8_bounds': lb, 'builds': []}
    z0 = np.zeros(3); m0 = hold_probe(gid, pick, ctl, z0, work); info['builds'].append({'d': z0.tolist(), **{k: m0.get(k) for k in R8_KEYS}})
    Gm = np.zeros((4, 3))
    for i in range(3):
        dz = np.zeros(3); dz[i] = step; mi = hold_probe(gid, pick, ctl, dz, work); info['builds'].append({'d': dz.tolist(), **{k: mi.get(k) for k in R8_KEYS}})
        Gm[:, i] = [(mi[k] - m0[k]) / step for k in R8_KEYS]
    anchor = (z0, np.array([m0[k] for k in R8_KEYS], float)); need = np.array([lb[k] * (1 + margin) for k in R8_KEYS], float); z = None
    for it in range(rounds):
        za, ma = anchor; lin = lambda x: ma + Gm @ (x - za) - need
        best = None
        for x0 in ([0, 0.1, 0], [0, 0.3, -0.2], [0.1, 0.2, 0], [-0.1, 0.2, 0], [0, -0.1, 0.1]):
            r = minimize(lambda x: float(x @ x), np.array(x0, float), constraints=[{'type': 'ineq', 'fun': fn}, {'type': 'ineq', 'fun': lin}], bounds=[(-1, 1)] * 3, method='SLSQP', options={'maxiter': 100, 'ftol': 1e-10})
            if min(float(fn(r.x).min()), float(lin(r.x).min())) >= -1e-6 and (best is None or r.fun < best.fun): best = r
        if best is None: info['error'] = 'no offset meets R9 and the linearised R8'; return None, info
        z = np.array([round(float(v), 4) for v in best.x]); m = hold_probe(gid, pick, ctl, z, work); mv = np.array([m[k] for k in R8_KEYS], float)
        info['builds'].append({'d': z.tolist(), **{k: m.get(k) for k in R8_KEYS}})
        if bool(np.all(mv >= np.array([lb[k] for k in R8_KEYS]))): info.update(feasible=True, r8=dict(zip(R8_KEYS, mv.tolist())), min_slack_r9=round(float(fn(z).min()), 4)); return z, info
        anchor = (z, mv)
    info['error'] = 'R8 not met after the secant rounds'; return None, info


# ------------------------------------------------------------------------------------------------ produce
def gate_numbers(folder):
    """(files, worst reach, worst shoulder pull cm) of the gate files in folder/<body>/."""
    wr = ws = 0.0; n = 0
    for g in glob.glob(f'{folder}/*/*_gate.json'):
        o = json.load(open(g)); wr = max(wr, o['reach'][0]); ws = max(ws, o['shoulder_pull_cm']); n += 1
    return n, wr, ws


RISE_CHOICE = {}      # (gun, pick, body, side, clip) -> the rise option that passed at an earlier gesture scale: tried first


def build_clip(gid, pick, body, side, clip, base, ctl, outdir, d, w1, low=None, quiet=True, retime=None):
    """One clip of the variant. With the retarget (low['follow_rise'] == 'gen') the rise option is searched: the combinations (waypoint fraction, extra rise frames) of checks.lowered_variant
    retarget_fractions x retarget_extras in that order, at most retarget_max_tries of them; the first build with no gate fail, the visible arm chain inside the approved lowered bounds (smooth.ratio_fails)
    and the shipped hidden window start with hide_end not later and the hidden window at least tm1.hidden_min_frames is kept; the choice is recorded in the spec (_retarget). An option that passed at another
    gesture scale is tried first. None passing: the build with the fewest fails (reported). Every try is logged to GA_SEARCH_LOG (default <outdir>/../search.log)."""
    if not (low and low.get('follow_rise') == 'gen'): return build_clip1(gid, pick, body, side, clip, base, ctl, outdir, d, w1, low, quiet, retime)
    import smooth
    lv = manifest.load()['checks']['lowered_variant']; L0 = json.load(open(base + '_gate.json'))['layout']; hmin = manifest.load()['checks']['draft']['tm1']['hidden_min_frames']
    combos = [(f, e) for f in lv['retarget_fractions'] for e in lv['retarget_extras']][:lv['retarget_max_tries']]
    if os.environ.get('GA_RETARGET_FRAC') or os.environ.get('GA_RETARGET_EXTRA'): combos = [(float(os.environ.get('GA_RETARGET_FRAC', 0.0)), int(os.environ.get('GA_RETARGET_EXTRA', 0)))]
    key = (gid, pick, body, side, clip)
    if key in RISE_CHOICE and RISE_CHOICE[key] in combos: combos = [RISE_CHOICE[key]] + [c for c in combos if c != RISE_CHOICE[key]]
    log = os.environ.get('GA_SEARCH_LOG') or os.path.join(os.path.dirname(outdir.rstrip('/')), 'search.log'); best = None; name = os.path.basename(base)
    for frac, extra in combos:
        o = build_clip1(gid, pick, body, side, clip, base, ctl, outdir, d, w1, dict(low, follow_opt={'frac': frac, 'extra': extra}), quiet, retime); Lh = o['layout']
        okwin = Lh['hide_start'] == L0['hide_start'] and Lh['hide_end'] <= L0['hide_end'] and (Lh['hide_end'] - Lh['hide_start'] + 1) >= hmin and (Lh['hide_end'] == L0['hide_end'] or extra > 0)
        rf = smooth.ratio_fails(f'{outdir}/{name}', base)
        bad = list(o['fails']) + rf + ([] if okwin else [f"hidden window {Lh['hide_start']}-{Lh['hide_end']} against the shipped {L0['hide_start']}-{L0['hide_end']}"])
        try: open(log, 'a').write(f"{name} s={low.get('s')} frac={frac} extra={extra} {'PASS' if not bad else 'fail: ' + '; '.join(bad)[:300]}" + chr(10))
        except Exception: pass
        if not bad: RISE_CHOICE[key] = (frac, extra); return o
        if best is None or len(bad) < best[0]: best = (len(bad), frac, bad, extra)
    o = build_clip1(gid, pick, body, side, clip, base, ctl, outdir, d, w1, dict(low, follow_opt={'frac': best[1], 'extra': best[3]}), quiet, retime); o = dict(o); o['fails'] = list(o['fails']) + [b for b in best[2] if b not in o['fails']]
    return o


def build_pick(gid, pick, ctl, outdir, z, w1map, low, sides=None, log=None, retime=None):
    """Every clip file of the pick (or only the sides given) into outdir/<body>/. Returns the gate fails."""
    fails = []
    for body, side, clip, base in files_of(ctl, gid, pick):
        if sides and side not in sides: continue
        o = build_clip(gid, pick, body, side, clip, base, ctl, f'{outdir}/{body}', z, w1map[f'{body}_{side}_{clip}'], low, retime=retime)
        fails += [f'{body} {side} {clip}: {x}' for x in o['fails']]
    return fails


def bisect_s(gid, pick, ctl, root, z, w1map, retime=None):
    """Largest s (scale of the post-seat gesture about the lowered pose): 1.0 first, then 5 halvings of [0, 1]; the reach and shoulder pull of the right-hand clips within checks.rreload."""
    lim = manifest.load()['checks']['rreload']; trials = []; nfiles = len([1 for f in files_of(ctl, gid, pick) if f[1] == 'right'])

    def trial(s):
        d = f'{root}/lowered/bs_{pick}/s{int(round(s * 1000)):04d}'; shutil.rmtree(d, ignore_errors=True) if False else None
        build_pick(gid, pick, ctl, d + '/clips', z, w1map, dict({'s': s}, **FOLLOW()), sides=('right',), retime=retime); n, wr, ws = gate_numbers(d + '/clips')
        ok = n == nfiles and wr <= lim['reach_max'] and ws <= lim['shoulder_pull_max_cm']; trials.append((s, n, round(wr, 3), round(ws, 2), ok)); return ok
    if trial(1.0): return 1.0, trials
    lo, hi = 0.0, 1.0
    for _ in range(manifest.load()['checks']['lowered_variant']['s_halvings']):
        m = (lo + hi) / 2
        if trial(m): lo = m
        else: hi = m
    return lo, trials


def layout_of(gid, picks, take, clips, ctl):
    """{pick+take: {clip: layout}} (latest hide_start, earliest hide_end over bodies and hands) and the gate fails."""
    lay = {}; fails = []
    for pick in picks:
        for clip in CLIPS:
            e = None
            for body in BODIES:
                for side in SIDES:
                    b = f'{clips}/{body}/' + os.path.basename(clip_base(ctl, body, gid, side, pick + take, clip))
                    o = json.load(open(b + '_gate.json')); L = dict(o['layout'])
                    if o['fails']: fails.append(f'{body} {side} {pick}{take} {clip}: {o["fails"]}')
                    if e is None: e = dict(L)
                    else:
                        e['hide_start'] = max(e['hide_start'], L['hide_start']); e['hide_end'] = min(e['hide_end'], L['hide_end'])
            lay.setdefault(pick + take, {})[clip] = e
    return lay, fails


def produce(gid, root, ctl_arg=None, jobs=1, magsets=True, only=None, final=True, retime=None):
    """Lowered and raised variants of every pick of the gun with the discard layer. Writes <root>/lowered and <root>/raised (clips, solve, layout.json, report.json, magsets). Exit code."""
    import lowprod
    g, r = lowprod.gun_entry(gid)
    if not g.get('lowered') or not r.get('slots') or r.get('shares') or (r.get('parked') and os.environ.get('GA_INCLUDE_PARKED') != '1'): print(f'{gid}: no lowered entry, no slots, shared or parked: not made'); return 3
    take = 'A' if r['weight'] == 'light' else 'B'; picks = [p + take for p in r['slots'] if not only or p in only]
    root = os.path.abspath(root).replace(chr(92), '/').rstrip('/'); ctl = lowprod.ship_root(gid, ctl_arg)
    reps = []; made = []
    lowok = all(os.path.exists(f"{common.path('low_clips')}/{b}/lowered_{g['lowered']['pose']}.glb") for b in BODIES)
    if not lowok: print(f'{gid}: the lowered set lowered_{g["lowered"]["pose"]}.glb is missing: lowered variants not made, raised variants only', flush=True)
    for pk in picks:
        t0 = time.time(); rep = {'pick': pk}; sd = f'{root}/lowered/solve'; os.makedirs(sd, exist_ok=True)
        z, info = solve(gid, pk, ctl); rep.update(info); rep['d_m'] = None if z is None else [round(float(x), 4) for x in z]
        json.dump(rep, open(f'{sd}/{pk}.json', 'w'), indent=1)
        if z is None: rep['error'] = 'no offset meets the target'; reps.append(rep); print(json.dumps(rep), flush=True); continue
        w1map = info['w1']
        f_r = build_pick(gid, pk, ctl, f'{root}/raised/clips', z, w1map, None, retime=retime)
        if lowok:
            s, trials = bisect_s(gid, pk, ctl, root, z, w1map, retime=retime); rep['s'] = s; rep['trials'] = trials
            f_l = build_pick(gid, pk, ctl, f'{root}/lowered/clips', z, w1map, dict({'s': s}, **FOLLOW()), retime=retime)
        else: f_l = ['lowered set missing']
        rep['gate_fails'] = {'raised': f_r, 'lowered': f_l}; rep['seconds'] = round(time.time() - t0); reps.append(rep); made.append(pk[:-1])
        print(json.dumps({k: v for k, v in rep.items() if k != 'trials'}), flush=True)
    json.dump(reps, open(f'{root}/report_{"_".join(picks)}.json', 'w'), indent=1)
    if not final: return 1 if any(x.get('error') and not x.get('too_large') for x in reps) else (3 if any(x.get('too_large') for x in reps) else 0)
    rc = 0
    for stance in ('lowered', 'raised'):
        clips = f'{root}/{stance}/clips'
        if not made or (stance == 'lowered' and not lowok): continue
        lay, fails = layout_of(gid, made, take, clips, ctl); json.dump({'layout': lay, 'fails': fails}, open(f'{root}/{stance}/layout.json', 'w'), indent=1)
        print(f'{stance}: {len(glob.glob(clips + "/*/*.glb"))} clips, {len(fails)} gate fails'); rc = rc or (1 if fails else 0)
        for f in fails: print('  gate fail', f)
        if magsets:
            try: lowprod.magsets(gid, made, take, clips, f'{root}/{stance}/magsets') if stance == 'lowered' else None
            except Exception as e: print(f'  magsets {stance}: {type(e).__name__}: {e}'[:300])
    return 1 if any(x.get('error') and not x.get('too_large') for x in reps) else (rc or (3 if any(x.get('too_large') for x in reps) else 0))      # 3: a lift above the natural limit, no variant made (reported)


def finalize(gid, root, ctl_arg=None):
    """After per-pick runs (produce --no-final) into one root: layout.json and the lowered magazine sets over every pick present, report.json from the per-pick reports."""
    import lowprod
    g, r = lowprod.gun_entry(gid); take = 'A' if r['weight'] == 'light' else 'B'; root = os.path.abspath(root).replace(chr(92), '/').rstrip('/'); ctl = lowprod.ship_root(gid, ctl_arg); rc = 0
    reps = []
    for f in sorted(glob.glob(f'{root}/report_*.json')): reps += json.load(open(f))
    json.dump(reps, open(f'{root}/report.json', 'w'), indent=1)
    for stance in ('lowered', 'raised'):
        clips = f'{root}/{stance}/clips'; made = [p for p in r['slots'] if glob.glob(f'{clips}/*/{gid}_*_{p}{take}_*.glb')]
        if not made: continue
        lay, fails = layout_of(gid, made, take, clips, ctl); json.dump({'layout': lay, 'fails': fails}, open(f'{root}/{stance}/layout.json', 'w'), indent=1)
        print(f'{stance}: {len(glob.glob(clips + "/*/*.glb"))} clips, {len(fails)} gate fails'); rc = rc or (1 if fails else 0)
        for f in fails: print('  gate fail', f)
        if stance == 'lowered':
            try: lowprod.magsets(gid, made, take, clips, f'{root}/lowered/magsets')
            except Exception as e: print(f'  magsets: {type(e).__name__}: {e}'[:300])
    return rc


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ('produce', 'finalize'): raise SystemExit(__doc__)
    root = common.opt(a, '--root'); ctl = common.opt(a, '--control'); jobs = int(common.opt(a, '--jobs') or 1); pk = common.opt(a, '--picks')
    if a[0] == 'finalize': sys.exit(finalize(a[1], root, ctl))
    rt = common.opt(a, '--retime')      # --retime <delta>: stretch (+) or cut (-) the hidden window only (retime.py)
    sys.exit(produce(a[1], root, ctl, jobs, only=pk.split(',') if pk else None, final='--no-final' not in a, retime={'delta': int(rt)} if rt else None))
