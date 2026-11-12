"""Numeric checks of the top-magazine reload arm clips; no Blender.
usage: checks.py [clips dir] [--guns id,id] [--bodies pma,pwa] [--raised dir] [--all] [--json out.json] [--jobs n]
clips dir holds <body>/<clip>.glb (default: weapons.json paths clips). Clips of disabled top-magazine guns (Borg)
are skipped. Prints one line per check: pass or FAIL, the worst value, the threshold, the worst item.
--all also prints every failing item.

run(clips_dir, guns=None, bodies=None, thresholds=None) -> [{check, item, value, threshold, unit, ok, note}]
An item is <body>/<clip>[:<gun>]. Each clip is measured with every gun of this build that plays it: a long clip with
the guns whose long_partner it is, a category clip with the guns of that partner category, a clip without category
with the gun the pick was made with (Saratoga), a pair with the top-magazine gun in both hands.

Checks (THRESHOLDS holds name, default, unit, source):
  clip_frames      number of keys of the clip (a length the game resamples breaks the timing)
  const_quat_w     constant rotation tracks with w < 0 that are not the game template's own (the importer
                   mis-encoded a w < 0 constant track of the lowered clips; the template's tracks come from the game)
  hand_on_gun      largest move of a hand relative to its gun, against the template's first frame
  contact_miss     gap between the striking gun (with the hand on it) and the seated magazine at the hit frame
  contact_depth    depth of the striking gun inside the magazine box at the hit frame
  hands_gap        smallest distance between the two hands around the hit
  wrist            largest wrist bend while the guns are in view
  hidden           frames of the hidden window (down..seated) with a gun vertex inside the view
  hidden_speed     fastest move of a gun in the held part of the clip (hold_start..hold_end)
  eye_distance     smallest distance from the eye to the partner gun over the clip
  face_cover       long partners: peak share of the view covered by the gun, over the reference gun's clip"""
import os, sys, json, hashlib
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common, manifest

REF_LONG = 'carnage'     # the long picks were made with it; face_cover compares against its clip
REF_SMG = 'saratoga'     # the single picks were made with it
TAPS = {'doubletap': [15]}   # extra contact frames of a pick, before the hit frame

# name: (default, unit, kind, source). kind: max = value must be <= threshold, min = value must be >= threshold.
# "baseline" = no documented limit: the default is the worst value of the shipped clips (2026-11-11), rounded out.
THRESHOLDS = {
    'clip_frames': (None, 'frames', 'eq', 'weapons.json topmag.frames.length'),
    'const_quat_w': (0, 'tracks', 'max', 'lowered NOTES.md: a w < 0 constant track was mis-encoded'),
    'hand_on_gun_cm': (0.1, 'cm', 'max', 'baseline; README end pose fix: hands and guns unchanged (0.04 cm)'),
    'contact_miss_long_cm': (1.0, 'cm', 'max', 'BRIEF_LONG2.md 2: miss < 1 cm'),
    'contact_depth_long_cm': (0.5, 'cm', 'max', 'BRIEF_LONG2.md 2: interpenetration a few mm at most'),
    'contact_miss_smg_cm': (2.0, 'cm', 'max', 'BRIEF.md: < 2 cm miss at f25; categories.json max residual 1.7 cm'),
    'contact_depth_smg_cm': (1.7, 'cm', 'max', 'categories.json max residual 1.7 cm'),
    'contact_miss_pair_cm': (2.0, 'cm', 'max', 'BRIEF.md: < 2 cm miss at f25'),
    'contact_depth_pair_cm': (0.9, 'cm', 'max', 'baseline (shipped worst 0.87)'),
    'hands_gap_cm': (0.1, 'cm', 'min', 'baseline (shipped worst 0.12); axe checks_*.json hands_gap 1.4 to 6.0 cm'),
    'wrist_deg': (113.0, 'deg', 'max', 'baseline (shipped worst 112.4); hang results.json wrist 107 to 112 deg'),
    'hidden_frames': (0, 'frames', 'max', 'BRIEF.md: both guns fully out of view f46 to f62'),
    'hidden_speed_cm': (0.1, 'cm/frame', 'max', 'baseline; BRIEF_LONG2.md 2: nearly still; axe checks hide_speed 0.02'),
    'eye_long_cm': (20.0, 'cm', 'min', 'BRIEF_LONG.md 1, BRIEF_LONG2.md 2: eye clearance >= 20 cm, all frames'),
    'eye_smg_cm': (5.0, 'cm', 'min', 'partner tables (data/table_*.json): eye 5.2 cm and up before the category bumps'),
    'face_cover_pts': (3.0, 'points', 'max', 'BRIEF_LONG2.md 2: coverage not above the Carnage version by more than 3 points'),
}


