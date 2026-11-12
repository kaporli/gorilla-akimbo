"""The check gate (tools/anim/build.sh check): numeric checks over the clips the build ships. Each check prints pass or
FAIL with the worst value, its limit and the worst item. Limits are in weapons.json "checks". Exit code 1 on a failure.

usage: gate.py [--guns id,id] [--bodies pma,pwa] [--clips <dir>] [--only area,area] [--with-test]
  --guns    lowered and long-partner checks for these guns only (default: every gun of the build)
  --clips   top-magazine arm clips folder to check instead of paths.clips (<body>/<clip>.glb); the checks of the
            built anim sets are skipped then
  --only    areas: clips (end pose, unchanged frames, frame count), sets (SIMD buffers, frame counts of the built
            sets), lowered, raised (raised pose clips, the reload and top-magazine clips that end in them), topmag,
            magtrack. Not run by default: roundtrip (built sets exported back to glb and
            compared with the glbs they were imported from; one set of each kind, every set with --roundtrip-all).
            A wrongly encoded track (a constant quaternion with w < 0 once was) shows there.
The built sets are read from WORK/sets (build.sh all first). Results also go to WORK/check/report.txt.
"""
import concurrent.futures, hashlib, importlib, json, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import Clip

manifest = common.manifest
AREAS = ('clips', 'sets', 'lowered', 'raised', 'topmag', 'magtrack')   # 'roundtrip' only when named in --only
JOBS = int(os.environ.get('JOBS', '4'))
T = manifest.load()['checks']


def row(check, item, value, threshold, unit, ok, note=''):
    return {'check': check, 'item': item, 'value': value, 'threshold': threshold, 'unit': unit, 'ok': bool(ok), 'note': note}


def work():
    return manifest.path('work') + ('/test' if manifest.with_test() else '')


# ---- which clips ---------------------------------------------------------------------------------------------------
def arm_clips(clips, guns, bodies, picked):
    """[(body, clip glb)] of the top-magazine arm clips the build takes from a clips folder. With --guns: the
    long-partner clips of those guns, the size category clips they use, and the pairs of a top-magazine gun."""
    from topmagsets import plan
    keep = None
    if picked:
        keep = set()
        cats = manifest.partner_categories()
        for g in guns:
            if g.get('long_partner'): keep.add('_' + g['long_partner'] + '.glb')
            for tm, row_ in (g.get('partner') or {}).items():
                keep.update('_' + c + '.glb' for c in row_)
            if 'topmag' in g: keep.add('pair_')
    out = []
    for body, _, files, _ in plan(clips):
        for p, _ in files:
            n = os.path.basename(p)
            if os.path.basename(os.path.dirname(p)) == 'topmag':
                continue   # a raised partner's copy ends in that gun's raised idle: area "raised" checks it
            if body in bodies and (body, p) not in out and (keep is None or any(n.endswith(k) or n.startswith(k) for k in keep)):
                out.append((body, p))
    return out


# ---- clips: end pose, unchanged frames, frame count, quaternions ---------------------------------------------------
def _clip_one(a):
    body, p, pre = a
    sys.path.insert(0, os.path.join(common.HERE, 'endpose'))
    import verify, fix_endpose
    idle = common.idle_glb(body); f0, f1 = fix_endpose.window(p)
    end, frames = verify.end_pose(p, idle)
    anims = Glb(p).j['animations']
    r = {'end': end, 'frames': frames, 'want': f1 + 1, 'clips': len(anims), 'pre': None}
    if pre and os.path.exists(pre):
        o = verify.against_original(pre, p, f0)
        r['pre'] = o['pre']; r['dev'] = o['dev']
    return f'{body}/{os.path.basename(p)}', r


