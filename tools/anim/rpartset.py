"""Gun part sets for the shell-fed shotguns' own reload clips (tube: Carnage, Tactician): the gun's moving parts and
shells as the approved drafts show them, in the same six slots as the arm set, so the weapon plays them in sync
with the arm clip (as rmagset2.py does for the SMG magazines).

Two sets per gun, body and hand, each a copy of a game set with the clips replaced:
  barrel set  (the gun's base1 set, component Barrel): the pump joints posed from the gun's own empty reload at the
              draft's part frame (spec _part_frames: the frame whose fore-end travel equals the draft's _pump_cm, as
              the draft previews posed it). Pump joints: those the gun's clip moves over the stroke the part frames
              cover. Every other joint holds its rest (idle) pose.
  shell set   (the gun's mag_std set, components Magazine and MagazineReload): the draft's shells (_objects.json,
              mesh matrix per frame in gun axes, null where not drawn) on the two shell joints the gun has
              (`magazine`, mesh mag_std, float track 0; `magazine_reload`, mesh mag_stdr, track 1).
Shell rules (two meshes for up to four drafted shells):
  - per frame at most two shells (per barrel on break-open guns): the spent (or live) shell first, then by the length
    of the run of frames over which the shell keeps its gun-axes matrix (a shell riding the gun before one waiting in a
    world-fixed rig), then draft order. A shell left out is reported (frames outside the hidden
    window count as a miss).
  - a shell keeps its joint while drawn; the spent shell starts on `magazine` (the idle's joint).
  - hand-back (the 2026-11-15 rule of rmagset2.roles): the clip ends as the idle shows, `magazine` at the idle's
    matrix (the game's empty reload's last frame: the shell in the chamber, where the drafts' spent shell starts) and shown, `magazine_reload` hidden. From the first frame of the hidden
    window where `magazine` is free, a shell drawn to the end moves onto it; if none is, `magazine` shows at the
    idle matrix from there.
  - a hidden joint sits at the next matrix it shows (else the last, else the idle) with scale 0.001; its float
    track is 0. Float tracks per frame, held to the last key (glb.fit_track_keys).
Idle items (the quick-drop fallback slots): every joint at its idle for the given key count.

usage: rpartset.py <base1 set glb> <mag set glb or -> <mag_std mesh glb or -> <out barrel glb> <out shell glb or ->
                   <spec json>=<clip name>:<keys>:<hide_start>:<hide_end> | idle=<clip name>:<keys> [...] [--report <json>]
check(): rebuilds every frame from the written keys: shell mesh matrices against the draft (cm, deg), pump travel
against _pump_cm (cm), last frame against the idle (cm, deg), float keys per track.
"""
import sys, os, json, copy, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'authoring', 'reload'))
from glb import Glb, fit_track_keys
from rmagset import m4, quat
from rmagset2 import bind_world, node_local

FPS = 30.0; SMALL = 0.001; EPS = 1e-6


def mat(row): return np.array(row, float).reshape(4, 4)


def rest_local(g, i):
    n = g.j['nodes'][i]; return np.array(n.get('translation', [0, 0, 0]), float), np.array(n.get('rotation', [0, 0, 0, 1]), float)


def pump_joints(gb, clip, pf):
    """Joints the gun's clip moves between the part frames' lowest and highest frame."""
    from wclip import TClip
    c = TClip(gb, clip); a, b = min(pf), max(pf); out = []
    fr = np.linspace(a, b, max(int((b - a) * 4) + 2, 2))
    for i, n in enumerate(gb.names):
        if n == 'Armature': continue
        T = np.array([c.local(i, f / FPS)[0] for f in fr]); Q = np.array([c.local(i, f / FPS)[1] for f in fr])
        if np.ptp(T, axis=0).max() > 1e-4 or np.ptp(Q, axis=0).max() > 1e-4: out.append(n)
    return out


