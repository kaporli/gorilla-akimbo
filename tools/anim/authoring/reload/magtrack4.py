"""Magazine track, SMG/shotgun FRONT round 3: magtrack3's 'inertia' plus 'strip' and 'slide', and the lead of the
fresh magazine as a parameter.

modes (plan['mode']):
  inertia  seated up to `release`, then free with the world velocity of its centre over the last frame and the
           gun's spin (magtrack3). A gun at rest that then jerks away leaves it falling from rest.
  strip    caught on a rig edge on `release`: the magazine stays where it is in the world while the gun is pulled off
           along the well; free from rest once the gun's seat is `clear` metres (default 0.13) away from it.
  slide    the gun holds still; from `release` the magazine slides down the well under gravity (the share of g along
           the well), from rest relative to the gun; free once `clear` metres (default 0.12) out, with the velocity it
           has then.
After it is free: gravity 9.81 m/s2 at 30 fps, no drag, `tumble` deg/frame extra spin, gone below `floor` (0.08 m).
The fresh magazine exists from `appear` (at the latest `lead` frames before the seat, default 6) at the gun's seat
pose of the seated frame (world-fixed).
Output as magtrack2/3: frames [{'m', 's', 'state'}], release, free_from, gone, exit_gun_axes, enter_gun_axes.
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
from magtrack2 import m4, rot_axis, log_rot, vanilla, G_ACC


def build(gid, clip, G, plan):
    v = vanilla(gid, clip); S = v['seat']; cen = np.r_[v['centre'], 1]; N = len(G); ex = np.array(plan.get('exit') or v['exit'], float); ex /= np.linalg.norm(ex)
    GW = [m4(t, q) for t, q in G]; r = int(plan['release']); mode = plan.get('mode', 'inertia'); seated = int(plan['seated']); floor = plan.get('floor', 0.08)
    lead = int(plan.get('lead', 6)); loosen = sorted(plan.get('loosen', [])); pre = lambda f: max([0.0] + [d for lf, d in loosen if f >= lf])
    T = lambda d: np.block([[np.eye(3), np.asarray(d, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
    Wm = {f: GW[f] @ T(ex * pre(f)) @ S for f in range(0, r + 1)}; state = {f: ('seated' if pre(f) == 0 else 'loose') for f in range(r + 1)}
    f = r
    if mode == 'inertia':
        a, b = Wm[r - 1], Wm[r]; vel = (b @ cen)[:3] - (a @ cen)[:3]; om = log_rot(b[:3, :3] @ a[:3, :3].T)
    elif mode == 'strip':
        clear = plan.get('clear', 0.13); c0 = (Wm[r] @ cen)[:3]
        while f < N - 1:
            seat_c = (GW[f + 1] @ S @ cen)[:3]
            if float(np.linalg.norm(seat_c - c0)) >= clear: break
            f += 1; Wm[f] = Wm[r].copy(); state[f] = 'guided'
        vel = np.zeros(3); om = np.zeros(3)
    elif mode == 'slide':
        clear = plan.get('clear', 0.12); s = 0.0; u = 0.0; prev = (Wm[r] @ cen)[:3]
        while f < N - 1 and s < clear:
            f += 1; g_along = G_ACC * max(0.0, float(-(GW[f][:3, :3] @ ex)[1])); u += g_along; s += u
            Wm[f] = GW[f] @ T(ex * (pre(r) + s)) @ S; state[f] = 'guided'
        vel = (Wm[f] @ cen)[:3] - (Wm[f - 1] @ cen)[:3]; om = log_rot(Wm[f][:3, :3] @ Wm[f - 1][:3, :3].T)
    else: raise ValueError(mode)
    free_from = f + 1
    om = om + GW[f][:3, :3] @ np.array([math.radians(plan.get('tumble', 2)), 0, 0])
    p = (Wm[f] @ cen)[:3]; R = Wm[f][:3, :3]; gone = None
    while f < N - 1:
        f += 1; vel = vel + np.array([0, -G_ACC, 0]); p = p + vel; R = rot_axis(om, np.linalg.norm(om)) @ R
        if p[1] < floor: gone = f; break
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = p - R @ cen[:3]; Wm[f] = M; state[f] = 'falling'
    gone = gone or N
    appear = min(max(int(plan['appear']), gone if gone < N else int(plan['appear'])), seated - lead)
    fresh = GW[seated] @ S; out = []
    for f in range(N):
        if f < min(gone, appear) and f in Wm:
            M = np.linalg.inv(GW[f]) @ Wm[f]; sc = 1.0; st = state[f]
        elif appear <= f < seated:
            M = np.linalg.inv(GW[f]) @ fresh; sc = 1.0; st = 'fresh'
        elif f >= seated:
            M = S; sc = 1.0; st = 'seated'
        else:
            M = S; sc = 0.0; st = 'gone'
        out.append({'m': [round(float(x), 6) for x in M.ravel()], 's': sc, 'state': st})
    return {'gun': gid, 'clip': clip, 'plan': plan, 'release': r, 'free_from': free_from, 'gone': gone, 'frames': out,
            'exit_gun_axes': [round(float(x), 3) for x in ex], 'enter_gun_axes': [round(float(x), 3) for x in v['enter']]}
