"""Round 2 builder: moves with a chosen speed profile instead of eased keys.

Round 1 put a few keys on a Catmull-Rom spline: every move started and stopped softly at 2 to 4 cm/frame. The
shipped clips the owner likes move 60 to 70 cm in 12 frames, peak near 10 cm/frame a little after the middle of the
move, lose 5 to 9 cm/frame in the last two frames (a hard stop), and stand still in between
(round2/measure/round1_vs_approved.txt). A timeline here is a list of such moves; it is sampled on every frame and
handed to author.py as one key per frame, so the spline no longer shapes the motion.

TL(ctx, lag, drag)
  .hold(f)                           stay until frame f
  .to(f, pos, rot, prof, antic, antic_f, rlag)   move from the current pose, arriving on frame f
        prof: speed profile, a Beta shape (a, b) or a name from PROFILES; the peak sits at (a-1)/(a+b-2) of the move
        antic: share of the move made backwards first (anticipation), over antic_f frames
        rlag: frames the rotation trails the translation (the muzzle arrives late: follow-through)
  .kick(f, move, rot, ...)           impact on top (author.py kick: fast attack, smooth return): rebound, overshoot
  .spec()                            author.py keys and shakes
drag: degrees the muzzle trails per cm/frame of grip speed across the barrel (the tip lags the hand), smoothed.

build(take id, gun, fn, params, out dir, clip) -> (spec, glb): as rlib.build, the motion function gets (ctx, TL).
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import author, rlib
from rlib import K, kick

PROFILES = {'snap': (2.2, 2.4), 'drive': (3.0, 1.8), 'slam': (3.6, 1.35), 'heavy': (2.7, 2.1), 'rise': (2.5, 1.9), 'ease': (2.0, 2.0), 'settle': (1.6, 2.6)}


def beta_cdf(a, b, n):
    """s(0..n) of a move of n frames: integral of u^(a-1) (1-u)^(b-1), 0 at frame 0, 1 at frame n."""
    u = (np.arange(n * 16) + 0.5) / (n * 16); v = u ** (a - 1) * (1 - u) ** (b - 1); c = np.r_[0, np.cumsum(v)]; c /= c[-1]
    return c[::16]


class TL:
    def __init__(self, ctx, lag=1.0, drag=1.0, drag_max=7.0):
        self.c = ctx; self.N = ctx.N; self.P = np.zeros((self.N, 3)); self.R = np.zeros((self.N, 3))
        self.f = 0; self.p = np.zeros(3); self.r = np.zeros(3); self.rf = 0; self.lag, self.drag, self.drag_max = lag, drag, drag_max
        self.kicks = []; self.marks = {}; self.nodrag = []   # nodrag: [(f0, f1)] frames without muzzle drag

    def _fill(self, arr, f0, f1, v0, v1, prof):
        f0, f1 = int(f0), int(min(f1, self.N - 1))
        if f1 <= f0: return
        a, b = PROFILES[prof] if isinstance(prof, str) else prof
        s = beta_cdf(a, b, f1 - f0)
        for k in range(f1 - f0 + 1): arr[f0 + k] = v0 + (v1 - v0) * s[k]
        arr[f1:] = v1

    def hold(self, f):
        self.f = max(self.f, int(f)); self.rf = max(self.rf, self.f)
        return self

    def to(self, f, pos, rot, prof='drive', antic=0.0, antic_f=3, rlag=None, rprof=None):
        f = int(f); pos = np.array(pos, float); rot = np.array(rot, float); rl = self.lag if rlag is None else rlag
        f0 = self.f; p0, r0 = self.p.copy(), self.r.copy()
        if antic and f - f0 > antic_f + 2:
            pa = p0 - (pos - p0) * antic; ra = r0 - (rot - r0) * antic
            self._fill(self.P, f0, f0 + antic_f, p0, pa, 'ease'); self._fill(self.R, f0, f0 + antic_f, r0, ra, 'ease')
            f0 += antic_f; p0, r0 = pa, ra
        self._fill(self.P, f0, f, p0, pos, prof)
        rl = int(round(rl))
        self._fill(self.R, max(f0 + rl // 2, self.rf if self.rf > f0 else f0), f + rl, r0, rot, rprof or prof)
        self.f = f; self.p = pos; self.r = rot; self.rf = f + rl
        return self

    def kick(self, f, move=(0, 0, 0), rot=(0, 0, 0), attack=0.6, release=3.0, lag=0.6):
        self.kicks.append(kick(int(f), move, rot, attack, release, lag)); return self

    def mark(self, name, f):
        self.marks[name] = int(f); return self

    def arrays(self):
        """Per-frame offsets with the muzzle drag added."""
        P, R = self.P.copy(), self.R.copy(); P[-1] = 0; R[-1] = 0
        V = np.gradient(P, axis=0) * 100                      # cm/frame, world axes (the gun points along -z in the idle)
        d = np.stack([-V[:, 1] * self.drag, V[:, 0] * self.drag, np.zeros(self.N)], 1)   # pitch against up-speed, yaw against side-speed
        d = np.clip(d, -self.drag_max, self.drag_max)
        k = np.array([0.15, 0.35, 0.35, 0.15]); ds = np.zeros_like(d)   # trails by about one frame
        for i in range(self.N):
            for j, w in enumerate(k):
                ds[i] += w * d[max(i - j, 0)]
        ds[0] = 0; ds[-1] = 0; ds[-2] *= 0.3
        for f0, f1 in self.nodrag: ds[max(f0, 0):min(f1 + 1, self.N)] = 0   # the well must stay on the magazine's axis there
        return P, R + ds

    def spec_keys(self):
        P, R = self.arrays()
        return [K(f, P[f], R[f]) for f in range(self.N)]


def build(tid, gun, fn, params, outdir, clip='empty_reload', left=None, body='pma'):
    ctx = rlib.Ctx(gun, left, body, clip, params)
    tl = TL(ctx, params.get('lag', 1.0), params.get('drag', 1.0)); m = fn(ctx, tl) or {}
    keys = tl.spec_keys(); keys[0] = K(0); keys[-1] = K(ctx.N - 1)
    spec = {'_draft': tid, '_gun': gun, '_left_gun': ctx.left, '_body': body, '_gun_clip': clip, '_timing': ctx.T, '_params': ctx.P, '_two_arm': False,
            '_marks': tl.marks, '_mag': m.get('mag', {}), '_round': 2,
            'src': ctx.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': ctx.N, 'keys': {'Right': keys, 'Left': [K(0)]},
            'shakes': {'Right': tl.kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6}
    for sh in spec['shakes']['Right']: sh['release'] = round(min(sh.get('release', 6.0), max((ctx.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    os.makedirs(outdir, exist_ok=True); out = f'{outdir}/{tid}.glb'; spec['out'] = out
    json.dump(spec, open(f'{outdir}/{tid}.json', 'w'), indent=1)
    author.build(spec, out)
    return spec, out, ctx