# Shell joint pairs of the gun's mag_std rig: (old joint, its mesh leaf, reload joint, its mesh leaf, float tracks, the
# joint name the drafts key their shells by (None: one pair, shells not keyed)). The float tracks follow the rig's
# trackNames (showMagazine, showMagazineReload; break-open: Left, ReloadLeft, Right, ReloadRight).
PAIRS = {
    'magazine': [('magazine', 'mag_std', None, 'mag_stdr', (0, 1), None)],
    'left_magazine': [('left_magazine', 'left_mag_std', 'left_magazine_reload', 'left_mag_stdr', (0, 1), 'left_mag_std'),
                      ('right_magazine', 'right_mag_std', 'right_magazine_reload', 'right_mag_stdr', (2, 3), 'right_mag_std')],
    'l_bullet': [('l_bullet', 'l_bullet', 'l_bullet_reload', 'l_bullet_reload', (0, 1), 'l_bullet'),
                 ('r_bullet', 'r_bullet', 'r_bullet_reload', 'r_bullet_reload', (2, 3), 'r_bullet')],
}


class Rig:
    """The shell set's joints, per pair: mesh to joint as rmagset2 (W(joint) = inv(SLOT) M inv(IBM) inv(leaf local));
    the old joint's IBM from the mesh glb (its skin joint of that name, else its first), the reload joint's derived from
    the rig's bind pose so both meshes coincide at their binds."""
    def __init__(self, mag_glb, base_glb, mesh_glb):
        from wclip import TClip
        self.g = Glb(mag_glb); gb = Glb(base_glb); an = [a['name'] for a in gb.j['animations']]
        self.SLOT = m4(*TClip(gb, 'reload' if 'reload' in an else an[0]).world(0)[gb.names.index('mag_slot')])
        sk = Glb(mesh_glb); s = sk.j['skins'][0]; sj = [sk.names[x] for x in s['joints']]
        ibms = np.asarray(sk.acc(s['inverseBindMatrices']), float).reshape(-1, 4, 4)
        names = self.g.names; self.ix = {n: i for i, n in enumerate(names)}; B, self.par = bind_world(self.g)
        key = next(k for k in PAIRS if k in names)
        an2 = [a['name'] for a in self.g.j['animations']]
        self.c0 = TClip(self.g, 'reload' if 'reload' in an2 else an2[0])
        ce = TClip(self.g, 'empty_reload' if 'empty_reload' in an2 else an2[0]); WE = ce.wf(ce.frames - 1)
        self.pairs = []; self.LL = {}; self.IB = {}; self.TRK = {}; self.S = {}
        for a, aleaf, b, bleaf, trk, src in PAIRS[key]:
            if b is None: b = 'magazine_reload' if 'magazine_reload' in names else 'reload_magazine'
            k0 = sj.index(src) if src in sj else 0; IBM = ibms[k0].T; leaf = sj[k0] if src is None else aleaf
            self.LL[a] = m4(*node_local(self.g, self.ix[leaf])) if leaf != a else np.eye(4)
            self.LL[b] = m4(*node_local(self.g, self.ix[bleaf])) if bleaf != b else np.eye(4)
            self.IB[a] = IBM; self.IB[b] = np.linalg.inv(B[self.ix[bleaf]]) @ B[self.ix[leaf]] @ IBM
            self.TRK[a], self.TRK[b] = trk
            # the idle shell: the game's empty reload's last frame, the shell in the chamber (its track on), where the
            # drafts' spent shell starts and their chambered shell ends
            self.S[a] = self.SLOT @ m4(*WE[self.ix[a]]) @ self.LL[a] @ self.IB[a]
            self.pairs.append((a, b, src))
        self.ntracks = 2 * len(self.pairs)
        self.P0 = {k: m4(*self.c0.wf(0)[k]) for k in range(len(names))}       # parents (mag_plug) as the game clip's frame 0

    def joint_world(self, j, M):
        return np.linalg.inv(self.SLOT) @ M @ np.linalg.inv(self.IB[j]) @ np.linalg.inv(self.LL[j])

    def mesh(self, j, Wj):
        return self.SLOT @ Wj @ self.LL[j] @ self.IB[j]

    def objects(self, objs, src):
        """The drafted shells of one pair: {names, joints: {name: rows}}."""
        if objs is None: return {'names': [], 'joints': {}}
        if src is None: return objs
        J = {n: objs['joints'][n][src] for n in objs['names'] if isinstance(objs['joints'][n], dict) and src in objs['joints'][n]}
        return {'names': [n for n in objs['names'] if n in J], 'joints': J}

    def plan(self, objs, n, hide):
        """Per frame {joint: (matrix, shown)} over every pair, per pair {joint: object} per frame, and reports."""
        per = [dict() for _ in range(n)]; on = {}; reps = {}
        for a, b, src in self.pairs:
            o = self.objects(objs, src)
            if not o['names']:       # no drafted shell on this pair: the idle throughout
                p = [{a: (self.S[a], True), b: (self.S[a], False)} for _ in range(n)]; q = [dict() for _ in range(n)]; r = {'idle': True}
            else:
                p, q, r = plan_shells(o, n, hide, self.S[a], a, b)
            for f in range(n): per[f].update(p[f])
            on[(a, b)] = (q, o); reps[a] = r
        return per, on, reps


