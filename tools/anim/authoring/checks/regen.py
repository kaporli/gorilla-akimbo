"""Regenerates the shipped reload clips from a tool tree and compares them with the shipped ones.

usage: regen.py list [--manifest weapons.json]
       regen.py run <tree> <family> --out <dir> [--guns a,b] [--picks P,Q] [--sides right,left] [--bodies pma,pwa]
                    [--clips reload,empty_reload] [--limit n] [--jobs n] [--include-parked] [--shipped <dir>]
                    [--ref <folder>] [--manifest weapons.json] [--report file.md] [--compare-only]

<tree>    the tool tree's authoring directory (.../anim/authoring). Its generators run unchanged.
<family>  grip, bullpup, smg_front, top, tube, break (SMG and shotgun reloads), front, masamune, hercules (rifle
          reloads, prod.py), fallback (the quick-drop clips, fallback.py, both bodies and hands, FB and FBloop).
--out     everything made goes here: <out>/clips/<body>/... (reloads), <out>/fallback/<body>/... (fallback).
          The generators write nothing else outside WORK and AUTHORING.
--limit   regenerate only the first n of the acceptance clips (after the other filters).

The acceptance set comes from the manifest (default: tools/anim/weapons.json next to this tree's repo): every
guns[].reload.slots pick, per body and side, reload and empty_reload (the file clip_file() in rreload.py would pick),
plus the reload.fallback clips (FB, FBloop). Guns with reload.parked are not shipped; they are listed and run only
with --include-parked. Shipped clip folders are the manifest's paths (reload.clips, default paths.rreload_clips;
fallback.clips).

Per family the report holds: clip count, max position deviation (cm) and rotation deviation (deg) over every joint
and frame (checks/cmpclips.py), byte-identical glb count, the same for _track.json (byte equal, else the largest
matrix element difference), and the clips that fail. Every other file of a clip (the siblings: the spec <clip>.json,
_track, _gate, _objects, _inertia, _phys, _prims: whatever <clip>_*.json the shipped folder holds) is compared byte for byte
too, and counted per kind. pass = every clip present, glb and _track.json byte-identical, every other sibling identical.
The spec and some others hold absolute paths (out, src, _track ...) that differ by the output folder: a sibling that differs
only there is identical after the output root is replaced by the shipped root (counted as 'path only', and passing); a
sibling that is not byte-identical for any other cause is classified (key order, number format, key set, value) and fails.
The deviation in cm and deg stays in the report as the measure of a glb that differs.

Before and after the run the shipped folders are checked: size and mtime of every file, and SHA-256 of the accepted
files; any change is printed and gives exit code 2. Set WORK and AUTHORING in the environment first, so the
generators write into a scratch folder. A write guard (a sitecustomize.py on PYTHONPATH) is advisable.
--ref     compare with a previous output instead of the shipped folders: <folder>/<clips|fallback>/<body>/... (the --out
          layout of an earlier run). The shipped folders are not read for comparison; their guard still applies to <folder>.
Exit code 0 pass, 1 a family fails, 2 the shipped folders changed, 3 refused to start.
Ordering: the generators of different families share <out>/rest (rest glbs are written once and reused) and fallback reads
the reload clips and rest glbs of the families before it. A run writes <out>/.regen_running/<family> while it generates and
refuses to start (exit 3, no waiting) when that folder holds a marker of another run: run the families of one --out one
after the other, fallback last. The marker of a run that was killed stays: remove it by hand. A fallback run also stops
when a rest glb already under <out>/rest does not parse (a half-written file).
"""
import glob, hashlib, json, os, subprocess, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import common
import cmpclips

TAKE = {'light': 'A', 'heavy': 'B'}
SIDES = ('right', 'left')
CLIPS = ('reload', 'empty_reload')
FAMILIES = ('grip', 'bullpup', 'smg_front', 'top', 'tube', 'break', 'front', 'masamune', 'hercules', 'fallback')
SMG_GEN = {'SG08': 'grip1', 'SG12': 'grip2', 'SG13': 'grip2'}


def load_manifest(path=None):
    path = path or os.path.normpath(os.path.join(HERE, '..', '..', 'weapons.json'))
    return json.load(open(path))


