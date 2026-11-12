"""Weapon anim clips sampled by time. WolvenKit exports of weapon sets keep reduced keys (a track may have 12 keys
over 4 s), so fk.Clip (which indexes keys) is wrong for them. TClip interpolates each track at a time in seconds.

TClip(glb, clip): .duration (s), .frames (30 fps frame count, last frame included), .local(i, t), .world(t)
world(t) -> {node index: (translation, rotation xyzw)} in the model space of the glb.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import qmul, qrot

FPS = 30.0


class TClip:
    def __init__(self, g, name):
        self.g = g if isinstance(g, Glb) else Glb(g)
        self.nodes = self.g.j['nodes']; self.names = self.g.names
        self.par = {}
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []): self.par[c] = i
        self.tr = {}
        for (nm, path), (t, v) in self.g.tracks(name).items():
            t = np.asarray(t, float).ravel(); v = np.array(v, float)
            if path == 'rotation':
                for k in range(1, len(v)):
                    if np.dot(v[k], v[k - 1]) < 0: v[k] = -v[k]
            self.tr[(nm, path)] = (t, v)
        self.duration = max(float(t[-1]) for t, _ in self.tr.values())
        self.frames = int(round(self.duration * FPS)) + 1

    def _at(self, key, t):
        ts, v = self.tr[key]
        if t <= ts[0]: return v[0]
        if t >= ts[-1]: return v[-1]
        k = int(np.searchsorted(ts, t, side='right')) - 1
        w = (t - ts[k]) / (ts[k + 1] - ts[k])
        return v[k] * (1 - w) + v[k + 1] * w

    def local(self, i, t):
        n = self.nodes[i]; nm = n.get('name')
        tr = self._at((nm, 'translation'), t) if (nm, 'translation') in self.tr else np.array(n.get('translation', [0, 0, 0]), float)
        r = self._at((nm, 'rotation'), t) if (nm, 'rotation') in self.tr else np.array(n.get('rotation', [0, 0, 0, 1]), float)
        return tr, r / np.linalg.norm(r)

    def world(self, t):
        W = {}

        def w(i):
            if i in W: return W[i]
            tr, r = self.local(i, t)
            if i in self.par:
                pt, pr = w(self.par[i]); W[i] = (pt + qrot(pr, tr), qmul(pr, r))
            else:
                W[i] = (tr, r)
            return W[i]
        for i in range(len(self.nodes)): w(i)
        return W

    def wf(self, f):
        """World pose at 30 fps frame f (clamped)."""
        return self.world(min(max(f, 0), self.frames - 1) / FPS)

    def moved(self, eps=1e-4):
        """Names of joints whose local transform changes over the clip."""
        out = []
        for (nm, path), (t, v) in self.tr.items():
            if np.abs(v - v[0]).max() > eps and nm not in out: out.append(nm)
        return out