def plan_shells(objs, n, hide, S, A, B2):
    """Per frame {joint: (matrix, shown)} for both shell joints, and a report."""
    names = objs['names']; J = objs['joints']
    row = lambda o, f: (J[o][f] if f < len(J[o]) else None)
    def runs(o):
        # per frame, the length of the run of frames with the same gun-axes matrix: long for a shell riding the gun,
        # short for one waiting in a world-fixed rig (it moves in gun axes whenever the gun moves)
        same = [f > 0 and row(o, f) is not None and row(o, f - 1) is not None and np.abs(np.array(row(o, f)) - np.array(row(o, f - 1))).max() < EPS for f in range(n)]
        out = [0] * n; f = 0
        while f < n:
            g = f + 1
            while g < n and same[g]: g += 1
            for h in range(f, g): out[h] = g - f
            f = g
        return out
    run = {o: runs(o) for o in names}
    pick = []; dropped = []
    for f in range(n):
        pres = [o for o in names if row(o, f) is not None]
        pres.sort(key=lambda o: (0 if o in ('spent', 'live') else 1, -run[o][f], names.index(o)))
        pick.append(pres[:2])
        for o in pres[2:]: dropped.append((o, f))
    on = [dict() for _ in range(n)]          # joint -> object
    for f in range(n):
        prev = on[f - 1] if f else {}
        for j, o in prev.items():
            if o in pick[f]: on[f][j] = o
        for o in pick[f]:
            if o in on[f].values(): continue
            j = A if A not in on[f] else B2
            on[f][j] = o
    # hand-back: from the first free frame of `magazine` in the hidden window
    h0, h1 = hide; hb = next((f for f in range(h0, n) if A not in on[f]), None)
    moved = None
    if hb is not None:
        last = on[n - 1].get(B2)
        if last is not None and all(on[f].get(B2) == last for f in range(hb, n)):
            for f in range(hb, n): on[f][A] = last; del on[f][B2]
            moved = last
    raw = []
    for f in range(n):
        d = {}
        for j in (A, B2):
            o = on[f].get(j); d[j] = (mat(row(o, f)), True) if o else None
        if hb is not None and f >= hb and d[A] is None: d[A] = (S, True)
        raw.append(d)
    # hidden joints: at the next matrix they show, else the last, else the idle
    out = [dict() for _ in range(n)]
    for j in (A, B2):
        for f in range(n):
            if raw[f][j] is not None: out[f][j] = raw[f][j]; continue
            nxt = next((raw[g][j][0] for g in range(f + 1, n) if raw[g][j] is not None), None)
            prv = next((raw[g][j][0] for g in range(f - 1, -1, -1) if raw[g][j] is not None), None)
            out[f][j] = (nxt if nxt is not None else prv if prv is not None else S, False)
    miss = sorted({f for o, f in dropped if not (h0 <= f <= h1)})
    # no hand-back needed when the old joint keeps its shell to the end (the end check compares it with the idle)
    rep = {'hand_back': hb, 'hand_back_in_hidden': (hb is None and A in on[n - 1]) or (hb is not None and h0 <= hb <= h1), 'moved_to_magazine': moved,
           'dropped_frames_in_view': miss, 'dropped': len(dropped),
           'assign': {j: sorted({on[f][j] for f in range(n) if j in on[f]}) for j in (A, B2)}}
    return out, on, rep