def clip_dir(man, key):
    """Default folder of a paths entry (the environment is not consulted: this is the shipped set)."""
    return common.mp(man['paths'][key]['default']).split(';')[0].rstrip('/')


def clip_file(d, body, gid, side, pick, take, clip, ext='.glb'):
    p = f'{d}/{body}/{gid}_{side}_{pick}{take}_{clip}{ext}'
    if not os.path.exists(p):      # a gun whose two clips are the same has one (named after either)
        other = 'reload' if clip == 'empty_reload' else 'empty_reload'
        q = f'{d}/{body}/{gid}_{side}_{pick}{take}_{other}{ext}'
        if os.path.exists(q): p = q
    return p


def acceptance(man=None, include_parked=False):
    """[dict(family, gun, body, side, pick, take, clip, kind, shipped, rel, parked)]: the clips the archives are built from."""
    man = man or load_manifest()
    bodies = list(man['game_files']['bodies'])
    out = []
    for g in man['guns']:
        r = g.get('reload') or {}
        parked = bool(r.get('parked'))
        if (not r.get('slots') and not r.get('fallback')) or (parked and not include_parked): continue      # a fallback-only gun (top-magazine guns) has the fallback clips only
        take = TAKE[r['weight']]; d = clip_dir(man, r.get('clips', 'rreload_clips'))
        for body in bodies:
            for side in SIDES:
                for clip in CLIPS:
                    for pick in r.get('slots') or []:
                        f = clip_file(d, body, g['id'], side, pick, take, clip)
                        out.append(dict(family=r['category'], gun=g['id'], body=body, side=side, pick=pick, take=take, clip=clip, kind='reload',
                                        shipped=f, rel=f'{body}/{os.path.basename(f)}', parked=parked, root='clips'))
        fb = r.get('fallback')
        if fb:
            d = clip_dir(man, fb.get('clips', 'smg_fallback_clips'))
            for body in bodies:
                for side in SIDES:
                    for k in ('FB', 'FBloop'):
                        f = f'{d}/{body}/{g["id"]}_{side}_{k}_reload.glb'
                        out.append(dict(family='fallback', gun=g['id'], body=body, side=side, pick=k, take=None, clip='reload', kind=k,
                                        shipped=f, rel=f'{body}/{os.path.basename(f)}', parked=parked, root='fallback'))
    seen = set(); uniq = []
    for i in out:      # a gun whose two clips are the same has one file: listed once
        if i['shipped'] not in seen: seen.add(i['shipped']); uniq.append(i)
    return uniq


def select(items, family, o):
    cs = lambda v: v.split(',') if v else None
    guns, picks, sides, bodies, clips = (cs(o(n)) for n in ('--guns', '--picks', '--sides', '--bodies', '--clips'))
    sel = [i for i in items if i['family'] == family and (not guns or i['gun'] in guns) and (not picks or i['pick'] in picks)
           and (not sides or i['side'] in sides) and (not bodies or i['body'] in bodies) and (not clips or i['kind'] != 'reload' or i['clip'] in clips)]
    n = o('--limit')
    return sel[:int(n)] if n else sel


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def stat_tree(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f); s = os.stat(p); out[p] = (s.st_size, s.st_mtime_ns)
    return out


def siblings(shipped):
    """{suffix: path} of the files next to a shipped glb that belong to it: '.json' (the spec) and '_<kind>.json'."""
    b = shipped[:-4]; out = {}
    if os.path.exists(b + '.json'): out['.json'] = b + '.json'
    for f in sorted(glob.glob(glob.escape(b) + '_*.json')): out[f[len(b):]] = f
    return out


def related(i):
    """The shipped files a clip owns: glb and every sibling."""
    b = i['shipped'][:-4]
    return ([b + '.glb'] if os.path.exists(b + '.glb') else []) + list(siblings(i['shipped']).values())


