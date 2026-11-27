"""Warden reloads lifted into view for the magazine release (experiment, 2026-11-24).

A variant is the shipped reload with one smooth world offset on the reloading gun and hand: minimum jerk in over frames
start..release, held to free_from (the magazine has left the well), minimum jerk out to end, zero before start and after end, so
frame 0 and the end are exact. smgprod.py applies it (--lift <json>, author.py bumps with profile minjerk): the arm is solved by the author's IK, the
magazine track, hide window and gate are rebuilt on the lifted gun by the family's own generator path. No hand numbers: the
size comes from the R9 measure (checks/visibility.py: game camera, eye joint, hfov 100).

solve   the offset: a world translation moves the magazine well and the hand rigidly, so each frame of the window
        [release, free_from] gives linear conditions on the offset (point in front of the eye, inside the frame with margin EPS), the arm
        reach gives a ball (hand within REACH of the arm length from the rest shoulder). Both bodies, both reload clips. The
        smallest pure lift (dy only, 1 mm steps) is taken when it satisfies all of them; else the smallest offset (Euclid) with forward and inward parts.
        The left clips get the offset with x negated (smgprod), so their conditions are in the same unknown.
timing  window start and end: the latest end (up to the first frame the fresh-magazine station needs the gun on its shipped path) and the
        earliest start (longest ramp in) for which a build has no gate fail, no draft rule fail that the control lacks, and passes R9.
verify  R9 absolute on a clips folder: well and hand inside the frame (margin > 0) on every frame of the release window, per
        clip; elbow and shoulder angles and reach against the control (the same generator with no offset).

vis2    (plift2, 2026-11-24) the discard-only raise, as an arm-driven stop (no thigh, no bump): top3.st38 with its stop moved by stop_m, its pitch and roll changed, and the drive
        along the magazine's exit line drop_m long (LIFT2, set by smgprod --lift for an entry with stop_m); lead frames earlier drive start (the wind-up hold shortened). The opener
        from the idle to the wind-up and the drop to the belt station after the stop are the generator's own, so frame 0 and the end are the shipped idle (R6).
        Visibility target (R9 on the whole gun, checks.draft.r9 camera): every vertex of the assembled gun mesh (body and seated magazine) and every joint of the reloading hand
        inside the frame with the margin of the shipped idle's own worst gun vertex (frame 0 of the control clip, per body, rounded up to 0.001), from the arrival at the wind-up
        (release - 7) through the frame the magazine has left the frame, plus the magazine well point inside the frame (EPS) from release to free_from; hand within the arm reach.
        stop solves (stop_m, pitch) on a rigid-move surrogate of the control clip (the gun and hand move with the stop; the drive follows the shipped progress) and
        vis checks a built clips folder against the same target. Both bodies, both hands, both reload clips.

usage:  lift.py stop <control root> --out <lift.json> [--pick ST38B] [--drop 0.18] [--lead 2] [--objective move|up]   solve the arm-driven stop
        lift.py vis <clips dir> [--control <control clips dir>] [--pick ST38B] [--json out]                            R9 whole gun and hand on a built folder
        lift.py solve <control clips dir> --out <lift.json> [--picks ST38B,ST40B,ST32B]
        lift.py timing <control root> --lift <lift.json> --root <trial dir> [--picks ..]   (control root holds clips/ and rest/; trial builds run smgprod.py)
        lift.py verify <clips dir> [--control <clips dir>] [--picks ..] [--json out.json]
"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'checks'))
import renv, common
import numpy as np
import visibility as V
from glb import Glb
from fk import Clip

GUN = os.environ.get('SMG_GUN') or 'warden'
EPS = 0.001          # margin the point must keep inside the frame (the R9 rounding)
REACH = 0.985        # checks.rreload.reach_max: hand to shoulder over the arm length
BODIES = ('pma', 'pwa'); CLIPS = ('empty_reload', 'reload')


def stem(d, body, side, pick, nm): return f'{d}/{body}/{GUN}_{side}_{pick}_{nm}'


def series(d, body, side, pick, nm):
    """Well and hand world points per frame of a clip (raised stance: the clip alone), with its track plan."""
    s = stem(d, body, side, pick, nm); sp = json.load(open(s + '.json')); trk = json.load(open(s + '_track.json'))
    r, L = V.poses(s + '.glb', 'reload_draft', None, side, 'raised'); S = 'Right' if side == 'right' else 'Left'
    st = V.seat(common.gun(GUN)); well, hand = [], []
    for p in L:
        W = r.world(p); well.append(V.R.place(W[r.idx['Weapon' + S]], st[None])[0]); hand.append(W[r.idx[S + 'Hand']][0])
    return dict(well=np.array(well), hand=np.array(hand), R=int(trk['release']), F=int(trk['free_from']), spec=sp, trk=trk)


def arm(spec, side):
    """Rest shoulder and total arm length of the clip's rig (the author's template frame 0)."""
    g = Glb(common.mp(spec['src'])); c = Clip(g, spec['template']); W = c.world(0); ix = {n: i for i, n in enumerate(g.names)}; S = 'Right' if side == 'right' else 'Left'
    s0, e0, h0 = W[ix[S + 'Arm']][0], W[ix[S + 'ForeArm']][0], W[ix[S + 'Hand']][0]
    return np.array(s0), float(np.linalg.norm(e0 - s0) + np.linalg.norm(h0 - e0))


def rows(P, eye, hh):
    """Linear conditions a . d <= b on the offset d that keep point P + d in front of the eye (0.02 m) and inside the frame by EPS
    (|x| <= k tan(h) fwd, |y| <= k tan(v) fwd, fwd = -z of the point against the eye)."""
    th = math.tan(hh); tv = th * 9 / 16; k = 1 - EPS; Q = P - eye
    A = [[0.0, 0.0, 1.0]]; b = [-Q[2] - 0.0201]
    for ax, t in ((0, th), (1, tv)):
        for sg in (1.0, -1.0):
            a = [0.0, 0.0, k * t]; a[ax] = sg; A.append(a); b.append(-sg * Q[ax] - k * t * Q[2])
    return A, b


def collect(d, pick, win=None):
    """Constraint rows over both bodies, both hands, both reload clips, the window release..free_from, well and hand. The offset is given for the right
    hand; a left clip gets it with x negated (smgprod), so its rows have the x column flipped."""
    A = []; B = []; info = {}; ball = []
    for body in BODIES:
        eye, hh = V.camera(body)
        for side in ('right', 'left'):
            m = np.array([-1.0, 1.0, 1.0]) if side == 'left' else np.ones(3)
            for nm in CLIPS:
                sr = series(d, body, side, pick, nm); R, F = sr['R'], sr['F']; info[(body, side, nm)] = (R, F)
                f1 = win or F
                for f in range(R, f1 + 1):
                    for P in (sr['well'][f], sr['hand'][f]):
                        a, b = rows(P, eye, hh); A += (np.array(a) * m).tolist(); B += b
                s0, L = arm(sr['spec'], side)
                for f in range(R, f1 + 1): ball.append((sr['hand'][f], s0, REACH * L, m))
    return np.array(A), np.array(B), info, ball


def margins(d, pick, off):
    """Worst well and hand margin over the window with offset off (m, right hand; left gets x negated), per body, hand and clip."""
    out = {}
    for body in BODIES:
        eye, hh = V.camera(body)
        for side in ('right', 'left'):
            o = off * (np.array([-1.0, 1.0, 1.0]) if side == 'left' else 1.0)
            for nm in CLIPS[:1]:
                sr = series(d, body, side, pick, nm)
                idx = list(range(sr['R'], sr['F'] + 1))
                out[f'{body}_{side}'] = {'well': round(float(min(V.margin(sr['well'][idx] + o, eye, hh))), 3), 'hand': round(float(min(V.margin(sr['hand'][idx] + o, eye, hh))), 3)}
    return out


def solve_pick(d, pick, win=None):
    from scipy.optimize import minimize
    A, B, info, ball = collect(d, pick, win)
    fe = lambda dd: float(np.min(B - A @ dd)) >= 0 and all(np.linalg.norm(h + m * dd - s) <= r for h, s, r, m in ball)
    # pure lift: smallest dy in 1 mm steps
    for k in range(0, 2000):
        dd = np.array([0.0, k * 0.001, 0.0])
        if fe(dd): return dd, 'lift', info
    cons = [{'type': 'ineq', 'fun': lambda x: B - A @ x}, {'type': 'ineq', 'fun': lambda x: np.array([r - np.linalg.norm(h + m * x - s) for h, s, r, m in ball])}]
    best = None
    for x0 in ([0, 0.5, -0.3], [0, 0.8, -0.5], [0, 0.3, -0.6], [0.1, 0.6, -0.2], [-0.1, 0.6, -0.2], [0, 1.0, 0]):
        r = minimize(lambda x: float(x @ x), x0, constraints=cons, method='SLSQP', options={'maxiter': 500, 'ftol': 1e-12})
        if r.success and float(np.min(B - A @ r.x)) >= -1e-6 and (best is None or r.fun < best.fun): best = r
    if best is None: return None, 'infeasible', info
    x = best.x.copy()
    for _ in range(40):      # the optimizer lands on the boundary: nudge by 1e-4 m into the feasible set until the margins hold
        if fe(x): break
        x = x + np.array([0, 1e-4, -1e-4])
    return x, 'lift+forward/inward', info


def cmd_solve(a):
    d = a[0]; out = common.opt(a, '--out'); picks = (common.opt(a, '--picks') or 'ST38B,ST40B,ST32B').split(',')
    res = {}
    for pk in picks:
        dd, kind, info = solve_pick(d, pk)
        if dd is None: print(pk, 'no offset within the arm reach'); res[pk] = None; continue
        R, F = info[('pma', 'right', 'empty_reload')]
        print(f'{pk}: {kind} move_cm {np.round(dd * 100, 1).tolist()} window {R}..{F}', margins(d, pk, dd))
        res[pk] = {'move_m': [round(float(x), 4) for x in dd], 'kind': kind, 'release': R, 'free_from': F}
        res[pk[:-1]] = res[pk]      # smgprod keys a pick without its take
    json.dump(res, open(out, 'w'), indent=1)


# ------------------------------------------------------------------------------------------------ timing
def station_frame(plan):
    """First frame the fresh magazine's rig or the gun's pick-up station needs the gun on its shipped path (the offset must be gone by then)."""
    fr = plan.get('fresh', {'mode': 'still'}); m = fr['mode']; se = int(plan['seated'])
    if m == 'slap': return int(fr['pick']) - 5          # the approach to the pick-up starts 5 frames before it (top3.slap_load)
    if m == 'present': return min(int(plan['appear']), se - 6)
    if m in ('toss', 'drop'): return se - int(fr.get('n', 7))
    if m == 'fall': return se - int(fr.get('n', 5))
    return min(int(plan['appear']), se - 6)


def draft_fails(clips_dir, pick, body, side, nm='empty_reload'):
    """The draft rules (checks/draftcheck.py: R1 to R8) on one clip: ['R5 stop_loss_max_cm_f 4.4 >= 4.5', ...]."""
    import draftcheck
    it = draftcheck.item_of(stem(clips_dir, body, side, pick, nm) + '.glb', 'top', 'B')
    return draftcheck.check_item(it)['fails']


def trial(lift, pick, start, end, root, ctl, clips=('empty_reload',), frames=None):
    """Builds one pick with the offset window start..release..free_from..end (both bodies, both hands) into <root>/<pick>_<start>_<end>; returns (dir, summary):
    gate fails, draft fails that the control (same generator, no offset) does not have, hidden window, elbow step."""
    import subprocess, shutil
    d = f'{root}/{pick}_{start}_{end}' if frames is None else f'{root}/{pick}_' + '_'.join(str(x) for x in frames); os.makedirs(d + '/work', exist_ok=True)
    for b in BODIES:
        os.makedirs(f'{d}/rest/{b}', exist_ok=True)
        t = f'{d}/rest/{b}/rest_{GUN}_R__{GUN}_L.glb'
        if not os.path.exists(t): shutil.copyfile(f'{ctl}/rest/{b}/rest_{GUN}_R__{GUN}_L.glb', t)
    L = {pick[:-1]: dict(lift, frames=frames or [start, lift['release'], lift['free_from'], end])}; lj = f'{d}/lift.json'; json.dump(L, open(lj, 'w'))
    env = dict(os.environ, ROUND_OUT=d, WORK=d + '/work', AUTHORING=d + '/work', PYTHONDONTWRITEBYTECODE='1')
    ps = [subprocess.Popen([sys.executable, '-B', os.path.join(HERE, 'smgprod.py'), 'build', 'top3', '--picks', pick[:-1], '--clips', ','.join(clips), '--sides', sd, '--bodies', b, '--lift', lj],
                           env=env, cwd=HERE, stdout=open(f'{d}/work/{b}_{sd}.log', 'w'), stderr=subprocess.STDOUT) for b in BODIES for sd in ('right', 'left')]
    for p in ps: p.wait()
    key = lambda x: ' '.join(x.split()[:2])
    out = {'start': start, 'end': end, 'fails': [], 'draft_new': [], 'hidden': [], 'elbow_step': [], 'missing': 0}
    for b in BODIES:
        for sd in ('right', 'left'):
            for nm in clips:
                g = f'{d}/clips/{b}/{GUN}_{sd}_{pick}_{nm}_gate.json'
                if not os.path.exists(g): out['missing'] += 1; continue
                o = json.load(open(g)); out['fails'] += [f'{b} {sd} {x}' for x in o['fails']]; out['hidden'].append(o['hidden_frames']); out['elbow_step'].append(o['elbow_step_deg'])
                base = {key(x) for x in draft_fails(ctl + '/clips', pick, b, sd, nm)}
                out['draft_new'] += [f'{b} {sd} {x}' for x in draft_fails(d + '/clips', pick, b, sd, nm) if key(x) not in base]
    return d, out


def cmd_timing(a):
    ctl = a[0]; lj = common.opt(a, '--lift'); root = common.opt(a, '--root'); L = json.load(open(lj)); res = {}
    for pk in (common.opt(a, '--picks') or 'ST38B,ST40B,ST32B').split(','):
        lift = L[pk]; trk = json.load(open(stem(ctl + '/clips', 'pma', 'right', pk, 'empty_reload') + '_track.json')); hi = station_frame(trk['plan']); R = lift['release']
        print(f'{pk}: station {hi}; ramp start 0 up to {R - 4}, window end {hi} (latest), then earlier ends', flush=True)
        chosen = None; log = []
        order = [(s, hi) for s in range(0, R - 3, 2)] + [(0, e) for e in range(hi - 2, lift['free_from'] + 2, -2)]
        for s0, e in order:
            d, o = trial(lift, pk, s0, e, root, ctl)
            rc = cmd_verify([d + '/clips', '--picks', pk], quiet=True); o['r9'] = all(r['r9_absolute'] for r in rc) and bool(rc)
            o['pass'] = not o['fails'] and not o['draft_new'] and o['r9'] and not o['missing']; log.append(o)
            print(f'  start {s0} end {e}: gate {o["fails"]} draft {sorted({x.split(" ", 2)[2] for x in o["draft_new"]})} hidden {o["hidden"]} R9 {o["r9"]} {"PASS" if o["pass"] else ""}', flush=True)
            if o['pass']: chosen = (s0, e); break
        res[pk] = {'start': chosen[0] if chosen else None, 'end': chosen[1] if chosen else None, 'trials': log}
    json.dump(res, open(root + f'/timing_{common.opt(a, "--picks") or "all"}.json', 'w'), indent=1)


# ------------------------------------------------------------------------------------------------ verify
def angles(glb, clip, side, N):
    """Elbow angle, upper-arm turn against the rest pose, clavicle turn against rest (deg), shoulder joint shift (cm), reach ratio: worst over the clip."""
    from fk import qmul, qinv
    g = Glb(glb); c = Clip(g, clip); ix = {n: i for i, n in enumerate(g.names)}; S = 'Right' if side == 'right' else 'Left'
    W0 = c.world(0); el = []; ua = []; cl = []; sh = []; rr = []
    ang = lambda q: math.degrees(2 * math.atan2(float(np.linalg.norm(q[:3])), abs(float(q[3]))))
    for f in range(N):
        W = c.world(f); s, e, h = W[ix[S + 'Arm']][0], W[ix[S + 'ForeArm']][0], W[ix[S + 'Hand']][0]
        u = (s - e) / np.linalg.norm(s - e); w = (h - e) / np.linalg.norm(h - e); el.append(math.degrees(math.acos(float(np.clip(u @ w, -1, 1)))))
        ua.append(ang(qmul(qinv(W0[ix[S + 'Arm']][1]), W[ix[S + 'Arm']][1]))); cl.append(ang(qmul(qinv(W0[ix[S + 'Shoulder']][1]), W[ix[S + 'Shoulder']][1])))
        sh.append(float(np.linalg.norm(s - W0[ix[S + 'Arm']][0])) * 100); rr.append(float(np.linalg.norm(h - s) / (np.linalg.norm(e - s) + np.linalg.norm(h - e))))
    return {'elbow_min_deg': round(min(el), 1), 'elbow_max_deg': round(max(el), 1), 'upper_arm_turn_max_deg': round(max(ua), 1), 'clavicle_turn_max_deg': round(max(cl), 1),
            'shoulder_shift_max_cm': round(max(sh), 2), 'reach_max': round(max(rr), 3)}


def cmd_verify(a, quiet=False):
    d = a[0]; ctl = common.opt(a, '--control'); picks = (common.opt(a, '--picks') or 'ST38B,ST40B,ST32B').split(','); rows_ = []
    for pk in picks:
        for body in BODIES:
            for side in ('right', 'left'):
                for nm in CLIPS:
                    s = stem(d, body, side, pk, nm)
                    if not os.path.exists(s + '.glb'): continue
                    trk = json.load(open(s + '_track.json')); m = V.measure(GUN, body, side, s + '.glb', trk, 'reload_draft', None, 'raised'); w = m['release']
                    n = w['n']; ok = w['in_view'] == n and w['hand_in_view'] == n
                    row = {'clip': f'{pk}_{nm}', 'body': body, 'side': side, 'window': w['window'], 'n': n, 'well_in_view': w['in_view'], 'hand_in_view': w['hand_in_view'],
                           'worst_well': w['worst_margin'], 'worst_hand': w['worst_hand'], 'r9_absolute': ok, 'arm': angles(s + '.glb', 'reload_draft', side, m['frames'])}
                    if ctl:
                        c = stem(ctl, body, side, pk, nm); row['arm_control'] = angles(c + '.glb', 'reload_draft', side, m['frames'])
                        mc = V.measure(GUN, body, side, c + '.glb', json.load(open(c + '_track.json')), 'reload_draft', None, 'raised')['release']
                        row['control'] = {'in_view': mc['in_view'], 'hand_in_view': mc['hand_in_view'], 'n': mc['n'], 'worst_well': mc['worst_margin'], 'worst_hand': mc['worst_hand']}
                    rows_.append(row)
    for r in ([] if quiet else rows_):
        print(f"{r['clip']:22s} {r['body']} {r['side']:5s} win {r['window']} well {r['well_in_view']}/{r['n']} ({r['worst_well']:+.3f}) hand {r['hand_in_view']}/{r['n']} ({r['worst_hand']:+.3f}) "
              f"R9 abs {'pass' if r['r9_absolute'] else 'FAIL'} | elbow {r['arm']['elbow_min_deg']}..{r['arm']['elbow_max_deg']} reach {r['arm']['reach_max']} shoulder {r['arm']['shoulder_shift_max_cm']} cm")
    js = common.opt(a, '--json')
    if js: json.dump(rows_, open(js, 'w'), indent=1)
    if quiet: return rows_
    return 0 if all(r['r9_absolute'] for r in rows_) else 1


# ------------------------------------------------------------------------------------------------ vis2: discard-only lift
_cloud = {}
CONTROL = None      # control clips root (<root>/clips), set by cmd_plan / cmd_vis; the idle is read from its ST38B clip


def cloud():
    """Every vertex of the assembled gun (body parts and the seated magazine, weapon bone space) and of the standard magazine alone."""
    if not _cloud:
        import guns as GN
        g = common.gun(GUN)['mesh']; _cloud['gun'] = GN.assembled(g); _cloud['mag'] = GN.mesh(common.need(GN.find(g + '__mag_std_01.glb')))
    return _cloud


def rchecks_eye():
    import rchecks
    return rchecks.EYE


def eye_pts():
    """The gun points rgate measures the eye distance on (rchecks.gun_points, every 4th), cached."""
    if 'E' not in _cloud:
        import rchecks, manifest
        _cloud['E'] = np.array(rchecks.gun_points(GUN))[::4]; _cloud['eye_min'] = manifest.load()['checks']['rreload']['eye_min_cm'] / 100.0
    return _cloud['E'], _cloud['eye_min']


def idle_margin(body):
    """Worst margin of any gun vertex in the shipped idle (frame 0 of the clip, the pose the reload returns to), rounded up to 0.001."""
    sp = stem(CONTROL, body, 'right', IDLE_PICK, 'empty_reload'); r, L = V.poses(sp + '.glb', 'reload_draft', None, 'right', 'raised'); eye, hh = V.camera(body)
    W = r.world(L[0]); m = float(V.margin(V.R.place(W[r.idx['WeaponRight']], cloud()['gun']), eye, hh).min())
    return math.ceil(m * 1000) / 1000


def object_event(base):
    """Discard event of a tube or break clip from its _objects.json: (R, F) of the spent part (first frame more than 1 cm from its frame 0 position, first frame more than 5 cm away), or None
    (a magazine clip has no _objects.json, a gun whose spent parts are not modelled has no spent entry). joints[spent] is one list of 4x4 matrices (gun axes, None where the part is absent) or a dict of such lists."""
    import numpy as _np
    f = base + '_objects.json'
    if not os.path.exists(f): return None
    sp = (json.load(open(f)).get('joints') or {}).get('spent')
    if not sp: return None
    best = None
    for ser in ([sp] if isinstance(sp, list) else list(sp.values())):
        m0 = next((m for m in ser if m is not None), None)
        if m0 is None: continue
        p0 = _np.array(m0, float).reshape(4, 4)[:3, 3]; p = _np.array([_np.array(m if m is not None else m0, float).reshape(4, 4)[:3, 3] for m in ser]); mv = _np.linalg.norm(p - p0, axis=1) * 100
        R = next((i for i in range(len(p)) if mv[i] > 1.0), None)
        if R is None: continue
        F = next((i for i in range(R, len(p)) if mv[i] > 5.0), len(p) - 1)
        if best is None or R < best[0]: best = (R, F)
    return best


def series2(d, body, side, pick, nm):
    """Per frame of a clip (raised stance, the clip alone): weapon bone transform, reloading hand joints (world), the track, plan frames."""
    s = stem(d, body, side, pick, nm); trk = json.load(open(s + '_track.json')); sp = json.load(open(s + '.json'))
    r, L = V.poses(s + '.glb', 'reload_draft', None, side, 'raised'); S = 'Right' if side == 'right' else 'Left'
    hj = [r.idx[n] for n in r.names if n.startswith(S + 'Hand')]; wt = []; hand = []
    for p in L:
        W = r.world(p); wt.append((np.array(W[r.idx['Weapon' + S]][0], float), tuple(W[r.idx['Weapon' + S]][1]))); hand.append(np.array([W[j][0] for j in hj]))
    ev = object_event(s)      # tube and break clips: no magazine; the discard is the spent hull or shell leaving the gun (the track's release and free_from are placeholders there)
    R, F = ev if ev else (int(trk['release']), int(trk['free_from']))
    return dict(wt=wt, hand=hand, trk=trk, spec=sp, R=R, F=F, n=len(L), body=body, side=side, event='object' if ev else 'magazine')


def mag_pts(sr, f, off=None):
    """World points of the magazine mesh at frame f (shifted by off), from the track matrix in gun axes; None when the track has it gone."""
    fr = sr['trk']['frames'][f]
    if fr.get('state') == 'gone' or fr.get('s', 1.0) == 0.0: return None
    m = np.array(fr['m'], float).reshape(4, 4); P = cloud()['mag'][::5] @ m[:3, :3].T + m[:3, 3]
    P = V.R.place(sr['wt'][f], P)
    return P if off is None else P + off


def gun_world(sr, f): return V.R.place(sr['wt'][f], cloud()['gun'])


def mag_gone_frame(sr, off, eye, hh):
    """First frame at or after free_from with no magazine vertex inside the frame (or the magazine gone), the control shifted by off (held offset)."""
    for f in range(sr['F'], sr['n']):
        P = mag_pts(sr, f, off)
        if P is None or float(V.margin(P, eye, hh).max()) <= 0: return f
    return sr['n'] - 1


def face_rows(P, eye, hh, m):
    """The binding constraint per face for the point set P: rows a . d <= b (5 faces: in front, x+, x-, y+, y-), b the smallest over the points (a is the same for every point)."""
    th = math.tan(hh); tv = th * 9 / 16; k = 1 - m; Q = P - eye; A = [[0.0, 0.0, 1.0]]; b = [float((-Q[:, 2] - 0.0201).min())]
    for ax, t in ((0, th), (1, tv)):
        for sg in (1.0, -1.0):
            a = [0.0, 0.0, k * t]; a[ax] = sg; A.append(a); b.append(float((-sg * Q[:, ax] - k * t * Q[:, 2]).min()))
    return A, b


def vis2(clips, pick, json_out=None):
    """R9 on the whole gun for a clips folder: per clip (both bodies, hands, reload clips) the worst margin of gun vertices and hand joints from f1 (the clip's lift spec, else release)
    to the frame the magazine has left the frame (from the clip's own track), against the idle target."""
    out = []; mt = {b: idle_margin(b) for b in BODIES}
    for body in BODIES:
        eye, hh = V.camera(body)
        for side in ('right', 'left'):
            for nm in CLIPS:
                s = stem(clips, body, side, pick, nm)
                if not os.path.exists(s + '.glb'): continue
                sr = series2(clips, body, side, pick, nm); lf = sr['spec'].get('_lift'); f1 = (lf['frames'][1] if 'frames' in lf and 'stop_m' not in lf else sr['R'] - lf.get('from', ARRIVE)) if lf else sr['R']
                w1 = mag_gone_frame(sr, None, eye, hh); g = []; h = []
                for f in range(f1, w1 + 1):
                    g.append(float(V.margin(gun_world(sr, f), eye, hh).min())); h.append(float(V.margin(sr['hand'][f], eye, hh).min()))
                out.append({'clip': f'{pick}_{nm}', 'body': body, 'side': side, 'window': [f1, w1], 'target': mt[body], 'gun_worst': round(min(g), 3), 'hand_worst': round(min(h), 3),
                            'pass': min(g) >= mt[body] - 1e-9 and min(h) >= mt[body] - 1e-9})
    if json_out: json.dump(out, open(json_out, 'w'), indent=1)
    return out


# ---- vis2, arm-driven stop: the stop of the release moves by d, its pitch and roll change, the drive along the magazine's exit line gets length D (shipped 0.18 m)
DROP0 = 0.18        # top3.STOP_DRIVE: the arm drives the gun this far (m) along the exit line and stops it dead on the release frame (ST38 0.18, ST40 0.20)
HOLD_AFTER = 4      # ST32: the hold offset lasts until the release + 4 (top3.st32: the spin ends there, the departure to the belt station starts)
ARRIVE = 7          # top3.STOP_DRIVE: the wind-up is reached this many frames before the release (ST38 7, ST40 6)


IDLE_PICK = 'ST38B'      # the pick whose clip frame 0 gives the idle margin (every pick starts in the same idle)


def family_module(gun, pick):
    """The generator module (smgprod.FAMILIES) that makes `pick` of `gun`; None when the gun is not made by smgprod."""
    import smgprod, importlib
    for fam, (gid, take, pks, eng) in smgprod.FAMILIES.items():
        if gid == gun and pick[:-1] in pks: return importlib.import_module(fam)
    return None


def hook(gun, pick):
    """'stop' (arm-driven stop of the discard, LIFT2), 'hold' (offset of the in-hand hold) or None (the family's generator has no lowered hook): read from the generator's STOP_DRIVE table."""
    F = family_module(gun, pick); sd = getattr(F, 'STOP_DRIVE', None) if F else None
    if not sd or pick[:-1] not in sd: return None
    return 'hold' if sd[pick[:-1]]['drop'] is None else 'stop'


def use(pick, gun=None):
    """Sets GUN, IDLE_PICK, DROP0 and ARRIVE from the generator's own constants for the pick (ST38B or ST38)."""
    global DROP0, ARRIVE, IDLE_PICK, GUN
    if gun: GUN = gun
    IDLE_PICK = pick if pick.endswith(('A', 'B')) else pick + 'B'
    F = family_module(GUN, pick); d = F.STOP_DRIVE[pick[:-1] if pick.endswith(('A', 'B')) else pick]; DROP0 = d['drop'] or DROP0; ARRIVE = d['arrive']


def drive_profile(sr):
    """World exit direction e of the drive (the shipped drive from the wind-up hold to the stop) and the progress s(f) in 0..1 of the gun along it."""
    G = [w[0] for w in sr['wt']]; R = sr['R']; e = G[R] - G[R - 4]; e = e / np.linalg.norm(e)
    L = float((G[R] - G[R - 4]) @ e); s = [min(1.0, max(0.0, float((G[f] - G[R - 4]) @ e) / L)) for f in range(len(G))]
    return e, s


# ---- vis2, arm-driven stop with the stop pitch free: variables d (stop offset, 3) and dp (stop pitch change, deg, about the gun's rest x axis)
_hull = {}


def hull():
    if 'H' not in _hull:
        from scipy.spatial import ConvexHull
        G = cloud()['gun']; _hull['H'] = G[ConvexHull(G).vertices]
    return _hull['H']


def rot_world(sr, dp, dr=0.0, f=None):
    """World rotation of a pitch change dp and a roll change dr (deg) of the stop: the author builds q = q0 . Rx(p) Ry Rz(r), so the pitch change is q0 Rx(dp) q0^-1 on the left and the
    roll change is the gun's own z turn q Rz(dr) q^-1 (q taken at frame f, the stop frame by default)."""
    from scipy.spatial.transform import Rotation as Rot
    q0 = Rot.from_quat(sr['wt'][0][1]); Rp = q0 * Rot.from_rotvec([math.radians(dp), 0, 0]) * q0.inv()
    if not dr: return Rp
    q = Rot.from_quat(sr['wt'][sr['R'] if f is None else f][1]); return Rp * (q * Rot.from_rotvec([0, 0, math.radians(dr)]) * q.inv())


def pose4(sr, f, d, dp, dr, D, m):
    """(rotation about the gun origin, world shift of the origin) at frame f for the arm-driven stop (offset d, pitch change dp, roll change dr, drive length D) against the control clip.
    The wind-up hold moves by d + DROP0 e - D e' (e' = the exit direction after the rotation), the stop by d, the drive in between by the shipped progress s."""
    e, s = sr.setdefault('_drive', drive_profile(sr)); Rw = rot_world(sr, dp, dr); e2 = Rw.apply(e)
    wu = DROP0 * e - D * e2; return Rw, d * m + wu * (1.0 - s[f])


def cons4(z, S, f1, mt, D, ang=None):
    """Slacks (>= 0 ok): per clip and frame the 5 view faces over the hull and hand (idle margin), the well point (EPS) at the release frames, and the reach. z = d, or d + [dp] (+ [dr])."""
    d = z[:3]; dp, dr = (ang if ang is not None else (z[3], z[4] if len(z) > 4 else 0.0)); out = []
    for sr, body, m, eye, hh, s0, L, w1 in S:
        for f in range(f1, w1 + 1):
            Rw, sh = pose4(sr, f, d, dp, dr, D, m); g0 = sr['wt'][f][0]
            tf = lambda P: g0 + Rw.apply(P - g0) + sh
            P = tf(np.concatenate([V.R.place(sr['wt'][f], hull()), sr['hand'][f]])); a, b = face_rows(P, eye, hh, mt[body]); out += [b[k] for k in range(5)]
            Ep, em = eye_pts(); out.append(float(np.linalg.norm(tf(V.R.place(sr['wt'][f], Ep)) - rchecks_eye(), axis=1).min()) - em)      # rgate eye rule: no gun point nearer than eye_min_cm to the eye
            if sr['R'] <= f <= sr['F']:
                W = tf(V.R.place(sr['wt'][f], V.seat(common.gun(GUN))[None])); a, b = face_rows(W, eye, hh, EPS); out += [b[k] for k in range(5)]
            out.append(REACH * L - float(np.linalg.norm(tf(sr['hand'][f][0:1])[0] - s0)))
    return np.array(out)


def solve4(d, pick, D=None, f1=None, up=False, quiet=False, ang=None, starts=None):
    """Stop offset d (3) and pitch change dp (and, when ang is None and 5 variables are wanted, roll change) for drive length D: the smallest rigid move of the gun (mean squared
    displacement of its hull vertices at the stop) meeting cons4. ang = (dp, dr) fixes the angles and solves d alone. up: highest stop instead of the smallest move."""
    from scipy.optimize import minimize
    use(pick); D = DROP0 if D is None else D
    f1 = f1 if f1 is not None else json.load(open(stem(d, 'pma', 'right', pick, 'empty_reload') + '_track.json'))['release'] - ARRIVE
    mt = {b: idle_margin(b) for b in BODIES}; S = []
    for body in BODIES:
        eye, hh = V.camera(body)
        for side in ('right', 'left'):
            m = np.array([-1.0, 1.0, 1.0]) if side == 'left' else np.ones(3)
            for nm in CLIPS:
                sr = series2(d, body, side, pick, nm); s0, L = arm(sr['spec'], side); w1 = max(sr['F'], min(sr['F'] + 3, sr['n'] - 1)); S.append((sr, body, m, eye, hh, s0, L, w1))
    H = hull(); sr0 = S[0][0]; g0 = sr0['wt'][sr0['R']][0]
    def cost(z):
        dp, dr = (ang if ang is not None else (z[3], 0.0)); Rw = rot_world(sr0, dp, dr); disp = Rw.apply(H - g0) + g0 - H + z[:3]; return float((disp ** 2).sum(1).mean())
    nv = 3 if ang is not None else 4; best = None
    for x0 in (starts or ([-0.2, 0.15, -0.3, 0], [-0.2, 0.15, -0.3, -10], [-0.1, 0.1, -0.1, 0], [0.0, 0.03, 0.0, 0], [-0.05, 0.05, -0.05, -5])):
        x0 = list(x0)[:nv]
        r = minimize((lambda z: -z[1]) if up else cost, np.array(x0, float), constraints=[{'type': 'ineq', 'fun': lambda z: cons4(z, S, f1, mt, D, ang)}],
                     bounds=[(-1, 1)] * 3 + [(-40, 40)] * (nv - 3), method='SLSQP', options={'maxiter': 200, 'ftol': 1e-10})
        sl = float(cons4(r.x, S, f1, mt, D, ang).min())
        if not quiet: print('  start', x0, '->', np.round(r.x, 3), 'cost', round(r.fun, 5), 'min slack', round(sl, 4), flush=True)
        if sl >= -1e-6 and (best is None or r.fun < best.fun): best = r
    return (None if best is None else best.x), mt


# ---- vis2, hold offset (ST32, plift4): no drive and no stop, the gun is held in the fingers while it turns; the offset moves the hold position of the in-hand turn
R8_MARGIN = 0.005    # the surrogate R8 must clear the limit by this share (the built clip is measured again)


def r8_limits(gid, pick):
    """The R8 lower bounds (checks.draft.r8_min) of the gun's family and take, or None."""
    import rgate, manifest
    return ((manifest.load()['checks']['draft'].get('r8_min') or {}).get(rgate.family({'_pick': pick, '_gun': gid})) or {}).get(pick[-1])


def r8_slacks(G, Q, release, lb, margin=R8_MARGIN):
    """Slack (value / limit - 1 - margin, >= 0 ok) of each R8 measure (survey.sustained) of a gun series (m) against the bounds lb."""
    import survey
    m = survey.sustained(G, Q, release)
    return [float(m[k]) / lb[k] - 1.0 - margin if k in m else -1.0 for k in ('path_cm', 'v90_cm_f', 'rel_path_cm', 'rel_v90_cm_f') if lb.get(k) is not None]


def hold_profile(R, f, arrive):
    """Weight of the hold offset at frame f (ST32): in over the move to the hold (frame 0 to the arrival), held to the end of the in-hand turn (release + HOLD_AFTER), out over 8 frames."""
    import author
    return author.bump_w([0, R - arrive, R + HOLD_AFTER, R + HOLD_AFTER + 8], f, 'minjerk')


def cons_hold(z, S, f1, mt, lb=None):
    """Slacks (>= 0 ok) of a rigid offset z (3, right hand; left gets x negated) of the gun and hand over frames f1 .. min(mag out of frame, release + HOLD_AFTER): the 5 view faces over hull and hand
    (idle margin), the well point (EPS) from the release to free_from, the reach."""
    out = []
    for sr, body, m, eye, hh, s0, L, w1 in S:
        for f in range(f1, min(w1, sr['R'] + HOLD_AFTER) + 1):
            d = z * m; P = np.concatenate([V.R.place(sr['wt'][f], hull()), sr['hand'][f]]) + d; a, b = face_rows(P, eye, hh, mt[body]); out += [b[k] for k in range(5)]
            Ep, em = eye_pts(); out.append(float(np.linalg.norm(V.R.place(sr['wt'][f], Ep) + d - rchecks_eye(), axis=1).min()) - em)
            if sr['R'] <= f <= sr['F']:
                W = V.R.place(sr['wt'][f], V.seat(common.gun(GUN))[None]) + d; a, b = face_rows(W, eye, hh, EPS); out += [b[k] for k in range(5)]
            out.append(REACH * L - float(np.linalg.norm(sr['hand'][f][0] + d - s0)))
        if lb:      # R8 on the gun series with the offset applied over the hold profile (surrogate of the built clip)
            G = np.array([w[0] for w in sr['wt']]) + np.array([hold_profile(sr['R'], f, ARRIVE) for f in range(sr['n'])])[:, None] * (z * m)[None]
            out += r8_slacks(G, [w[1] for w in sr['wt']], sr['R'], lb)
    return np.array(out)


def solve_hold(d, pick, quiet=False, r8=False):
    """The smallest offset of the hold position (3, right hand) that meets the visibility target (idle margin, whole gun and hand) from the arrival at the hold to the magazine out of frame, and the reach."""
    from scipy.optimize import minimize
    use(pick); f1 = json.load(open(stem(d, 'pma', 'right', pick, 'empty_reload') + '_track.json'))['release'] - ARRIVE; mt = {b: idle_margin(b) for b in BODIES}; S = []
    lb = r8_limits(GUN, pick) if r8 else None
    for body in BODIES:
        eye, hh = V.camera(body)
        for side in ('right', 'left'):
            m = np.array([-1.0, 1.0, 1.0]) if side == 'left' else np.ones(3)
            for nm in CLIPS:
                sr = series2(d, body, side, pick, nm); s0, L = arm(sr['spec'], side); w1 = max(sr['F'], min(sr['F'] + 3, sr['n'] - 1)); S.append((sr, body, m, eye, hh, s0, L, w1))
    best = None
    for x0 in ([0, 0.1, 0], [0, 0.3, -0.1], [0, 0.5, -0.3], [-0.1, 0.3, 0.0]):
        r = minimize(lambda z: float(z @ z), np.array(x0, float), constraints=[{'type': 'ineq', 'fun': lambda z: cons_hold(z, S, f1, mt, lb)}], bounds=[(-1, 1)] * 3, method='SLSQP', options={'maxiter': 200, 'ftol': 1e-12})
        sl = float(cons_hold(r.x, S, f1, mt, lb).min())
        if not quiet: print('  start', x0, '->', np.round(r.x, 4), 'cost', round(r.fun, 5), 'min slack', round(sl, 4), flush=True)
        if sl >= -1e-6 and (best is None or r.fun < best.fun): best = r
    return (None if best is None else best.x), mt


def cmd_hold(a):
    """vis2 solve for a pick with no stop (ST32): the hold offset from the control clips."""
    global CONTROL
    ctl = a[0]; CONTROL = ctl + '/clips'; out = common.opt(a, '--out'); pick = common.opt(a, '--pick') or 'ST32B'
    use(pick, common.opt(a, '--gun')); r8 = '--r8' in a; x, mt = solve_hold(CONTROL, pick, r8=r8)
    if x is None: print(pick, 'no offset meets the target'); return 1
    rel = json.load(open(stem(CONTROL, 'pma', 'right', pick, 'empty_reload') + '_track.json'))
    res = {pick[:-1]: {'stop_m': [round(float(v), 4) for v in x], 'pitch_deg': 0.0, 'roll_deg': 0.0, 'drop_m': 0.0, 'lead': 0, 'release': rel['release'], 'free_from': rel['free_from'], 'idle_margin': mt, 'objective': 'hold', 'from': ARRIVE, 'r8': r8}}
    print(json.dumps(res)); json.dump(res, open(out, 'w'), indent=1); return 0


def cmd_stop(a):
    """vis2 solve: the arm-driven stop offset and pitch from the control clips. --objective move (smallest rigid move of the gun, default) or up (highest stop)."""
    global CONTROL
    ctl = a[0]; CONTROL = ctl + '/clips'; out = common.opt(a, '--out'); pick = common.opt(a, '--pick') or 'ST38B'; use(pick, common.opt(a, '--gun')); D = float(common.opt(a, '--drop') or DROP0)
    up = (common.opt(a, '--objective') or 'move') == 'up'; lead = int(common.opt(a, '--lead') or 2)
    rel0 = json.load(open(stem(CONTROL, 'pma', 'right', pick, 'empty_reload') + '_track.json'))['release']; fb = common.opt(a, '--from')      # --from n: the window starts n frames before the release (default: the wind-up arrival)
    x, mt = solve4(CONTROL, pick, D, f1=(rel0 - int(fb)) if fb is not None else None, up=up, starts=[[0.0, 0.05, 0.0, 0], [-0.05, 0.1, -0.1, -5]])
    if x is None: print(pick, 'no stop meets the target'); return 1
    rel = json.load(open(stem(CONTROL, 'pma', 'right', pick, 'empty_reload') + '_track.json'))
    res = {pick[:-1]: {'stop_m': [round(float(v), 4) for v in x[:3]], 'pitch_deg': round(float(x[3]), 2), 'roll_deg': 0.0, 'drop_m': D, 'lead': lead, 'release': rel['release'], 'free_from': rel['free_from'],
                      'idle_margin': mt, 'objective': 'up' if up else 'move', **({'from': int(fb)} if fb is not None else {})}}
    print(json.dumps(res)); json.dump(res, open(out, 'w'), indent=1); return 0


def cmd_vis(a):
    """vis2 check of a clips folder: R9 on the whole gun and the reloading hand against the idle margin; exit 1 when a clip fails."""
    global CONTROL
    CONTROL = common.opt(a, '--control') or a[0]; pick = common.opt(a, '--pick') or 'ST38B'; use(pick, common.opt(a, '--gun')); rows_ = vis2(a[0], pick, common.opt(a, '--json'))
    for r in rows_: print(f"{r['clip']:22s} {r['body']} {r['side']:5s} window {r['window']} gun worst {r['gun_worst']:+.3f} hand worst {r['hand_worst']:+.3f} target {r['target']:+.3f} {'pass' if r['pass'] else 'FAIL'}")
    return 0 if all(r['pass'] for r in rows_) else 1


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] not in ('solve', 'verify', 'timing', 'stop', 'vis', 'hold'): raise SystemExit(__doc__)
    sys.exit({'solve': cmd_solve, 'verify': cmd_verify, 'timing': cmd_timing, 'stop': cmd_stop, 'hold': cmd_hold, 'vis': cmd_vis}[a[0]](a[1:]))
