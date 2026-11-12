"""Own magazine track of a one-handed rifle reload (round 2), after the Shingen tracks (tools/anim/magtrack.py).

The game's magazine animation follows a left hand that is not there: the magazine glides off and hangs in the air.
An own track replaces it: the magazine stays seated until the arm throws it, leaves along the well, then falls
freely (gravity, the velocity and spin it had at release, a little tumble), and is shrunk to nothing once it is
gone. The fresh magazine does not fly in: it stands still in the world where the draft takes it from (belt, thigh,
chest) and the gun is pushed onto it along the well; before that it has scale 0.

All matrices are 4x4 of the magazine MESH in gun axes (mesh vertex -> gun), so the game's joint value would be
track * bind. vanilla(gid, clip) gives the same for the game's own animation (the leaving joint, then the incoming).

build(gid, clip, G, plan) -> {'frames': [{'m': 16 floats row-major, 's': scale, 'state': name}], ...}
  G     per frame (translation, rotation xyzw) of the gun in the world (from the built arm clip)
  plan  release   frame the magazine starts to leave
        mode      'throw' (default): slides down the well over `slide` frames, accelerating, then flies free with the
                  world velocity it has; 'hook': it stays where it is in the world (caught on the rig) while the gun
                  is pulled off it over `slide` frames, then drops from rest
        loosen    [[frame, metres], ...] steps down the well before the release (a shake works it loose)
        slide, travel   frames and metres of the guided part (default 4 frames, 0.15 m)
        tumble    extra spin, degrees per frame about the gun's x axis (default 6)
        floor     height at which the old magazine is gone (default 0.08: it lies on the ground, then scale 0)
        appear    frame the fresh magazine exists at its station (scale 1); it is world-fixed from there
        seated    frame it is in (the gun's own seated frame)
checks(track, G, cam) -> numbers: free-fall acceleration error, frames on screen per state, fresh magazine drift.
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from wclip import TClip
import gungeo

G_ACC = 9.81 / 900.0     # m per frame^2 at 30 fps
_van = {}


def m4(t, q):
    x, y, z, w = q; M = np.eye(4)
    M[:3, :3] = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    M[:3, 3] = t
    return M


def rot_axis(axis, ang):
    a = np.asarray(axis, float); n = np.linalg.norm(a)
    if n < 1e-12 or abs(ang) < 1e-12: return np.eye(3)
    a = a / n; K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def log_rot(R):
    """Rotation vector of a rotation matrix."""
    c = np.clip((np.trace(R) - 1) / 2, -1, 1); th = math.acos(c)
    if th < 1e-9: return np.zeros(3)
    v = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(th))
    return v * th


def vanilla(gid, clip):
    """{'M': [4x4 per frame], 'seat': 4x4, 'centre': mesh centroid (mesh axes), 'exit': unit exit direction in gun
    axes, 'enter': unit direction the incoming magazine travels to the seat, 'dist': [m from the seat per frame]}"""
    if (gid, clip) in _van: return _van[(gid, clip)]
    gun = common.gun(gid); b = gungeo.wanim(gun, 'base1'); m = gungeo.wanim(gun, 'mag_std')
    bs = b if 'mag_slot' in Glb(b).names else gungeo.wanim(gun, 'rcv1')
    gb = Glb(bs); an = [a['name'] for a in gb.j['animations']]
    st, sq = TClip(gb, clip if clip in an else ('reload' if 'reload' in an else an[0])).world(0)[gb.names.index('mag_slot')]; S = m4(st, sq)
    sk = Glb(common.find('weapon_meshes', gun['mesh'] + '__mag_std_01.glb')); s = sk.j['skins'][0]
    jn = sk.names[s['joints'][0]]; ibm = np.asarray(sk.acc(s['inverseBindMatrices']), float).reshape(-1, 4, 4)[0].T
    V = gungeo.verts(common.find('weapon_meshes', gun['mesh'] + '__mag_std_01.glb')); cen = (V.min(0) + V.max(0)) / 2
    mg = Glb(m); c = TClip(mg, clip); W0 = c.wf(0)
    pair = [('magazine', jn if jn in mg.names else 'magazine')]
    if 'magazine_reload' in mg.names and 'mag_stdr' in mg.names and 'magazine_reload' in c.moved(): pair.append(('magazine_reload', 'mag_stdr'))
    Ms = []; dist = []
    for f in range(c.frames):
        W = c.wf(f); best = None
        for j, leaf in pair:
            d = float(np.linalg.norm(W[mg.names.index(j)][0] - W0[mg.names.index(j)][0]))
            if best is None or d < best[0]: best = (d, W[mg.names.index(leaf)])
        Ms.append(S @ m4(*best[1]) @ ibm); dist.append(best[0])
    seat = S @ m4(*W0[mg.names.index(pair[0][1])]) @ ibm
    ctr = lambda M: (M @ np.r_[cen, 1])[:3]
    dist = np.array(dist); out_f = next(f for f in range(len(dist)) if dist[f] > 0.005)
    cl = next(f for f in range(out_f, len(dist)) if dist[f] > 0.10)
    ex = ctr(Ms[cl]) - ctr(seat); ex /= np.linalg.norm(ex)
    seated = len(dist) - 1
    while seated > 0 and dist[seated - 1] <= 0.003: seated -= 1
    ne = seated
    while ne > 0 and dist[ne - 1] < 0.10: ne -= 1
    en = ctr(seat) - ctr(Ms[ne]); en /= np.linalg.norm(en)
    _van[(gid, clip)] = {'M': Ms, 'seat': seat, 'centre': cen, 'exit': ex, 'enter': en, 'dist': dist, 'out': out_f, 'seated': seated}
    return _van[(gid, clip)]


def build(gid, clip, G, plan):
    v = vanilla(gid, clip); S = v['seat']; cen = np.r_[v['centre'], 1]; N = len(G); ex = np.array(plan.get('exit') or v['exit'], float); ex /= np.linalg.norm(ex)
    GW = [m4(t, q) for t, q in G]; r = int(plan['release']); k = int(plan.get('slide', 4)); travel = plan.get('travel', 0.15)
    mode = plan.get('mode', 'throw'); appear = int(plan['appear']); seated = int(plan['seated']); floor = plan.get('floor', 0.08)
    loosen = sorted(plan.get('loosen', [])); out = []; T = lambda d: np.block([[np.eye(3), np.asarray(d, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
    pre = lambda f: max([0.0] + [d for lf, d in loosen if f >= lf])
    Wm = {}                                              # world matrices of the old magazine from the release on
    for f in range(0, r + 1): Wm[f] = GW[f] @ T(ex * pre(f)) @ S
    if mode == 'hook':
        for j in range(1, k + 1): Wm[r + j] = Wm[r].copy()   # it stays; the gun must be pulled off along the well by the arm
        vel = np.zeros(3); om = np.zeros(3)
    else:
        s0 = pre(r)
        for j in range(1, k + 1): Wm[r + j] = GW[min(r + j, N - 1)] @ T(ex * (s0 + (travel - s0) * (j / k) ** 2)) @ S
        a, b = Wm[r + k - 1], Wm[r + k]
        vel = (b @ cen)[:3] - (a @ cen)[:3]; om = log_rot(b[:3, :3] @ a[:3, :3].T)
    om = om + GW[min(r + k, N - 1)][:3, :3] @ np.array([math.radians(plan.get('tumble', 6)), 0, 0])
    p = (Wm[r + k] @ cen)[:3]; R = Wm[r + k][:3, :3]; gone = None; f = r + k
    while f < N - 1:
        f += 1; vel = vel + np.array([0, -G_ACC, 0]); p = p + vel; R = rot_axis(om, np.linalg.norm(om)) @ R
        if p[1] < floor: gone = f; break
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = p - R @ cen[:3]; Wm[f] = M
    gone = gone or N
    appear = min(max(appear, gone if gone < N else appear), seated - 6)   # one mesh in the preview: the old one lands first
    fresh = GW[seated] @ S                                # world-fixed fresh magazine: where the seat is at the seated frame
    for f in range(N):
        if f < min(gone, appear) and f in Wm:
            M = np.linalg.inv(GW[f]) @ Wm[f]; sc = 1.0; state = 'seated' if f < r and pre(f) == 0 else 'loose' if f < r else 'guided' if f <= r + k else 'falling'
        elif appear <= f < seated:
            M = np.linalg.inv(GW[f]) @ fresh; sc = 1.0; state = 'fresh'
        elif f >= seated:
            M = S; sc = 1.0; state = 'seated'
        else:
            M = S; sc = 0.0; state = 'gone'
        out.append({'m': [round(float(x), 6) for x in M.ravel()], 's': sc, 'state': state})
    return {'gun': gid, 'clip': clip, 'plan': plan, 'release': r, 'free_from': r + k + 1, 'gone': gone, 'frames': out,
            'exit_gun_axes': [round(float(x), 3) for x in ex], 'enter_gun_axes': [round(float(x), 3) for x in v['enter']]}


def world_centres(track, G, gid, clip):
    v = vanilla(gid, clip); cen = np.r_[v['centre'], 1]
    return [(m4(*G[f]) @ np.array(row['m']).reshape(4, 4) @ cen)[:3] for f, row in enumerate(track['frames'])]