def defaults():
    return {k: v[0] for k, v in THRESHOLDS.items()}


def top_guns():
    """{clip name: gun} of the enabled top-magazine guns"""
    return {name: g for name, _, _, g in manifest.topmag_guns()}


def parse(name, tops):
    """clip file stem -> dict(kind long|smg|pair, top, side, pick, tag) or None for a clip that is not built"""
    codes = {g['topmag']['pair_code']: n for n, g in tops.items()}
    p = name.split('_')
    if p[0] == 'pair':
        if len(p) != 3 or any(c not in codes for c in p[1]):
            return None
        return dict(kind='pair', top=codes[p[1][0]], other=codes[p[1][1]], side='left', pick=p[2], tag=None)
    if p[0] not in tops or len(p) < 3:
        return None
    tag = '_'.join(p[3:]) or None
    long = set(manifest.long_partners().values())
    return dict(kind='long' if tag in long else 'smg', top=p[0], side=p[1], pick=p[2], tag=tag)


def clip_guns(c):
    """ids of the guns that play the clip in this build"""
    if c['kind'] == 'pair':
        return [c['other']]
    if c['kind'] == 'long':
        out = [g['id'] for g in manifest.guns() if g.get('long_partner') == c['tag'] and g.get('mesh')]
        return sorted(out, key=lambda i: i != c['tag'])
    if c['tag'] is None:
        return [REF_SMG]
    i = manifest.PICKS.index(c['pick']) if c['pick'] in manifest.PICKS else None
    out = []
    for g in manifest.guns():
        row = (g.get('partner') or {}).get(c['top'])
        # a gun with a long partner set never plays the size-category clips (topmagsets.py builds those only for
        # partners without one)
        if row and i is not None and row[i] == c['tag'] and not g.get('long_partner') and has_mesh(g['id']):
            out.append(g['id'])
    return out


def has_mesh(gun):
    import geo
    try:
        return all(common.find('weapon_meshes', p + '.glb') for p in geo.parts(gun))
    except (KeyError, TypeError, SystemExit):
        return False


# ---- one clip ------------------------------------------------------------------------------------------------------
_FK = {}
_TREE = {}


def eye_tree(gun):
    """nearest-vertex search over a gun's vertices (gun-local)"""
    import geo
    from scipy.spatial import cKDTree
    if gun not in _TREE:
        _TREE[gun] = cKDTree(geo.load(gun)['all'])
    return _TREE[gun]


def fk(path):
    """per frame model space transforms of the arm and weapon joints, and the clip's raw tracks"""
    from glb import Glb
    from fk import Clip
    key = hashlib.md5(open(path, 'rb').read()).hexdigest()
    if key not in _FK:
        g = Glb(path); name = g.j['animations'][0]['name']; c = Clip(g, name)
        want = [f'{S}{j}' for S in ('Left', 'Right') for j in ('Arm', 'ForeArm', 'Hand')] + ['WeaponLeft', 'WeaponRight']
        ix = {n: g.names.index(n) for n in want}
        W = []
        for f in range(c.frames):
            w = c.world(f); W.append({n: w[i] for n, i in ix.items()})
        _FK[key] = (W, c.tr, c.frames)
    return _FK[key]


