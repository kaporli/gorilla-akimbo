"""SMG magazine set (glb) from the production magazine tracks: rmagset.py for the SMG reloads, where the old magazine
is still falling while the fresh one is already on its rig (track rows m2, s2), so both mesh joints are always used.
One set per gun, body and hand; six clips named as the arm set's slots (reload, reload_01, reload_02,
empty_reload, _01, _02), each with the track of the arm clip in the same slot.

usage: rmagset2.py <vanilla magazine set glb> <weapon set glb with mag_slot> <magazine mesh glb> <out glb>
                   <track json>=<clip name>:<keys>[:<gun map json>] [...]

Joint roles, per clip from the gun's own clip of that kind (its float tracks: track 0 shows the mesh on
`magazine` (mag_std), track 1 the mesh on `magazine_reload` (mag_stdr); inferred in phase 1, consistent on every
gun): the old magazine is on the joint whose mesh shows on frame 0, the fresh one on the other.
  old    rows m (seated, loose, guided, falling) until the fresh one appears, then m2 while it falls; then hidden
  fresh  rows m from the frame it appears (fresh, fresh_move, seated)
A hidden magazine sits at its seat with scale 0.001 and its float track is 0. The float tracks are written per frame
from the track (1 where that mesh shows) and held to the last key (glb.fit_track_keys, the 2026-11-13 fix).
Mesh to joint (as rmagset): W(joint) = inv(SLOT) M inv(IBM) inv(leaf local), the second mesh's bind derived from the
bind pose so the two meshes coincide when both joints are at their bind (IBM2 = inv(B[mag_stdr]) B[mag_std] IBM).
Other joints (mag_plug) keep the gun's own track, time-mapped onto the clip (gun map) when given.
check(): rebuilds every frame's mesh matrix from the written keys and compares it with the track (cm).
"""
import sys, os, json, copy
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'authoring', 'reload'))
from glb import Glb, fit_track_keys
from rmagset import m4, quat

FPS = 30.0; SMALL = 0.001
OLD = ('seated', 'loose', 'guided', 'falling')
NEW = ('fresh', 'fresh_move', 'seated')


def bind_world(g):
    """World matrix of every node in its rest (bind) transform."""
    par = {}
    for i, n in enumerate(g.j['nodes']):
        for c in n.get('children', []): par[c] = i
    W = {}
    def w(i):
        if i in W: return W[i]
        n = g.j['nodes'][i]; L = m4(n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1]))
        W[i] = (w(par[i]) @ L) if i in par else L
        return W[i]
    for i in range(len(g.j['nodes'])): w(i)
    return W, par


def roles(tr):
    """Per frame (old matrix, old shown, fresh matrix, fresh shown) from a track."""
    rows = tr['frames']; r = tr['release']; S = np.array(rows[-1]['m']).reshape(4, 4)
    ap = next((f for f in range(r + 1, len(rows)) if rows[f]['state'] in NEW), len(rows))
    out = []
    for f, row in enumerate(rows):
        m = np.array(row['m']).reshape(4, 4)
        if f < ap: old, os_ = (m, row['s'] > 0.5) if row['state'] in OLD else (S, False); fr, fs = S, False
        else:
            old, os_ = (np.array(row['m2']).reshape(4, 4), row.get('s2', 0) > 0.5) if 'm2' in row else (S, False); fr, fs = m, row['s'] > 0.5
        out.append((old, os_, fr, fs))
    # Hand-back: once the fresh magazine is seated and the old one is gone, it moves to the old magazine's joint (the
    # joint the gun's idle shows) at the same matrix, so the clip ends as the idle starts and the blend into the idle
    # swaps no mesh (a 2-frame flash of the other mesh at the clip's end, Warden, 2026-11-15). Seated comes in the
    # hidden part, so the swap is out of view.
    hb = next((f for f in range(ap, len(rows)) if rows[f]['state'] == 'seated' and not out[f][1]), None)
    if hb is not None:
        for f in range(hb, len(rows)):
            old, os_, fr, fs = out[f]
            out[f] = (fr, fs, S, False)
    return out, ap, hb


