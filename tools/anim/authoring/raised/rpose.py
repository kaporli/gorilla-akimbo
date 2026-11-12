"""Raised pose per gun: shift one hand's gun in clips of the dual-wield rig (two-bone IK, the hand stays on the grip),
the family poses of weapons.json, and the first-person metric.

A delta is (offset [dx, dy, dz] in metres, glTF axes: x = V's right, y = up, z = back toward the camera;
angles [pitch, yaw, roll] in degrees about the gun's own axes) for the RIGHT hand; the left hand gets the mirror.
Pitch and yaw stay 0 in the raised families: the muzzle direction is kept, only roll (cant about the barrel) is used.

weapons.json:
  raised_families  {name: {dir, aim_dir, roll, s_ref, clavicle, target, s_max}}: pose = game pose + s * dir (idle
                   clips) or s * aim_dir (aim clips), roll * min(1, s / s_ref) about the barrel, clavicle scaled the same
  gun "raised"     {"family": "C", "pose": "C_<name>", "s": {"pma": 0.145, "pwa": 0.15}}; {"family": "none"} keeps the
                   game pose on purpose (the autotune reports it and leaves it alone)
  checks.raised    camera of the metric, autotune rules, check limits
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import common
for _p in (HERE, os.path.join(common.HERE, 'lowered')):   # lowered last: it has modules named like the gate's
    if _p not in sys.path: sys.path.append(_p)
import numpy as np
import lauthor as A
from lpose import Rig, Glb, qmul, qinv, qrot, blend, FPS
from fk import Clip
import guns as GN

M = common.manifest.load()
FAM = M.get('raised_families', {})
RULES = M['checks']['raised']
CAM = RULES['camera']
EYE = np.array(CAM['eye'], float); HH = math.radians(CAM['hfov_169'] / 2); HV = math.atan(math.tan(HH) * 9 / 16)
GRID = (160, 90)
IDLE, AIM = 'idlepose_shoulder', 'idlepose_ironsight'
AIM_CLIPS = (AIM,)
# The pose clips of the game's dual-wield base set the Ready and Equip states play (the lowered sets own
# friendly_idlepose, safe_action and equip_safe), and how the delta comes in: 1 = the whole clip, 'in' = eased in
# over the first 40 % (the gun starts out of view, far from the idle), 'out' = eased out over the last 40 %.
POSE_CLIPS = {'idlepose_shoulder': 1, 'idlepose_ironsight': 1, 'idlepose_sprint': 1, 'idlepose_slide': 1, 'idlepose_frenzy': 1,
              'sprint_start': 1, 'sprint_stop': 1, 'sprint_to_slide': 1, 'vault': 1, 'equip_sprint': 'in', 'first_equip': 'in'}
# Clips of the per-hand reload set (the Lexington dual-wield set) that are arm motion, not additive.
HAND_CLIPS = {'equip': 'in', 'unequip': 'out', 'melee': 1}
_rigs = {}
_bindrel = {}


def rig_of(path):
    if path not in _rigs: _rigs[path] = Rig(Glb(path))
    return _rigs[path]


def base(body='pma'):
    """(rig, glb path) of the game's dual-wield base set."""
    p = common.need(common.idle_glb(body))
    return rig_of(p), p


def clip_frames(rig, clip):
    n = int(round(rig.duration(clip) * FPS)) + 1
    return [rig.sample(clip, i / FPS) for i in range(n)]


def mirror(d):
    o, e = d
    return ([-o[0], o[1], o[2]], [e[0], -e[1], -e[2]])


ZERO = {'Right': [[0, 0, 0], [0, 0, 0]], 'Left': [[0, 0, 0], [0, 0, 0]]}


