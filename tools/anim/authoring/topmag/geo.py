"""Geometry shared by the top-magazine generators and checks: gun meshes in gun-local space (the Weapon bone frame),
the top-magazine gun's magazine box, V's hand vertices, the first-person camera.
A gun key is a manifest gun id (see parts() for its mesh parts)."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'author'))
import common, manifest
from glb import Glb
from fk import Clip, qmul, qrot
import author

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
DATA = HERE + '/data/'
TOPGUN = 'shingen'
PARTS = json.load(open(DATA + 'parts.json'))
ALIAS = {'generic_smg': 'guillotine'}                      # manifest id -> parts.json key
RIG = {'guillotine': 'w_smg__budget_guillotine'}           # parts key without a manifest mesh -> weapon rig
EYES = {'pma': np.array([0, 1.693, -0.044]), 'pwa': np.array([0, 1.6947, -0.0372])}
SIDES = {'left': ('Left', 'Right'), 'right': ('Right', 'Left')}   # clip side = top-magazine hand: (holder, striker)

# single picks: id -> (clip side, pick name, contact frames, category family)
PICKS = {'v10': ('left', 'flip', [25], '10'), 'v09': ('left', 'doubletap', [15, 25], '09'),
         'v06': ('left', 'uppercut', [25], '06'), 'm10': ('right', 'flip', [25], '10'),
         'm09': ('right', 'doubletap', [15, 25], '09'), 'm06': ('right', 'uppercut', [25], '06')}
PAIRS = {'d07': 'overunder', 'd01': 'scissor', 'd03b': 'clap'}


def pick_spec(pid, body='pma'):
    """the spec of a pick (data/picks/<id>.json) for one body"""
    s = json.load(open(DATA + f'picks/{pid}.json'))
    s['body'] = body
    return s


_RIG = {}


def template(body, name='reload'):
    """(joint names, clip, first frame in model space) of the body's template clip"""
    return _rig({'body': body, 'template': name, 'frames': 0})[1:4]


def _rig(spec):
    """the author's rig state for a spec's source and template, loaded once"""
    k = (author.src_path(spec), spec['template'])
    if k not in _RIG:
        author.setup(spec)
        _RIG[k] = (author.src, author.names, author.tc, author.rest, author.idx, dict(author.SIDES))
    return _RIG[k]


def load_spec(spec):
    """Solver of one spec (dict or json path), over the shared author (authoring/author/author.py), which works on
    one spec at a time: every call here makes its spec the current one first. Returns a dict: gun_pose(side, f),
    solve(f) -> local transforms of the solved joints, solveW(f) -> model space transforms of all joints, rest, idx,
    names, SIDES, tc, qmul, qeuler, qrot."""
    if not isinstance(spec, dict):
        spec = json.load(open(spec))
    src, names, tc, rest, idx, sides = _rig(spec)

    def use():
        if author.spec is not spec:
            author.spec, author.src, author.names, author.tc, author.rest, author.idx = spec, src, names, tc, rest, idx
            author.N = spec['frames']
            author.SIDES.clear(); author.SIDES.update(sides); author.DIAG.clear(); author.ELB.clear()

    def gun_pose(S, f):
        use(); return author.gun_pose(S, f)

    def solve(f):
        use(); return author.solve(f)

    def solveW(f):
        W = dict(rest)
        for n, (t, q) in solve(f).items():       # parents come first
            pt, pq = W[tc.par[n]]
            W[n] = (pt + qrot(pq, t), qmul(pq, q))
        return W

    return {'spec': spec, 'names': names, 'idx': idx, 'tc': tc, 'rest': rest, 'SIDES': sides, 'gun_pose': gun_pose,
            'solve': solve, 'solveW': solveW, 'qmul': qmul, 'qeuler': author.qeuler, 'qrot': qrot}


def build(spec, out):
    """write the clip of a spec"""
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    return author.build(spec, out)


def wmesh(part):
    p = common.find('weapon_meshes', part + '.glb')
    if not p:
        raise SystemExit(f'missing weapon mesh {part}.glb: see weapons.json paths weapon_meshes')
    return p


