"""Real inertia for one-handed reload drafts (BRIEF-NEW-TECHNIQUES.md): the hand is driven along a target path and
the gun follows it as a mass on a spring-damper (underdamped), position and rotation separately, so big moves
overshoot and settle, stops rebound, rotation lags translation and the muzzle trails.

spring(P, R, take) -> (P, R)   per-frame offsets (m, deg) of the target timeline -> simulated offsets
report(P, R, Pt, Rt, stops)    overshoot (cm, deg) at each stop, settle frames, rotation lag (frames)
Parameters per take: natural frequency w (rad per frame) and damping ratio z; rotation softer than translation.
The last END frames are blended onto the target (the idle), so the clip ends exactly in the idle.
"""
import numpy as np

PARAM = {'A': {'wp': 1.5, 'zp': 0.6, 'wr': 1.0, 'zr': 0.62}, 'B': {'wp': 1.3, 'zp': 0.58, 'wr': 0.95, 'zr': 0.52}}
END = 8
SUB = 10


def _sim(T, w, z):
    T = np.asarray(T, float); N = len(T); x = T[0].copy(); v = np.zeros_like(x); out = np.zeros_like(T); out[0] = x; dt = 1.0 / SUB
    for f in range(1, N):
        for k in range(SUB):
            t = T[f - 1] + (T[f] - T[f - 1]) * (k + 1) / SUB
            a = w * w * (t - x) - 2 * z * w * v; v = v + a * dt; x = x + v * dt
        out[f] = x
    return out


def spring(P, R, take):
    p = PARAM[take]; Ps = _sim(P, p['wp'], p['zp']); Rs = _sim(R, p['wr'], p['zr']); N = len(P)
    for k in range(END):
        f = N - END + k; w = (k + 1) / END; w = w * w * (3 - 2 * w)
        Ps[f] = Ps[f] * (1 - w) + P[f] * w; Rs[f] = Rs[f] * (1 - w) + R[f] * w
    Ps[0] = P[0]; Rs[0] = R[0]
    return Ps, Rs


def report(P, R, Pt, Rt, stops):
    """stops: [(frame, direction of the move (unit, world offsets))]. Overshoot: largest excursion past the target
    along the move direction in the 8 frames after the stop (cm), and the largest angle past the target (deg);
    settle: frames until within 0.3 cm and 1 deg; rotation lag: shift (frames) that best aligns the rotation speed
    with the translation speed over the clip."""
    out = []
    for f, d in stops:
        f = int(f); seg = range(f, min(f + 9, len(P)))
        ov = max(float((P[g] - Pt[g]) @ d) for g in seg) * 100   # past the target, frame by frame
        dr = Rt[f] - Rt[max(f - 6, 0)]; nr = float(np.linalg.norm(dr)); ovr = max(float((R[g] - Rt[g]) @ (dr / nr)) for g in seg) if nr > 2 else 0.0
        st = next((g - f for g in range(f, len(P)) if np.linalg.norm(P[g] - Pt[g]) < 0.003 and np.max(np.abs(R[g] - Rt[g])) < 1.0), len(P) - f)
        out.append({'frame': f, 'overshoot_cm': round(max(ov, 0.0), 2), 'overshoot_deg': round(max(ovr, 0.0), 1), 'settle_f': int(st)})
    vp = np.r_[0, np.linalg.norm(np.diff(P, axis=0), axis=1)]; vr = np.r_[0, np.linalg.norm(np.diff(R, axis=0), axis=1)]
    best = max(range(0, 6), key=lambda s: float(np.dot(vp[:len(vp) - s], vr[s:])))
    return {'stops': out, 'rotation_lag_f': best,
            'max_overshoot_cm': round(max([s['overshoot_cm'] for s in out] or [0]), 2), 'max_overshoot_deg': round(max([s['overshoot_deg'] for s in out] or [0]), 1)}