def shift(body, L, deltas, clav=None, rig=None):
    """L: local pose (the base rig, or rig). deltas: {'Right': (offset, angles), 'Left': ...} as given (already
    mirrored). clav: {'Right': [p, y, r], ...} degrees on the clavicle. -> (new local pose, stats per shifted side)."""
    brig, p = base(body); rig = rig or brig
    A.setup({'base': p, 'lowered': ZERO})
    A.rig = rig; A.idx = rig.idx
    A.rest = rig.world(L); A.REST_L = L
    for S in ('Right', 'Left'): A.CLAV[S] = np.array((clav or {}).get(S, [0, 0, 0]), float)
    off = {S: (np.array(deltas[S][0], float), np.array(deltas[S][1], float), 1.0) if S in deltas else (np.zeros(3), np.zeros(3), 0.0)
           for S in ('Right', 'Left')}
    N, st = A.solve_offsets(off)
    N = list(N)
    for S in ('Right', 'Left'):
        if S not in deltas:  # the other arm stays exactly as it was
            for j in arm_joints(S): N[j] = L[j]
    return N, {S: st[S] for S in deltas}


def arm_joints(S):
    if S not in A.SIDES: A.setup({'base': base()[1], 'lowered': ZERO})
    ch, hh, ph = A.SIDES[S]
    return ch[:4] + hh + ph


# ---------------------------------------------------------------- families
def delta(fam, s, aim=False, w=1.0):
    """Right-hand (offset, angles) of a family at s; w scales the whole delta (eased clips)."""
    f = FAM[fam]; d = np.array(f['aim_dir' if aim else 'dir'], float) * s * w
    return (d.tolist(), [0, 0, f['roll'] * min(1.0, s / f['s_ref']) * w])


def clav(fam, s, w=1.0):
    f = FAM[fam]; c = (np.array(f.get('clavicle', [0, 0, 0]), float) * min(1.5, s / f['s_ref']) * w).tolist()
    return {'Right': c, 'Left': c}


def pose(body, L0, fam, s, sides=('Right', 'Left'), aim=False, w=1.0, rig=None):
    """Pose L0 with the family delta on the given hands. s: number, or {side: s}."""
    if not isinstance(s, dict): s = {S: s for S in sides}
    L = L0; st = {}
    for S in sides:
        if s.get(S, 0) <= 0 or w <= 0: continue
        d = delta(fam, s[S], aim, w); d = d if S == 'Right' else mirror(d)
        L, x = shift(body, L, {S: d}, {S: clav(fam, s[S], w)[S]}, rig); st.update(x)
    return L, st


def ramp(kind, f, n):
    """Weight of the delta at frame f of n frames (POSE_CLIPS / HAND_CLIPS kinds)."""
    if kind == 1 or n < 2: return 1.0
    x = f / (0.4 * (n - 1)) if kind == 'in' else (n - 1 - f) / (0.4 * (n - 1))
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- manifest
def raised_guns(all_=False):
    """[(gun, raised entry)] of the guns of this build with a raised family (not "none")."""
    return [(g, g['raised']) for g in common.manifest.arm_guns() if g.get('raised') and (all_ or g['raised'].get('family') != 'none')]


def sharers(g):
    """The gun and the guns that have no model variable of their own and use this gun's (same arm set)."""
    out = [g]
    if g.get('vars'):
        out += [o for o in common.manifest.guns(all_=True) if o is not g and not o.get('vars') and not o.get('generic')
                and o.get('arm_set') == g.get('arm_set') and o.get('mesh')]
    return out


def clip_glb(pose_name, body, kind=''):
    """Authored clips of a raised pose: '' = the base set pose clips, '_hands' = equip, unequip, melee."""
    return f'{common.path("raised_clips")}/{body}/raised_{pose_name}{kind}.glb'


# ---------------------------------------------------------------- gun geometry and metric
_pts = {}


def _mesh_tris(path):
    g = Glb(path); out = []
    for m in g.j['meshes']:
        for pr in m['primitives']:
            P = g.acc(pr['attributes']['POSITION']); I = np.ravel(g.acc(pr['indices'])).astype(int).reshape(-1, 3)
            out.append(P[I])
    return np.concatenate(out)


