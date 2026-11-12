"""Magazine track, round 3: magtrack2 plus the mode 'inertia'.

magtrack2's 'throw' slides the magazine down the well over a few frames from rest relative to the gun, then lets it
fly. That fits a gun that accelerates away from it (the upward snap of F09). A gun that is moving fast and stops
dead (a chop, a toss, a whip) is the other case: the released magazine simply keeps the velocity and spin it had on
the release frame, and the gun stops under it. 'inertia' does that: seated up to the release frame, free from the
next frame on with the world velocity of its centre and the angular velocity of the gun over the last frame, plus an
optional push along the well (the release spring). The gun's travel must lie along the well axis at the release, or
the magazine leaves through the side of the well: exit_check() measures that.

build(gid, clip, G, plan) as magtrack2.build; plan['mode'] == 'inertia' takes
  release   last frame the magazine is seated (the gun's stop frame)
  push      m/frame added along the well (default 0.01)
  tumble    extra spin, degrees per frame about the gun's x axis (default 3)
Other modes go to magtrack2.build unchanged.
exit_check(track, gid, clip) -> cm: largest sideways offset from the well axis while the magazine is within 10 cm of
its seat after the release (gun axes).
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import magtrack2
from magtrack2 import m4, rot_axis, log_rot, vanilla, G_ACC


def build(gid, clip, G, plan):
    if plan.get('mode') != 'inertia': return magtrack2.build(gid, clip, G, plan)
    v = vanilla(gid, clip); S = v['seat']; cen = np.r_[v['centre'], 1]; N = len(G); ex = np.array(plan.get('exit') or v['exit'], float); ex /= np.linalg.norm(ex)
    GW = [m4(t, q) for t, q in G]; r = int(plan['release']); appear = int(plan['appear']); seated = int(plan['seated']); floor = plan.get('floor', 0.08)
    loosen = sorted(plan.get('loosen', [])); pre = lambda f: max([0.0] + [d for lf, d in loosen if f >= lf])
    T = lambda d: np.block([[np.eye(3), np.asarray(d, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
    Wm = {f: GW[f] @ T(ex * pre(f)) @ S for f in range(0, r + 1)}
    a, b = Wm[r - 1], Wm[r]
    vel = (b @ cen)[:3] - (a @ cen)[:3] + GW[r][:3, :3] @ ex * plan.get('push', 0.01)
    om = log_rot(b[:3, :3] @ a[:3, :3].T) + GW[r][:3, :3] @ np.array([math.radians(plan.get('tumble', 3)), 0, 0])
    p = (b @ cen)[:3]; R = b[:3, :3]; gone = None; f = r
    while f < N - 1:
        f += 1; vel = vel + np.array([0, -G_ACC, 0]); p = p + vel; R = rot_axis(om, np.linalg.norm(om)) @ R
        if p[1] < floor: gone = f; break
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = p - R @ cen[:3]; Wm[f] = M
    gone = gone or N
    appear = min(max(appear, gone if gone < N else appear), seated - 6)
    fresh = GW[seated] @ S; out = []
    for f in range(N):
        if f < min(gone, appear) and f in Wm:
            M = np.linalg.inv(GW[f]) @ Wm[f]; sc = 1.0; state = ('seated' if pre(f) == 0 else 'loose') if f <= r else 'falling'
        elif appear <= f < seated:
            M = np.linalg.inv(GW[f]) @ fresh; sc = 1.0; state = 'fresh'
        elif f >= seated:
            M = S; sc = 1.0; state = 'seated'
        else:
            M = S; sc = 0.0; state = 'gone'
        out.append({'m': [round(float(x), 6) for x in M.ravel()], 's': sc, 'state': state})
    return {'gun': gid, 'clip': clip, 'plan': plan, 'release': r, 'free_from': r + 1, 'gone': gone, 'frames': out,
            'exit_gun_axes': [round(float(x), 3) for x in ex], 'enter_gun_axes': [round(float(x), 3) for x in v['enter']]}


def exit_check(track, gid, clip):
    """Sideways offset (cm) from the well axis while the leaving magazine is within 10 cm of the seat, gun axes; and
    the frames it took to get 10 cm out."""
    v = vanilla(gid, clip); cen = np.r_[v['centre'], 1]; S = v['seat']; ex = np.array(track['exit_gun_axes'], float); r = track['release']
    worst = 0.0; n = 0; back = 0.0
    for f in range(r + 1, len(track['frames'])):
        row = track['frames'][f]
        if row['state'] not in ('guided', 'falling', 'loose'): break
        dv = (np.array(row['m']).reshape(4, 4) @ cen)[:3] - (S @ cen)[:3]; al = float(dv @ ex); d = float(np.linalg.norm(dv))
        if d > 0.10:     # out of the well within this frame: the sideways part where the straight step crosses 10 cm
            if n == 0: worst = max(worst, float(np.linalg.norm(dv - al * ex)) / d * 0.10); back = min(back, al / d * 0.10)
            break
        worst = max(worst, float(np.linalg.norm(dv - al * ex))); back = min(back, al); n += 1
    return {'off_axis_cm': round(worst * 100, 2), 'frames_to_10cm': n, 'into_gun_cm': round(-back * 100, 2)}
