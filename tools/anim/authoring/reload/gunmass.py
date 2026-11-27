"""Mass, centre and inertia of a gun from its mesh, and the finger torque of an in-hand turn. Metres, kilograms, seconds.
Solid: voxel fill of the union of the gun's parts (the scene's one assembly, lowered/guns.part_names) plus the seated standard magazine.
Z rays on a xy grid of H metres; a ray is inside a part where the signed crossing count is not zero; intervals of all parts are merged per ray, so
overlaps count once (the game meshes carry nested shells and flipped faces, so a closed-form tetra sum double counts). Uniform density RHO.
Inertia is about the in-hand spin pivot PIV (gun axes, z = barrel), parallel axis rule. Method and checks: gg-work/migration/ptorque/REPORT.md.

Finger torque (net_torque): the torque the fingers apply to turn the gun in the hand = I alpha minus the gravity moment of the centre of mass about
the pivot. alpha = angular acceleration of the gun relative to the hand, in gun axes (second difference of the relative rotation at 30 fps);
gravity moment = m (c - p) x g, g in gun axes. The gyro term and the pivot's own acceleration are not included. Used by the draft check
(checks/fingertorque.py) and by r3lib.TL3 (a spin is slowed until its torque is within the limit).
"""
import os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import guns as GN
from glb import Glb
from fk import Clip, qrot

RHO = 1000.0                       # kg/m3, uniform. Mass, inertia and torque scale with it; counts of frames do not.
H = 0.0015                         # voxel cell, m
PIV = np.array([0.0, -0.03, -0.02])    # trigger finger, gun axes (bull3.py, top3.py in-hand spin pivot)
DT = 1 / 30.0
G = np.array([0.0, -9.81, 0.0])
TURN_DEG_F = 0.5                   # in-hand turn frame: gun turning relative to the hand faster than this (dilated by one frame)
_cache = {}


def _part_intervals(T, h, origin):
    ox, oy = origin; a, b, c = T[:, 0], T[:, 1], T[:, 2]
    nrm = np.cross(b - a, c - a); I, J, Z, SG = [], [], [], []
    for k in np.nonzero(np.abs(nrm[:, 2]) > 1e-14)[0]:
        A, B, C = a[k], b[k], c[k]
        x0, x1 = min(A[0], B[0], C[0]), max(A[0], B[0], C[0]); y0, y1 = min(A[1], B[1], C[1]), max(A[1], B[1], C[1])
        i0 = int(np.ceil((x0 - ox) / h)); i1 = int(np.floor((x1 - ox) / h)); j0 = int(np.ceil((y0 - oy) / h)); j1 = int(np.floor((y1 - oy) / h))
        if i1 < i0 or j1 < j0: continue
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing='ij'); px = ox + ii.ravel() * h; py = oy + jj.ravel() * h
        d = (B[1] - C[1]) * (A[0] - C[0]) + (C[0] - B[0]) * (A[1] - C[1])
        l1 = ((B[1] - C[1]) * (px - C[0]) + (C[0] - B[0]) * (py - C[1])) / d; l2 = ((C[1] - A[1]) * (px - C[0]) + (A[0] - C[0]) * (py - C[1])) / d; l3 = 1 - l1 - l2
        m = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not m.any(): continue
        I.append(ii.ravel()[m]); J.append(jj.ravel()[m]); Z.append((l1 * A[2] + l2 * B[2] + l3 * C[2])[m]); SG.append(np.full(m.sum(), np.sign(nrm[k, 2])))
    I = np.concatenate(I).astype(np.int64); J = np.concatenate(J).astype(np.int64); Z = np.concatenate(Z); SG = np.concatenate(SG)
    key = (I + 5) * 100000 + (J + 5); o = np.lexsort((Z, key)); key, Z, SG = key[o], Z[o], SG[o]
    first = np.r_[True, key[1:] != key[:-1]]; cs = np.cumsum(-SG)
    start_cs = np.where(first, cs + SG, 0)           # cumulative sum before the column's first crossing
    seg = np.cumsum(first) - 1; w = cs - start_cs[first][seg]
    nxt = np.r_[key[1:] == key[:-1], False]; ins = nxt & (np.abs(w) > 0.5)
    idx = np.nonzero(ins)[0]
    return key[idx], Z[idx], Z[idx + 1]


