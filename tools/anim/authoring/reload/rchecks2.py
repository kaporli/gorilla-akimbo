"""Round 2 checks: the arm checks of rchecks.py, the magazine checks redone with the mesh's bind matrix, and the
motion numbers of motionstats.py.

Round 1 placed the magazine point cloud with the joint's world matrix and forgot the inverse bind (a half turn about
the joint), so its "magazine on screen" counts were unreliable. Here the cloud is mesh vertex -> gun -> world.

check(spec, track=None) -> dict. track: own magazine track (magtrack2.build); None = the game's own animation.
  mag_detached      frames the old magazine is out of the gun before the fresh one is seated
  mag_ballistic     of those, frames in which its world acceleration is gravity within 25 % (free fall)
  mag_hang          of those, frames in which it is in the air and not in free fall (glides, hangs, slows down)
  mag_seen_fpp      detached frames on screen in first person; fresh_seen_fpp the same for the incoming magazine
  fresh_drift_cm    how far the fresh magazine moves in the world before it is seated (own track: 0, it stands still)
  fresh_off_axis_cm largest sideways offset from the well axis in the last 10 cm of the insertion (it would pass
                    through the receiver)
  guided_off_axis_cm the same for the old magazine while it is still in the well
  release           frame it leaves, release_grip_acc: change of the grip's velocity at that frame (cm/frame^2): the
                    jerk that throws it
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import Clip
import rchecks, magtrack2, motionstats, gungeo


def gun_world(spec):
    g = Glb(spec['out']); c = Clip(g, spec['clip']); i = g.names.index('WeaponRight')
    return [c.world(f)[i] for f in range(spec['frames'])]


def check(spec, track=None, arm=True):
    if isinstance(spec, str): spec = json.load(open(spec))
    gid, clip = spec['_gun'], spec['_gun_clip']; N = spec['frames']; T = spec['_timing']
    out = rchecks.check(spec) if arm else {'draft': spec['_draft'], 'fails': []}
    for k in ('mag_float', 'mag_float_frames', 'mag_insert_seen', 'mag_exit'): out.pop(k, None)
    out['fails'] = [f for f in out['fails'] if 'magazine' not in f and 'insert' not in f]
    G = gun_world(spec); v = magtrack2.vanilla(gid, clip)
    V = gungeo.verts(common.find('weapon_meshes', common.gun(gid)['mesh'] + '__mag_std_01.glb'))[::5]; V1 = np.c_[V, np.ones(len(V))]
    seat = v['seat']; cen = np.r_[v['centre'], 1]
    if track:
        Ms = [np.array(r['m']).reshape(4, 4) for r in track['frames']]; sc = [r['s'] for r in track['frames']]; st = [r['state'] for r in track['frames']]
    else:
        Ms = [v['M'][min(f, len(v['M']) - 1)] for f in range(N)]; sc = [1.0] * N
        d = v['dist'][:N]
        st = ['seated' if d[f] < 0.005 else ('incoming' if f >= T['near'] else 'away') for f in range(N)]
    C = np.array([(rchecks.place(G[f], (Ms[f] @ cen)[None, :3]))[0] for f in range(N)])
    on = []
    for f in range(N):
        if sc[f] < 0.5: on.append(False); continue
        P = rchecks.place(G[f], (V1 @ Ms[f].T)[:, :3]); on.append(bool(rchecks.screen(P)[2].any()))
    A = np.zeros((N, 3)); A[1:-1] = C[2:] - 2 * C[1:-1] + C[:-2]
    det = [f for f in range(N) if sc[f] > 0.5 and st[f] not in ('seated', 'fresh', 'incoming', 'loose')]
    g = magtrack2.G_ACC; ball = [f for f in det if 0 < f < N - 1 and abs(A[f][1] + g) < 0.25 * g and np.linalg.norm(A[f][[0, 2]]) < 0.25 * g and st[f] != 'guided']
    guided = [f for f in det if st[f] == 'guided']
    ff = track['free_from'] if track else -1
    hang = [f for f in det if f not in ball and f not in guided and C[f][1] > 0.15 and f != ff and f != (track['gone'] - 1 if track else -1)]
    fresh = [f for f in range(N) if st[f] in ('fresh', 'incoming') and sc[f] > 0.5]
    out['mag_detached'] = len(det); out['mag_ballistic'] = len(ball); out['mag_hang'] = len(hang); out['mag_hang_frames'] = hang[:40]
    out['mag_seen_fpp'] = int(sum(1 for f in det if on[f])); out['mag_seen_fpp_frames'] = [f for f in det if on[f]][:30]
    out['fresh_seen_fpp'] = int(sum(1 for f in fresh if on[f])); out['fresh_frames'] = [fresh[0], fresh[-1]] if fresh else None
    out['fresh_drift_cm'] = round(float(max(np.linalg.norm(C[f] - C[fresh[-1]]) for f in fresh)) * 100, 1) if fresh else 0.0
    def off_axis(frames, axis):
        worst = 0.0
        for f in frames:
            dv = (Ms[f] @ cen)[:3] - (seat @ cen)[:3]; al = float(dv @ axis)
            if abs(al) < 0.10: worst = max(worst, float(np.linalg.norm(dv - al * axis)))
        return round(worst * 100, 1)
    out['fresh_off_axis_cm'] = off_axis(fresh, v['enter']); out['guided_off_axis_cm'] = off_axis(guided, v['exit'])
    if track:
        r = track['release']; gp = np.array([t for t, q in G]); a = (gp[min(r + 1, N - 1)] - 2 * gp[r] + gp[r - 1]) * 100 if 0 < r < N - 1 else np.zeros(3)
        out['release'] = r; out['release_grip_acc'] = round(float(np.linalg.norm(a)), 1); out['mag_gone'] = track['gone']
        fall = [f for f in det if st[f] == 'falling']; out['mag_fall_frames'] = [fall[0], fall[-1]] if fall else None
        out['mag_apex_cm'] = round(float(max(C[f][1] for f in fall) - C[fall[0]][1]) * 100, 1) if fall else 0
    if out['mag_hang'] > 0: out['fails'].append(f"magazine hangs in the air {out['mag_hang']} f")
    if out['fresh_seen_fpp'] > 0: out['fails'].append(f"fresh magazine on screen {out['fresh_seen_fpp']} f")
    if out['fresh_off_axis_cm'] > 1.5: out['fails'].append(f"insertion {out['fresh_off_axis_cm']} cm off the well axis")
    if track and out['guided_off_axis_cm'] > 1.5: out['fails'].append(f"exit {out['guided_off_axis_cm']} cm off the well axis")
    s = motionstats.stats(spec['out'], spec['clip'], 'Right', 0.55)
    out['motion'] = {k: s[k] for k in ('peak_speed', 'p90_speed', 'mean_move_speed', 'peak_at', 'attack_frames', 'stop', 'peak_acc', 'jerk_events', 'hold_share', 'whip', 'peak_muzzle_speed', 'big_moves')}
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]; tr = common.opt(argv, '--track')
    o = check(argv[0], json.load(open(tr)) if tr else None, arm='--mag-only' not in argv)
    for k, x in o.items(): print(f'{k:20s} {x}')
