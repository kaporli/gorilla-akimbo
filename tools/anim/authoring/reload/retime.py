"""Hidden-window retime of a reload clip (owner rule 2026-11-25): only the off-screen window hide_start .. hide_end is stretched or cut; every frame up to hide_start (the visible start: raise, discard)
and every frame from hide_end on (the visible end: rise back) is frame-identical, the end part shifted by delta frames.

frame map (old -> new, float):  f <= hs: f;  hs < f < he: hs + (f - hs) * (he - hs + delta) / (he - hs);  f >= he: f + delta.
Used by discard.build_clip(retime=dict(hs=, he=, delta=)) and stance.py / discard.py --retime. delta > 0 stretches, < 0 cuts; the window keeps at least 2 frames.

What is re-timed (spec json and track): spec frames and keys (frames outside the window copy the old key, frames inside are interpolated from the old keys), bumps, _marks, _keys, the track (release, free_from, gone,
frames resampled: state and matrix of the nearest old frame, which is exact outside the window), the per-frame lists of length N (_gun_map, _part_frames, _judge arrays) resampled, the frame lists of _gun_anchors and _mag.
Fields it does not know raise RuntimeError (nothing is written silently wrong): in-hand slot offsets (_slot_cm_max) and spins (_spins) inside the window are refused.
"""
import numpy as np


class Map:
    def __init__(self, hs, he, delta):
        if he - hs + delta < 2: raise RuntimeError(f'hidden window {hs}..{he} cannot take delta {delta}: it would keep fewer than 2 frames')
        self.hs, self.he, self.delta = int(hs), int(he), int(delta); self.k = (self.he - self.hs + self.delta) / (self.he - self.hs)

    def fwd(self, f):
        if f <= self.hs: return float(f)
        if f >= self.he: return float(f + self.delta)
        return self.hs + (f - self.hs) * self.k

    def inv(self, g):
        if g <= self.hs: return float(g)
        if g >= self.he + self.delta: return float(g - self.delta)
        return self.hs + (g - self.hs) / self.k

    def fi(self, f): return int(round(self.fwd(f)))


def _lerp_key(a, b, w):
    out = [None, [float(x + (y - x) * w) for x, y in zip(a[1], b[1])], [float(x + (y - x) * w) for x, y in zip(a[2], b[2])]] + list(a[3:])
    return out


def keys(kl, m, N):
    """New key list of one side: a key at every new frame that has one in the old list (old frames outside the window copy the key; inside, linear in position and euler angles between the neighbours)."""
    old = {int(k[0]): k for k in kl}; fr = sorted(old); out = []
    for g in range(N + m.delta):
        t = m.inv(g); f0 = int(np.floor(t + 1e-9))
        if abs(t - round(t)) < 1e-9 and int(round(t)) in old:
            k = list(old[int(round(t))]); k[0] = g; out.append(k); continue
        lo = max([f for f in fr if f <= t] or [fr[0]]); hi = min([f for f in fr if f >= t] or [fr[-1]])
        if lo == hi: k = list(old[lo]); k[0] = g; out.append(k); continue
        k = _lerp_key(old[lo], old[hi], (t - lo) / (hi - lo)); k[0] = g; out.append(k)
    return out


def resample(lst, m, N):
    """A per-frame list of length N (or N + 1) onto the new frames: the entry of the nearest old frame."""
    n = len(lst); return [lst[min(n - 1, max(0, int(round(m.inv(g)))))] for g in range(n + m.delta)]


def spec(sp, m):
    """New spec dict (a copy); raises on a field it cannot re-time."""
    import copy
    s = copy.deepcopy(sp); N = s['frames']
    if s.get('_slot_cm_max') or s.get('_spins'): raise RuntimeError('in-hand slot offsets or spins: not re-timed')
    s['frames'] = N + m.delta
    s['keys'] = {side: keys(kl, m, N) for side, kl in s['keys'].items()}
    if 'bumps' in s:
        for side, bl in s['bumps'].items():
            for b in bl: b['f'] = [m.fi(f) for f in b['f']]
    if '_marks' in s: s['_marks'] = {k: (m.fi(v) if isinstance(v, (int, float)) else v) for k, v in s['_marks'].items()}
    if '_keys' in s: s['_keys'] = s['_keys'] + m.delta
    for k in ('_gun_map', '_part_frames'):
        if k in s: s[k] = resample(s[k], m, N)
    if '_gun_anchors' in s: s['_gun_anchors'] = [[m.fi(a), m.fi(b)] for a, b in s['_gun_anchors']]
    if '_timing' in s and isinstance(s['_timing'], dict):
        t = s['_timing']
        for k in ('frames', 'out', 'clear', 'far', 'near', 'seated'):
            if isinstance(t.get(k), (int, float)): t[k] = m.fi(t[k]) if k != 'frames' else t[k] + m.delta
    return s


def track(tr, m):
    t = dict(tr); n = len(tr['frames'])
    for k in ('release', 'free_from', 'gone'):
        if isinstance(t.get(k), (int, float)): t[k] = min(n + m.delta, m.fi(t[k]))
    t['frames'] = resample(tr['frames'], m, n)
    return t
