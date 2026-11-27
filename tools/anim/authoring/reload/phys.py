"""Physics of loose gun parts and shells for the shell-family drafts (TUBE, BREAK-OPEN), driven by the gun's real
motion (the built arm clip after the spring-damper, sampled per frame). 30 fps, gravity 9.81 m/s2 (0.0109 m per
frame squared), no drag.

  slider(G, p, u, smax, ...)   a part or shell that slides along a guide fixed in the gun (pump fore-end, a shell in
                               a chamber): s'' = (g - a_p) . u_world, the gun's acceleration at the point as a
                               pseudo-force; stops at 0 and smax with restitution; lock and drive windows
  hinge(G, q, h, c, tmax, ...) the barrels of a break-open on their hinge pin: theta'' = (g - a_c) . t_world / r_eff
                               (a_c: acceleration of the barrel's centre of mass carried by the gun at the current
                               angle); latch: held shut until released, catches again when the barrels come home
  free(W0, W1, N, f)           rigid body from two world matrices (its velocity and spin at release), free fall
  Objects are returned per frame as world 4x4 matrices of the object's mesh (vertex -> world) or None (not drawn).
"""
import math
import numpy as np
from magtrack2 import m4, rot_axis, log_rot

G_ACC = 9.81 / 900.0
GV = np.array([0.0, -G_ACC, 0.0])
SUB = 8


def worlds(G): return [m4(t, q) for t, q in G]


def point_acc(GW, f, p):
    """Acceleration (m/frame^2, world) of the gun's material point p (gun axes) at frame f."""
    N = len(GW); a, b, c = GW[max(f - 1, 0)], GW[f], GW[min(f + 1, N - 1)]; P = np.r_[p, 1]
    return (a @ P)[:3] - 2 * (b @ P)[:3] + (c @ P)[:3]


def slider(GW, p, u, smax, s0=0.0, v0=0.0, rest=0.15, locks=(), drives=(), lock_home_after=None, min_open=0.0):
    """1-D motion along the gun-axes unit u (outward) of a body at gun point p + u s. locks: [(f0, f1, value)];
    drives: [(f0, f1, s0, s1)] kinematic (pushed by a contact); lock_home_after: from that frame the body locks at 0
    when it comes home (a pump in battery). Returns s per frame and the frame it first reached smax (or None)."""
    N = len(GW); s, v = s0, v0; S = []; hit = None; locked = False; u = np.asarray(u, float) / np.linalg.norm(u); opened = s0 > 0.01      # opened: been more than 1 cm open (the action latches home only after a stroke)
    for f in range(N):
        lk = next((x for x in locks if x[0] <= f <= x[1]), None); dr = next((x for x in drives if x[0] <= f <= x[1]), None)
        if locked or lk is not None:
            if lk is not None: s = lk[2]
            opened = opened or s > 0.01; v = 0.0; S.append(s); continue
        if dr is not None:
            f0, f1, a, b = dr; s_new = a + (b - a) * (f - f0) / max(f1 - f0, 1); v = s_new - s; s = s_new; S.append(s); continue
        uw = GW[f][:3, :3] @ u; acc = float((GV - point_acc(GW, f, np.asarray(p) + u * s)) @ uw)
        for k in range(SUB):
            v += acc / SUB; s += v / SUB
            if s < 0:
                s = 0.0; v = -v * rest if v < 0 else v
                if lock_home_after is not None and f >= lock_home_after and (hit is not None or opened): locked = True; v = 0.0; break   # in battery: the action locks on the hit
            if s > smax:
                s = smax; v = -v * rest if v > 0 else v
                if hit is None: hit = f
        opened = opened or s > 0.01
        if lock_home_after is not None and f >= lock_home_after and s <= 1e-4 and (hit is not None or opened): locked = True; s = 0.0
        S.append(s)
    return np.array(S), hit


def hinge_rot(h, q, th):
    """4x4 in gun axes: rotation by th (rad) about axis h through point q."""
    R = rot_axis(h, th); M = np.eye(4); M[:3, :3] = R; M[:3, 3] = np.asarray(q) - R @ np.asarray(q); return M


def hinge(GW, q, h, c, tmax, release, r_eff=None, rest=0.3, drives=(), relatch=True, spring_g=1.0):
    """Barrel angle per frame (rad). Held shut until `release`; then free under gravity and the gun's motion; bounces
    off the open stop (tmax) with restitution `rest`; catches shut again when it comes home (after being open more
    than 5 deg). drives: [(f0, f1, th0, th1)] kinematic (pressed open or shut against something). The cocking springs
    push the barrels open with spring_g times gravity at the barrels' centre: to shut them a move has to give them
    enough swing to reach the latch against that push (a flick or a sudden stop)."""
    N = len(GW); h = np.asarray(h, float) / np.linalg.norm(h); q = np.asarray(q, float); c = np.asarray(c, float)
    r = np.linalg.norm((c - q) - ((c - q) @ h) * h); r_eff = r_eff or 1.33 * r; th, w = 0.0, 0.0; out = []; was_open = False; shut = True; events = {}
    for f in range(N):
        if f < release: out.append(0.0); continue
        if f == release: shut = False; events['release'] = f
        dr = next((x for x in drives if x[0] <= f <= x[1]), None)
        if dr is not None:
            f0, f1, a, b = dr; tn = a + (b - a) * (f - f0) / max(f1 - f0, 1); w = tn - th; th = tn; out.append(th); shut = False
            if th > math.radians(5): was_open = True
            if f == f1 and tn <= 1e-6 and was_open: shut = True; w = 0.0; events['shut'] = f      # driven home: the latch catches
            if f == f1 and tn >= tmax - 1e-6: events.setdefault('open', f)
            continue
        if shut: out.append(0.0); continue
        M = hinge_rot(h, q, th); cc = (M @ np.r_[c, 1])[:3]; rad = cc - q; t = np.cross(h, rad); t /= (np.linalg.norm(t) or 1)
        a_c = point_acc(GW, f, cc); tw = GW[f][:3, :3] @ t; acc = float((GV - a_c) @ tw) / r_eff + spring_g * G_ACC / r_eff   # the cocking springs push the barrels open
        for k in range(SUB):
            w += acc / SUB; th += w / SUB
            if th > tmax:
                th = tmax; w = -w * rest if w > 0 else w; events.setdefault('open', f)
            if th > math.radians(5): was_open = True
            if th < 0:
                if relatch and was_open: th = 0.0; w = 0.0; shut = True; events['shut'] = f; break
                th = 0.0; w = max(w, 0.0)
        out.append(th)
    return np.array(out), events


def free_from(Wprev, W, N, f, floor=0.08, mesh_centre=None, extra_v=None):
    """Rigid body from frame f on: velocity and spin from the last two world matrices (centre and orientation),
    then gravity only. Returns {frame: world matrix} until it lands (centre under `floor`) and the landing frame."""
    cen = np.r_[mesh_centre if mesh_centre is not None else np.zeros(3), 1]
    p = (W @ cen)[:3]; v = p - (Wprev @ cen)[:3] + (extra_v if extra_v is not None else 0); om = log_rot(W[:3, :3] @ Wprev[:3, :3].T); R = W[:3, :3].copy()
    out = {}; g = f
    while g < N - 1:
        g += 1; v = v + GV; p = p + v; R = rot_axis(om, np.linalg.norm(om)) @ R
        if p[1] < floor: return out, g, v
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = p - R @ cen[:3]; out[g] = M
    return out, None, v