def wanim(name):
    return common.find('weapon_anims', name + '.anims.glb')


def M4(t, q):
    x, y, z, w = q
    R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                  [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t; return M


def app(M, V): return V @ M[:3, :3].T + M[:3, 3]


def key_of(gun):
    return ALIAS.get(gun, gun)


def parts(gun):
    """mesh parts of a gun's default appearance: the manifest's parts list, else that of a gun with the same mesh,
    else <mesh>__base1_01; guns without a mesh in the manifest (pistols, revolvers) come from data/parts.json"""
    k = key_of(gun)
    if k in PARTS:
        return PARTS[k]
    g = common.gun(gun)
    if g.get('parts'):
        return g['parts']
    for o in manifest.guns(all_=True):
        if o.get('mesh') == g['mesh'] and o.get('parts'):
            return o['parts']
    return [g['mesh'] + '__base1_01']


def rig(gun):
    """weapon rig stem of an SMG (for its magazine at rest), else None"""
    k = key_of(gun)
    if k in RIG:
        return RIG[k]
    for g in manifest.guns(all_=True):
        if g['id'] == gun:
            return g.get('mesh') if g['type'] == 'smg' else None
    return None


def verts(path):
    g = Glb(path); P = []
    for m in g.j['meshes']:
        for p in m['primitives']: P.append(g.acc(p['attributes']['POSITION']))
    return g, np.vstack(P)


def mag_rest(base):
    """magazine vertices (gun-local) at frame 0 of the gun's reload; empty if the rig or mag animation is unknown"""
    mp = next((p for p in (common.find('weapon_meshes', f'{base}__{s}.glb') for s in ('mag_std_01', 'mag_stdr_01')) if p), None)
    if not (mp and wanim(base + '__base1') and wanim(base + '__mag_std')):
        return np.zeros((0, 3))
    gw = Glb(wanim(base + '__base1'))
    if 'mag_slot' not in gw.names and wanim(base + '__rcv1'): gw = Glb(wanim(base + '__rcv1'))
    if 'mag_slot' not in gw.names: return np.zeros((0, 3))
    an = [a['name'] for a in gw.j['animations']]
    slot = M4(*Clip(gw, 'reload' if 'reload' in an else an[0]).world(0)[gw.names.index('mag_slot')])
    mg = Glb(wanim(base + '__mag_std')); mc = Clip(mg, 'reload'); W0 = mc.world(0)
    g, V = verts(mp); sk = g.j['skins'][0]; ibm = g.acc(sk['inverseBindMatrices']); jn = [g.names[k] for k in sk['joints']]
    M = slot @ M4(*W0[mg.names.index(jn[0])]) @ ibm[0].reshape(4, 4).T
    return V @ M[:3, :3].T + M[:3, 3]


_cache = {}


def load(gun):
    """dict(body, mag, all): vertices of the gun's parts, its magazine at rest, both"""
    if gun not in _cache:
        body = np.vstack([verts(wmesh(p))[1] for p in parts(gun)])
        r = rig(gun)
        mag = mag_rest(r) if r else np.zeros((0, 3))
        rm = common.rifle_mag(gun) if not r and gun in [g['id'] for g in manifest.guns(all_=True)] else None
        if rm is not None:
            mag = rm[0]                      # a rifle's magazine, seated (it hangs below the receiver)
        _cache[gun] = dict(body=body, mag=mag, all=np.vstack([body, mag]))
    return _cache[gun]


def tris(gun):
    """(vertices, triangles) of the gun's parts"""
    k = ('tris', gun)
    if k not in _cache:
        V, T = [], []; n = 0
        for p in parts(gun):
            g = Glb(wmesh(p))
            for m in g.j['meshes']:
                for pr in m['primitives']:
                    v = g.acc(pr['attributes']['POSITION']); i = g.acc(pr['indices']).astype(int).reshape(-1, 3)
                    V.append(v); T.append(i + n); n += len(v)
        rm = common.rifle_mag(gun) if gun in [g['id'] for g in manifest.guns(all_=True)] else None
        if rm is not None:                   # a rifle's seated magazine is part of what strikes and what is seen
            V.append(rm[0]); T.append(rm[1] + n); n += len(rm[0])
        _cache[k] = (np.vstack(V), np.vstack(T))
    return _cache[k]


def dense(gun, step=0.006):
    """vertices plus surface samples every `step` m"""
    k = ('dense', gun, step)
    if k not in _cache:
        V, T = tris(gun)
        A_, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
        L = np.maximum.reduce([np.linalg.norm(B - A_, axis=1), np.linalg.norm(C - A_, axis=1), np.linalg.norm(C - B, axis=1)])
        out = [V]
        for n in range(2, 40):
            m = (L > step * (n - 1)) & (L <= step * n) if n < 39 else L > step * (n - 1)
            if not m.any(): continue
            uv = np.array([(i / n, j / n) for i in range(n + 1) for j in range(n + 1 - i)])
            a, b, c = A_[m], B[m], C[m]
            P = a[:, None] + uv[None, :, :1] * (b - a)[:, None] + uv[None, :, 1:] * (c - a)[:, None]
            out.append(P.reshape(-1, 3))
        _cache[k] = np.unique(np.round(np.vstack(out), 4), axis=0)
    return _cache[k]


# ---- the top-magazine gun's magazine (joint frame box, per-frame matrix in gun-local space) and body ---------------
_top = common.gun(TOPGUN)['mesh']
_gw = Glb(common.need(wanim(_top + '__base1')))
SLOT = M4(*Clip(_gw, 'reload').world(0)[_gw.names.index('mag_slot')])
_mg = Glb(common.need(wanim(_top + '__mag_std'))); MC = Clip(_mg, 'reload'); MI = _mg.names.index('mag_std')
_mm, MAGV = verts(wmesh(_top + '__mag_std_01'))
IBM = _mm.acc(_mm.j['skins'][0]['inverseBindMatrices'])[0].reshape(4, 4).T
MAGB = app(IBM, MAGV)                         # magazine verts in the mag joint's frame
LO, HI = MAGB.min(0), MAGB.max(0)
SHB = load(TOPGUN)['body']
_MAGW = {}


def mag_local(f):
    """magazine joint in the gun's frame at frame f of the game's reload (clamped to its last frame)"""
    f = min(f, MC.frames - 1)
    if f not in _MAGW:
        _MAGW[f] = SLOT @ M4(*MC.world(f)[MI])
    return _MAGW[f]


def gunM(ns, S, f): return M4(*ns['gun_pose'](S, f))
def magJ(ns, S, f): return gunM(ns, S, f) @ mag_local(f)


def box_signed(P):
    """signed distance of points to the magazine box (its joint frame): + inside depth, - outside gap"""
    inside = np.minimum(P - LO, HI - P).min(1)
    out = np.linalg.norm(np.maximum(np.maximum(LO - P, P - HI), 0), axis=1)
    return np.where(inside > 0, inside, -out)


# top-magazine gun body inside test: per 1 cm z slice, y range and x half width (convex-ish slices)
_sl = {}
for _z0 in np.arange(-0.32, 0.21, 0.01):
    _s = SHB[(SHB[:, 2] >= _z0) & (SHB[:, 2] < _z0 + 0.01)]
    if len(_s) > 10: _sl[round(_z0, 2)] = (_s[:, 1].min(), _s[:, 1].max(), _s[:, 0].min(), _s[:, 0].max())


def shingen_depth(Pl):
    """depth (m) of points (gun-local) inside the top-magazine gun's body slices; 0 if none"""
    best = 0.0
    zk = np.floor(Pl[:, 2] * 100) / 100
    for z0, (y0, y1, x0, x1) in _sl.items():
        m = np.isclose(zk, z0)
        if not m.any(): continue
        Q = Pl[m]
        d = np.minimum.reduce([Q[:, 1] - y0, y1 - Q[:, 1], Q[:, 0] - x0, x1 - Q[:, 0]])
        if (d > 0).any(): best = max(best, d.max())
    return best


def segdist(P, a, b):
    ab = b - a; t = np.clip((P - a) @ ab / (ab @ ab), 0, 1); return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def contact_mt(P):
    """signed smallest translation between points (magazine joint frame) and the magazine box, metres:
    - gap (miss) = distance from the box to the nearest point; + penetration = shortest exit along a box axis
    (only points overlapping the box in the other two axes block that exit). Returns (value, vector in mag frame that
    moves the points to just touching / just clear)."""
    inside = np.all((P > LO) & (P < HI), 1)
    if not inside.any():
        q = np.clip(P, LO, HI); d = np.linalg.norm(P - q, axis=1); k = np.argmin(d)
        return -d[k], (q[k] - P[k])
    best = None
    for ax in range(3):
        o = [i for i in range(3) if i != ax]
        m = np.all((P[:, o] > LO[o]) & (P[:, o] < HI[o]), 1) & (P[:, ax] > LO[ax]) & (P[:, ax] < HI[ax])
        if not m.any(): continue
        up = (HI[ax] - P[m, ax]).max(); dn = (P[m, ax] - LO[ax]).max()
        for s, sg in ((up, 1), (dn, -1)):
            if best is None or s < best[0]:
                v = np.zeros(3); v[ax] = sg * s; best = (s, v)
    return best[0], best[1]


# ---- V's hand ------------------------------------------------------------------------------------------------------
def hand(body, S):
    """V's hand (palm and fingers) vertices in the Weapon bone frame of side S (Left, Right), from the arm mesh
    skinned to frame 0 of the template clip. The hand is rigid with the gun in every clip of the author, so the
    points hold for every frame and gun. Cached in the work folder."""
    k = ('hand', body, S)
    if k in _cache:
        return _cache[k]
    p = common.work('topmag', 'cache') + f'/hand_{body}_{S}.npy'
    if os.path.exists(p):
        _cache[k] = np.load(p)
        return _cache[k]
    suf = 'l' if S == 'Left' else 'r'
    names, _, W0 = template(body)
    W = {names[i]: M4(*v) for i, v in W0.items()}
    g = Glb(common.need(common.arm_mesh(body, suf))); sk = g.j['skins'][0]
    jn = [g.names[j] for j in sk['joints']]; ibm = g.acc(sk['inverseBindMatrices'])
    B = {n: np.linalg.inv(ibm[i].reshape(4, 4).T) for i, n in enumerate(jn)}
    have = [n for n in jn if n in W]
    G = {}
    for i, n in enumerate(jn):
        if n in W: G[i] = W[n] @ ibm[i].reshape(4, 4).T
        else:  # follow the nearest animated joint (bind positions), rigidly
            d = min(have, key=lambda h: np.linalg.norm(B[h][:3, 3] - B[n][:3, 3]))
            G[i] = W[d] @ np.linalg.inv(B[d])
    handset = {i for i, n in enumerate(jn) if (S + 'Hand') in n or (S + 'InHand') in n or n.startswith(f'{suf}_')
               and any(t in n for t in ('ind_', 'mid_', 'ring_', 'pinky', 'thumb'))}
    P = []
    for m in g.j['meshes']:
        for pr in m['primitives']:
            a = pr['attributes']; V = g.acc(a['POSITION']); J = g.acc(a['JOINTS_0']).astype(int); Wt = g.acc(a['WEIGHTS_0'])
            if 'JOINTS_1' in a:
                J = np.hstack([J, g.acc(a['JOINTS_1']).astype(int)]); Wt = np.hstack([Wt, g.acc(a['WEIGHTS_1'])])
            Wt = Wt / np.maximum(Wt.sum(1, keepdims=True), 1e-9)
            hw = sum(Wt[:, c] * np.isin(J[:, c], list(handset)) for c in range(J.shape[1]))
            sel = hw > 0.5
            if not sel.any(): continue
            V4 = np.c_[V[sel], np.ones(sel.sum())]; out = np.zeros((sel.sum(), 3))
            for c in range(J.shape[1]):
                Ms = np.stack([G[j] for j in J[sel, c]])
                out += Wt[sel, c][:, None] * np.einsum('nij,nj->ni', Ms, V4)[:, :3]
            P.append(out)
    P = np.vstack(P)
    L = (np.linalg.inv(W[f'Weapon{S}']) @ np.c_[P, np.ones(len(P))].T).T[:, :3]
    np.save(p, L)
    _cache[k] = L
    return L


# ---- first-person camera: at the eye, pitched 18 deg down, 80 deg horizontal field of view, 16:9 -------------------
PITCH = np.radians(18); TH = np.tan(np.radians(40)); ASP = 9 / 16
FWD = np.array([0, -np.sin(PITCH), -np.cos(PITCH)]); UP = np.array([0, np.cos(PITCH), -np.sin(PITCH)])
RGT = np.array([1., 0, 0])


def onscreen(P, eye):
    """True if any point is inside the view"""
    d = P - eye; z = d @ FWD
    x = (d @ RGT) / np.maximum(z, 1e-4) / TH; y = (d @ UP) / np.maximum(z, 1e-4) / (TH * ASP)
    return bool(((z > 0.02) & (np.abs(x) < 1) & (np.abs(y) < 1)).any())


def coverage(Pw, T, eye, W=320, H=180):
    """share of the view covered by a mesh (world vertices, triangles). Triangles up to 6 px are marked by sample
    points 1.5 px apart or closer, larger ones are drawn (PIL)."""
    from PIL import Image, ImageDraw
    d = Pw - eye; C = np.c_[d @ RGT, d @ UP, d @ FWD]
    near = 0.02; fx = (W / 2) / TH
    z = C[:, 2]; front = z > near
    zs = np.where(front, z, 1.0)
    X = W / 2 + fx * C[:, 0] / zs; Y = H / 2 - fx * C[:, 1] / zs
    A = np.zeros((H, W), bool)
    full = front[T].all(1)
    Tf = T[full]; xs, ys = X[Tf], Y[Tf]
    vis = ~((xs.max(1) < 0) | (xs.min(1) > W) | (ys.max(1) < 0) | (ys.min(1) > H))
    xs, ys = xs[vis], ys[vis]
    big = (xs.max(1) - xs.min(1) > 6) | (ys.max(1) - ys.min(1) > 6)
    uv = np.array([(i / 4, j / 4, 1 - i / 4 - j / 4) for i in range(5) for j in range(5 - i)])
    sx = (xs[~big] @ uv.T).ravel(); sy = (ys[~big] @ uv.T).ravel()
    ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H); A[sy[ok].astype(int), sx[ok].astype(int)] = True
    im = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(im)
    lim = 20.0 * W
    for k in np.nonzero(big)[0]:
        dr.polygon([(float(np.clip(xs[k, i], -lim, lim)), float(np.clip(ys[k, i], -lim, lim))) for i in range(3)], fill=255)
    for t in T[front[T].any(1) & ~full]:   # clip against the near plane
        poly = []; Q = C[t]
        for i in range(3):
            a, b = Q[i], Q[(i + 1) % 3]
            if a[2] > near: poly.append(a)
            if (a[2] > near) != (b[2] > near):
                u = (near - a[2]) / (b[2] - a[2]); poly.append(a + u * (b - a))
        if len(poly) >= 3:
            dr.polygon([(float(np.clip(W / 2 + fx * c[0] / c[2], -lim, lim)), float(np.clip(H / 2 - fx * c[1] / c[2], -lim, lim))) for c in poly], fill=255)
    A |= np.asarray(im) > 0
    return float(A.mean())


def long_guns():
    """ids of the long partner guns that have their own clip set, in manifest order"""
    out = []
    for g in manifest.guns():
        if g.get('long_partner') == g['id'] and g['id'] not in out:
            out.append(g['id'])
    return out
