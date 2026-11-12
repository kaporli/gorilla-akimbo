"""Shared geometry for the dual-wield magazine tracks.

Rig space of the arm clips (glTF): x = V's right, y = up, z = back; the camera looks along -z.
Camera model: fitted in game (eye E, hfov 97, 16:9, no pitch). EYES: the eye points of the arm clip checks, reported
next to E.

The magazine rig, its seated pose and the arm clip reader are the build's (tools/anim/magtrack.py). The clips of a pick,
their bodies and the release frame come from the flight spec; the partner guns of a clip come from weapons.json.
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
import manifest
import magtrack as MT
from glb import Glb
from fk import Clip

HERE = os.path.dirname(os.path.abspath(__file__))
E = np.array([0, 1.605, 0])
EYES = {'pma': np.array([0, 1.693, -0.044]), 'pwa': np.array([0, 1.6947, -0.0372])}
TX = np.tan(np.radians(97 / 2)); TY = TX * 9 / 16
FPS = MT.FPS
NAMES, EMPTY = MT.NAMES, MT.EMPTY
m4, quat = MT.m4, MT.quat
SLOT, MG, G0 = MT.SLOT, MT.MG, MT.G0
MAG = MT.MAG
MAGGUN = next(g for _, _, _, g in manifest.topmag_guns() if 'magazine' in g['topmag'])
FRAMES = MAGGUN['topmag']['frames']            # seated, length, down
# Partner gun geometry by gun id. partner_parts.json: guns the manifest has no parts list for, and mag_rig.
PARTS = json.load(open(os.path.join(HERE, 'partner_parts.json'), encoding='utf-8'))
for _g in manifest.guns(all_=True):
    if _g.get('parts'):
        PARTS[_g['id']] = dict(PARTS.get(_g['id'], {}), parts=_g['parts'])


def app(M, V): return V @ M[:3, :3].T + M[:3, 3]


def wmesh(stem): return common.need(common.find('weapon_meshes', stem + '.glb'))


# ---- the spec ------------------------------------------------------------------------------------------------------
def load_spec(path=None):
    """The flight spec (input of tools/anim/magtrack.py) with absolute clip paths; default: manifest path mag_spec."""
    return manifest.mag_spec(path)


def raw_clips(key, pick, path=None):
    """The clip names of one pick as the spec file writes them (for a new entry of the same pick)."""
    return json.load(open(path or manifest.path('mag_spec'), encoding='utf-8'))[key][pick]['clips']


def spec_keys(spec):
    return [k for k in spec if not k.startswith('_')]


def clip_path(c, clips_dir=None):
    """A spec clip entry as a file. clips_dir: take <body>/<file> from that folder instead."""
    c = c.replace('\\', '/')
    if clips_dir:
        return '/'.join([clips_dir.rstrip('/')] + c.split('/')[-2:])
    return c if os.path.isabs(c) else common.path('clips') + '/' + c


def resolved(spec, clips_dir=None):
    """Copy of the spec with every clip as an existing absolute file (what tools/anim/magtrack.py reads)."""
    out = {}
    for k, v in spec.items():
        out[k] = v if k.startswith('_') else [dict(e, clips=[common.need(clip_path(c, clips_dir)) for c in e['clips']],
                                                   **({'pose_clips': [common.need(clip_path(c, clips_dir)) for c in e['pose_clips']]}
                                                      if 'pose_clips' in e else {}))
                                              for e in v]
    return out


def pick_name(entry):
    """lupper, flip, clap ...: third word of the clip names."""
    return os.path.splitext(os.path.basename(entry['clips'][0]))[0].split('_')[2]


def pick_id(key, entry):
    return f'{key}_{pick_name(entry)}'


def find_pick(spec, name):
    """'<family>_<side>_<pick index or name>' -> (key, pick index)"""
    key, p = name.rsplit('_', 1)
    if key not in spec:
        raise SystemExit(f'spec: no set {key}')
    for i, e in enumerate(spec[key]):
        if p == str(i) or p == pick_name(e):
            return key, i
    raise SystemExit(f'spec: no pick {p} in {key}')


# ---- partner guns of a clip ----------------------------------------------------------------------------------------
_warned = set()


def partner_keys(clip, pick):
    """Gun ids whose geometry the clip is checked against.
    pair_<codes>_<pick>: the magazine gun itself. <gun>_<side>_<pick>_<long partner>: that gun.
    <gun>_<side>_<pick>_<category>: every gun of that partner category for this pick index, without the top-magazine
    guns and the long partners (they have their own clips)."""
    w = os.path.basename(clip)[:-4].split('_')
    if w[0] == 'pair':
        codes = set(w[1])
        if codes != {MAGGUN['topmag']['pair_code']}:
            raise SystemExit(f'{clip}: pair of two different guns is not handled')
        return [MAGGUN['id']]
    suffix = '_'.join(w[3:])
    if suffix in set(manifest.long_partners().values()):
        return [suffix]
    name = MAGGUN['topmag']['clip_name']; keys = []
    for g in manifest.guns():
        row = (g.get('partner') or {}).get(name)
        if not row or row[pick] != suffix or 'topmag' in g or g.get('long_partner'):
            continue
        if g['id'] not in PARTS:
            if g['id'] not in _warned:
                _warned.add(g['id']); print(f'partner_parts.json: no parts for {g["id"]}, skipped', file=sys.stderr)
            continue
        keys.append(g['id'])
    return sorted(keys)


def spec_cases(spec, key, pick, clips_dir=None, bodies=None):
    """[(clip file, body, magazine side, striker side, [partner gun ids])] of one pick."""
    e = spec[key][pick]; side = e['side']; other = 'Right' if side == 'Left' else 'Left'; out = []
    for c in e['clips']:
        p = clip_path(c, clips_dir); body = p.split('/')[-2]
        if bodies and body not in bodies:
            continue
        out.append((common.need(p), body, side, other, partner_keys(p, pick)))
    return out


# ---- the magazine --------------------------------------------------------------------------------------------------
MI = MG.names.index('mag_std')
_mm = Glb(wmesh(os.path.basename(MAG['vanilla_set']).split('.')[0] + '_01'))
IB = _mm.acc(_mm.j['skins'][0]['inverseBindMatrices'])[0].reshape(4, 4).T
MAGV = np.vstack([_mm.acc(p['attributes']['POSITION']) for m in _mm.j['meshes'] for p in m['primitives']])
MAGB = app(IB, MAGV)                      # magazine verts in the mag_std joint frame
LO, HI = MAGB.min(0), MAGB.max(0)
MAGC = (LO + HI) / 2                      # box centre (joint frame)
MAGS = MAGB[::4]                          # vertex subset for visibility / eye tests


def vanilla_G(name, f):
    """gun-local 4x4 of the mag_std joint in the vanilla clip at integer frame f"""
    c = MT.vclip(name); f = max(0, min(int(f), c.frames - 1))
    return SLOT @ m4(*c.world(f)[MI])


def box_signed(P):
    """signed distance of points (mag joint frame) to the magazine box: + inside depth, - outside gap"""
    inside = np.minimum(P - LO, HI - P).min(1)
    out = np.linalg.norm(np.maximum(np.maximum(LO - P, P - HI), 0), axis=1)
    return np.where(inside > 0, inside, -out)


def read_track(g, name):
    """A written set glb read back through FK: gun-local mag_std 4x4 and magazine scale per frame, frame count."""
    c = Clip(g, name); i = g.names.index('mag_std')
    Gs, Ss = [], []
    for f in range(c.frames):
        W = c.world(f); Gs.append(SLOT @ m4(*W[i]))
        Ss.append(float(np.mean(c.tr[('magazine', 'scale')][1][f])))
    return Gs, Ss, c.frames


def set_glb(d, key):
    return f'{d}/{MAG["set_prefix"]}_{key}.glb'


# ---- arm clips -----------------------------------------------------------------------------------------------------
class Arm(MT.Arm):
    def __init__(self, path):
        super().__init__(path); self.path = path


# ---- partner geometry (striker gun-local) --------------------------------------------------------------------------
def tris(parts):
    V, T = [], []; n = 0
    for p in parts:
        g = Glb(wmesh(p))
        for m in g.j['meshes']:
            for pr in m['primitives']:
                v = g.acc(pr['attributes']['POSITION']); i = g.acc(pr['indices']).astype(int).reshape(-1, 3)
                V.append(v); T.append(i + n); n += len(v)
    return np.vstack(V), np.vstack(T)


def dense(V, T, step=0.008, nmax=30):
    """mesh vertices plus samples on every triangle longer than step"""
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    L = np.maximum.reduce([np.linalg.norm(B - A, axis=1), np.linalg.norm(C - A, axis=1), np.linalg.norm(C - B, axis=1)])
    out = [V]
    for n in range(2, nmax):
        m = (L > step * (n - 1)) & (L <= step * n) if n < nmax - 1 else L > step * (n - 1)
        if not m.any(): continue
        uv = np.array([(i / n, j / n) for i in range(n + 1) for j in range(n + 1 - i)])
        a, b, c = A[m], B[m], C[m]
        out.append((a[:, None] + uv[None, :, :1] * (b - a)[:, None] + uv[None, :, 1:] * (c - a)[:, None]).reshape(-1, 3))
    return np.unique(np.round(np.vstack(out), 4), axis=0)


def mag_rest(base):
    """magazine vertices (gun-local) at frame 0 of the gun's reload; empty if the rig or mag animation is unknown"""
    wa = lambda n: common.find('weapon_anims', n)
    mp = next((p for p in (common.find('weapon_meshes', f'{base}__{s}.glb') for s in ('mag_std_01', 'mag_stdr_01')) if p), None)
    if not (mp and wa(base + '__base1.anims.glb') and wa(base + '__mag_std.anims.glb')):
        return np.zeros((0, 3))
    gw = Glb(wa(base + '__base1.anims.glb'))
    if 'mag_slot' not in gw.names and wa(base + '__rcv1.anims.glb'): gw = Glb(wa(base + '__rcv1.anims.glb'))
    if 'mag_slot' not in gw.names: return np.zeros((0, 3))
    an = [a['name'] for a in gw.j['animations']]
    slot = m4(*Clip(gw, 'reload' if 'reload' in an else an[0]).world(0)[gw.names.index('mag_slot')])
    mg = Glb(wa(base + '__mag_std.anims.glb')); W0 = Clip(mg, 'reload').world(0)
    g = Glb(mp); V = np.vstack([g.acc(p['attributes']['POSITION']) for m in g.j['meshes'] for p in m['primitives']])
    sk = g.j['skins'][0]; ibm = g.acc(sk['inverseBindMatrices']); j = g.names[sk['joints'][0]]
    return app(slot @ m4(*W0[mg.names.index(j)]) @ ibm[0].reshape(4, 4).T, V)


_pc = {}


def partner_pts(key):
    """dense surface samples of a partner gun (body parts + its magazine at rest), gun-local"""
    if key not in _pc:
        P = dense(*tris(PARTS[key]['parts']))
        if key == MAGGUN['id']:
            mag = app(G0, MAGB)                       # the magazine gun as partner: its own seated magazine
        else:
            mag = mag_rest(PARTS[key]['mag_rig']) if 'mag_rig' in PARTS[key] else np.zeros((0, 3))
            rm = common.rifle_mag(key) if 'mag_rig' not in PARTS[key] else None
            if rm is not None:
                mag = dense(*rm)                      # a rifle's seated magazine
        _pc[key] = np.vstack([P, mag])
    return _pc[key]


# ---- camera --------------------------------------------------------------------------------------------------------
def onscreen_frac(Pw):
    X = Pw - E; z = -X[:, 2]; ok = z > 0.02
    on = ok & (np.abs(X[:, 0]) < TX * z) & (np.abs(X[:, 1]) < TY * z)
    return on.mean()


def screen(p):
    """1280x720 pixel of a rig-space point"""
    fp = 640 / TX; q = p - E
    return np.array([640 + fp * q[0] / -q[2], 360 - fp * q[1] / -q[2]])
