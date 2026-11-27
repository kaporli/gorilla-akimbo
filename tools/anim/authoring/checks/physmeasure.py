"""Physics measures of a reload clip's free parts (the pphys survey, gg-work/migration/pphys/REPORT.md, moved into the draft area).
Units: cm, degrees, frames at 30 fps, world y up. Reads <clip>.json, .glb, _track, _objects, _phys; nothing is written.
Reuses survey._clip_series and the gun and magazine geometry of reload/rchecks.py. The floors (weapons.json checks.draft.phys_floor) are
float rounding: a measure within them is zero. Every number is rounded to 5 decimals before it meets a floor, as the survey did.

  magazine   C[f] world centre, seat[f] the well point carried by the Weapon bone, v_in[f] = C[f] - C[f-1], free step v_in[f+1] = v_in[f] + g.
             flight    frames with the magazine falling on f-1, f, f+1 and no contact (bounce, floor, gun surface within the sampling
                       spacing): acceleration against g and spin change against the floors (gate R3).
             fresh     steps inside a fresh run (not the first frame, a new object) with no contact: still (step and spin within the
                       floors) or in free flight at g, else counted (gate R4a).
             release   first free step against the carrier: linear impulse (cm/f) and angular impulse (deg/f), reported; exit speed
                       against the largest well-point step up to the release (carrier-energy bound), reported.
  shells     spent and live shells and other objects of _objects.json. A frame is judged when the object is not carried (pose fixed in
             the gun, a hand or the world), not in contact (gun surface, floor, bounce, landing frame) and not at g within the floors.
             Judged and within 1.5 cm/f2 of g with constant spin: free flight not at g (gate). Everything else (loading and ejection
             near the hands) is not judged, counted only.
"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..', 'reload')); sys.path.insert(0, os.path.join(HERE, '..')); sys.path.insert(0, HERE)
import renv, survey
import numpy as np

G_CM = survey.G_CM
GV = np.array([0.0, -G_CM, 0.0])
NEAR_G = 1.5            # cm/f2: acceleration within this of g counts as flight, further off is a hand frame
_cache = {}


def _rotvec(Rm):
    import magtrack2
    return magtrack2.log_rot(Rm) * 180.0 / math.pi


def _geo(gid):
    """KD-tree of the gun surface, contact spacing (cm: sampling resolution of the gun and magazine clouds), magazine points."""
    if gid in _cache: return _cache[gid]
    import rchecks
    from scipy.spatial import cKDTree
    gp = rchecks.gun_points(gid, 6000); t = cKDTree(gp)
    d, _ = t.query(gp, k=2); spacing = float(np.median(d[:, 1])) * 100
    mp = rchecks.mag_points(gid, 400)
    if mp is not None:
        dm, _ = cKDTree(mp).query(mp, k=2); spacing += float(np.median(dm[:, 1])) * 100
    _cache[gid] = (t, spacing, mp); return _cache[gid]


def _hands(glb, clip):
    from glb import Glb
    from wclip import TClip
    import magtrack2
    c = TClip(Glb(glb), clip); out = {}
    for nm in ('LeftHand', 'RightHand'):
        if nm in c.names:
            i = c.names.index(nm); out[nm] = [magtrack2.m4(*[np.array(x, float) for x in c.wf(f)[i]]) for f in range(c.frames)]
    return out


def measure(base, spec, F):
    """-> {'mag': {...} | None, 'objects': {...} | None}. F = checks.draft.phys_floor: pos_cm_f, acc_cm_f2, rot_deg_f."""
    import magtrack2
    side = spec.get('_side', 'Right'); gid = spec.get('_gun')
    G, Q, _ = survey._clip_series(base + '.glb', spec['clip'], side); n = len(G)
    GW = [magtrack2.m4(G[f], Q[f]) for f in range(n)]
    out = {'mag': None, 'objects': None}
    track = json.load(open(base + '_track.json')) if os.path.exists(base + '_track.json') else None
    ph = json.load(open(base + '_phys.json')) if os.path.exists(base + '_phys.json') else None
    if track is not None and any(x['state'] == 'falling' for x in track['frames']):
        out['mag'] = _mag(spec, track, GW, gid, F, n)
    if os.path.exists(base + '_objects.json'):
        out['objects'] = _objects(base, spec, ph, GW, gid, F, n)
    return out


def _mag(spec, track, GW, gid, F, n):
    import magtrack2
    FP, FA, FW = F['pos_cm_f'], F['acc_cm_f2'], F['rot_deg_f']
    fr = list(track['frames'])
    while len(fr) < n: fr.append({'state': 'beyond', 'm': None, 's': 0.0})
    st = [x['state'] for x in fr]; sc = [x['s'] for x in fr]; plan = track.get('plan') or {}
    v = magtrack2.vanilla(gid, spec['_gun_clip']); cen = np.r_[v['centre'], 1]; Seat = v['seat']
    tree, spacing, mp = _geo(gid)
    Mm = [None if x.get('m') is None else np.array(x['m']).reshape(4, 4) for x in fr]
    valid = [Mm[f] is not None and sc[f] > 0.5 and st[f] != 'gone' for f in range(n)]
    C = [(GW[f] @ Mm[f] @ cen)[:3] * 100 if valid[f] else None for f in range(n)]
    seat = [(GW[f] @ Seat @ cen)[:3] * 100 for f in range(n)]
    Rw = [GW[f][:3, :3] @ Mm[f][:3, :3] if valid[f] else None for f in range(n)]
    Rg = [GW[f][:3, :3] for f in range(n)]
    wg = [None] + [_rotvec(Rg[f] @ Rg[f - 1].T) for f in range(1, n)]

    def vin(f): return C[f] - C[f - 1] if f >= 1 and valid[f] and valid[f - 1] else None
    def win(f): return _rotvec(Rw[f] @ Rw[f - 1].T) if f >= 1 and valid[f] and valid[f - 1] else None
    def dist_gun(f):
        P = (Mm[f][:3, :3] @ mp.T).T + Mm[f][:3, 3]
        d, _ = tree.query(P); return float(d.min()) * 100
    bt = [b['t'] for b in ((track.get('phys') or {}).get('bounces') or [])]
    floor_cm = float(plan.get('floor', 0.08)) * 100
    mg = {'mode': plan.get('mode'), 'contact_dist_cm': round(spacing, 3)}
    f0 = next((f for f in range(n) if st[f] == 'falling'), None)
    if f0 is None: return mg
    k = f0 - 1; guided = []
    while k >= 0 and st[k] == 'guided': guided.append(k); k -= 1
    sep = k       # last attached frame
    well_step = [0.0] + [round(float(np.linalg.norm(seat[f] - seat[f - 1])), 5) for f in range(1, n)]
    # release (reported): the first free step against the carrier
    rel = {'guided_frames': len(guided)}
    v_ff = vin(f0)
    if v_ff is not None and sep >= 1:
        v_well = seat[sep] - seat[sep - 1]
        if not guided: dv = v_ff - GV - v_well
        else:
            vprev = vin(f0 - 1); dv = v_ff - GV - vprev if vprev is not None else None
        rel['linear_cm_f'] = None if dv is None else round(float(np.linalg.norm(dv)), 4)
        w_ff = win(f0); w_ref = wg[sep] if not guided else win(f0 - 1)
        rel['angular_deg_f'] = round(float(np.linalg.norm(w_ff - w_ref)), 4) if w_ff is not None and w_ref is not None else None
        exit_ = float(np.linalg.norm(np.array([round(float(x), 4) for x in v_ff]) - GV))
        wmax = max(well_step[1:sep + 1]); rel['exit_cm_f'] = round(exit_, 4); rel['carrier_max_cm_f'] = round(wmax, 4); rel['carrier_margin_cm_f'] = round(wmax - exit_, 4)
    mg['release'] = rel
    # free flight (gate): frames falling on f-1, f, f+1, outside contact
    segs = []; cur = []
    for f in range(f0, n):
        if st[f] == 'falling' and valid[f]: cur.append(f)
        else:
            if cur: segs.append(cur); cur = []
    if cur: segs.append(cur)
    flight = 0; over = []; worst = 0.0
    for sg in segs:
        for f in sg[1:-1]:
            if not (valid[f - 1] and valid[f + 1]): continue
            A = C[f + 1] - 2 * C[f] + C[f - 1] - GV; wa = win(f + 1) - win(f)
            if any(abs(f + d - t) <= 1.01 for t in bt for d in (-1, 0, 1)): continue
            if min(C[f - 1][1], C[f][1], C[f + 1][1]) <= floor_cm: continue
            if min(dist_gun(f + d) for d in (-1, 0, 1)) <= spacing: continue
            a_v = round(float(A[1]), 5); a_h = round(float(np.linalg.norm(A[[0, 2]])), 5); dw = round(float(np.linalg.norm(wa)), 5)
            flight += 1
            if abs(a_v) > FA or a_h > FA or dw > FW:
                over.append(f); worst = max(worst, abs(a_v) / FA, a_h / FA, dw / FW)
    mg['flight'] = {'frames': flight, 'off_g': len(over), 'off_g_frames': over[:6], 'worst_x_floor': round(worst, 2)}
    # fresh part (gate): steps inside a fresh run, no contact; still or in free flight at g, else counted
    fresh_f = [f for f in range(1, n) if st[f] in ('fresh', 'fresh_move') and st[f - 1] in ('fresh', 'fresh_move') and valid[f] and valid[f - 1]]
    moving = []; judged = 0
    for f in fresh_f:
        vv = vin(f); wv = win(f)
        if dist_gun(f) <= spacing: continue
        judged += 1
        v_ = round(float(np.linalg.norm(vv)), 5); w_ = round(float(np.linalg.norm(wv)), 5)
        a_res = wa = None
        if f + 1 < n and valid[f + 1] and st[f + 1] in ('fresh', 'fresh_move', 'seated'):
            a_res = round(float(np.linalg.norm(C[f + 1] - 2 * C[f] + C[f - 1] - GV)), 5); wa = round(float(np.linalg.norm(win(f + 1) - wv)), 5)
        static = v_ <= FP and w_ <= FW; ball = a_res is not None and a_res <= FA and wa <= FW
        if not static and not ball: moving.append((f, v_))
    mg['fresh'] = {'frames': len(fresh_f), 'no_contact': judged, 'moving': len(moving), 'moving_frames': [f for f, _ in moving[:6]], 'moving_all': [f for f, _ in moving], 'max_step_cm_f': max([x for _, x in moving], default=0.0)}
    return mg


def _objects(base, spec, ph, GW, gid, F, n):
    import magtrack2
    FP, FA, FW = F['pos_cm_f'], F['acc_cm_f2'], F['rot_deg_f']
    J = json.load(open(base + '_objects.json')); hs = _hands(base + '.glb', spec['clip'])
    tree, spacing, _ = _geo(gid)
    ev = {'land': [], 'bounce_t': [], 'contact_t': []}
    if ph:
        for key in ('spent', 'fresh'):
            for e in (ph.get(key) if isinstance(ph.get(key), list) else []):
                if isinstance(e, dict) and e.get('land') is not None: ev['land'].append(e['land'])
        stt = ph.get('stats') if isinstance(ph.get('stats'), dict) else {}
        ev['bounce_t'] = [b.get('t') for b in (stt.get('bounces') or []) if isinstance(b, dict)]
        ev['contact_t'] = [c.get('t') for c in (stt.get('contacts') or []) if isinstance(c, dict)]
    carriers = {'gun': GW, 'world': [np.eye(4)] * n}; carriers.update(hs)
    res = {'objects': 0, 'flight_off_g': 0, 'flight_frames': [], 'worst_x_floor': 0.0, 'hand_frames': 0}
    for name, v in J['joints'].items():
        for sub, tr in (v.items() if isinstance(v, dict) else [(name, v)]):
            M = [None if (f >= len(tr) or tr[f] is None) else np.array(tr[f]).reshape(4, 4) for f in range(n)]
            ok = [m is not None and abs(np.linalg.det(m[:3, :3])) > 0.2 for m in M]
            P = [(GW[f] @ M[f])[:3, 3] * 100 if ok[f] else None for f in range(n)]
            Rw = [GW[f][:3, :3] @ M[f][:3, :3] if ok[f] else None for f in range(n)]
            res['objects'] += 1
            rows = []
            for f in range(1, n):
                if not (ok[f] and ok[f - 1]): continue
                best = None
                for cn, CW in carriers.items():
                    a = np.linalg.inv(CW[f]) @ (GW[f] @ M[f]); b = np.linalg.inv(CW[f - 1]) @ (GW[f - 1] @ M[f - 1])
                    dp = float(np.linalg.norm(a[:3, 3] - b[:3, 3])) * 100; dr = float(np.linalg.norm(_rotvec(b[:3, :3].T @ a[:3, :3])))
                    if best is None or dp < best[0]: best = (dp, dr)
                rec = {'f': f, 'rel_step': round(best[0], 5), 'rel_rot': round(best[1], 5)}
                if f + 1 < n and ok[f + 1]:
                    A = P[f + 1] - 2 * P[f] + P[f - 1] - GV; rec['a_res'] = round(float(np.linalg.norm(A)), 5)
                    wa = _rotvec(Rw[f + 1] @ Rw[f].T) - _rotvec(Rw[f] @ Rw[f - 1].T); rec['dw'] = round(float(np.linalg.norm(wa)), 5)
                rec['dist_gun'] = round(float(tree.query((M[f][:3, 3])[None, :])[0][0]) * 100, 3)
                rows.append(rec)
            # centre of mass: the body point that moves ballistically, fitted from the frames with constant spin (over 1 deg/f, change under 2e-4 deg/f)
            Eq = []; Rhs = []
            for f in range(1, n - 1):
                if not (ok[f - 1] and ok[f] and ok[f + 1]): continue
                w0 = _rotvec(Rw[f] @ Rw[f - 1].T); w1 = _rotvec(Rw[f + 1] @ Rw[f].T)
                R2 = Rw[f + 1] - 2 * Rw[f] + Rw[f - 1]      # the origin of a body up to 15 cm long may be off g by its spin: |R2| x 15 cm (a fast spin gave 1.04 and left no frame)
                if np.linalg.norm(w1 - w0) <= 2e-4 and np.linalg.norm(w0) > 1.0 and np.linalg.norm(P[f + 1] - 2 * P[f] + P[f - 1] - GV) < 1.0 + 15.0 * np.linalg.norm(R2, 2):
                    Eq.append(R2); Rhs.append(-(P[f + 1] - 2 * P[f] + P[f - 1] - GV))
            r_com = np.zeros(3)
            if len(Eq) >= 3:
                r_com = np.linalg.lstsq(np.vstack(Eq), np.concatenate(Rhs), rcond=1e-3)[0]      # spin about one fixed axis: the part of r along it is unobservable and must not be fitted (rcond=None put noise into it: 1100 cm)
                if np.linalg.norm(r_com) > 15.0: r_com = np.zeros(3)      # a shell is under 15 cm long
            for x in rows:
                f = x['f']
                if 'a_res' in x:
                    Ac = P[f + 1] - 2 * P[f] + P[f - 1] - GV + (Rw[f + 1] - 2 * Rw[f] + Rw[f - 1]) @ r_com; x['a_res_c'] = round(float(np.linalg.norm(Ac)), 5)
            for x in rows:
                if x['rel_step'] <= FP and x['rel_rot'] <= FW: continue                      # carried
                if x.get('a_res') is not None and min(x['a_res'], x.get('a_res_c', 9e9)) <= FA and x.get('dw', 1) <= FW: continue      # at g within the floors
                f = x['f']
                if any(abs(f - l) <= 1 for l in ev['land']) or any(t is not None and abs(f - t) <= 1.01 for t in ev['bounce_t'] + ev['contact_t']) or x['dist_gun'] <= spacing: continue
                a = min(x.get('a_res', 9e9), x.get('a_res_c', 9e9))
                if a <= NEAR_G and x.get('dw', 1) <= FW:
                    res['flight_off_g'] += 1; res['worst_x_floor'] = max(res['worst_x_floor'], a / FA)
                    if len(res['flight_frames']) < 6: res['flight_frames'].append([f'{name}/{sub}', f, round(a, 5)])
                else: res['hand_frames'] += 1
    res['worst_x_floor'] = round(res['worst_x_floor'], 2)
    return res
