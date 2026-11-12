"""Checks a top-magazine arm clip's end against the idle pose, and against its version before the end-pose fix.

usage: verify.py <fixed glb> [<orig glb>] [--body pma|pwa] [--idle <glb>]
prints: frames before F0 identical to the original (max local difference), hand and gun world deviation over the
whole clip, last frame against the idle (worst joint, world, and the worst per hand), elbow shift at the last frame,
the largest frame-to-frame acceleration of the elbows from F0 - 2 on (original and fixed) and the speed at the end.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import Clip

HANDS = ('WeaponRight', 'WeaponLeft', 'RightHand', 'LeftHand')


def ang(q1, q2):
    d = abs(float(np.dot(q1 / np.linalg.norm(q1), q2 / np.linalg.norm(q2)))); return np.degrees(2 * np.arccos(min(1, d)))


def side_of(name):
    n = name.lower()
    return 'right' if 'right' in n else 'left' if 'left' in n else 'body'


def end_pose(fixed, idle):
    """Last frame against idlepose_shoulder, world: {'right'|'left'|'body': (cm, deg, worst joint)} and the frame count."""
    B = Glb(fixed); I = Glb(idle)
    cb = Clip(B, B.j['animations'][0]['name']); ci = Clip(I, 'idlepose_shoulder')
    ii = {n: i for i, n in enumerate(I.names)}
    WB = cb.world(cb.frames - 1); WI = ci.world(0)
    out = {s: (0.0, 0.0, '') for s in ('right', 'left', 'body')}
    for i, n in enumerate(B.names):
        if n not in ii: continue
        d = np.linalg.norm(WB[i][0] - WI[ii[n]][0]) * 100; a = ang(WB[i][1], WI[ii[n]][1])
        s = side_of(n)
        if d + a / 10 > out[s][0] + out[s][1] / 10: out[s] = (d, a, n)
    return out, cb.frames


def against_original(orig, fixed, f0):
    """Frames before f0: max local difference (cm or deg). Whole clip: hand and gun world deviation (cm, deg).
    Elbows: (shift at the end cm, max acceleration original, fixed cm/f^2, speed at the last frame cm/f)."""
    A = Glb(orig); B = Glb(fixed)
    ca, cb = Clip(A, A.j['animations'][0]['name']), Clip(B, B.j['animations'][0]['name'])
    ix = {n: i for i, n in enumerate(A.names)}
    N = ca.frames
    if cb.frames != N:
        return {'pre': float('inf'), 'dev': {}, 'elbow': {}, 'frames': (N, cb.frames)}
    pre = 0.0
    for f in range(f0):
        for i in range(len(A.names)):
            ta, qa = ca.local(i, f); tb, qb = cb.local(i, f)
            pre = max(pre, np.linalg.norm(ta - tb) * 100, ang(qa, qb))
    WA = [ca.world(f) for f in range(N)]; WB = [cb.world(f) for f in range(N)]
    dev = {j: (max(np.linalg.norm(WA[f][ix[j]][0] - WB[f][ix[j]][0]) * 100 for f in range(N)),
               max(ang(WA[f][ix[j]][1], WB[f][ix[j]][1]) for f in range(N))) for j in HANDS}
    el = {}
    for S in ('Right', 'Left'):
        e = ix[f'{S}ForeArm']
        PA = np.array([WA[f][e][0] for f in range(N)]); PB = np.array([WB[f][e][0] for f in range(N)])
        el[S] = (np.linalg.norm(PB[-1] - PA[-1]) * 100, np.abs(np.diff(PA[f0 - 2:], 2, axis=0)).max() * 100,
                 np.abs(np.diff(PB[f0 - 2:], 2, axis=0)).max() * 100, np.linalg.norm(PB[-1] - PB[-2]) * 100)
    return {'pre': pre, 'dev': dev, 'elbow': el, 'frames': (N, N)}


def report(fixed, orig, idle, f0):
    """The lines verify.py prints (one string, '|' separated in batch logs)."""
    end, n = end_pose(fixed, idle)
    lines = []
    if orig:
        r = against_original(orig, fixed, f0)
        lines.append('pre f0-%d max diff %.4f (cm|deg)' % (f0 - 1, r['pre']))
        lines.append('hand/gun max dev  ' + '  '.join('%s %.2fcm/%.2fd' % (k, *v) for k, v in r['dev'].items()))
    worst = max(end.values(), key=lambda v: v[0] + v[1] / 10)
    lines.append('last frame vs idle worst: %s %.3f cm %.3f deg' % (worst[2], worst[0], worst[1]))
    lines.append('last frame vs idle per hand: ' + '  '.join('%s %.3f cm %.3f deg' % (s, end[s][0], end[s][1]) for s in ('right', 'left', 'body')))
    if orig:
        for S, (sh, aa, ab, ve) in r['elbow'].items():
            lines.append('%s elbow: moved %.1f cm at end; max accel f%d-%d orig %.2f fixed %.2f cm/f^2; last-frame speed %.3f cm/f'
                         % (S, sh, f0 - 2, n - 1, aa, ab, ve))
    return lines


if __name__ == '__main__':
    from fix_endpose import window
    argv = sys.argv[1:]
    body = common.opt(argv, '--body'); idle = common.opt(argv, '--idle')
    fixed = argv[0]; orig = argv[1] if len(argv) > 1 else None
    body = body or os.path.basename(os.path.dirname(os.path.abspath(fixed)))
    print('\n'.join(report(fixed, orig, idle or common.need(common.idle_glb(body)), window(fixed)[0])))
