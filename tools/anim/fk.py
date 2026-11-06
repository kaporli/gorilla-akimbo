"""Forward kinematics over glb anim clips (WolvenKit exports, glTF Y-up)."""
import numpy as np


def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return np.array([w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2,
                     w1*z2 + x1*y2 - y1*x2 + z1*w2, w1*w2 - x1*x2 - y1*y2 - z1*z2])


def qinv(q):
    return np.array([-q[0], -q[1], -q[2], q[3]]) / np.dot(q, q)


def qrot(q, v):
    return qmul(qmul(q, np.array([v[0], v[1], v[2], 0.0])), np.array([-q[0], -q[1], -q[2], q[3]]))[:3]


def slerp(a, b, t):
    d = np.dot(a, b)
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        r = a + t * (b - a)
        return r / np.linalg.norm(r)
    th = np.arccos(d)
    return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)


class Clip:
    """Local transforms per frame of one clip."""

    def __init__(self, g, name):
        self.g = g
        self.nodes = g.j['nodes']
        self.par = {}
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []):
                self.par[c] = i
        self.tr = g.tracks(name)
        self.frames = max(len(t) for t, _ in self.tr.values())

    def local(self, i, f):
        n = self.nodes[i]
        nm = n.get('name')
        t = np.array(n.get('translation', [0, 0, 0]), float)
        r = np.array(n.get('rotation', [0, 0, 0, 1]), float)
        if (nm, 'translation') in self.tr:
            v = self.tr[(nm, 'translation')][1]; t = v[min(f, len(v) - 1)]
        if (nm, 'rotation') in self.tr:
            v = self.tr[(nm, 'rotation')][1]; r = v[min(f, len(v) - 1)]
        return t, r / np.linalg.norm(r)

    def world(self, f, local=None):
        """{node: (t, r)} in model space. local: optional {node: (t, r)} overrides."""
        W = {}

        def w(i):
            if i in W:
                return W[i]
            t, r = local[i] if local and i in local else self.local(i, f)
            if i in self.par:
                pt, pr = w(self.par[i])
                W[i] = (pt + qrot(pr, t), qmul(pr, r))
            else:
                W[i] = (t, r)
            return W[i]
        for i in range(len(self.nodes)):
            w(i)
        return W
