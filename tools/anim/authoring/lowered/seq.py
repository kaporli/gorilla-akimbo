"""Preview sequence and numeric checks of a lowered stance pair. Each hand plays its own clip set (the graph is per
hand: the right hand's state machine drives everything but the left arm, the left one the left arm), any two guns,
either body. The sequence blends the states with the graph's durations and easing.

usage: seq.py <right glb> <left glb> <right gun> <left gun> <body> <out prefix> [--no-glb]
  guns: manifest id or mesh stem
writes <out>_seq.glb (clip "seq"), <out>_seq.json (frame labels), <out>_checks.txt
"""
import os, sys, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from lpose import Rig, Glb, blend, ease, pose_delta, write_clips, qrot, FPS
from guns import verts

EYE = np.array([0, 1.605, 0.0]); HH = math.radians(34); HV = math.atan(math.tan(HH) * 0.75)
RAISED = ('raised (idlepose_shoulder)', 'trigger down: cut to raised (0 s)')   # the game's own pose, not these clips
_rigs = {}


def _rig(path):
    if path not in _rigs: _rigs[path] = Rig(Glb(path))
    return _rigs[path]


def _place(tq, V):
    """Points V (n, 3) moved by a joint's world (t, q)."""
    t, (x, y, z, w) = tq
    R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                  [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    return t + V @ R.T


def frames_of(rig, clip):
    n = int(round(rig.duration(clip) * FPS)) + 1
    return [rig.sample(clip, i / FPS) for i in range(n)]


def run(RGLB, LGLB, RG, LG, BODY, OUT=None, write=True):
    """Builds the sequence, writes the files (with OUT) and returns the numbers:
    {'seam': {name: (cm, deg, worst joint)}, 'labels': {label: {'apart', 'eye', 'on'}}, 'apart', 'eye', 'raised_eye',
     'apart_own', 'eye_own' (frames that are not the game's raised pose), 'frames', 'lines'}"""
    RG, LG = common.gun(RG)['mesh'], common.gun(LG)['mesh']
    r = _rig(RGLB); l = _rig(LGLB); b = _rig(common.need(common.idle_glb(BODY)))
    assert r.names == b.names == l.names
    SH = b.sample('idlepose_shoulder', 0)
    LEFT = [i for i, n in enumerate(r.names) if 'Left' in n or 'left' in n]

    def merge(pr, pl):
        p = list(pr)
        for i in LEFT: p[i] = pl[i]
        return p

    FRr, FRl = frames_of(r, 'friendly_idlepose'), frames_of(l, 'friendly_idlepose_l')
    SAr, SAl = frames_of(r, 'safe_action'), frames_of(l, 'safe_action_l')
    EQr, EQl = frames_of(r, 'equip_safe'), frames_of(l, 'equip_safe_l')
    FR = [merge(a, c) for a, c in zip(FRr, FRl)]
    SA = [merge(a, c) for a, c in zip(SAr, SAl)]
    EQ = [merge(a, c) for a, c in zip(EQr, EQl)]
    loopN = len(FR) - 1
    fr_t = [0]

    def friendly():
        p = FR[fr_t[0] % loopN]; fr_t[0] += 1; return p

    seq, lab = [], []

    def add(p, t): seq.append(p); lab.append(t)

    def trans(src_fn, dst_fn, dur, kind, t):
        n = max(1, int(round(dur * FPS)))
        for k in range(1, n + 1):
            add(blend(src_fn(), dst_fn(), ease(kind, k / n)), t)

    for _ in range(15): add(SH, RAISED[0])
    trans(lambda: SH, friendly, 0.3, 'EaseInOut', 'blend in 0.3 s')
    for _ in range(45): add(friendly(), 'lowered idle')
    trans(friendly, lambda: SA[0], 0.1, 'EaseInOut', 'safe_action')
    for p in SA[1:]: add(p, 'safe_action (fire pressed in safe zone)')
    fr_t[0] = 0
    trans(lambda: SA[-1], friendly, 0.1, 'EaseInOut', 'lowered idle')
    for _ in range(20): add(friendly(), 'lowered idle')
    for _ in range(20): add(SH, RAISED[1])
    trans(lambda: SH, friendly, 0.5, 'EaseInOut', 'trigger up: blend back 0.5 s')
    for _ in range(20): add(friendly(), 'lowered idle')
    last = friendly()
    trans(lambda: last, lambda: SH, 0.2, 'EaseOut', 'safe off: blend out 0.2 s')
    for _ in range(20): add(SH, RAISED[0])
    A_END = len(seq)
    for p in EQ: add(p, 'equip_safe (draw)')
    fr_t[0] = 0
    trans(lambda: EQ[-1], friendly, 0.3, 'EaseInOut', 'Ready/Safe blend 0.3 s')
    for _ in range(25): add(friendly(), 'lowered idle')
    if OUT and write:
        write_clips(r, RGLB, {'seq': seq}, OUT + '_seq.glb')
        json.dump({'labels': lab, 'a_end': A_END, 'right_gun': RG, 'left_gun': LG, 'body': BODY}, open(OUT + '_seq.json', 'w'))

    res = {'seam': {}, 'labels': {}, 'frames': len(seq)}
    lines = [f'{BODY}  right {RG} ({RGLB.split("/")[-1]})  left {LG} ({LGLB.split("/")[-1]})']
    for nm, A, B in (('friendly loop seam f0 vs fN', FR[0], FR[-1]), ('equip_safe end vs friendly f0', EQ[-1], FR[0]),
                     ('safe_action start vs friendly f0', SA[0], FR[0]), ('safe_action end vs friendly f0', SA[-1], FR[0])):
        dp, dr, w = pose_delta(r, A, B)
        res['seam'][nm] = (dp * 100, dr, w)
        lines.append(f'{nm}: max {dp*100:.3f} cm, {dr:.3f} deg (worst {w})')
    non_arm = [n for n in r.names if not any(k in n for k in ('Arm', 'Hand', 'Weapon', 'arm_', 'Shoulder', 'Thumb', 'Index', 'Middle', 'Ring', 'Pinky'))]
    dp2, dr2, w2 = pose_delta(r, FR[0], SH, set(non_arm))
    res['seam']['friendly f0 vs idlepose_shoulder, joints outside the arms'] = (dp2 * 100, dr2, w2)
    lines.append(f'friendly f0 vs idlepose_shoulder, joints outside the arms: max {dp2*100:.3f} cm, {dr2:.3f} deg (worst {w2})')
    VR, VL = verts(RG), verts(LG)
    iR, iL = r.idx['WeaponRight'], r.idx['WeaponLeft']
    eye_min, gg_min, cover = [], [], []
    for k, p in enumerate(seq):
        W = r.world(p)
        PR = _place(W[iR], VR[::4]); PL = _place(W[iL], VL[::4])
        eye_min.append(min(np.linalg.norm(PR - EYE, axis=1).min(), np.linalg.norm(PL - EYE, axis=1).min()))
        gg_min.append(np.sqrt(((PR[::2, None, :] - PL[None, ::2, :]) ** 2).sum(-1)).min())
        P = np.concatenate([PR, PL]) - EYE; fwd = -P[:, 2]; ok = fwd > 0.02
        on = (np.abs(np.arctan2(P[ok, 0], fwd[ok])) < HH) & (np.abs(np.arctan2(P[ok, 1], fwd[ok])) < HV)
        cover.append(on.sum() / len(P))
    for t in dict.fromkeys(lab):
        ks = [k for k in range(len(lab)) if lab[k] == t]
        res['labels'][t] = {'apart': min(gg_min[k] for k in ks) * 100, 'eye': min(eye_min[k] for k in ks) * 100,
                            'on': float(np.mean([cover[k] for k in ks]))}
        lines.append(f'{t}: guns apart min {min(gg_min[k] for k in ks)*100:.1f} cm, eye min {min(eye_min[k] for k in ks)*100:.1f} cm, '
                     f'gun vertices on screen mean {np.mean([cover[k] for k in ks]):.2f}')
    own = [k for k in range(len(lab)) if lab[k] not in RAISED]
    res.update(apart=min(gg_min) * 100, eye=min(eye_min) * 100, raised_eye=min(eye_min[k] for k in range(15)) * 100,
               raised_apart=min(gg_min[k] for k in range(15)) * 100,
               apart_own=min(gg_min[k] for k in own) * 100, eye_own=min(eye_min[k] for k in own) * 100)
    lines.append(f'OVERALL guns apart min {min(gg_min)*100:.1f} cm, eye min {min(eye_min)*100:.1f} cm '
                 f'(raised pose: eye {res["raised_eye"]:.1f} cm)')
    res['lines'] = lines
    if OUT:
        open(OUT + '_checks.txt', 'w').write('\n'.join(lines) + '\n')
    return res


if __name__ == '__main__':
    a = sys.argv[1:7]
    res = run(*a, write='--no-glb' not in sys.argv)
    print('\n'.join(res['lines'][-1:])); print('seq frames', res['frames'])