def measure(job):
    """rows of one clip file. job: (path, body, name, clip dict, guns, thresholds)"""
    path, body, name, c, guns, th = job
    import geo
    from geo import M4, app, box_signed, mag_local, hand, EYES
    from fk import qmul, qinv
    from scipy.spatial import cKDTree
    rows = []
    fr = common.gun(c['top'])['topmag']['frames']

    def row(check, key, value, gun=None, note=''):
        d, unit, kind, src = THRESHOLDS[key]
        t = th.get(key, d)
        if t is None:
            t = fr['length']
        if value is None:
            ok = False
        elif kind == 'max': ok = value <= t + 1e-9
        elif kind == 'min': ok = value >= t - 1e-9
        else: ok = value == t
        if src.startswith('baseline'):
            note = (note + '; ' if note else '') + 'baseline'
        rows.append({'check': check, 'item': f'{body}/{name}' + (f':{gun}' if gun else ''), 'value': value,
                     'threshold': t, 'unit': unit, 'ok': bool(ok), 'note': note})

    W, tr, N = fk(path)
    hit, down, seated = fr.get('hit', 25), fr['down'], fr['seated']
    sh, st = geo.SIDES[c['side']]
    G = {S: [M4(*W[f][f'Weapon{S}']) for f in range(N)] for S in ('Left', 'Right')}
    eye = EYES[body]

    # clip_frames, const_quat_w
    step = [float(np.abs(np.diff(t) - 1 / float(manifest.load()['reload_clip']['fps'])).max()) for (t, v) in tr.values() if len(t) > 1]
    row('clip_frames', 'clip_frames', N, note='' if not step or max(step) < 1e-4 else f'uneven key times ({max(step):.4f} s)')
    names, tc, rest = geo.template(body)
    cw = [n for (n, p), (t, v) in tr.items() if p == 'rotation' and v[0][3] < 0 and np.abs(v - v[0]).max() < 1e-7]
    own = [n for n in cw if np.abs(tr[(n, 'rotation')][1][0] - np.float32(tc.local(names.index(n), 0)[1])).max() > 1e-6]
    row('const_quat_w', 'const_quat_w', len(own), note=f'{len(cw)} constant w < 0 tracks, {len(cw) - len(own)} from the template' + (': ' + ' '.join(own[:4]) if own else ''))

    # hand_on_gun, wrist: against the template's first frame
    ri = {n: rest[names.index(n)] for n in W[0]}
    drift = 0.0; wrist = (0.0, 0, '')
    view = [f for f in range(N) if f < down or f > seated]
    for S in ('Left', 'Right'):
        g0 = M4(*ri[f'Weapon{S}']); h0 = np.linalg.inv(g0) @ M4(*ri[f'{S}Hand'])
        hq0, fq0 = ri[f'{S}Hand'][1], ri[f'{S}ForeArm'][1]
        for f in range(N):
            hp, hq = W[f][f'{S}Hand']; ep, fq = W[f][f'{S}ForeArm']
            h = np.linalg.inv(G[S][f]) @ M4(hp, hq)
            drift = max(drift, float(np.linalg.norm(h[:3, 3] - h0[:3, 3])), float(np.abs(h[:3, :3] - h0[:3, :3]).max()) * 0.1)
            if f in view:
                uf = (hp - ep) / np.linalg.norm(hp - ep)
                rel = qmul(hq, qinv(qmul(fq, qmul(qinv(fq0), hq0))))
                sw = 2 * np.degrees(np.arccos(min(1.0, np.sqrt(rel[3] ** 2 + np.dot(rel[:3], uf) ** 2))))
                if sw > wrist[0]: wrist = (float(sw), f, S)
    row('hand_on_gun', 'hand_on_gun_cm', round(drift * 100, 3))
    row('wrist', 'wrist_deg', round(wrist[0], 1), note=f'{wrist[2]} f{wrist[1]}')

    # hands_gap: around every contact frame
    HL, HR = hand(body, 'Left'), hand(body, 'Right')
    cf = TAPS.get(c['pick'], []) + [hit]
    gap = (9.0, 0)
    for f in sorted({f for k in cf for f in range(k - 3, k + 4)}):
        d = float(cKDTree(app(G['Left'][f], HL)).query(app(G['Right'][f], HR))[0].min())
        if d < gap[0]: gap = (d, f)
    row('hands_gap', 'hands_gap_cm', round(gap[0] * 100, 2), note=f'f{gap[1]}')

    # speed of the gun origins in the held part
    sp = max(float(np.linalg.norm(G[S][f + 1][:3, 3] - G[S][f][:3, 3])) for S in ('Left', 'Right')
             for f in range(fr['hold_start'], fr['hold_end']))
    if not c.get('raised_copy'):   # a raised copy eases into its raised pose while hidden, by design (area raised)
        row('hidden_speed', 'hidden_speed_cm', round(sp * 100, 3))

    TOP = geo.load(c['top'])['all']
    kind = c['kind']
    pairs = [(sh, st), (st, sh)] if kind == 'pair' else [(sh, st)]
    for gun in guns:
        V = geo.load(gun)['all']
        # contact at the hit frame(s): striking gun and its hand against the seated magazine of the other gun
        for a, b in pairs:
            P = np.vstack([V, hand(body, b)]); worst = None
            for k in cf:
                d = float(box_signed(app(np.linalg.inv(G[a][k] @ mag_local(min(k, hit))) @ G[b][k], P)).max()) * 100
                if worst is None or abs(d) > abs(worst[0]): worst = (d, k)
            tag = gun if kind != 'pair' else f'{b}_hits_{a}'
            row('contact_miss', f'contact_miss_{kind}_cm', round(max(0.0, -worst[0]), 2), tag, f'f{worst[1]}')
            row('contact_depth', f'contact_depth_{kind}_cm', round(max(0.0, worst[0]), 2), tag, f'f{worst[1]}')
        # hidden window: any gun vertex in view
        vis = [f for f in range(down, seated + 1)
               if geo.onscreen(app(G[st][f], V), eye) or geo.onscreen(app(G[sh][f], TOP), eye)]
        row('hidden', 'hidden_frames', len(vis), gun if kind != 'pair' else None, f'visible f{vis[0]}..f{vis[-1]}' if vis else '')
        # eye distance over the clip
        tree = eye_tree(gun)
        e = tree.query(np.array([app(np.linalg.inv(G[st][f]), eye[None])[0] for f in range(N)]))[0]
        if kind == 'pair':
            e = np.minimum(e, tree.query(np.array([app(np.linalg.inv(G[sh][f]), eye[None])[0] for f in range(N)]))[0])
        k = int(np.argmin(e))
        row('eye_distance', 'eye_long_cm' if kind == 'long' else 'eye_smg_cm', round(float(e[k]) * 100, 1), gun if kind != 'pair' else None,
            f'f{k}')
        # long partners: peak view coverage; turned into face_cover (over the reference gun) by run()
        if kind == 'long':
            Vt, T = geo.tris(gun)
            cov = {f: geo.coverage(app(G[st][f], Vt), T, eye) for f in view[::2] if geo.onscreen(app(G[st][f], Vt), eye)}
            pk = max(cov, key=cov.get) if cov else 0
            for f in (pk - 1, pk + 1):
                if f in view and f not in cov: cov[f] = geo.coverage(app(G[st][f], Vt), T, eye)
            pk = max(cov, key=cov.get) if cov else 0
            rows.append({'check': '_cover', 'item': f'{body}/{name}:{gun}', 'value': round(cov.get(pk, 0.0) * 100, 2),
                         'note': f'f{pk}', 'key': (body, c['side'], c['pick']), 'gun': gun, 'tag': c['tag']})
    return rows


