"""Lowered start and end for a reload clip (plift3, 2026-11-24).

The game plays a reload clip as an absolute pose in either stance (0.2 s blend in from the idle the state machine was in, 0 s or 0.3 s blend out).
A clip that starts and ends in the raised idle therefore pops the gun up when the player reloads from the lowered stance. A lowered variant
starts and ends in the lowered idle (friendly_idlepose frame 0 of the gun's lowered set) and keeps the shipped motion in between.

overlay  the arm joints (the ones that differ between the lowered pose and the raised idle) of the reloading side: new = clip composed with an offset
         that is the lowered pose at frame 0 and fades out by frame `a` (minimum jerk, from frame `h`), and again from frame `b` to `e` toward the
         lowered pose at the last frame. Local joint space, rotation by slerp: the frames between a and b are the shipped clip. The other
         arm is the lowered pose on every frame (in game it follows its own machine).
rest     the lowered pose as an `idle` clip of the rest glb (R6 and the end transition are measured against it).

gun_pose the lowered gun pose of one side as the author's key (offset in metres, euler pitch yaw roll in degrees) relative to the rest idle. smgprod starts and ends the
         gun path there (the author's IK then keeps the reach cap, the post-seat keys are shifted by it) and the overlay only trades the author's arm solution for the
         lowered set's own arm at the first and last frames.

usage as module: lowover.rest(rest_glb, low_glb, out_glb), lowover.overlay(clip_glb, clip_name, low_glb, side, N, h, a, b, e)
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
from glb import Glb
from fk import Clip, qmul, qinv, slerp

LOW_CLIP = 'friendly_idlepose'


def mj(t):
    t = min(1.0, max(0.0, t)); return t * t * t * (t * (6 * t - 15) + 10)


def w_start(f, h, a):
    """1 until frame h, minimum jerk down to 0 at frame a."""
    return 1.0 if f <= h else (0.0 if f >= a else 1.0 - mj((f - h) / (a - h)))


def w_end(f, b, e):
    """0 until frame b, minimum jerk up to 1 at frame e."""
    return 0.0 if f <= b else (1.0 if f >= e else mj((f - b) / (e - b)))


def euler_xyz(q):
    """pitch, yaw, roll (deg) with q = qx(pitch) qy(yaw) qz(roll), the author's qeuler order (gun axes)."""
    x, y, z, w = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    return [math.degrees(math.atan2(-R[1, 2], R[2, 2])), math.degrees(math.asin(max(-1, min(1, R[0, 2])))), math.degrees(math.atan2(-R[0, 1], R[0, 0]))]


def gun_pose(rest_glb, low_glb, side):
    """(offset, euler) of Weapon<side> in the lowered pose against the rest idle, in the author's key convention."""
    r = Glb(rest_glb); l = Glb(low_glb); Wr = Clip(r, 'idle').world(0); Wl = Clip(l, LOW_CLIP).world(0); i = r.names.index('Weapon' + side)
    (g0, q0), (gl, ql) = Wr[i], Wl[i]; rel = qmul(qinv(q0), ql)
    return np.array(gl - g0), np.array(euler_xyz(rel))


def arm_joints(rest_glb, low_glb, tol_cm=0.01, tol_deg=0.05):
    """Names of the joints whose local transform differs between the raised idle and the lowered pose (arms and their IK helpers)."""
    r = Glb(rest_glb); l = Glb(low_glb); cr = Clip(r, 'idle'); cl = Clip(l, LOW_CLIP); out = []
    for i, nm in enumerate(r.names):
        t0, q0 = cr.local(i, 0); t1, q1 = cl.local(i, 0); d = qmul(qinv(q0), q1)
        if np.linalg.norm(t0 - t1) * 100 > tol_cm or math.degrees(2 * math.atan2(np.linalg.norm(d[:3]), abs(d[3]))) > tol_deg or nm in ('LeftShoulder', 'RightShoulder'): out.append(nm)   # the shoulders: the author's reach cap turns them
    return out


def rest(rest_glb, low_glb, out_glb):
    """The rest glb with its `idle` clip replaced by the lowered pose (friendly_idlepose frame 0, every joint)."""
    g = Glb(rest_glb); l = Glb(low_glb); cl = Clip(l, LOW_CLIP); a = g.anim('idle'); assert g.names == l.names
    for ch in a['channels']:
        i = ch['target']['node']; t, q = cl.local(i, 0); s = a['samplers'][ch['sampler']]; n = len(g.acc(s['input']))
        v = np.tile(t if ch['target']['path'] == 'translation' else q, (n, 1))
        s['output'] = g.add_acc(v, 'VEC3' if ch['target']['path'] == 'translation' else 'VEC4')
    g.save(out_glb); return out_glb


def overlay(clip_glb, clip, low_glb, side, N, h, a, b, e, joints):
    """Rewrites the clip glb in place. side: 'Right' or 'Left' (the reloading arm); joints: arm_joints() names."""
    g = Glb(clip_glb); l = Glb(low_glb); cl = Clip(l, LOW_CLIP); cc = Clip(g, clip); an = g.anim(clip); ix = {n: i for i, n in enumerate(g.names)}
    assert g.names == l.names
    tin = g.add_acc(np.arange(N) / 30.0, 'SCALAR'); done = 0
    for nm in joints:
        i = ix[nm]; own = nm.startswith(side) or f'{side}Arm' in nm or f'_{side.lower()}_' in nm
        tl, ql = cl.local(i, 0)
        T = []; Q = []
        if own:
            t0, q0 = cc.local(i, 0); t1, q1 = cc.local(i, N - 1); d0 = qmul(qinv(q0), ql); d1 = qmul(qinv(q1), ql)
            for f in range(N):
                t, q = cc.local(i, f); ws, we = w_start(f, h, a), w_end(f, b, e)
                q = qmul(q, slerp(np.array([0, 0, 0, 1.0]), d0, ws)); q = qmul(q, slerp(np.array([0, 0, 0, 1.0]), d1, we))
                t = t + ws * (tl - t0) + we * (tl - t1); T.append(t); Q.append(q / np.linalg.norm(q))
        else:
            T = [tl] * N; Q = [ql] * N
        Q = np.array(Q)
        for k in range(1, N):
            if np.dot(Q[k], Q[k - 1]) < 0: Q[k] = -Q[k]
        for ch in an['channels']:
            if ch['target']['node'] != i: continue
            v = np.array(T) if ch['target']['path'] == 'translation' else Q
            an['samplers'][ch['sampler']] = {'input': tin, 'output': g.add_acc(v, 'VEC3' if ch['target']['path'] == 'translation' else 'VEC4'), 'interpolation': 'LINEAR'}; done += 1
    g.save(clip_glb); return done