def check_clips(clips, guns, bodies, picked):
    E = T['endpose']
    jobs = [(b, p, f'{manifest.path("clips_pre_endpose")}/{b}/{os.path.basename(p)}') for b, p in arm_clips(clips, guns, bodies, picked)]
    with concurrent.futures.ProcessPoolExecutor(JOBS) as ex:
        res = list(ex.map(_clip_one, jobs))
    rows = []; n = f'{len(res)} clips'
    if not res:
        return [row('clips: top-magazine arm clips found', clips, 0, '> 0', 'clips', False)]
    for side in ('right', 'left', 'body'):
        name = {'right': 'right arm and gun', 'left': 'left arm and gun', 'body': 'other joints'}[side]
        it, v = max(((i, r['end'][side][0]) for i, r in res), key=lambda x: x[1])
        rows.append(row(f'end pose = idle pose, {name}, position', it, v, f'<= {E["end_max_cm"]}', 'cm', v <= E['end_max_cm'], n))
        it, v = max(((i, r['end'][side][1]) for i, r in res), key=lambda x: x[1])
        rows.append(row(f'end pose = idle pose, {name}, rotation', it, v, f'<= {E["end_max_deg"]}', 'deg', v <= E['end_max_deg'], n))
    withpre = [(i, r) for i, r in res if r['pre'] is not None]
    if withpre:
        m = f'{len(withpre)} clips with a version before the end-pose fix'
        it, v = max(((i, r['pre']) for i, r in withpre), key=lambda x: x[1])
        rows.append(row('frames before the seated frame unchanged by the end-pose fix', it, v, f'<= {E["unchanged_max"]}', 'cm or deg', v <= E['unchanged_max'], m))
        it, v = max(((i, max(d[0] for d in r['dev'].values())) for i, r in withpre), key=lambda x: x[1])
        rows.append(row('hands and guns moved by the end-pose fix, position', it, v, f'<= {E["hand_dev_max_cm"]} (baseline 0.04)', 'cm', v <= E['hand_dev_max_cm'], m))
        it, v = max(((i, max(d[1] for d in r['dev'].values())) for i, r in withpre), key=lambda x: x[1])
        rows.append(row('hands and guns moved by the end-pose fix, rotation', it, v, f'<= {E["hand_dev_max_deg"]} (baseline 0.08)', 'deg', v <= E['hand_dev_max_deg'], m))
    else:
        rows.append(row('frames before the seated frame unchanged by the end-pose fix', 'no clip has a version in paths.clips_pre_endpose', 0, 'skipped', '', True, 'not applicable'))
    bad = [(i, r) for i, r in res if r['frames'] != r['want'] or r['clips'] != 1]
    rows.append(row('arm clip glb: one clip of the top-magazine length', bad[0][0] + f' ({bad[0][1]["frames"]} frames)' if bad else f'all {res[0][1]["want"]} frames',
                    len(bad), '0 clips off', 'clips', not bad, n))
    return rows


# ---- sets: SIMD buffers and frame counts of the built anim sets ----------------------------------------------------
RELOAD_CLIPS = ('reload', 'reload_01', 'reload_02', 'empty_reload', 'empty_reload_01', 'empty_reload_02')


def set_sources():
    """[(archive, set name, [(clip name in the set, source glb, clip name in the glb)])] of the build."""
    sys.path.insert(0, common.ANIM)
    from topmagsets import plan as tplan
    from lowsets import plan as lplan
    W = work(); out = []
    for body in manifest.bodies():
        for side in ('right', 'left'):
            name = manifest.reload_set(body, side); glb = f'{W}/tmp_reload/{name}/{name}.glb'
            # The clips flick.py writes (flick.CLIPS); the set's other clips are the game's own, passed through.
            mine = [c + ('' if side == 'right' else '_l') for c in RELOAD_CLIPS]
            out.append(('GorillaAkimbo', name, [(c, glb, c) for c in mine] if os.path.exists(glb) else None))
    for body, name, files, _ in tplan(manifest.path('clips')):
        out.append(('GorillaAkimbo', name, [(n, p, None) for p, n in files]))
    m = manifest.magazine()
    if m:
        for fam in m['families']:
            for side in ('left', 'right'):
                name = f'{m["set_prefix"]}_{fam}_{side}'; glb = f'{W}/tmp_mag/glb/{name}.glb'
                clips = [(a['name'], glb, a['name']) for a in Glb(glb).j['animations']] if os.path.exists(glb) else None
                out.append(('GorillaAkimbo', name, clips))
    import raisedsets
    for body, side, kind, name, glb, hands, _ in raisedsets.plan():
        suf = '' if side == 'right' else '_l'
        if kind == 'base':
            out.append(('GorillaAkimbo', name, [(c + suf, glb, c + suf) for c in raisedsets.POSE_CLIPS]))
        else:
            built = f'{W}/tmp_reload/{name}/{name}.glb'
            out.append(('GorillaAkimbo', name, [(c + suf, built, c + suf) for c in RELOAD_CLIPS + raisedsets.HAND_CLIPS]
                        if os.path.exists(built) else None))
    for body, side, name, clip, _ in lplan(manifest.path('low_clips')):
        keep = ['friendly_idlepose', 'safe_action', 'equip_safe']
        out.append(('GorillaAkimboLowered', name, [(k + ('_l' if side == 'left' else ''),) * 1 + (clip, k + ('_l' if side == 'left' else '')) for k in keep]))
    return out