def raised_pose(gun, c):
    """raised pose whose copy of clip c this gun plays, or None (a gun without a model variable of its own plays the
    sets of the gun whose variable it uses: for a long clip, its long partner)"""
    poses = manifest.raised_poses()
    g = common.gun(gun)
    vs = manifest.gun_vars(g) or (manifest.gun_vars(common.gun(c['tag'])) if c['kind'] == 'long' else [])
    return next((poses[v] for v in vs if v in poses), None)


def run(clips_dir, guns=None, bodies=None, thresholds=None, jobs=None, raised=None):
    """Check every built clip under clips_dir (<body>/<clip>.glb). guns: gun ids to keep (default all of this build),
    bodies: default all, thresholds: {name: value} over THRESHOLDS. raised: folder of the raised partner copies
    (<raised>/<body>/topmag/<clip>__<pose>.glb); a gun with a raised pose is then measured on its copy where it exists
    (item <clip>__<pose>:<gun>). Returns a list of dicts
    {'check', 'item', 'value', 'threshold', 'unit', 'ok', 'note'}."""
    th = defaults(); th.update(thresholds or {})
    tops = top_guns()
    clips_dir = clips_dir.replace('\\', '/')
    todo = []
    for body in (bodies or common.BODIES):
        d = f'{clips_dir}/{body}'
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.glb'):
                continue
            c = parse(fn[:-4], tops)
            if not c:
                continue
            gl = [g for g in clip_guns(c) if not guns or g in guns or c['kind'] == 'pair'
                  or (c['kind'] == 'long' and c['tag'] == REF_LONG == g)]   # face_cover compares with it
            if guns and c['kind'] == 'pair' and c['other'] not in guns:
                gl = []
            if gl and raised:
                # a partner with a raised pose plays the build's copy of the clip (raised/rmakeclips.py), not the clip
                rest = []
                for g in gl:
                    pose = raised_pose(g, c)
                    cp = f'{raised}/{body}/topmag/{fn[:-4]}__{pose}.glb' if pose else None
                    if cp and os.path.exists(cp):
                        todo.append((cp, body, f'{fn[:-4]}__{pose}', dict(c, raised_copy=pose), [g], th))
                    else:
                        rest.append(g)
                gl = rest
            if gl:
                todo.append((f'{d}/{fn}', body, fn[:-4], c, gl, th))
        # face_cover needs the reference gun's own clips: take the shipped ones when this folder has none
        want = {(t[3]['top'], t[3]['side'], t[3]['pick']) for t in todo if t[1] == body and t[3]['kind'] == 'long'}
        for top, side, pick in sorted(want):
            fn = f'{top}_{side}_{pick}_{REF_LONG}.glb'
            ref = f'{common.path("clips")}/{body}/{fn}'
            if not os.path.exists(f'{d}/{fn}') and os.path.exists(ref):
                todo.append((ref, body, fn[:-4], parse(fn[:-4], tops), [REF_LONG], th))
    jobs = jobs or min(8, os.cpu_count() or 1)
    if jobs > 1 and len(todo) > 1:
        from multiprocessing import Pool
        with Pool(min(jobs, len(todo))) as pool:
            res = pool.map(measure, todo, chunksize=1)
    else:
        res = [measure(t) for t in todo]
    rows = [r for rs in res for r in rs]
    # face_cover: peak coverage minus the reference gun's clip of the same body, hand and pick
    cov = [r for r in rows if r['check'] == '_cover']; rows = [r for r in rows if r['check'] != '_cover']
    ref = {r['key']: r['value'] for r in cov if r['gun'] == REF_LONG and r['tag'] == REF_LONG}
    t = th['face_cover_pts']
    for r in cov:
        base = ref.get(r['key'])
        v = None if base is None else round(r['value'] - base, 2)
        rows.append({'check': 'face_cover', 'item': r['item'], 'value': v, 'threshold': t, 'unit': 'points',
                     'ok': v is not None and v <= t + 1e-9,
                     'note': f'peak {r["value"]} % at {r["note"]}' + (f', {REF_LONG} {base} %' if base is not None else f', no {REF_LONG} clip to compare')})
    return rows