class Guard:
    """Size and mtime of every file under the shipped folders, SHA-256 of the files of the accepted clips."""
    def __init__(self, items):
        self.roots = sorted({os.path.dirname(os.path.dirname(i['shipped'])) for i in items})
        self.files = sorted({f for i in items for f in related(i)})
        self.stat = {r: stat_tree(r) for r in self.roots}
        self.sha = {f: sha(f) for f in self.files}

    def changed(self):
        bad = []
        for r in self.roots:
            now = stat_tree(r)
            bad += [p for p in set(now) | set(self.stat[r]) if now.get(p) != self.stat[r].get(p)]
        bad += [f for f in self.files if not os.path.exists(f) or sha(f) != self.sha[f]]
        return sorted(set(bad))


def command(tree, family, pick, gun_list, body, side, clips, out):
    """(script, args) of the generator run for one pick, body and side (several guns, one process)."""
    sel = ['--picks', pick, '--bodies', body, '--sides', side]
    if clips: sel += ['--clips', clips]
    if gun_list: sel += ['--guns', ','.join(gun_list)]
    R = tree + '/reload'
    if family in ('grip', 'bullpup', 'top'):
        sub = SMG_GEN.get(pick) or {'bullpup': 'bull3', 'top': 'top3'}[family]
        return R + '/smgprod.py', ['build', sub, '--picks', pick, '--bodies', body, '--sides', side] + (['--clips', clips] if clips else [])
    if family == 'smg_front': return R + '/frontprod.py', ['build'] + sel
    if family == 'break': return R + '/breakprod.py', ['build'] + sel
    if family == 'tube':      # tube2.py has no --clips: both clips are built
        return R + '/tube2.py', ['build', '--picks', pick, '--bodies', body, '--sides', side] + (['--guns', ','.join(gun_list)] if gun_list else [])
    if family in ('front', 'masamune', 'hercules'): return R + '/prod.py', ['build'] + sel + ['--out', out + '/clips']
    raise SystemExit('no generator for family ' + family)


def run_jobs(tree, family, sel, out, jobs, limited_clips):
    """Runs one generator process per (pick, body, side) group; returns [(argv, exit code, seconds)]."""
    env = dict(os.environ, ROUND_OUT=out, PYTHONDONTWRITEBYTECODE='1')
    env.setdefault('WORK', out + '/work'); env.setdefault('AUTHORING', out + '/work')
    os.makedirs(out + '/work', exist_ok=True)
    plan = []
    if family == 'fallback':
        seats = common_seats()
        for gid, body, side in sorted({(i['gun'], i['body'], i['side']) for i in sel}):
            plan.append([sys.executable, '-B', tree + '/reload/fallback.py', 'build', '--guns', gid, '--bodies', body, '--sides', side])
    else:
        groups = defaultdict(lambda: [set(), set()])
        for i in sel:
            g = groups[(i['pick'], i['body'], i['side'])]; g[0].add(i['gun']); g[1].add(i['clip'])
        for (pick, body, side), (guns, clips) in sorted(groups.items()):
            script, args = command(tree, family, pick, sorted(guns), body, side, ','.join(sorted(clips)) if limited_clips else None, out)
            plan.append([sys.executable, '-B', script] + args)

    def one(argv):
        t = time.time(); cwd = os.path.dirname(argv[2])
        r = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return argv, r.returncode, round(time.time() - t, 1), r.stdout[-600:] if r.returncode else ''
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        return list(ex.map(one, plan))


def common_seats():
    return None


def start_marker(out, family):
    """Marks <out> as in use by this run; exit 3 when another run's marker is there (the families share <out>/rest)."""
    d = out + '/.regen_running'
    if os.path.isdir(d) and os.listdir(d):
        print(f'regen: {out} is in use by a run of: {", ".join(sorted(os.listdir(d)))} ({d}). Run the families of one --out one after '
              f'the other, fallback last; remove the marker only if that run was killed.', file=sys.stderr)
        raise SystemExit(3)
    os.makedirs(d, exist_ok=True)
    m = f'{d}/{family}'
    open(m, 'w').write(f'pid {os.getpid()}\n')
    return m


