"""One-handed reload drafts: shared builder.

A draft is a function motion(ctx) -> dict that fills an author.py spec from a context:
  ctx.T        timing table of the gun's own reload clip (timing.table): frames, out, clear, far, near, seated, handle
  ctx.N        clip length = the gun's own reload clip length
  ctx.g0       world position of the right gun (grip) in the raised idle; ctx.gl0 the left gun's
  ctx.P        parameters (the draft's own defaults updated by the caller): every number of a draft is a parameter
  ctx.off(world point)   offset key value that puts the grip on a world point
The motion returns {'Right': keys, 'Left': keys or None, 'shakes': {...}, 'spin': [...], plus any author.py key}.
Keys are [frame, [dx, dy, dz], [pitch, yaw, roll]] offsets from the raised idle (author.py conventions).
spin: [[frame, degrees], ...] turns the gun in the hand about spin_axis through spin_pivot (gun axes), on top of
the arm motion (the hand keeps its path, the gun rotates in it).

build(draft id, gun, motion, params, out dir, clip='empty_reload', left=None, body='pma') -> (spec, glb)
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import Clip, qmul, qinv, qrot
import author, rest, timing


class Ctx:
    def __init__(self, gun, left, body, clip, params):
        self.gun, self.left, self.body, self.clip = gun, left or gun, body, clip
        self.T = timing.table(gun, clip); self.N = self.T['frames']
        self.rest, self.rest_info = rest.make(gun, self.left, body)
        g = Glb(self.rest); W = Clip(g, 'idle').world(0); self.W0 = {n: W[i] for i, n in enumerate(g.names)}
        self.g0 = np.array(self.W0['WeaponRight'][0]); self.gl0 = np.array(self.W0['WeaponLeft'][0])
        self.q0 = self.W0['WeaponRight'][1]; self.ql0 = self.W0['WeaponLeft'][1]
        self.P = dict(params); self._nat = {}

    def off(self, p, side='Right'):
        return [round(float(x), 4) for x in (np.array(p, float) - (self.g0 if side == 'Right' else self.gl0))]

    def joint(self, n):
        return np.array(self.W0[n][0])

    def wrist(self, pos, rot, side='Right'):
        """(hand twist about the forearm, wrist swing, reach) of one pose: offset pos, angles rot."""
        sp = {'src': self.rest, 'template': 'idle', 'frames': 1, 'keys': {side: [[0, list(pos), list(rot)]]}, 'reach': [0.93, 0.985]}
        if getattr(author, 'spec', None) is None or author.spec.get('src') != self.rest or author.N != 1: author.setup(sp)
        author.spec['keys'] = sp['keys']; author.solve(0)
        tw, sw = author.DIAG[(side, 0)]; return tw, sw, author.ELB[(side, 0)][1]

    def natural(self, pos, rot, span=40, step=10, keep=0.004, twist_w=0.35):
        """Angles near rot that bend the wrist least with the grip at offset pos (coordinate search). keep: cost per
        degree of leaving rot, so a designed look is kept where the wrist allows it. The forearm takes most of a
        twist, so twist counts twist_w."""
        rot = [float(x) for x in rot]; key = (tuple(np.round(pos, 3)), tuple(rot), span, step)
        if key in self._nat: return self._nat[key]
        def cost(r):
            tw, sw, _ = self.wrist(pos, r)
            return sw * sw + twist_w * tw * tw + keep * sum((a - b) ** 2 for a, b in zip(r, rot)) * 10
        best = list(rot); cb = cost(best); st = step
        while st >= 2.5:
            moved = True
            while moved:
                moved = False
                for i in range(3):
                    for d in (-st, st):
                        r = list(best); r[i] += d
                        if abs(r[i] - rot[i]) > span: continue
                        cc = cost(r)
                        if cc < cb - 1e-6: best, cb, moved = r, cc, True
            st /= 2
        out = [round(x, 1) for x in best]; self._nat[key] = out
        return out


def K(f, pos=(0, 0, 0), rot=(0, 0, 0), **tan):
    k = [int(round(f)), [round(float(x), 4) for x in pos], [round(float(x), 2) for x in rot]]
    if tan: k.append(tan)
    return k


def kick(f, move=(0, 0, 0), rot=(0, 0, 0), attack=0.7, release=4.5, lag=0.6):
    return {'type': 'kick', 'f': f, 'move': list(move), 'rot': list(rot), 'attack': attack, 'release': release, 'lag': lag}


def clean(keys, N):
    """Sorts keys, drops duplicates of a frame (the later wins), pins the first and last frame to the idle."""
    by = {}
    for k in keys: by[k[0]] = k
    ks = [by[f] for f in sorted(by) if 0 < f < N - 1]
    return [K(0)] + ks + [K(N - 1)]


def _qaxis(ax, deg):
    h = math.radians(deg) / 2; v = np.zeros(3); v['xyz'.index(ax)] = 1
    return np.array([*(v * math.sin(h)), math.cos(h)])


def apply_spin(glb, clip, spin, axis='x', pivot=(0, -0.03, -0.02)):
    """Rewrites the WeaponRight track of a built clip: the gun turns in the hand."""
    g = Glb(glb); i = g.names.index('WeaponRight'); a = g.anim(clip); c = Clip(g, clip); n = c.frames
    t0, r0 = c.local(i, 0); pv = np.array(pivot, float); T = []; R = []
    raw = {ch['target']['path']: np.asarray(g.acc(a['samplers'][ch['sampler']]['output']), float)[0] for ch in a['channels'] if ch['target']['node'] == i}
    raw_t, raw_r = raw['translation'], raw['rotation']
    for f in range(n):
        d = float(author.hermite([(k[0], [k[1]]) for k in spin], f)[0]); q = _qaxis(axis, d)
        if abs(d) % 360 < 1e-9: R.append(raw_r); T.append(raw_t); continue   # a full turn: exactly the idle
        R.append(qmul(r0, q)); T.append(t0 + qrot(r0, pv - qrot(q, pv)))
    R = np.array(R)
    for k in range(1, n):
        if np.dot(R[k], R[k - 1]) < 0: R[k] = -R[k]
    tin = g.add_acc(np.arange(n) / 30.0, 'SCALAR')
    for ch in a['channels']:
        if ch['target']['node'] == i:
            vals = np.array(T) if ch['target']['path'] == 'translation' else R
            a['samplers'][ch['sampler']] = {'input': tin, 'output': g.add_acc(vals, 'VEC3' if ch['target']['path'] == 'translation' else 'VEC4'), 'interpolation': 'LINEAR'}
    g.save(glb)


def build(did, gun, motion, params, outdir, clip='empty_reload', left=None, body='pma', name=None):
    ctx = Ctx(gun, left, body, clip, params)
    m = motion(ctx)
    spec = {'_draft': did, '_gun': gun, '_left_gun': ctx.left, '_body': body, '_gun_clip': clip, '_timing': ctx.T,
            '_params': ctx.P, '_two_arm': bool(m.get('Left')), '_notes': m.get('notes', ''),
            'src': ctx.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': ctx.N,
            'keys': {'Right': clean(m['Right'], ctx.N), 'Left': clean(m['Left'], ctx.N) if m.get('Left') else [K(0)]},
            'shakes': m.get('shakes', {})}
    for S, ks in spec['shakes'].items():   # a kick must have died out by the last frame, or the clip does not end in the idle
        for sh in ks:
            if sh.get('type') == 'kick': sh['release'] = round(min(sh.get('release', 6.0), max((ctx.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    for k in ('swivel', 'pole', 'elbow', 'reach', 'protract_max', 'twist_share', 'shoulder', 'bumps', 'lock'):
        if k in m: spec[k] = m[k]
    if 'reach' not in spec: spec['reach'] = [0.93, 0.985]
    if 'twist_share' not in spec: spec['twist_share'] = 0.6
    if m.get('spin'): spec['_spin'] = {'keys': m['spin'], 'axis': m.get('spin_axis', 'x'), 'pivot': list(m.get('spin_pivot', (0, -0.03, -0.02)))}
    os.makedirs(outdir, exist_ok=True)
    stem = name or did; out = f'{outdir}/{stem}.glb'; spec['out'] = out
    json.dump(spec, open(f'{outdir}/{stem}.json', 'w'), indent=1)
    author.build(spec, out)
    diag = {'twist': {}, 'elb': {}}
    for (S, f), (tw, sw) in author.DIAG.items(): diag['twist'].setdefault(S, []).append([f, round(tw, 1), round(sw, 1)])
    for (S, f), (el, r, mv, sh) in author.ELB.items(): diag['elb'].setdefault(S, []).append([f, round(el, 1), round(r, 3), round(float(sh) * 100, 2)])
    json.dump(diag, open(f'{outdir}/{stem}_ik.json', 'w'))
    if m.get('spin'): apply_spin(out, 'reload_draft', m['spin'], m.get('spin_axis', 'x'), m.get('spin_pivot', (0, -0.03, -0.02)))
    return spec, out