def build(base_glb, mag_glb, mesh_glb, out_b, out_m, items):
    from wclip import TClip
    gb = Glb(base_glb); R = Rig(mag_glb, base_glb, mesh_glb) if mag_glb != '-' else None; gm = R.g if R else None
    banims, manims, report = [], [], []
    for spec_path, name, keys, hide in items:
        idle = spec_path == 'idle'
        if idle:
            n = keys; pf = None; pj = []; objs = None
        else:
            # the part frames index the gun's own clip: break-open drafts map their hinge angle on the empty reload's
            # barrel curve (breakgeo.hinge), tube drafts their fore-end travel on _gun_clip's stroke
            sp = json.load(open(spec_path)); n = sp['frames']; pf = sp['_part_frames']; gclip = 'empty_reload' if '_hinge_deg' in sp else sp['_gun_clip']
            pj = pump_joints(gb, gclip, pf); cg = TClip(gb, gclip); objs = json.load(open(sp['_objects'])) if R else None
        # barrel set
        ti = gb.add_acc((np.arange(keys) / FPS).astype(np.float32), 'SCALAR'); samplers, channels = [], []
        for k, nd in enumerate(gb.j['nodes']):
            nm = nd.get('name')
            if nm == 'Armature': continue
            t0, q0 = rest_local(gb, k); T, Q = [], []
            for f in range(keys):
                if nm in pj: t, q = cg.local(k, pf[min(f, n - 1)] / FPS)
                else: t, q = t0, q0
                q = np.asarray(q, float)
                if (Q and np.dot(q, Q[-1]) < 0) or (not Q and q[3] < 0): q = -q
                T.append(t); Q.append(q)
            for path, arr, kind in (('translation', np.array(T, np.float32), 'VEC3'), ('rotation', np.array(Q, np.float32), 'VEC4')):
                samplers.append({'input': ti, 'output': gb.add_acc(arr, kind), 'interpolation': 'LINEAR'}); channels.append({'sampler': len(samplers) - 1, 'target': {'node': k, 'path': path}})
        van = next((a for a in gb.j['animations'] if a['name'] == name), None) or next((a for a in gb.j['animations'] if a['name'] in ('reload', 'empty_reload')), gb.j['animations'][0])
        ex = copy.deepcopy(van.get('extras', {})); ex.pop('trackKeys', None); ex.pop('constTrackKeys', None)
        ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
        banims.append({'name': name, 'samplers': samplers, 'channels': channels, 'extras': ex})
        # shell set
        rep = {'idle': idle}
        if R:
            per, _, reps = R.plan(None if idle else objs, n, hide)
            rep = {**(reps[R.pairs[0][0]] if len(reps) == 1 else {}), 'pairs': reps, 'idle': idle}
            rep['hand_back_in_hidden'] = all(x.get('hand_back_in_hidden', True) for x in reps.values())
            rep['dropped_frames_in_view'] = sorted({f for x in reps.values() for f in x.get('dropped_frames_in_view', [])})
            manims.append(shell_anim(R, gm, name, keys, n, per))
        rep.update({'name': name, 'spec': os.path.basename(spec_path), 'frames': n, 'keys': keys, 'part_joints': pj, 'hide': hide})
        report.append(rep); print(f"{name:16s} <- {os.path.basename(spec_path)} ({n} frames, {keys} keys, parts {pj}, hand-back f{rep.get('hand_back')})")
    gb.j['animations'] = banims; gb.save(out_b)
    if R: gm.j['animations'] = manims; gm.save(out_m)
    print('saved', out_b, out_m)
    return report