def set_summary(anims):
    """{clip: (buffer type, frames, duration)} of an .anims file (WolvenKit JSON), cached by the file's hash."""
    cache = work() + '/check/sets'
    os.makedirs(cache, exist_ok=True)
    h = hashlib.sha256(open(anims, 'rb').read()).hexdigest()[:20]
    cj = f'{cache}/{h}.json'
    if os.path.exists(cj):
        return json.load(open(cj))
    tmp = f'{cache}/{h}'
    os.makedirs(tmp, exist_ok=True)
    env = dict(os.environ, DOTNET_ROOT=manifest.path('dotnet_root'))
    subprocess.run([manifest.path('wolvenkit'), 'convert', 's', anims, '-o', tmp], capture_output=True, env=env)
    js = f'{tmp}/{os.path.basename(anims)}.json'
    if not os.path.exists(js):
        return None
    out = {}
    for a in json.load(open(js, encoding='utf-8'))['Data']['RootChunk']['animations']:
        d = a['Data']['animation']['Data']; b = d['animBuffer']['Data']
        out[d['name']['$value']] = (b['$type'], b.get('numFrames'), b.get('duration'))
    json.dump(out, open(cj, 'w'))
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def check_sets():
    S = T['sets']; W = work()
    src = set_sources()
    missing = [n for a, n, _ in src if not os.path.exists(f'{W}/sets/{a}/{n}.anims')]
    if missing:
        return [row('built anim sets present', missing[0], len(missing), '0 missing', 'sets', False, 'run build.sh all')]
    with concurrent.futures.ThreadPoolExecutor(JOBS) as ex:
        sums = list(ex.map(lambda s: set_summary(f'{W}/sets/{s[0]}/{s[1]}.anims'), src))
    known = 0; nclips = 0; notsimd = []; frames = []; dur = []; unknown = []; absent = []
    fcache = {}
    for (arch, name, clips), sm in zip(src, sums):
        if sm is None:
            absent.append(f'{name} (conversion failed)'); continue
        if clips is None:
            unknown.append(name); continue
        for cname, glb, gname in clips:
            nclips += 1
            if cname not in sm:
                absent.append(f'{name}: {cname}'); continue
            typ, nf, d = sm[cname]
            if typ != 'animAnimationBufferSimd': notsimd.append(f'{name}: {cname} ({typ})')
            if (glb, gname) not in fcache:
                g = Glb(glb); fcache[(glb, gname)] = Clip(g, gname or g.j['animations'][0]['name']).frames
            want = fcache[(glb, gname)]
            if nf != want:
                if [want, nf] in S['resampled_baseline']: known += 1
                else: frames.append(f'{name}: {cname} has {nf} frames, its glb {want} keys')
            if abs(d - (want - 1) / S['fps']) > S['duration_tolerance_s']: dur.append(f'{name}: {cname} lasts {d:.4f} s, its glb {(want - 1) / S["fps"]:.4f}')
    n = f'{nclips} clips in {len(src)} sets'
    rows = [row('built sets: shipped clips present', absent[0] if absent else 'all', len(absent), '0 missing', 'clips', not absent, n),
            row('built sets: SIMD buffers', notsimd[0] if notsimd else 'all SIMD', len(notsimd), '0 not SIMD', 'clips', not notsimd, n),
            row('built sets: frame count = the glb key count', frames[0] if frames else f'{nclips - known} equal, {known} resampled as in the baseline (reload, lowered)',
                len(frames), '0 resampled beyond the baseline', 'clips', not frames, n),
            row('built sets: duration = (frames - 1) / 30', dur[0] if dur else 'all equal', len(dur), '0 off', 'clips', not dur, n)]
    if unknown:
        rows.append(row('built sets: source glb in the work folder', unknown[0], len(unknown), '0 unknown', 'sets', False, 'rebuild the step (its glb is kept in WORK/tmp_*)'))
    return rows


# ---- roundtrip: built sets exported back to glb against the glbs they were imported from --------------------------

