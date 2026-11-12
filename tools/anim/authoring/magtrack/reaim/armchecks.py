"""Arm clip checks of one pick, before and after a re-aim, per clip and partner gun (read from the clip glbs):
contact frame against the seated magazine and depth at K, worst striker-into-magazine K-5 to K, striker into the
magazine gun's body K-7 to K+7, arm meshes (K-9 to K+9, mm, negative = inside), striker gun eye clearance (all frames,
clip-check eye and the camera-fit eye E), max on-screen fraction of both guns while they are down, frames that differ.
usage: armchecks.py <set>_<pick> <before clips dir> <after clips dir> [--out <json>] [--jobs 6] [--spec <spec.json>]
  default out: <authoring work>/magtrack/armchecks_<pick>.json
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.spatial import cKDTree
from reaim_core import g
from mag_geom import app, partner_pts, onscreen_frac, m4, E, EYES, Glb
from mag_contacts import signed, contact

_MESH, _DENSE, _SN, _ARM = {}, {}, {}, {}


def mesh(k):
    if k not in _MESH: _MESH[k] = g.tris(g.PARTS[k]['parts'])
    return _MESH[k]


def dn(k):
    if k not in _DENSE: _DENSE[k] = g.dense(*mesh(k), 0.006, 40)
    return _DENSE[k]


# the magazine gun's body as 1 cm z slices: y range and x range per slice
_sl = {}


def body_depth(Pl):
    """depth (m) of points (magazine gun local) inside the gun body slices; 0 if none"""
    if not _sl:
        B = mesh(g.MAGGUN['id'])[0]
        for z0 in np.arange(-0.32, 0.21, 0.01):
            s = B[(B[:, 2] >= z0) & (B[:, 2] < z0 + 0.01)]
            if len(s) > 10: _sl[round(z0, 2)] = (s[:, 1].min(), s[:, 1].max(), s[:, 0].min(), s[:, 0].max())
    best = 0.0
    zk = np.floor(Pl[:, 2] * 100) / 100
    for z0, (y0, y1, x0, x1) in _sl.items():
        m = np.isclose(zk, z0)
        if not m.any(): continue
        Q = Pl[m]
        d = np.minimum.reduce([Q[:, 1] - y0, y1 - Q[:, 1], Q[:, 0] - x0, x1 - Q[:, 0]])
        if (d > 0).any(): best = max(best, d.max())
    return best


def surf_normals(k, step=0.004):
    """surface samples of a gun with their face normals (for the inside/outside sign)"""
    if k not in _SN:
        V, T = mesh(k); A_, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
        N = np.cross(B - A_, C - A_); ar = np.linalg.norm(N, axis=1); ok = ar > 1e-12; N[ok] /= ar[ok, None]
        P, NN = [A_, B, C, (A_ + B + C) / 3], [N, N, N, N]
        L = np.maximum.reduce([np.linalg.norm(B - A_, axis=1), np.linalg.norm(C - A_, axis=1), np.linalg.norm(C - B, axis=1)])
        for n in range(2, 30):
            m = (L > step * (n - 1)) & (L <= step * n) if n < 29 else L > step * (n - 1)
            if not m.any(): continue
            uv = np.array([(i / n, j / n) for i in range(n + 1) for j in range(n + 1 - i)])
            a, b, c = A_[m], B[m], C[m]
            P.append((a[:, None] + uv[None, :, :1] * (b - a)[:, None] + uv[None, :, 1:] * (c - a)[:, None]).reshape(-1, 3))
            NN.append(np.repeat(N[m], len(uv), 0))
        P = np.vstack(P); NN = np.vstack(NN); _SN[k] = (cKDTree(P), P, NN)
    return _SN[k]


def robust(d, inside, k=3):
    """negative depth of the k-th deepest inside vertex (single flipped normals are not penetration), else min gap"""
    if inside.sum() >= k: return -float(np.sort(d[inside])[-k])
    return float(d.min())


class Rig:
    """Joints of one arm clip in world space per integer frame."""
    def __init__(self, path):
        self.g = Glb(path); self.c = g.Clip(self.g, 'smack'); self.idx = {n: i for i, n in enumerate(self.g.names)}
        self.cache = {}

    def W(self, f):
        if f not in self.cache: self.cache[f] = self.c.world(min(f, self.c.frames - 1))
        return self.cache[f]

    def gun(self, S, f): return m4(*self.W(f)[self.idx['Weapon' + S]])


def arm_data(body, S):
    if (body, S) not in _ARM:
        gl = Glb(g.common.need(g.common.arm_mesh(body, 'l' if S == 'Left' else 'r'))); sk = gl.j['skins'][0]
        jn = [gl.names[j] for j in sk['joints']]; ibm = gl.acc(sk['inverseBindMatrices'])
        IB = [ibm[k].reshape(4, 4).T for k in range(len(jn))]
        V, J, Wt, NV = [], [], [], []
        for m in gl.j['meshes']:
            for pr in m['primitives']:
                a = pr['attributes']; v = gl.acc(a['POSITION']); j = gl.acc(a['JOINTS_0']).astype(int); w = gl.acc(a['WEIGHTS_0'])
                if 'JOINTS_1' in a: j = np.hstack([j, gl.acc(a['JOINTS_1']).astype(int)]); w = np.hstack([w, gl.acc(a['WEIGHTS_1'])])
                V.append(v); J.append(j); Wt.append(w / np.maximum(w.sum(1, keepdims=True), 1e-9)); NV.append(gl.acc(a['NORMAL']))
        _ARM[(body, S)] = (jn, IB, np.vstack(V), np.vstack(J), np.vstack(Wt), np.vstack(NV))
    return _ARM[(body, S)]


def arm_world(rig, body, S, f):
    """arm mesh vertices and normals (world) at frame f; mesh joints missing from the rig follow the proximal joint of
    the nearest rig bone segment, rigidly"""
    jn, IB, V, J, Wt, NV = arm_data(body, S); names = rig.g.names; idx = rig.idx; par = rig.c.par
    Wj = rig.W(f)
    Wm = {n: m4(*Wj[idx[n]]) for n in jn if n in idx}
    key = ('drv', body, S)
    if key not in _ARM:
        B = {n: np.linalg.inv(IB[k]) for k, n in enumerate(jn)}; have = [n for n in jn if n in idx]; segs = []
        for n in have:
            p = names[par[idx[n]]] if par.get(idx[n]) is not None else None
            if p in B and p in idx: segs.append((p, B[p][:3, 3], B[n][:3, 3]))
            segs.append((n, B[n][:3, 3], B[n][:3, 3]))
        drv = {}
        for n in jn:
            if n in idx: continue
            x = B[n][:3, 3]; best = None
            for d, a, b in segs:
                ab = b - a; t = 0 if ab @ ab < 1e-18 else max(0, min(1, (x - a) @ ab / (ab @ ab)))
                dist = np.linalg.norm(a + ab * t - x)
                if best is None or dist < best[0]: best = (dist, d)
            drv[n] = best[1]
        _ARM[key] = (B, drv)
    B, drv = _ARM[key]
    G = np.stack([(Wm[n] @ IB[k]) if n in Wm else (Wm[drv[n]] @ np.linalg.inv(B[drv[n]])) for k, n in enumerate(jn)])
    V4 = np.c_[V, np.ones(len(V))]; out = np.zeros((len(V), 3)); nout = np.zeros((len(V), 3))
    for c in range(J.shape[1]):
        out += Wt[:, c][:, None] * np.einsum('nij,nj->ni', G[J[:, c]], V4)[:, :3]
        nout += Wt[:, c][:, None] * np.einsum('nij,nj->ni', G[J[:, c]][:, :3, :3], NV)
    return out, nout / np.maximum(np.linalg.norm(nout, axis=1, keepdims=True), 1e-9)


def pts_vs_gun(Pw, rig, gun_side, gun, f):
    tree, P, N = surf_normals(gun)
    Pl = app(np.linalg.inv(rig.gun(gun_side, f)), Pw); d, i = tree.query(Pl)
    s = np.einsum('ij,ij->i', Pl - P[i], N[i]); inside = (s < 0) & (d < 0.03)
    return robust(d, inside)


def arm_mesh(path, sh, st, gun, body, frames):
    """mm, worst over frames: magazine-gun-side arm vs the partner gun, partner-side arm vs the magazine gun (negative =
    deepest vertex inside), and partner-side arm vs magazine-gun-side arm (signed by the skinned vertex normals)"""
    rig = Rig(path); a = b = c = 9.0
    for f in frames:
        As, Ns = arm_world(rig, body, sh, f); At = arm_world(rig, body, st, f)[0]
        a = min(a, pts_vs_gun(As, rig, st, gun, f)); b = min(b, pts_vs_gun(At, rig, sh, g.MAGGUN['id'], f))
        d, i = cKDTree(As).query(At); sg = np.einsum('ij,ij->i', At - As[i], Ns[i]); inside = (sg < 0) & (d < 0.03)
        c = min(c, robust(d, inside))
    return round(a * 1000, 1), round(b * 1000, 1), round(c * 1000, 1)


def one(job):
    path, body, sh, st, key, K = job
    a = g.Arm(path); P = partner_pts(key); r = {}; n = g.FRAMES['length']
    c, k = contact(a, sh, st, P, lo=18, hi=32)
    r['contact_f'] = round(c, 2) if c is not None else None
    r['depth_K_mm'] = round(signed(a, sh, st, P, float(K))[0] * 1000, 1)
    r['mag_pen_mm'] = round(max(signed(a, sh, st, P, f)[0] for f in np.arange(K - 5, K + 0.01, 0.25)) * 1000, 1)
    D = dn(key)
    r['body_mm'] = round(max(body_depth(app(np.linalg.inv(a.W(sh, f)) @ a.W(st, f), D)) for f in range(K - 7, K + 8)) * 1000, 1)
    m = arm_mesh(path, sh, st, key, body, range(K - 9, K + 10))
    r['mesh_mm'] = dict(mag_gun_arm_vs_partner=m[0], partner_arm_vs_mag_gun=m[1], arm_vs_arm=m[2])
    V = mesh(key)[0]; e1, e2 = 9, 9
    for f in range(n):
        Pw = app(a.W(st, f), V)
        e1 = min(e1, np.linalg.norm(Pw - EYES[body], axis=1).min()); e2 = min(e2, np.linalg.norm(Pw - E, axis=1).min())
    r['eye_clip_cm'] = round(e1 * 100, 1); r['eye_E_cm'] = round(e2 * 100, 1)
    ShV = mesh(g.MAGGUN['id'])[0]
    r['onscreen_down'] = round(max(max(onscreen_frac(app(a.W(st, f), V)), onscreen_frac(app(a.W(sh, f), ShV)))
                                   for f in range(g.FRAMES['down'], g.FRAMES['seated'] + 1)), 3)
    return r


def diff_frames(p0, p1):
    a, b = g.Arm(p0), g.Arm(p1)
    return [f for f in range(a.frames) if max(np.abs(a.W(s, f) - b.W(s, f)).max() for s in ('Left', 'Right')) > 1e-6]


if __name__ == '__main__':
    a = sys.argv[1:]; opt = g.common.opt
    spec = g.load_spec(opt(a, '--spec')); out = opt(a, '--out'); jobs = int(opt(a, '--jobs', 6))
    if len(a) != 3: raise SystemExit(__doc__)
    key, pi = g.find_pick(spec, a[0]); K = spec[key][pi]['K']
    out = out or g.common.work('magtrack') + f'/armchecks_{g.pick_id(key, spec[key][pi])}.json'
    todo, meta = [], []
    cases = list(zip(g.spec_cases(spec, key, pi, a[1]), g.spec_cases(spec, key, pi, a[2])))
    for (p0, body, sh, st, keys), (p1, *_) in cases:
        for k in keys:
            for tag, p in (('before', p0), ('after', p1)):
                todo.append((p, body, sh, st, k, K)); meta.append((os.path.basename(p0)[:-4], body, k, tag))
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool: res = pool.map(one, todo)
    else:
        res = [one(j) for j in todo]
    rep = {}
    for (clip, body, k, tag), r in zip(meta, res):
        rep.setdefault(f'{clip}/{body}/{k}', {})[tag] = r
    for (p0, body, sh, st, keys), (p1, *_) in cases:
        rep[f'{os.path.basename(p0)[:-4]}/{body}/_frames_changed'] = diff_frames(p0, p1)
    json.dump(rep, open(out, 'w'), indent=1)
    for k, v in rep.items():
        if k.endswith('_frames_changed'): print(k, v); continue
        b, c = v['before'], v['after']
        print(f"{k:44s} contact {b['contact_f']}->{c['contact_f']} depth {b['depth_K_mm']}->{c['depth_K_mm']} magpen {b['mag_pen_mm']}->{c['mag_pen_mm']} "
              f"body {b['body_mm']}->{c['body_mm']} mesh {tuple(b['mesh_mm'].values())}->{tuple(c['mesh_mm'].values())} "
              f"eye {b['eye_clip_cm']}/{b['eye_E_cm']}->{c['eye_clip_cm']}/{c['eye_E_cm']} down {b['onscreen_down']}->{c['onscreen_down']}")
    print('wrote', out)