def gun_parts(G):
    """Mesh part names of a gun body (as lowered/guns.py: base, receiver, fixed stock, mesh_parts)."""
    names = [G + '__base1_01']
    for part in ['rcv1_01', 'rcv1_01_stock_01'] + list(GN._gun(G).get('mesh_parts', [])):
        if GN.find(f'{G}__{part}.glb'): names.append(f'{G}__{part}')
    return names


def place(tq, V):
    t, (x, y, z, w) = tq
    R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                  [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    return np.asarray(t) + V @ R.T


def surface(G, n=40000):
    """n points spread evenly over the gun's surface (body parts and seated magazine), weapon bone space."""
    if G in _pts: return _pts[G]
    T = [_mesh_tris(common.need(GN.find(p + '.glb'))) for p in gun_parts(G)]
    mp = GN.find(G + '__mag_std_01.glb')
    if mp and GN.wanim(G):
        gw = Glb(GN.wanim(G)); an = [x['name'] for x in gw.j['animations']]
        W0 = Clip(gw, 'reload' if 'reload' in an else an[0]).world(0)
        if 'mag_slot' in gw.names:
            st, sq = W0[gw.names.index('mag_slot')]; Mg = _mesh_tris(mp)
            T.append(place((st, sq), Mg.reshape(-1, 3)).reshape(-1, 3, 3))
    T = np.concatenate(T)
    ar = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    rng = np.random.default_rng(7); k = rng.choice(len(T), n, p=ar / ar.sum())
    u, v = rng.random(n), rng.random(n); f = u + v > 1; u[f], v[f] = 1 - u[f], 1 - v[f]
    P = T[k, 0] + (T[k, 1] - T[k, 0]) * u[:, None] + (T[k, 2] - T[k, 0]) * v[:, None]
    _pts[G] = P
    return P


def screen(P):
    """World points -> (sx, sy in -1..1 of the 16:9 view, in-front mask)."""
    Q = P - EYE; fwd = -Q[:, 2]; ok = fwd > 0.02
    sx = Q[:, 0] / np.maximum(fwd, 1e-6) / math.tan(HH); sy = Q[:, 1] / np.maximum(fwd, 1e-6) / math.tan(HV)
    return sx, sy, ok


def cover_grid(P):
    sx, sy, ok = screen(P)
    on = ok & (np.abs(sx) < 1) & (np.abs(sy) < 1)
    g = np.zeros((GRID[1], GRID[0]), bool)
    ix = np.clip(((sx[on] + 1) / 2 * GRID[0]).astype(int), 0, GRID[0] - 1); iy = np.clip(((1 - sy[on]) / 2 * GRID[1]).astype(int), 0, GRID[1] - 1)
    g[iy, ix] = True
    return g, (float(sy[on].max()) if on.any() else None)


def _bind_rel(rig, fa, hd):
    k = (id(rig), fa, hd)
    if k not in _bindrel:
        B = rig.world([rig.bind_local(i) for i in range(rig.n)]); _bindrel[k] = qmul(qinv(B[fa][1]), B[hd][1])
    return _bindrel[k]


def measure(body, L, guns, ref=None, gap=True):
    """guns: {'Right': mesh stem, 'Left': mesh stem}. ref: local pose of the game clip at the same frame (muzzle
    direction and hand-on-grip are measured against it). Per side: cover (% of the 16:9 screen the gun covers), top
    (top edge of the gun, -1 bottom .. 1 top), eye (cm, nearest gun point), muzzle (deg off the game clip direction),
    lateral (cm the muzzle moved across the view), elbow (deg, 180 = straight), reach (shoulder-to-wrist over arm
    length), wrist (deg from the bind pose), wrist_vs_game (deg from the game clip), grip (cm the hand moved on the
    gun). Plus gap: closest distance between the two guns (cm), cover_both."""
    rig, _ = base(body); W = rig.world(L); R = rig.world(ref) if ref is not None else None
    out = {}; clouds = {}
    for S, G in guns.items():
        gi = rig.idx[f'Weapon{S}']; P = place(W[gi], surface(G)); clouds[S] = P
        g, top = cover_grid(P)
        ua, fa, hd = [rig.idx[n] for n in (f'{S}Arm', f'{S}ForeArm', f'{S}Hand')]
        a, b = W[fa][0] - W[ua][0], W[hd][0] - W[fa][0]
        elbow = 180 - math.degrees(math.acos(np.clip(np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b), -1, 1)))
        rel = qmul(qinv(W[fa][1]), W[hd][1])
        d = qmul(qinv(_bind_rel(rig, fa, hd)), rel); wrist = math.degrees(2 * math.acos(min(1.0, abs(float(d[3])))))
        m = {'cover': round(100 * float(g.mean()), 1), 'top': None if top is None else round(top, 2),
             'eye': round(100 * float(np.linalg.norm(P - EYE, axis=1).min()), 1), 'elbow': round(elbow),
             'reach': round(float(np.linalg.norm(W[hd][0] - W[ua][0]) / (np.linalg.norm(a) + np.linalg.norm(b))), 3), 'wrist': round(wrist, 1)}
        if R is not None:
            z0, z1 = qrot(R[gi][1], np.array([0, 0, -1.0])), qrot(W[gi][1], np.array([0, 0, -1.0]))
            m['muzzle'] = round(math.degrees(math.acos(np.clip(np.dot(z0, z1), -1, 1))), 3)
            mz = np.array([[0, 0, surface(G)[:, 2].min()]])
            dm = place(W[gi], mz)[0] - place(R[gi], mz)[0]
            m['lateral'] = round(100 * float(np.linalg.norm(dm[:2])), 1)
            hr = qrot(qinv(R[gi][1]), R[hd][0] - R[gi][0]); hn = qrot(qinv(W[gi][1]), W[hd][0] - W[gi][0])
            m['grip'] = round(100 * float(np.linalg.norm(hr - hn)), 3)
            wr = qmul(qinv(R[fa][1]), R[hd][1]); dd = qmul(qinv(wr), rel)
            m['wrist_vs_game'] = round(math.degrees(2 * math.acos(min(1.0, abs(float(dd[3]))))), 1)
        out[S] = m
    if len(clouds) == 2:
        if gap:
            a, b = clouds['Right'][::25], clouds['Left'][::25]
            out['gap'] = round(100 * float(np.sqrt(((a[:, None] - b[None]) ** 2).sum(2)).min()), 1)
        out['cover_both'] = round(100 * float(cover_grid(np.concatenate([clouds['Right'], clouds['Left']]))[0].mean()), 1)
    return out