def _vox(parts, h, xmin=None):
    """parts: list of (n,3,3) triangle arrays -> V (m3), M1 (int x dV), S (int x x' dV), about the origin. xmin: drop the columns whose x is below it (a plane cut)."""
    allT = np.concatenate(parts); lo = allT.reshape(-1, 3).min(0) - h
    ox, oy = lo[0] + 0.5 * h + h * 1e-3, lo[1] + 0.5 * h + h * 7e-4        # grid off the mesh's own lattice (rays on shared edges)
    K, A, B = [], [], []
    for T in parts:
        k, a, b = _part_intervals(T, h, (ox, oy)); K.append(k); A.append(a); B.append(b)
    K = np.concatenate(K); A = np.concatenate(A); B = np.concatenate(B)
    o = np.lexsort((A, K)); K, A, B = K[o], A[o], B[o]
    off = K.astype(float) * 10.0; cm = np.maximum.accumulate(B + off)
    new = np.r_[True, (K[1:] != K[:-1]) | (A[1:] + off[1:] > cm[:-1])]
    gid = np.cumsum(new) - 1; ng = gid[-1] + 1
    z0 = np.zeros(ng); kk = np.zeros(ng, np.int64)
    z0[gid[new]] = A[new]; kk[gid[new]] = K[new]
    z1 = np.full(ng, -1e9); np.maximum.at(z1, gid, B)
    ix = kk // 100000 - 5; iy = kk % 100000 - 5; x = ox + ix * h; y = oy + iy * h
    if xmin is not None: k = x >= xmin; x, y, z0, z1 = x[k], y[k], z0[k], z1[k]
    L = z1 - z0; dV = h * h * L; zm = (z0 + z1) / 2
    V = dV.sum(); M1 = np.array([(dV * x).sum(), (dV * y).sum(), (dV * zm).sum()])
    S = np.zeros((3, 3)); S[0, 0] = (dV * (x * x + h * h / 12)).sum(); S[1, 1] = (dV * (y * y + h * h / 12)).sum(); S[2, 2] = (h * h * (z1 ** 3 - z0 ** 3) / 3).sum()
    S[0, 1] = S[1, 0] = (dV * x * y).sum(); S[0, 2] = S[2, 0] = (dV * x * zm).sum(); S[1, 2] = S[2, 1] = (dV * y * zm).sum()
    return float(V), M1, S


def _tris(path):
    g = Glb(path); out = []
    for m in g.j['meshes']:
        for pr in m['primitives']:
            P = np.asarray(g.acc(pr['attributes']['POSITION']), float); I = np.ravel(g.acc(pr['indices'])).astype(int).reshape(-1, 3); out.append(P[I])
    return np.concatenate(out)


def _seated_mag_tris(Gm):
    mp = GN.find(Gm + '__mag_std_01.glb'); wa = GN.wanim(Gm)
    if not (mp and wa): return None
    gw = Glb(wa); an = [x['name'] for x in gw.j['animations']]; W0 = Clip(gw, 'reload' if 'reload' in an else an[0]).world(0)
    if 'mag_slot' not in gw.names: return None
    st, sq = W0[gw.names.index('mag_slot')]; T = _tris(mp)
    return np.array([[st + qrot(sq, x) for x in tri] for tri in T])


def props(gid):
    """-> {'gun', 'mesh', 'mass_kg', 'com_m' (gun axes), 'I_pivot' (3x3, kg m2 about PIV), 'pivot_m'} for a manifest gun id
    (a gun without its own mesh follows its `shares`). None if there is no mesh."""
    if gid in _cache: return _cache[gid]
    g = common.gun(gid); Gm = g.get('mesh')
    if not Gm and (g.get('reload') or {}).get('shares'): return props(g['reload']['shares'])
    if not Gm: _cache[gid] = None; return None
    parts = [_tris(common.need(GN.find(n + '.glb'))) for n in GN.part_names(Gm)]; mg = _seated_mag_tris(Gm)
    if mg is not None: parts.append(mg)
    V, M1, S = _vox(parts, H); m = RHO * V; com = M1 / V; p = PIV
    SP = RHO * S - RHO * (np.outer(p, M1) + np.outer(M1, p)) + m * np.outer(p, p)
    I = np.trace(SP) * np.eye(3) - SP
    _cache[gid] = {'gun': gid, 'mesh': Gm, 'mass_kg': float(m), 'com_m': com, 'I_pivot': I, 'pivot_m': PIV, 'seated_magazine': mg is not None}
    return _cache[gid]