def _roundtrip_one(a):
    arch, name, clips = a
    W = work(); out = f'{W}/check/roundtrip/{name}'
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, DOTNET_ROOT=manifest.path('dotnet_root'))
    subprocess.run([manifest.path('wolvenkit'), 'export', f'{W}/sets/{arch}/{name}.anims', '-o', out, '-gp', manifest.path('game')],
                   capture_output=True, env=env)
    glb = f'{out}/{name}.anims.glb'
    if not os.path.exists(glb):
        return name, None
    # Exports hold reduced keys at uneven times: both sides are sampled by time, 30 per second.
    sys.path.insert(0, os.path.join(common.HERE, 'lowered'))
    from lpose import Rig, FPS
    B = Rig(Glb(glb)); res = {'hand_cm': 0.0, 'hand_deg': 0.0, 'all_cm': 0.0, 'worst': ''}
    hands = ('WeaponRight', 'WeaponLeft', 'RightHand', 'LeftHand')
    arm = ('Arm', 'Hand', 'Weapon', 'Shoulder', 'arm_')
    srcs = {}
    for cname, src, gname in clips:
        if src not in srcs: srcs[src] = Rig(Glb(src))
        Asrc = srcs[src]; gname = gname or Asrc.g.j['animations'][0]['name']
        small = Asrc.n < 20   # magazine sets: every joint
        for f in range(int(round(Asrc.duration(gname) * FPS)) + 1):
            WA = Asrc.world(Asrc.sample(gname, f / FPS)); WB = B.world(B.sample(cname, f / FPS))
            for i, n in enumerate(Asrc.names):
                if n not in B.idx or n == 'Armature' or not (small or any(k in n for k in arm)): continue
                d = float(np.linalg.norm(WA[i][0] - WB[B.idx[n]][0])) * 100
                if d > res['all_cm']: res['all_cm'] = d; res['worst'] = f'{cname} f{f} {n}'
                if n in hands or small:
                    q = abs(float(np.dot(WA[i][1], WB[B.idx[n]][1])))
                    res['hand_cm'] = max(res['hand_cm'], d); res['hand_deg'] = max(res['hand_deg'], float(np.degrees(2 * np.arccos(min(1, q)))))
    os.remove(glb)
    return name, res


def check_roundtrip(every):
    R = T['roundtrip']; W = work()
    src = [s for s in set_sources() if s[2] and os.path.exists(f'{W}/sets/{s[0]}/{s[1]}.anims')]
    if not every:   # one set of each kind
        kinds = {}
        for s in src:
            n = s[1]
            k = ('raised partner' if '_topmag_' in n and '_raised_' in n else 'raised pose' if '_raised_' in n else 'raised reload' if '_reload_' in n else
                 'lowered v2' if n.endswith('_safe_v2') else 'lowered v1' if '_safe_' in n else 'magazine' if '__mag_' in n else
                 'pair' if '_pair_' in n else 'long' if '_long_' in n else 'category' if '_topmag_' in n else 'reload')
            kinds.setdefault(k, s)
        src = list(kinds.values())
    with concurrent.futures.ThreadPoolExecutor(JOBS) as ex:
        res = list(ex.map(_roundtrip_one, src))
    failed = [n for n, r in res if r is None]; res = [(n, r) for n, r in res if r]
    n = f'{len(res)} sets' + ('' if every else ' (one of each kind; --roundtrip-all for every set)')
    rows = [row('round trip: sets exported back', failed[0] if failed else 'all', len(failed), '0 failed', 'sets', not failed, n)]
    if res:
        it, v = max(((i, r['hand_cm']) for i, r in res), key=lambda x: x[1])
        rows.append(row('round trip: hands, guns and magazine against the source glb, position', it, v, f'<= {R["hand_max_cm"]} (baseline)', 'cm', v <= R['hand_max_cm'], n))
        it, v = max(((i, r['hand_deg']) for i, r in res), key=lambda x: x[1])
        rows.append(row('round trip: hands, guns and magazine against the source glb, rotation', it, v, f'<= {R["hand_max_deg"]} (baseline)', 'deg', v <= R['hand_max_deg'], n))
        it, v = max(((i + ' ' + r['worst'], r['all_cm']) for i, r in res), key=lambda x: x[1])
        rows.append(row('round trip: any arm joint or helper, position', it, v, f'<= {R["any_max_cm"]} (baseline)', 'cm', v <= R['any_max_cm'], n))
    return rows


# ---- areas with their own check module -----------------------------------------------------------------------------
def load(area):
    sys.path.insert(0, os.path.join(common.HERE, area))   # one area per process, so the name is free
    return importlib.import_module('checks')


def check_lowered(guns, bodies):
    return load('lowered').run(guns, bodies, jobs=JOBS)


def check_topmag(clips, guns, bodies, picked):
    # a partner with a raised pose plays the raised copy of a clip (the build packs it from paths.raised_clips)
    return load('topmag').run(clips, guns=[g['id'] for g in guns] if picked else None, bodies=bodies,
                              thresholds={k: v for k, v in T['topmag'].items() if not k.startswith('_')},
                              raised=manifest.path('raised_clips'))


