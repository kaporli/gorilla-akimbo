"""Dual-wield magazine tracks for the Shingen (top magazine).

While dual-wielding, the other gun knocks the magazine off. The vanilla magazine track is a hand pull (it pops at f14
and is carried 26-34 cm toward the shooter), so these sets replace it: the magazine stays exactly at its seated pose
until the release frame K (the hit), then flies off in world space (launch velocity = the gun's own velocity at the
magazine + a push along the hit, gravity along world -y, constant spin), is shrunk once it is out of view (frame H) and
comes back at f46 with the vanilla insertion (the guns are down out of view f46-f62).

The track is stored gun-local, so it is converted with the MEAN Shingen pose of every arm clip that plays it (all
partner guns or categories of that pick, male and female V). One set per family and side:
w_smg__arasaka_shingen__mag_<long|smg|pair>_<left|right>.anims, holding reload, reload_01, reload_02 (pick 0, 1, 2) and
empty_reload, _01, _02 (the same tracks, held seated to f111).

spec (json; clips relative to paths.clips, as <body>/<clip>.glb): {"<family>_<side>": [{"clips": [<clip glb>...], "side": "Left"|"Right", "K": 25, "v": [x, y, z] (m/s,
relative push), "axis": [x, y, z], "spin": deg/s, "H": frame}, ... x3 picks]}

usage: magtrack.py <spec.json> <out dir> [--probe]
  --probe: vanilla tracks with the magazine 20 cm above its place for the whole clip (to see in game that the set plays).
"""
import sys, os, json, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifest
from glb import Glb, fit_track_keys
from fk import Clip

# The gun's vanilla magazine set and weapon set (glb exports of the game files): weapons.json, topmag.magazine.
MAG = manifest.magazine()
MAGGLB = manifest.gamefile(MAG['vanilla_set'], '.glb')
WEAPONGLB = manifest.gamefile(MAG['weapon_set'], '.glb')
for _p in (MAGGLB, WEAPONGLB):
    if not os.path.exists(_p):
        raise SystemExit(f'missing {_p}: run build.sh extract')
FPS = 30.0
GRAV = np.array([0, -9.81, 0])
NAMES = ('reload', 'reload_01', 'reload_02')
EMPTY = ('empty_reload', 'empty_reload_01', 'empty_reload_02')
INSERT = 46          # first frame of the vanilla insertion (magazine still shrunk), full size from INSERT + 1
SMALL = 0.001        # scale of the hidden magazine
# Empty variants: held seated after f95. 112 frames, not the vanilla 114: through WolvenKit's import 114 and 116 frames
# came back resampled (113 and 115 keys, up to 7 mm off the seat before the hit); 96 and 112 came back exact.
EMPTY_FRAMES = 112