def build(vanilla_glb, weapon_glb, mesh_glb, out, items):
    from wclip import TClip
    MG = Glb(vanilla_glb); gw = Glb(weapon_glb); an = [a['name'] for a in gw.j['animations']]
    SLOT = m4(*TClip(gw, 'reload' if 'reload' in an else an[0]).world(0)[gw.names.index('mag_slot')])
    sk = Glb(mesh_glb); s = sk.j['skins'][0]; leaf = sk.names[s['joints'][0]]; IBM = np.asarray(sk.acc(s['inverseBindMatrices']), float).reshape(-1, 4, 4)[0].T
    names = MG.names; ix = {n: i for i, n in enumerate(names)}; B, par = bind_world(MG)
    J2 = 'magazine_reload' if 'magazine_reload' in names else 'reload_magazine'     # Dian, Zhuo: reload_magazine
    IBM2 = np.linalg.inv(B[ix['mag_stdr']]) @ B[ix[leaf]] @ IBM
    LEAF = {'magazine': np.linalg.inv(m4(*node_local(MG, ix[leaf]))), J2: np.linalg.inv(m4(*node_local(MG, ix['mag_stdr'])))}
    IB = {'magazine': IBM, J2: IBM2}; TRK = {'magazine': 0, J2: 1}
    anims = []; report = []
    for track_path, name, keys, gmap in items:
        tr = json.load(open(track_path)); nt = len(tr['frames']); cg = TClip(MG, tr['clip'])
        ex0 = (MG.anim(tr['clip']).get('extras') or {}); k0 = [k for k in ex0.get('trackKeys') or [] if k['time'] == 0]
        shown0 = {k['trackIndex']: k['value'] for k in k0}
        oldj = 'magazine' if shown0.get(0, 0) >= 0.5 else J2; frj = J2 if oldj == 'magazine' else 'magazine'
        R, ap, hb = roles(tr); tracks = {}; vis = {0: [], 1: []}
        for k, node in enumerate(MG.j['nodes']):
            nm = node.get('name')
            if nm == 'Armature': continue
            T, Q, Sc = [], [], []
            for f in range(keys):
                fc = min(f, nt - 1); gf = (gmap[fc] if gmap else min(fc, cg.frames - 1)); t, q = cg.local(k, gf / FPS); sc = 1.0
                if nm in (oldj, frj):
                    old, os_, fr, fs = R[fc]; M, on = (old, os_) if nm == oldj else (fr, fs); sc = 1.0 if on else SMALL
                    if k == ix[oldj]: vis[TRK[oldj]].append(1 if os_ else 0); vis[TRK[frj]].append(1 if fs else 0)
                    Wj = np.linalg.inv(SLOT) @ M @ np.linalg.inv(IB[nm]) @ LEAF[nm]
                    P = m4(*cg.wf(gf)[par[k]]) if k in par else np.eye(4); Lm = np.linalg.inv(P) @ Wj; t, q = Lm[:3, 3], quat(Lm[:3, :3])
                if Q and np.dot(q, Q[-1]) < 0: q = -np.asarray(q)
                T.append(t); Q.append(q); Sc.append([sc, sc, sc])
            tracks[k] = (np.array(T, np.float32), np.array(Q, np.float32), np.array(Sc, np.float32))
        ti = MG.add_acc((np.arange(keys) / FPS).astype(np.float32), 'SCALAR'); samplers, channels = [], []
        for k, (T, Q, Sc) in tracks.items():
            for path, arr, kind in (('translation', T, 'VEC3'), ('rotation', Q, 'VEC4'), ('scale', Sc, 'VEC3')):
                samplers.append({'input': ti, 'output': MG.add_acc(arr, kind), 'interpolation': 'LINEAR'}); channels.append({'sampler': len(samplers) - 1, 'target': {'node': k, 'path': path}})
        van = MG.anim(name) if name in [a['name'] for a in MG.j['animations']] else MG.anim(tr['clip'])
        ex = copy.deepcopy(van.get('extras', {}))
        per = [{'trackIndex': i, 'time': round(f / FPS, 6), 'value': v} for f in range(nt) for i in (0, 1) for v in [vis[i][f]]]
        ex['trackKeys'] = fit_track_keys(per, keys, FPS); ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
        anims.append({'name': name, 'samplers': samplers, 'channels': channels, 'extras': ex})
        rep = {'name': name, 'track': os.path.basename(track_path), 'frames': nt, 'keys': keys, 'old_joint': oldj, 'fresh_joint': frj, 'fresh_from': ap,
               'old_shown': [f for f in range(nt) if vis[TRK[oldj]][f]][-1:], 'hand_back': hb, 'float_keys': len(ex['trackKeys'])}
        report.append(rep); print(f"{name:16s} <- {os.path.basename(track_path)} ({nt} frames, {keys} keys, old on {oldj}, fresh on {frj} from f{ap})")
    MG.j['animations'] = anims; MG.save(out); print('saved', out)
    return report, dict(SLOT=SLOT, IBM=IBM, IBM2=IBM2, leaf=leaf)


