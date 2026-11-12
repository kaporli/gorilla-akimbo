"""Time-based sampling of glb anim clips (WolvenKit exports store reduced, non-uniform keys per track),
forward kinematics, local-space pose blending like the anim graph (lerp translation, slerp rotation)."""
import math
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import qmul, qinv, qrot, slerp

FPS = 30.0


class Rig:
    def __init__(self, g):
        self.g = g; self.names = g.names; self.idx = {n: i for i, n in enumerate(g.names)}
        self.par = {}
        for i, n in enumerate(g.j['nodes']):
            for c in n.get('children', []): self.par[c] = i
        self.n = len(g.names)
        self._tracks = {}

    def bind_local(self, i):
        nd = self.g.j['nodes'][i]
        return np.array(nd.get('translation', [0, 0, 0]), float), np.array(nd.get('rotation', [0, 0, 0, 1]), float)

    def sample(self, clip, t):
        """[(t, r)] local per node at time t (seconds), clamped to the clip."""
        L = [self.bind_local(i) for i in range(self.n)]
        L = [[x[0].copy(), x[1].copy()] for x in L]
        if clip not in self._tracks:  # decoded once per clip
            a = self.g.anim(clip)
            self._tracks[clip] = [(c['target']['node'], c['target']['path'], np.ravel(self.g.acc(a['samplers'][c['sampler']]['input'])),
                                   self.g.acc(a['samplers'][c['sampler']]['output'])) for c in a['channels']
                                  if c['target']['path'] in ('translation', 'rotation')]
        for i, p, T, V in self._tracks[clip]:
            if t <= T[0] or len(T) == 1: v = V[0]
            elif t >= T[-1]: v = V[-1]
            else:
                k = int(np.searchsorted(T, t, side='right') - 1); u = (t - T[k]) / (T[k + 1] - T[k])
                v = V[k] + (V[k + 1] - V[k]) * u if p == 'translation' else slerp(V[k] / np.linalg.norm(V[k]), V[k + 1] / np.linalg.norm(V[k + 1]), u)
            L[i][0 if p == 'translation' else 1] = np.array(v, float)
        for x in L: x[1] = x[1] / np.linalg.norm(x[1])
        return [(x[0], x[1]) for x in L]

    def duration(self, clip):
        a = self.g.anim(clip)
        return max(float(np.ravel(self.g.acc(s['input']))[-1]) for s in a['samplers'])

    def world(self, L):
        W = [None] * self.n

        def w(i):
            if W[i] is not None: return W[i]
            t, r = L[i]
            if i in self.par:
                pt, pr = w(self.par[i]); W[i] = (pt + qrot(pr, t), qmul(pr, r))
            else:
                W[i] = (t, r)
            return W[i]
        for i in range(self.n): w(i)
        return W


def blend(A, B, w):
    """Local-space blend of two poses (list of (t, r)), w = weight of B."""
    return [(a[0] + (b[0] - a[0]) * w, slerp(a[1], b[1], w)) for a, b in zip(A, B)]


def ease(kind, x):
    x = min(max(x, 0.0), 1.0)
    if kind == 'EaseInOut': return x * x * (3 - 2 * x)
    if kind == 'EaseOut': return 1 - (1 - x) ** 2
    if kind == 'EaseIn': return x * x
    return x


def pose_delta(rig, A, B, joints=None):
    """Max world position (m) and rotation (deg) difference between two local poses over the given joints."""
    WA, WB = rig.world(A), rig.world(B); dp = dr = 0.0; worst = None
    for i in range(rig.n):
        n = rig.names[i]
        if joints and n not in joints: continue
        d = np.linalg.norm(WA[i][0] - WB[i][0]); q = abs(float(np.dot(WA[i][1], WB[i][1])))
        a = math.degrees(2 * math.acos(min(1.0, q)))
        if d > dp: dp = d; worst = n
        dr = max(dr, a)
    return dp, dr, worst


def write_clips(rig, base_glb, clips, out):
    """clips: {name: [pose per frame at 30 fps]}; writes a glb (copy of base_glb) holding only these clips."""
    g = Glb(base_glb); anims = []
    for name, frames in clips.items():
        N = len(frames); tin = g.add_acc(np.arange(N) / FPS, 'SCALAR'); samplers, channels = [], []
        for i in range(rig.n):
            if rig.names[i] == 'Armature': continue
            for p, k, kind in (('translation', 0, 'VEC3'), ('rotation', 1, 'VEC4')):
                vals = np.array([fr[i][k] for fr in frames])
                if p == 'rotation':  # w >= 0 on the first key, no sign flips after (WolvenKit mis-encodes w < 0 tracks)
                    if vals[0][3] < 0: vals[0] = -vals[0]
                    for j in range(1, len(vals)):
                        if np.dot(vals[j], vals[j - 1]) < 0: vals[j] = -vals[j]
                if np.allclose(vals, vals[0], atol=1e-7):
                    samplers.append({'input': g.add_acc(np.array([0.0]), 'SCALAR'), 'output': g.add_acc(vals[:1], kind), 'interpolation': 'LINEAR'})
                else:
                    samplers.append({'input': tin, 'output': g.add_acc(vals, kind), 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': i, 'path': p}})
        anims.append({'name': name, 'samplers': samplers, 'channels': channels})
    g.j['animations'] = anims
    g.save(out)
    return out