KIND = {'clip_frames': 'eq', 'hands_gap': 'min', 'eye_distance': 'min'}   # others: max


def summary(rows):
    """[(check, threshold, unit, ok, worst row, failing count, count)] per check and threshold"""
    groups = {}
    for r in rows:
        groups.setdefault((r['check'], r['threshold'], r['unit']), []).append(r)
    out = []
    for (check, t, unit), rs in groups.items():
        vals = [r for r in rs if r['value'] is not None]
        kind = KIND.get(check, 'max')
        worst = (min if kind == 'min' else max)(vals, key=lambda r: r['value']) if vals else rs[0]
        if kind == 'eq':
            worst = next((r for r in rs if not r['ok']), rs[0])
        out.append((check, t, unit, all(r['ok'] for r in rs), worst, sum(not r['ok'] for r in rs), len(rs)))
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    guns = common.opt(a, '--guns'); bodies = common.opt(a, '--bodies'); out = common.opt(a, '--json')
    raised = common.opt(a, '--raised')
    jobs = common.opt(a, '--jobs')
    show = '--all' in a
    a = [x for x in a if not x.startswith('--')]
    d = a[0] if a else common.path('clips')
    rows = run(d, guns.split(',') if guns else None, bodies.split(',') if bodies else None, jobs=int(jobs) if jobs else None,
               raised=raised)
    if out:
        json.dump(rows, open(out, 'w'), indent=1)
    bad = 0
    for check, t, unit, ok, w, nf, n in sorted(summary(rows), key=lambda s: s[0]):
        bad += not ok
        print(f'{"pass" if ok else "FAIL"} {check:14s} worst {w["value"]} {unit} (threshold {t}) {w["item"]} {w["note"]}'
              + (f' [{nf} of {n} fail]' if nf else f' [{n}]'))
    if show:
        for r in rows:
            if not r['ok']:
                print(f'  FAIL {r["check"]:14s} {r["item"]:52s} {r["value"]} {r["unit"]} (threshold {r["threshold"]}) {r["note"]}')
    sys.exit(1 if bad else 0)