def check_rest(out):
    """fallback reads <out>/rest/<body>/rest_<gun>_R__<gun>_L.glb: stop on a file that does not parse (a half-written one)."""
    from glb import Glb
    bad = []
    for f in sorted(glob.glob(out + '/rest/*/*.glb')):
        try: Glb(f)
        except Exception as e: bad.append(f'{f}: {type(e).__name__}')
    if bad:
        print('regen: rest glbs that do not parse (an earlier run was cut off or is still writing):\n  ' + '\n  '.join(bad), file=sys.stderr)
        raise SystemExit(3)


def seed_seats(tree, sel, out, shipped_dirs):
    """fallback.py reads the seated magazine matrix from <out>/clips/pma/<gun>_right_<SEAT_CLIP>_empty_reload_track.json.
    Copies it from the shipped clips (an input of the generator, listed in the report)."""
    import re
    src = open(tree + '/reload/fallback.py').read()
    m = re.search(r"SEAT_CLIP = (\{[^}]*\})", src)
    seat = eval(m.group(1)) if m else {}
    used = []
    for gid in sorted({i['gun'] for i in sel}):
        if gid not in seat: continue
        name = f'pma/{gid}_right_{seat[gid]}_empty_reload_track.json'
        dst = f'{out}/clips/{name}'
        if os.path.exists(dst): continue
        for d in shipped_dirs:
            s = f'{d}/{name}'
            if os.path.exists(s):
                os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(open(s, 'rb').read()); used.append(s); break
    return used


def seed_ref(sel, out):
    """Generator inputs kept next to the shipped clips: <production>/ref (gun geometry json). Copied to <out>/ref."""
    used = []
    for root in sorted({os.path.dirname(os.path.dirname(os.path.dirname(i['shipped']))) for i in sel}):
        for f in sorted(glob.glob(root + '/ref/*')):
            if os.path.isfile(f):
                dst = f'{out}/ref/{os.path.basename(f)}'; os.makedirs(os.path.dirname(dst), exist_ok=True)
                if not os.path.exists(dst): open(dst, 'wb').write(open(f, 'rb').read())
                used.append(f)
    return used


def track_diff(a, b):
    """0.0 when byte equal, else the largest absolute difference of any number in the two track files; inf on a shape mismatch."""
    if open(a, 'rb').read() == open(b, 'rb').read(): return 0.0
    import numpy as np
    A, B = json.load(open(a)), json.load(open(b))
    def flat(x):
        if isinstance(x, dict): return [v for k in sorted(x) for v in flat(x[k])]
        if isinstance(x, list): return [v for e in x for v in flat(e)]
        return [float(x)] if isinstance(x, (int, float)) and not isinstance(x, bool) else [hash(str(x)) % 100003]
    fa, fb = flat(A), flat(B)
    if len(fa) != len(fb): return float('inf')
    return float(np.abs(np.array(fa) - np.array(fb)).max()) if fa else 0.0


def json_keys(x, path=''):
    """Key order of every object in a json value: {path: [keys]}."""
    out = {}
    if isinstance(x, dict):
        out[path] = list(x)
        for k, v in x.items(): out.update(json_keys(v, path + '/' + k))
    elif isinstance(x, list):
        for n, v in enumerate(x): out.update(json_keys(v, path + f'[{n}]'))
    return out


def classify(a, b, root_a, root_b):
    """Why the regenerated json a is not byte-identical to the shipped json b: 'path only' (identical once the output
    root root_a is replaced by the shipped root root_b), else 'key order', 'number format' (same parsed values, other
    text: a float repr or whitespace), 'key set' (keys added or missing), 'value' (a parsed value differs)."""
    ta, tb = open(a, 'rb').read(), open(b, 'rb').read()
    if ta == tb: return 'identical'
    if ta.replace(root_a.encode(), root_b.encode()) == tb: return 'path only'
    try:
        A, B = json.loads(ta.decode('utf-8')), json.loads(tb.decode('utf-8'))
    except ValueError:
        return 'value (not json)'
    sa = json.dumps(A, sort_keys=True).replace(root_a, root_b); sb = json.dumps(B, sort_keys=True)
    if sa == sb:
        ka = {k: v for k, v in json_keys(A).items()}; kb = json_keys(B)
        return 'key order' if ka != kb else 'number format'
    def keyset(x): return {p: sorted(v) for p, v in json_keys(x).items()}
    if keyset(A) != keyset(B): return 'key set'
    return 'value'