def shell_anim(R, gm, name, keys, n, per):
    if True:
        ti = gm.add_acc((np.arange(keys) / FPS).astype(np.float32), 'SCALAR'); samplers, channels = [], []; vis = {i: [] for i in range(R.ntracks)}
        for k, nd in enumerate(gm.j['nodes']):
            nm = nd.get('name')
            if nm == 'Armature': continue
            T, Q, Sc = [], [], []
            for f in range(keys):
                fc = min(f, n - 1)
                if nm in R.TRK:
                    M, on = per[fc][nm]; Wj = R.joint_world(nm, M); P = R.P0[R.par[k]] if k in R.par else np.eye(4)
                    L = np.linalg.inv(P) @ Wj; t, q = L[:3, 3], quat(L[:3, :3]); sc = 1.0 if on else SMALL
                    vis[R.TRK[nm]].append(1 if on else 0)
                else:
                    t, q = R.c0.local(k, 0.0); sc = 1.0
                q = np.asarray(q, float)
                if (Q and np.dot(q, Q[-1]) < 0) or (not Q and q[3] < 0): q = -q
                T.append(t); Q.append(q); Sc.append([sc, sc, sc])
            for path, arr, kind in (('translation', np.array(T, np.float32), 'VEC3'), ('rotation', np.array(Q, np.float32), 'VEC4'), ('scale', np.array(Sc, np.float32), 'VEC3')):
                samplers.append({'input': ti, 'output': gm.add_acc(arr, kind), 'interpolation': 'LINEAR'}); channels.append({'sampler': len(samplers) - 1, 'target': {'node': k, 'path': path}})
        van = next((a for a in gm.j['animations'] if a['name'] == name), None) or next(a for a in gm.j['animations'] if a['name'] == 'reload')
        ex = copy.deepcopy(van.get('extras', {})); ex.pop('constTrackKeys', None)
        pk = [{'trackIndex': i, 'time': round(f / FPS, 6), 'value': vis[i][f]} for f in range(keys) for i in range(R.ntracks)]
        ex['trackKeys'] = fit_track_keys(pk, keys, FPS); ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
        return {'name': name, 'samplers': samplers, 'channels': channels, 'extras': ex}


def rot_deg(Ma, Mb):
    R = Ma[:3, :3] @ Mb[:3, :3].T; return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2))))


def corners(Ma, Mb):
    return max(float(np.linalg.norm((Ma - Mb) @ np.array([x, y, z, 1.0]))) for x in (-0.02, 0.02) for y in (-0.04, 0.04) for z in (-0.02, 0.02)) * 100


def hinge_angle(c, i, t, W0):
    M = m4(*c.world(t)[i]); R = M[:3, :3] @ W0[:3, :3].T
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2))))