def node_local(g, i):
    n = g.j['nodes'][i]; return n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1])


def check(out_glb, weapon_glb, mesh_glb, items):
    """Mesh matrix rebuilt from the written keys (world of the joint x leaf local x IBM, in gun axes) against the track,
    for every frame where that mesh shows; float tracks: one key per frame per track up to the key count, last value held."""
    from wclip import TClip
    g = Glb(out_glb); gw = Glb(weapon_glb); an = [a['name'] for a in gw.j['animations']]
    SLOT = m4(*TClip(gw, 'reload' if 'reload' in an else an[0]).world(0)[gw.names.index('mag_slot')])
    sk = Glb(mesh_glb); s = sk.j['skins'][0]; leaf = sk.names[s['joints'][0]]; IBM = np.asarray(sk.acc(s['inverseBindMatrices']), float).reshape(-1, 4, 4)[0].T
    ix = {n: i for i, n in enumerate(g.names)}; B, par = bind_world(g); names = g.names
    J2 = 'magazine_reload' if 'magazine_reload' in names else 'reload_magazine'; IBM2 = np.linalg.inv(B[ix['mag_stdr']]) @ B[ix[leaf]] @ IBM
    LL = {'magazine': m4(*node_local(g, ix[leaf])), J2: m4(*node_local(g, ix['mag_stdr']))}; IB = {'magazine': IBM, J2: IBM2}
    res = []
    for track_path, name, keys, gmap in items:
        tr = json.load(open(track_path)); R, ap, hb = roles(tr); c = TClip(g, name); worst = 0.0
        a = g.anim(name); tk = a['extras']['trackKeys']; ok_keys = all(sum(1 for k in tk if k['trackIndex'] == i) == keys for i in (0, 1))
        z0 = {k['trackIndex']: k['value'] for k in tk if k['time'] == 0}; oldj = 'magazine' if z0.get(0, 0) >= 0.5 else J2
        for f in range(len(tr['frames'])):
            W = c.wf(f); old, os_, fr, fs = R[f]
            for j, (M, on) in (('magazine', (old, os_) if oldj == 'magazine' else (fr, fs)), (J2, (old, os_) if oldj == J2 else (fr, fs))):
                if not on: continue
                Mr = SLOT @ m4(*W[ix[j]]) @ LL[j] @ IB[j]; cen = np.array([0, 0, 0, 1.0])
                d = max(float(np.linalg.norm((Mr - M) @ np.array([x, y, z, 1.0]))) for x in (-0.03, 0.03) for y in (-0.1, 0.1) for z in (-0.03, 0.03))
                worst = max(worst, d * 100)
        res.append({'name': name, 'worst_cm': round(worst, 4), 'float_keys_per_track_equal_keys': ok_keys, 'last_float': {i: [k['value'] for k in tk if k['trackIndex'] == i][-1] for i in (0, 1)}})
    return res


if __name__ == '__main__':
    # --report <json>: also run check() and write the build and check results there.
    argv = sys.argv[1:]; rep = None
    if '--report' in argv:
        i = argv.index('--report'); rep = argv[i + 1]; del argv[i:i + 2]
    items = []
    for a in argv[4:]:
        p, rest = a.rsplit('=', 1); parts = rest.split(':', 2); gm = json.load(open(parts[2])) if len(parts) > 2 else None
        items.append((p, parts[0], int(parts[1]), gm))
    r, _ = build(argv[0], argv[1], argv[2], argv[3], items)
    if rep:
        chk = check(argv[3], argv[1], argv[2], items)
        json.dump({'slots': r, 'check': chk}, open(rep, 'w'), indent=1)
        print('worst rebuilt mesh error', max(c['worst_cm'] for c in chk), 'cm')