def compare(sel, out):
    """[(item, state, cm, deg, track_state, note, siblings)] regenerated (under out) against shipped. siblings: {suffix: cause}
    for every sibling file of the shipped clip, cause 'identical', 'path only' or another classify() result or 'missing'."""
    rows = []
    for i in sel:
        a = f'{out}/{i["root"]}/{i["rel"]}'; b = i['shipped']
        if not os.path.exists(b):
            rows.append((i, 'no shipped file', None, None, '', '', {})); continue
        if not os.path.exists(a):
            rows.append((i, 'not regenerated', None, None, '', '', {})); continue
        r = cmpclips.compare(a, b)[0]
        ta, tb = a[:-4] + '_track.json', b[:-4] + '_track.json'
        if os.path.exists(tb):
            ts = 'missing' if not os.path.exists(ta) else ('identical' if track_diff(ta, tb) == 0.0 else f'differs {track_diff(ta, tb):.3g}')
        else:
            ts = '' if not os.path.exists(ta) else 'extra'
        root_a = out.replace('\\', '/'); root_b = os.path.dirname(os.path.dirname(os.path.dirname(b))).replace('\\', '/')
        # the regenerated tree is <out>/<clips|fallback>/<body>/file; the shipped one <root>/<clips|fallback>/<body>/file
        sib = {}
        for suf, sp in siblings(b).items():
            ap = a[:-4] + suf
            sib[suf] = classify(ap, sp, root_a, root_b) if os.path.exists(ap) else 'missing'
        extra = [f[len(a) - 4:] for f in sorted(glob.glob(glob.escape(a[:-4]) + '_*.json')) if f[len(a) - 4:] not in sib]
        for suf in extra: sib[suf] = 'extra'
        rows.append((i, r[1], r[2], r[3], ts, r[4], sib))
    return rows


KINDS_OK = ('identical', 'path only')


def summary(rows):
    n = len(rows); ident = sum(r[1] == 'identical' for r in rows)
    dev = [r for r in rows if r[1] in ('identical', 'differs') and r[2] is not None and r[2] != float('inf')]
    cm = max([r[2] for r in dev] or [0.0]); deg = max([r[3] for r in dev] or [0.0])
    bad = [r for r in rows if r[1] != 'identical']
    tbad = [r for r in rows if r[4] not in ('', 'identical')]
    sbad = [r for r in rows if any(c not in KINDS_OK for c in r[6].values())]
    tn = sum(r[4] != '' for r in rows); ti = sum(r[4] == 'identical' for r in rows)
    kinds = {}
    for r in rows:
        for suf, c in r[6].items():
            k = kinds.setdefault(suf, {})
            k[c] = k.get(c, 0) + 1
    ok = not bad and not tbad and not sbad and n > 0
    failing = [r for r in rows if r in bad or r in tbad or r in sbad]
    return dict(clips=n, cm=cm, deg=deg, identical=ident, tracks=tn, tracks_identical=ti, failing=failing, ok=ok, kinds=kinds)


def kinds_line(kinds):
    """'.json 24 (path only 24); _track.json 24 (identical 24); ...'"""
    return '; '.join(f'{suf} {sum(v.values())} (' + ', '.join(f'{c} {m}' for c, m in sorted(v.items())) + ')' for suf, v in sorted(kinds.items()))