def check_magtrack(clips, bodies):
    W = work(); sets = f'{W}/tmp_mag/glb'
    m = manifest.magazine()
    names = [f'{m["set_prefix"]}_{fam}_{side}.glb' for fam in m['families'] for side in ('left', 'right')]
    if clips or not all(os.path.exists(f'{sets}/{n}') for n in names):
        sets = f'{W}/check/mag'
        subprocess.run([sys.executable, f'{common.ANIM}/magtrack.py', manifest.path('mag_spec'), sets], check=True, capture_output=True)
    m = load('magtrack')
    thr = {k: v for k, v in T['magtrack'].items() if not k.startswith('_')}
    thr.update(m.load_baseline())   # known misses of the shipped tracks, per item
    return m.run(manifest.mag_spec(), sets, clips_dir=clips, bodies=bodies, thresholds=thr)


def check_rreload(bodies):
    """Production rifle reload clips and sets (authoring/reload/checks.py); only when named in --only."""
    return load('reload').run(bodies, jobs=JOBS)


def worst_rows(rows):
    """One row per check: the worst item (a failing one first), with the number of items and of failures."""
    by = {}
    for r in rows:
        by.setdefault(r['check'], []).append(r)
    out = []
    for check, rs in by.items():
        if len(rs) == 1:
            out.append(rs[0]); continue
        def off(r):
            try: return abs(float(r['value']) - float(r['threshold']))
            except (TypeError, ValueError): return 0.0
        bad = [r for r in rs if not r['ok']]
        w = dict(max(bad, key=off) if bad else min(rs, key=off))
        w['note'] = f'{len(rs)} items' + (f', {len(bad)} fail' if bad else '') + (f'; {w["note"]}' if w.get('note') else '')
        out.append(w)
    return out


def fmt(v):
    return f'{v:.3f}' if isinstance(v, float) else str(v)


if __name__ == '__main__':
    argv = sys.argv[1:]
    if '--with-test' in argv:
        argv.remove('--with-test'); os.environ['GA_TEST'] = '1'
    area = common.opt(argv, '--area'); out_json = common.opt(argv, '--json')
    picked = common.opt(argv, '--guns'); bodies = common.body_list(common.opt(argv, '--bodies'))
    clips_arg = common.opt(argv, '--clips'); only = common.opt(argv, '--only')
    guns = common.gun_list(picked)
    clips = (clips_arg or manifest.path('clips')).replace('\\', '/')
    if area:   # one area, in its own process (the areas' modules share names)
        rows = {'clips': lambda: check_clips(clips, guns, bodies, picked), 'sets': check_sets,
                'lowered': lambda: check_lowered(guns, bodies), 'raised': lambda: load('raised').run(guns, bodies, work=work(), jobs=JOBS),
                'topmag': lambda: check_topmag(clips, guns, bodies, picked),
                'magtrack': lambda: check_magtrack(clips_arg, bodies),
                'roundtrip': lambda: check_roundtrip('--roundtrip-all' in argv), 'rreload': lambda: check_rreload(bodies)}[area]()
        json.dump(rows, open(out_json, 'w'))
        sys.exit(0)
    areas = [a for a in (only.split(',') if only else AREAS) if not (a in ('sets', 'roundtrip') and clips_arg)]
    os.makedirs(work() + '/check', exist_ok=True)
    lines = [f'check: clips {clips}, bodies {",".join(bodies)}, guns {picked or "all of the build"}' + (', test content included' if manifest.with_test() else '')]
    print(lines[0], flush=True)
    bad = 0
    for a in areas:
        t0 = time.time(); js = f'{work()}/check/{a}.json'
        if os.path.exists(js): os.remove(js)
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.path.join(common.HERE, a), os.environ.get('PYTHONPATH', '')]))
        r = subprocess.run([sys.executable, os.path.abspath(__file__), '--area', a, '--json', js] + sys.argv[1:], capture_output=True, text=True, env=env)
        if not os.path.exists(js):
            rows = [row(f'{a}: checks ran', (r.stderr or r.stdout).strip().splitlines()[-1][:200] if (r.stderr or r.stdout).strip() else 'no output', 1, '0 errors', '', False)]
        else:
            rows = json.load(open(js))
        rows = worst_rows(rows)
        out = [f'-- {a} ({time.time() - t0:.0f} s)']
        for x in rows:
            bad += not x['ok']
            out.append(f'{"pass" if x["ok"] else "FAIL"}  {x["check"]}: {fmt(x["value"])} {x["unit"]}  limit {x["threshold"]}  worst: {x["item"]}'
                       + (f'  [{x["note"]}]' if x.get('note') else ''))
        print('\n'.join(out), flush=True); lines += out
    lines.append(f'check: {"all passed" if not bad else str(bad) + " failed"}')
    print(lines[-1])
    open(work() + '/check/report.txt', 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    sys.exit(1 if bad else 0)