def m4(t, q):
    x, y, z, w = np.asarray(q, float) / np.linalg.norm(q)
    R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                  [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t; return M


def quat(R):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_matrix(R).as_quat()


def rotm(axis, ang):
    from scipy.spatial.transform import Rotation as Rot
    a = np.asarray(axis, float); n = np.linalg.norm(a)
    return np.eye(3) if n < 1e-9 else Rot.from_rotvec(a / n * ang).as_matrix()


# ---- the vanilla magazine rig ------------------------------------------------------------------------------------
_gw = Glb(WEAPONGLB)
SLOT = m4(*Clip(_gw, 'reload').world(0)[_gw.names.index('mag_slot')])
MG = Glb(MAGGLB)
JOINTS = ('magazine', 'magazine_reload')                    # identical tracks in every vanilla clip
CHILD = {'magazine': 'mag_std', 'magazine_reload': 'mag_stdr'}
_vc = {}


def vclip(name):
    if name not in _vc: _vc[name] = Clip(MG, name)
    return _vc[name]


def vworld(name, f, node):
    c = vclip(name); f = max(0, min(int(f), c.frames - 1))
    return m4(*c.world(f)[MG.names.index(node)])


def vlocal(name, f, node):
    c = vclip(name); f = max(0, min(int(f), c.frames - 1))
    return c.local(MG.names.index(node), f)


def parent_world(name, f, joint):
    """rig-space 4x4 of the joint's parent (mag_plug) at frame f"""
    i = MG.names.index(joint); par = next(k for k, n in enumerate(MG.j['nodes']) if i in n.get('children', []))
    return vworld(name, f, MG.names[par])


G0 = SLOT @ vworld('reload', 0, 'mag_std')                 # seated mag_std joint, gun-local
_ls = vlocal('reload', 0, 'mag_std'); LSTD = m4(*_ls)      # mag_std local (constant)


def joint_local(Gstd, name, f, joint='magazine'):
    """local (t, q) of `joint` that puts its child mesh joint at gun-local Gstd"""
    P = parent_world(name, f, joint)
    L = np.linalg.inv(SLOT @ P) @ Gstd @ np.linalg.inv(LSTD)
    return L[:3, 3], quat(L[:3, :3])


# ---- arm clips -----------------------------------------------------------------------------------------------------
class Arm:
    def __init__(self, path):
        self.g = Glb(path); self.c = Clip(self.g, 'smack'); self.cache = {}; self.frames = self.c.frames

    def W(self, side, f):
        f0 = int(np.floor(f)); a = f - f0
        def at(k):
            k = max(0, min(k, self.frames - 1))
            if k not in self.cache: self.cache[k] = self.c.world(k)
            return self.cache[k][self.g.names.index('Weapon' + side)]
        (t0, r0), (t1, r1) = at(f0), at(f0 + 1)
        if np.dot(r0, r1) < 0: r1 = -r1
        return m4(t0 * (1 - a) + t1 * a, r0 * (1 - a) + r1 * a)


def mean_pose(arms, side, frames=96):
    """per frame: mean of the Shingen's Weapon<side> transforms (translation mean, sign-aligned quaternion mean)"""
    out = []
    for f in range(frames):
        Ms = [a.W(side, f) for a in arms]
        t = np.mean([M[:3, 3] for M in Ms], 0)
        qs = [quat(M[:3, :3]) for M in Ms]; q0 = qs[0]
        q = np.mean([q if np.dot(q, q0) >= 0 else -q for q in qs], 0)
        out.append(m4(t, q))
    return out


# ---- the track -----------------------------------------------------------------------------------------------------
def flight(Wm, K, v_rel, axis, spin, H, frames=96, centre=None, gunvel='pre'):
    """gun-local mag_std joint per frame (list of 4x4) and scale per frame, for one pick.
    Wm: mean Shingen pose per frame. centre: magazine centre in the mag_std joint frame (spin pivot)."""
    c_j = np.zeros(3) if centre is None else np.asarray(centre)
    M0 = Wm[K] @ G0; c0 = (M0 @ np.r_[c_j, 1])[:3]
    # launch = the gun's own velocity at the magazine centre + the push. gunvel: 'pre' = the gun's velocity going into
    # the hit (K-1 to K: what the magazine had while seated), 'post' = after it (K to K+1), 'none' = push only.
    cl = (np.linalg.inv(Wm[K]) @ np.r_[c0, 1])
    a, b = {'pre': (K - 1, K), 'post': (K, K + 1), 'none': (K, K)}[gunvel]
    vg = ((Wm[b] @ cl)[:3] - (Wm[a] @ cl)[:3]) * FPS
    v = vg + np.asarray(v_rel)
    G, S = [], []
    for f in range(frames):
        if f <= K:
            G.append(G0.copy()); S.append(1.0); continue
        t = (f - K) / FPS
        c = c0 + v * t + 0.5 * GRAV * t * t
        R = rotm(axis, np.radians(spin) * t)
        M = np.eye(4); M[:3, :3] = R @ M0[:3, :3]; M[:3, 3] = c - R @ M0[:3, :3] @ c_j
        G.append(np.linalg.inv(Wm[f]) @ M)
        S.append(1.0 if f <= H else SMALL)
    return G, S


def build_anim(name, Gs, Ss, pick, probe=False):
    """animation dict + accessors for one clip name. Gs/Ss: 96-frame track (None: vanilla, for --probe)."""
    van = MG.anim(name); n = EMPTY_FRAMES if name in EMPTY else vclip(name).frames
    times = np.arange(n) / FPS
    ti = MG.add_acc(times, 'SCALAR')
    tracks = {}
    for k, node in enumerate(MG.j['nodes']):
        nm = node.get('name')
        if nm == 'Armature': continue
        T, Q, Sc = [], [], []
        for f in range(n):
            t, q = vlocal(name, f, nm); s = 1.0
            if nm in JOINTS:
                if probe:
                    Gv = SLOT @ vworld(name, f, CHILD[nm]); Gv[:3, 3] += [0, 0.20, 0]     # 20 cm up, gun-local
                    t, q = joint_local(Gv, name, f, nm)
                elif f < len(Gs):
                    if f >= INSERT:
                        Gv = SLOT @ vworld(NAMES[pick], f, CHILD[nm]); s = SMALL if f == INSERT else 1.0
                    else:
                        Gv = Gs[f]; s = Ss[f]
                    t, q = joint_local(Gv, name, f, nm)
                else:
                    t, q = joint_local(G0, name, f, nm)        # empty variants: seated to the end
            if Q and np.dot(q, Q[-1]) < 0: q = -q
            T.append(t); Q.append(q); Sc.append([s, s, s])
        tracks[nm] = (np.array(T), np.array(Q), np.array(Sc))
    samplers, channels = [], []
    for k, node in enumerate(MG.j['nodes']):
        nm = node.get('name')
        if nm not in tracks: continue
        for path, arr, kind in (('translation', tracks[nm][0], 'VEC3'), ('rotation', tracks[nm][1], 'VEC4'), ('scale', tracks[nm][2], 'VEC3')):
            samplers.append({'input': ti, 'output': MG.add_acc(arr, kind), 'interpolation': 'LINEAR'})
            channels.append({'sampler': len(samplers) - 1, 'target': {'node': k, 'path': path}})
    ex = copy.deepcopy(van['extras'])
    ex['trackKeys'] = fit_track_keys(ex.get('trackKeys'), n, FPS)
    ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
    return {'name': name, 'samplers': samplers, 'channels': channels, 'extras': ex}


def tracks_for(entry, arms=None):
    # the mean Shingen pose comes from pose_clips when the entry has them (the clips the flight was made with), so
    # clips added to a pick later do not move its track
    arms = arms or [Arm(p) for p in entry.get('pose_clips') or entry['clips']]
    Wm = mean_pose(arms, entry['side'])
    return flight(Wm, entry['K'], entry['v'], entry['axis'], entry['spin'], entry['H'], centre=entry.get('centre'),
                  gunvel=entry.get('gunvel', 'pre'))


def write_set(entries, out, probe=False):
    anims = []
    for pick, e in enumerate(entries):
        Gs, Ss = (None, None) if probe else tracks_for(e)
        for name in (NAMES[pick], EMPTY[pick]):
            anims.append(build_anim(name, Gs, Ss, pick, probe))
    MG.j['animations'] = anims
    MG.save(out)
    print('saved', out)


if __name__ == '__main__':
    spec = manifest.mag_spec(sys.argv[1])
    for _k, _v in spec.items():
        for _e in ([] if _k.startswith('_') else _v):
            for _c in _e['clips'] + _e.get('pose_clips', []):
                if not os.path.exists(_c):
                    raise SystemExit(f'{sys.argv[1]}: clip {_c} is missing')
    outdir = sys.argv[2]; probe = '--probe' in sys.argv
    os.makedirs(outdir, exist_ok=True)
    for key, entries in spec.items():
        if key.startswith('_'): continue
        global_bin = (bytearray(MG.bin), copy.deepcopy(MG.j))
        write_set(entries, os.path.join(outdir, f'{MAG["set_prefix"]}_{key}.glb'), probe)
        MG.bin, MG.j = global_bin