def report(path, tree, family, sel, rows, s, cmds, guard_bad, seeded, runs, limited, elapsed):
    L = [f'# regen {family} from {tree}', '', f'clips {s["clips"]}{" (subset: --limit/--guns/--picks/--sides/--bodies/--clips)" if limited else ""}; max dev {s["cm"]:.4f} cm, {s["deg"]:.4f} deg; '
         f'glb byte-identical {s["identical"]}/{s["clips"]}; tracks identical {s["tracks_identical"]}/{s["tracks"]}; result {"PASS" if s["ok"] else "FAIL"}; shipped folders {"CHANGED" if guard_bad else "unchanged"}; {elapsed:.0f} s', '']
    L += ['Files per kind (raw byte comparison; "path only" = identical once the output folder is replaced by the shipped one): ' + kinds_line(s['kinds']), '']
    L += ['Generator runs (exit codes): ' + ', '.join(f'{os.path.basename(a[2])} {" ".join(a[3:])} -> {c}' for a, c, _, _ in runs[:40]) + (' ...' if len(runs) > 40 else ''), '']
    if seeded: L += ['Inputs copied from shipped clips: ' + ', '.join(seeded), '']
    for a, c, _, tail in runs:
        if c: L += [f'FAILED RUN {" ".join(a[2:])} exit {c}', '```', tail, '```']
    if s['failing']:
        L += ['| clip | state | cm | deg | track | note | siblings that are not identical |', '|---|---|---|---|---|---|---|']
        L += [f'| {r[0]["rel"]} | {r[1]} | {r[2] if r[2] is None else round(r[2], 4)} | {r[3] if r[3] is None else round(r[3], 4)} | {r[4]} | {r[5]} | '
              + ', '.join(f'{k} {c}' for k, c in r[6].items() if c not in KINDS_OK) + ' |' for r in s['failing']]
    if guard_bad: L += ['', 'CHANGED shipped files:'] + guard_bad
    open(path, 'w').write('\n'.join(L) + '\n')


def main(argv):
    flag = lambda n: n in argv
    opts = {n: common.opt(argv, n) for n in ('--manifest', '--out', '--guns', '--picks', '--sides', '--bodies', '--clips', '--limit', '--jobs', '--shipped', '--ref', '--report')}
    o = lambda n: opts.get(n)
    if not argv or argv[0] not in ('list', 'run'): raise SystemExit(__doc__)
    man = load_manifest(o('--manifest')); items = acceptance(man, flag('--include-parked'))
    if argv[0] == 'list':
        cnt = defaultdict(int)
        for i in items: cnt[(i['family'], i['pick'] if i['kind'] == 'reload' else 'FB/FBloop', i['parked'])] += 1
        for k, v in sorted(cnt.items(), key=str): print(*k, v)
        print(len(items), 'clips'); return 0
    tree = os.path.abspath(argv[1]).replace('\\', '/'); family = argv[2]; out = os.path.abspath(o('--out')).replace('\\', '/')
    if family not in FAMILIES: raise SystemExit('family: ' + ', '.join(FAMILIES))
    sel = select(items, family, o)
    if o('--shipped'):
        for i in sel: i['shipped'] = o('--shipped') + '/' + i['rel']
    if o('--ref'):
        for i in sel: i['shipped'] = os.path.abspath(o('--ref')).replace(chr(92), '/') + '/' + i['root'] + '/' + i['rel']
    if not sel: raise SystemExit('no clips selected')
    limited = any(o(n) for n in ('--limit', '--guns', '--picks', '--sides', '--bodies', '--clips'))
    t0 = time.time(); guard = Guard(sel); seeded = []; runs = []
    if not flag('--compare-only'):
        marker = start_marker(out, family)
        try:
            if family == 'fallback': check_rest(out)
            if family != 'front' and family != 'masamune' and family != 'hercules': seeded = seed_ref(sel, out)
            if family == 'fallback':
                seeded += seed_seats(tree, sel, out, [clip_dir(man, 'smg_reload_clips'), clip_dir(man, 'rreload_clips')])
            runs = run_jobs(tree, family, sel, out, int(o('--jobs') or 4), bool(o('--clips')))
        finally:
            if os.path.exists(marker): os.remove(marker)
    rows = compare(sel, out); s = summary(rows); bad = guard.changed()
    rp = o('--report') or f'{out}/report_{family}.md'
    report(rp, tree, family, sel, rows, s, None, bad, seeded, runs, limited, time.time() - t0)
    print(f'{family}: {s["clips"]} clips, max {s["cm"]:.4f} cm {s["deg"]:.4f} deg, glb identical {s["identical"]}, tracks identical {s["tracks_identical"]}/{s["tracks"]}'
          + f'; files {kinds_line(s["kinds"])}; ' + ('PASS' if s['ok'] else 'FAIL') + (', SHIPPED CHANGED' if bad else '') + f'; report {rp}')
    return 2 if bad else (0 if s['ok'] else 1)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