# ------------------------------------------------------------------------------------------------ arm
def _arm_world(g, name):
    """World position of a node of an arm glb (bind pose)."""
    par = {c: i for i, n in enumerate(g.j['nodes']) for c in n.get('children', [])}
    def wm(i):
        n = g.j['nodes'][i]; M = np.eye(4)
        if 'matrix' in n: M = np.array(n['matrix'], float).reshape(4, 4).T
        else:
            x, y, z, w = n.get('rotation', [0, 0, 0, 1]); sc = n.get('scale', [1, 1, 1])
            M[:3, :3] = qmat([x, y, z, w]) * np.array(sc); M[:3, 3] = n.get('translation', [0, 0, 0])
        return wm(par[i]) @ M if i in par else M
    return wm(g.names.index(name))[:3, 3]


_arm_cache = {}


def arm_inertia(body='pma', side='r'):
    """Forearm and hand of the player arm mesh (common.arm_mesh): mass and inertia about the elbow (the ForeArm joint), density RHO, voxel method of props().
    Parts: the forearm skin and the hand (the upper arm skin is the first submesh, left out); the forearm skin is cut at the plane through the elbow
    perpendicular to the elbow to hand line, so the overlap with the upper arm does not count. Rays run across that line (the meshes are open at their ends).
    -> {'mass_kg', 'com_m' (from the elbow, x along the forearm), 'I_elbow' (3x3, x along the forearm), 'I_axial', 'I_transverse' (mean of the two
    moments about axes through the elbow across the forearm), 'forearm_len_m'}. I_transverse is what turns the arm about the elbow."""
    key = (body, side)
    if key in _arm_cache: return _arm_cache[key]
    import common
    from glb import Glb
    g = Glb(common.need(common.arm_mesh(body, side))); S = 'Right' if side == 'r' else 'Left'
    el = _arm_world(g, S + 'ForeArm'); ha = _arm_world(g, S + 'Hand'); a = ha - el; L = float(np.linalg.norm(a)); a = a / L
    t = np.cross(a, [0.0, 0.0, 1.0]); t = t / np.linalg.norm(t) if np.linalg.norm(t) > 1e-6 else np.cross(a, [1.0, 0.0, 0.0]); t = t / np.linalg.norm(t)
    B = np.array([a, np.cross(t, a), t])                                    # rows: x along the forearm, y, z across it
    parts = []
    for m in g.j['meshes'][1:]:                                             # submesh 0 is the upper arm
        for pr in m['primitives']:
            P = np.asarray(g.acc(pr['attributes']['POSITION']), float); I = np.ravel(g.acc(pr['indices'])).astype(int).reshape(-1, 3)
            parts.append(((P - el) @ B.T)[I])
    V, M1, Sm = _vox(parts, H, xmin=0.0); m = RHO * V; com = M1 / V; SP = RHO * Sm
    Iel = np.trace(SP) * np.eye(3) - SP; ev = np.sort(np.linalg.eigvalsh(Iel))
    out = {'body': body, 'side': side, 'mass_kg': float(m), 'com_m': com, 'I_elbow': Iel, 'I_axial': float(ev[0]), 'I_transverse': float(ev[1:].mean()), 'I_principal': [float(x) for x in ev], 'forearm_len_m': L}
    _arm_cache[key] = out
    return out


def arm_mass(body='pma', side='r'):
    """Whole arm (upper arm, forearm, hand) of the player arm mesh: mass at density RHO, voxel union (overlaps count once), rays across the elbow to hand line. kg."""
    key = ('mass', body, side)
    if key in _arm_cache: return _arm_cache[key]
    g = Glb(common.need(common.arm_mesh(body, side))); S = 'Right' if side == 'r' else 'Left'
    el = _arm_world(g, S + 'ForeArm'); ha = _arm_world(g, S + 'Hand'); a = (ha - el) / np.linalg.norm(ha - el)
    t = np.cross(a, [0.0, 0.0, 1.0]); t = t / np.linalg.norm(t); B = np.array([a, np.cross(t, a), t]); parts = []
    for m in g.j['meshes']:
        for pr in m['primitives']:
            P = np.asarray(g.acc(pr['attributes']['POSITION']), float); I = np.ravel(g.acc(pr['indices'])).astype(int).reshape(-1, 3); parts.append((P @ B.T)[I])
    out = float(RHO * _vox(parts, H)[0]); _arm_cache[key] = out
    return out