def write_full(rig, base_glb, clips, out):
    """clips: {name: [local pose per frame at 30 fps]} -> glb (copy of base_glb) holding only these clips. Every track
    keeps all its keys: a clip whose tracks are all constant (a static pose) has no length otherwise, and WolvenKit
    cannot export the set it was imported into. Quaternions keep w >= 0 on the first key and never flip sign."""
    g = Glb(base_glb); anims = []
    for name, frames in clips.items():
        N = len(frames); tin = g.add_acc(np.arange(N) / FPS, 'SCALAR'); samplers, channels = [], []
        for i in range(rig.n):
            if rig.names[i] == 'Armature': continue
            for p, k, kind in (('translation', 0, 'VEC3'), ('rotation', 1, 'VEC4')):
                vals = np.array([fr[i][k] for fr in frames])
                if p == 'rotation':
                    if vals[0][3] < 0: vals[0] = -vals[0]
                    for j in range(1, len(vals)):
                        if np.dot(vals[j], vals[j - 1]) < 0: vals[j] = -vals[j]
                samplers.append({'input': tin, 'output': g.add_acc(vals, kind), 'interpolation': 'LINEAR'})
                channels.append({'sampler': len(samplers) - 1, 'target': {'node': i, 'path': p}})
        anims.append({'name': name, 'samplers': samplers, 'channels': channels})
    g.j['animations'] = anims
    g.save(out)
    return out