def check(base_glb, mag_glb, mesh_glb, out_b, out_m, items):
    """Every frame rebuilt from the written keys against the draft and the idle."""
    from wclip import TClip
    gb0 = Glb(base_glb); R = Rig(mag_glb, base_glb, mesh_glb) if mag_glb != '-' else None; gb = Glb(out_b); gm = Glb(out_m) if R else None; res = []
    for spec_path, name, keys, hide in items:
        cb = TClip(gb, name); r = {'name': name, 'spec': os.path.basename(spec_path), 'float_keys_per_track_equal_keys': True}
        # end = idle: base joints at rest (translation cm, rotation deg)
        eb = max(float(np.linalg.norm(cb.local(k, (keys - 1) / FPS)[0] - rest_local(gb, k)[0])) for k in range(len(gb.names)) if gb.names[k] != 'Armature') * 100
        ed = max(math.degrees(2 * math.acos(min(1.0, abs(float(np.dot(cb.local(k, (keys - 1) / FPS)[1] / np.linalg.norm(cb.local(k, (keys - 1) / FPS)[1]), rest_local(gb, k)[1]))))))
                 for k in range(len(gb.names)) if gb.names[k] != 'Armature')
        r['end'] = {'base_joints_cm': round(eb, 4), 'base_joints_deg': round(ed, 4)}
        if R:
            cm = TClip(gm, name); tk = gm.anim(name)['extras']['trackKeys']
            r['float_keys_per_track_equal_keys'] = all(sum(1 for k in tk if k['trackIndex'] == i) == keys for i in range(R.ntracks))
            fl = {i: [k['value'] for k in sorted(tk, key=lambda k: k['time']) if k['trackIndex'] == i] for i in range(R.ntracks)}
            # per pair: the old joint at the idle matrix and shown, the reload joint hidden (worst over the pairs)
            WL = cm.wf(keys - 1); e = {'magazine_cm': 0.0, 'magazine_deg': 0.0, 'magazine_shown': 1, 'reload_shown': 0}
            for a, b, _ in R.pairs:
                end_m = R.mesh(a, m4(*WL[R.ix[a]]))
                e['magazine_cm'] = max(e['magazine_cm'], round(corners(end_m, R.S[a]), 4)); e['magazine_deg'] = max(e['magazine_deg'], round(rot_deg(end_m, R.S[a]), 4))
                e['magazine_shown'] = min(e['magazine_shown'], fl[R.TRK[a]][-1]); e['reload_shown'] = max(e['reload_shown'], fl[R.TRK[b]][-1])
            r['end'].update(e)
        if spec_path == 'idle':
            res.append(r); continue
        sp = json.load(open(spec_path)); n = sp['frames']
        if R:
            objs = json.load(open(sp['_objects'])); per, ons, _ = R.plan(objs, n, hide); worst_cm = worst_deg = 0.0
            for f in range(n):
                W = cm.wf(f)
                for (a, b), (on, o2) in ons.items():
                    for j, o in on[f].items():
                        Md = mat(o2['joints'][o][f]) if f < len(o2['joints'][o]) and o2['joints'][o][f] is not None else None
                        if Md is None: continue
                        Mr = R.mesh(j, m4(*W[R.ix[j]]))
                        if fl[R.TRK[j]][f] < 0.5: worst_cm = max(worst_cm, 999.0)
                        worst_cm = max(worst_cm, corners(Mr, Md)); worst_deg = max(worst_deg, rot_deg(Mr, Md))
            r['shell_worst_cm'] = round(worst_cm, 4); r['shell_worst_deg'] = round(worst_deg, 4)
        if '_hinge_deg' in sp:
            # barrels: the barrel_hinge angle from its rest against the draft's _hinge_deg
            k = gb.names.index('barrel_hinge'); Wr, _ = bind_world(gb); Wr0 = Wr[k]      # rest world of barrel_hinge (bind)
            dev = max(abs(hinge_angle(cb, k, f / FPS, Wr0) - sp['_hinge_deg'][f]) for f in range(n))
            r['part_joint'] = 'barrel_hinge'; r['part_worst'] = round(dev, 4); r['part_unit'] = 'deg'
        else:
            # pump: travel of the pump joint from its rest against the draft's _pump_cm
            pj = pump_joints(gb0, sp['_gun_clip'], sp['_part_frames']); main = None; dev = 0.0
            if pj:
                trav = {j: max(float(np.linalg.norm(cb.local(gb.names.index(j), f / FPS)[0] - rest_local(gb, gb.names.index(j))[0])) for f in range(n)) for j in pj}
                main = max(trav, key=trav.get); k = gb.names.index(main); t0 = rest_local(gb, k)[0]
                dev = max(abs(float(np.linalg.norm(cb.local(k, f / FPS)[0] - t0)) * 100 - sp['_pump_cm'][f]) for f in range(n))
            r['part_joint'] = main; r['part_worst'] = round(dev, 4); r['part_unit'] = 'cm'
        res.append(r)
    return res


if __name__ == '__main__':
    argv = sys.argv[1:]; rep = None
    if '--report' in argv:
        i = argv.index('--report'); rep = argv[i + 1]; del argv[i:i + 2]
    items = []
    for a in argv[5:]:
        p, rest = a.rsplit('=', 1); parts = rest.split(':')
        hide = (int(parts[2]), int(parts[3])) if len(parts) > 3 else (0, -1)
        items.append((p, parts[0], int(parts[1]), hide))
    r = build(*argv[:5], items)
    if rep:
        chk = check(*argv[:5], items)
        json.dump({'slots': r, 'check': chk}, open(rep, 'w'), indent=1)
        print('worst shell', max(c.get('shell_worst_cm', 0) for c in chk), 'cm, part', max(c.get('part_worst', 0) for c in chk))