def gun_transverse(mp):
    """Inertia of the gun about its centre of mass across the bore: mean of the two largest principal moments, kg m2."""
    r = np.asarray(mp['com_m']) - np.asarray(mp['pivot_m']); m = mp['mass_kg']
    Ic = np.asarray(mp['I_pivot']) - m * (float(r @ r) * np.eye(3) - np.outer(r, r))
    return float(np.sort(np.linalg.eigvalsh(Ic))[1:].mean())


def spring_terms(gid, body='pma'):
    """The measured sides of the arm spring law: gun mass and transverse inertia, arm mass and inertia (arm_inertia: forearm and hand about the elbow). None without a mesh."""
    mp = props(gid)
    if mp is None: return None
    return {'m_gun': mp['mass_kg'], 'm_arm': arm_mass(body, 'r'), 'I_gun': gun_transverse(mp), 'I_arm': arm_inertia(body, 'r')['I_transverse']}


def arm_spring(gid, cfg, body='pma'):
    """Arm spring of a gun from its measured mass and inertia, no label. The arm and the gun are one mass on a spring-damper:
      position: w_p^2 = k_pos / (m_gun + m_arm)        k_pos in N/m   (the whole arm travels with the gun)
      rotation: w_r^2 = k_rot / (I_arm + I_gun)        k_rot in N m/rad (forearm and hand about the elbow, gun about its centre of mass)
      damping ratio z = cfg['zeta'] (damping coefficient c = 2 z sqrt(k M), so it follows the mass).
    cfg: weapons.json checks.draft.arm_spring. -> {'wp', 'wr', 'z'} in rad/frame (30 fps) as r3lib.SPRING, or None without a mesh."""
    t = spring_terms(gid, body)
    if t is None: return None
    return {'wp': math.sqrt(cfg['k_pos_n_m'] / (t['m_gun'] + t['m_arm'])) * DT, 'wr': math.sqrt(cfg['k_rot_nm_rad'] / (t['I_arm'] + t['I_gun'])) * DT, 'z': cfg['zeta']}



# ------------------------------------------------------------------------------------------------ rotation and torque
def qmat(q):
    x, y, z, w = np.asarray(q, float) / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def logR(R):
    c = (np.trace(R) - 1) / 2; th = math.acos(max(-1, min(1, c)))
    if th < 1e-9: return np.zeros(3)
    if abs(math.pi - th) < 1e-4:
        w, v = np.linalg.eigh((R + R.T) / 2); return v[:, -1] * th
    return th / (2 * math.sin(th)) * np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])


def net_torque(Rrel, Rw, mp, gravity=True, skip_steps=()):
    """Rrel (n,3,3): gun in the hand frame. Rw (n,3,3): gun in the world (gravity along -y). mp: props().
    -> (turn (n,) bool, tau (n,3) N m in gun axes). tau = I alpha - m (c - p) x g (without the gravity term when gravity is False), 0 outside frames 1..n-2.
    turn = in-hand turn frames: relative speed over TURN_DEG_F deg/f, dilated by one frame."""
    n = len(Rrel); I = np.asarray(mp['I_pivot']); m = mp['mass_kg']; r = np.asarray(mp['com_m']) - np.asarray(mp['pivot_m'])
    wk = np.array([logR(Rrel[k].T @ Rrel[k + 1]) / DT for k in range(n - 1)]).reshape(-1, 3)      # body frame, at k + 1/2
    sp = np.degrees(np.linalg.norm(wk, axis=1)) * DT
    turn = np.zeros(n, bool)
    for k in np.nonzero(sp > TURN_DEG_F)[0]:
        if int(k) in skip_steps: continue      # a step of a free flight (the gun is not held): no finger load
        turn[max(k - 1, 0):k + 3] = True
    tau = np.zeros((n, 3))
    for f in range(1, n - 1):
        tau[f] = I @ ((wk[f] - wk[f - 1]) / DT) - (m * np.cross(r, Rw[f].T @ G) if gravity else 0.0)
    return turn, tau
