"""Re-aim: a striker delta (world rigid transform per integer frame around the hit) on top of an arm clip.
Delta: the transform. RArm: a clip reader with the delta applied to the striking gun, as the rewritten clip will have it.
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
import mag_geom as g
from mag_geom import m4, quat
from scipy.interpolate import PchipInterpolator
from scipy.spatial.transform import Rotation as Rot


class Delta:
    """world delta of the striking gun (and hand) per frame: x -> R(f) (x - pivot) + pivot + t(f).
    t: PCHIP through tkeys [[f, [x, y, z] m], ...]; R: rotation vector (deg, world) PCHIP through rkeys.
    Identity outside each key range."""
    def __init__(self, tkeys=None, rkeys=None, pivot=(0, 0, 0)):
        self.tk = tkeys or []; self.rk = rkeys or []; self.pivot = np.asarray(pivot, float)
        self._t = self._mk(self.tk); self._r = self._mk(self.rk)

    @staticmethod
    def _mk(keys):
        if not keys: return None
        fs = [k[0] for k in keys]; vs = np.array([k[1] for k in keys], float)
        return (fs[0], fs[-1], PchipInterpolator(fs, vs, axis=0))

    def tr(self, f):
        if self._t is None: return np.zeros(3)
        a, b, p = self._t
        return np.zeros(3) if f <= a or f >= b else p(f)

    def rv(self, f):
        if self._r is None: return np.zeros(3)
        a, b, p = self._r
        return np.zeros(3) if f <= a or f >= b else p(f)

    def at(self, f):
        M = np.eye(4)
        R = Rot.from_rotvec(np.radians(self.rv(f))).as_matrix()
        M[:3, :3] = R; M[:3, 3] = self.pivot - R @ self.pivot + self.tr(f)
        return M

    def to_json(self): return dict(tkeys=self.tk, rkeys=self.rk, pivot=self.pivot.tolist())

    @classmethod
    def from_json(cls, d): return cls(d.get('tkeys'), d.get('rkeys'), d.get('pivot', (0, 0, 0)))


def load_delta(path):
    """A delta file: the Delta fields, or an opt.py result holding them under 'delta'. 'none' or None: no delta."""
    if not path or path == 'none': return None
    d = json.load(open(path, encoding='utf-8'))
    return Delta.from_json(d.get('delta', d))


class RArm(g.Arm):
    """Arm with a Delta on the striker side, applied on integer frames and interpolated between them like the rewritten
    clip will be"""
    def __init__(self, path, st, delta=None):
        super().__init__(path); self.st = st; self.delta = delta; self.dc = {}

    def W(self, side, f):
        if side != self.st or self.delta is None: return super().W(side, f)
        f0 = int(np.floor(f)); a = f - f0
        def at(k):
            k = max(0, min(k, self.frames - 1))
            if k not in self.dc:
                M = self.delta.at(k) @ g.Arm.W(self, side, k)
                self.dc[k] = (M[:3, 3], quat(M[:3, :3]))
            return self.dc[k]
        (t0, r0), (t1, r1) = at(f0), at(f0 + 1)
        if np.dot(r0, r1) < 0: r1 = -r1
        return m4(t0 * (1 - a) + t1 * a, r0 * (1 - a) + r1 * a)


def arm_of(delta, st):
    """path -> RArm, for mag_flight.Case(arm_of=...)"""
    return lambda path: RArm(path, st, delta)


def striker(spec, key, pick):
    return 'Right' if spec[key][pick]['side'] == 'Left' else 'Left'
