"""Magazine path of a gun's own reload animation, in gun axes (x = right, y = up, z = back toward the stock).

usage: magpath.py <base1 or rcv1 anims glb with mag_slot> <mag_std anims glb> [--clips reload,empty_reload] [--every 2]
module: track(base glb, mag glb, clip) -> dict with per-frame positions and the events:
  slot      seated position of the magazine in gun axes
  joints    per magazine joint (magazine, magazine_reload): per frame distance from its seat (cm), hidden flag
            (a jump of more than 30 cm in one frame = swapped away, not a motion)
  out       frame the magazine in the gun starts to leave (more than 0.5 cm from the seat), which joint
  clear     frame it is 12 cm from the seat (out of the magazine well)
  far       frame it is 30 cm away (carried off)
  in_start  frame the incoming magazine is within 30 cm, which joint
  seated    first frame from which the incoming magazine stays within 0.3 cm of the seat
  exit_dir  unit direction of the first 12 cm of the exit, gun axes
  exit_speed_cm_f  mean speed over the first 12 cm
  frames    clip length in 30 fps frames
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import qmul, qrot, qinv
from wclip import TClip, FPS


def slot_of(base_glb, clip=None):
    g = Glb(base_glb); an = [a['name'] for a in g.j['animations']]
    c = TClip(g, clip if clip in an else ('reload' if 'reload' in an else an[0]))
    return c, g.names.index('mag_slot')


def track(base_glb, mag_glb, clip):
    bc, si = slot_of(base_glb, clip)
    mg = Glb(mag_glb); mc = TClip(mg, clip)
    n = mc.frames; out = {'frames': n, 'joints': {}}
    js = [j for j in ('magazine', 'magazine_reload') if j in mg.names]
    pos = {j: [] for j in js}; rot = {j: [] for j in js}
    for f in range(n):
        st, sq = bc.wf(f)[si]; W = mc.wf(f)
        for j in js:
            t, q = W[mg.names.index(j)]
            pos[j].append(st + qrot(sq, t)); rot[j].append(qmul(sq, q))
    st0, sq0 = bc.wf(0)[si]
    out['slot'] = [round(float(x), 4) for x in st0]
    seat = {}
    for j in js:
        P = np.array(pos[j])
        # the seat: where the joint sits at frame 0 or at the last frame, whichever is near the slot
        cand = [P[0], P[-1]]; s = min(cand, key=lambda p: np.linalg.norm(p - st0)); seat[j] = s
        d = np.linalg.norm(P - s, axis=1) * 100
        step = np.r_[0, np.linalg.norm(np.diff(P, axis=0), axis=1) * 100]
        out['joints'][j] = {'dist_cm': [round(float(x), 1) for x in d], 'step_cm': [round(float(x), 1) for x in step],
                            'pos': P.round(4).tolist(), 'start_cm': round(float(d[0]), 1), 'end_cm': round(float(d[-1]), 1)}
    # leaving magazine: the joint seated at frame 0; incoming: the joint seated at the end
    leave = min(js, key=lambda j: out['joints'][j]['start_cm']); come = min(js, key=lambda j: out['joints'][j]['end_cm'])
    dl = np.array(out['joints'][leave]['dist_cm']); sl = np.array(out['joints'][leave]['step_cm'])
    # a teleport (swap) is a step over 30 cm; the real exit starts at the first frame over 0.5 cm that is not a teleport
    k = 0
    while k < n and (dl[k] <= 0.5): k += 1
    if k < n and sl[k] > 30:  # the seated joint is swapped away: the other joint is the one that leaves
        other = [j for j in js if j != leave]
        if other:
            leave = other[0]; dl = np.array(out['joints'][leave]['dist_cm']); k = 0
            while k < n and dl[k] <= 0.5: k += 1
    out['leave_joint'] = leave; out['come_joint'] = come
    out['out'] = int(k) if k < n else None
    def first(arr, thr, k0):
        for i in range(k0, n):
            if arr[i] >= thr: return i
        return None
    if out['out'] is not None:
        out['clear'] = first(dl, 12, k); out['far'] = first(dl, 30, k)
        P = np.array(out['joints'][leave]['pos']); kc = out['clear'] or min(k + 4, n - 1)
        v = P[kc] - P[max(k - 1, 0)]; out['exit_dir'] = [round(float(x), 2) for x in v / max(np.linalg.norm(v), 1e-9)]
        out['exit_speed_cm_f'] = round(float(np.linalg.norm(v)) * 100 / max(kc - k + 1, 1), 1)
    dc = np.array(out['joints'][come]['dist_cm'])
    seated = n - 1
    while seated > 0 and dc[seated - 1] <= 0.3: seated -= 1
    out['seated'] = int(seated)
    ins = seated
    while ins > 0 and dc[ins - 1] < 30 and np.array(out['joints'][come]['step_cm'])[ins] < 30: ins -= 1
    out['in_start'] = int(ins)
    P = np.array(out['joints'][come]['pos']); v = P[seated] - P[max(seated - 4, ins)]
    out['in_dir'] = [round(float(x), 2) for x in v / max(np.linalg.norm(v), 1e-9)]
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]; clips = (common.opt(argv, '--clips') or 'reload,empty_reload').split(','); ev = int(common.opt(argv, '--every') or 2)
    for clip in clips:
        try: t = track(argv[0], argv[1], clip)
        except Exception as e:
            print(clip, 'failed:', e); continue
        print(f'== {os.path.basename(argv[1])} {clip}: {t["frames"]} frames, slot {t["slot"]}, leaves {t["leave_joint"]} f{t["out"]}, clear f{t.get("clear")}, far f{t.get("far")}, '
              f'exit dir {t.get("exit_dir")} {t.get("exit_speed_cm_f")} cm/f, incoming {t["come_joint"]} from f{t["in_start"]}, seated f{t["seated"]}, in dir {t["in_dir"]}')
        for j, d in t['joints'].items():
            print('  ', j, ' '.join(f'{f}:{d["dist_cm"][f]:.0f}' for f in range(0, t['frames'], ev)))
