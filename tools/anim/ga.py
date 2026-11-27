"""ga: one command per stage of the gun and animation pipeline.

usage: ga.sh produce <gun> [--out <dir>] [--dry-run] [--jobs n] [--with-test] [--write-layout] [--no-build]
       ga.sh drafts <family> --round N [--out <dir>] [--take A|B] [--only id,id] [--no-render] [--dry-run]   (see authoring/draft/drafts.py)
       ga.sh pick <family> <id>[,id] --round N [--out <dir>] [--replace] [--allow-fail] [--dry-run]
       ga.sh gun add <id> [--from <seed.json>] [--out <dir>] [--dry-run] [--apply] [--ack step,step|all] [--render]   (see gunadd.py)
       ga.sh ingame <gun> [--partner <gun>] [--pick X] [--record] [--baseline] [--visual] | --dry-run | --restore <run>   (see ../ingame/README.md)

produce <gun>   the gun's production clips from its weapons.json reload entry (picks, family, take; the quick-drop fallback
                when the entry has one), its layout, then only the build steps that gun touches (build.py reload rreload --guns <gun>),
                then build.sh check for the gun's areas. Stops at the first step that fails.
  --out <dir>   make the clips in <dir>/clips and <dir>/fallback (and read them there); nothing shipped is touched.
                Without it: the clips are made in WORK/produce_<gun>/stage-<time> (build and checks read them there) and, when
                every step passed and the layout equals the manifest, the shipped clips that differ are moved to
                <folder>.prev-<YYYYMMDD> (clips/, fallback/) and replaced; identical ones stay. Nothing is deleted. The moved
                files are printed. Shared files (layout tables) are never replaced.
  --dry-run     print every step with its command, inputs and outputs; run nothing and write nothing.
  --jobs n      clip generators in parallel (default 3).
  --no-build    skip the WolvenKit archive build (build.py reload rreload); everything else runs.
  --write-layout  where the generated layout differs from the manifest, write the generated values into the gun's reload.layout and
                reload.fallback.layout of weapons.json (only keys the manifest has and the generator wrote; the entry is patched in place),
                then go on: the layout then equals the manifest and the checks read the new values.
Archives of a produce run are partial: build.py --guns writes them under WORK/guns-out, never into the checkout.
"""
import concurrent.futures, datetime, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
AUTH = HERE + '/authoring'
sys.path.insert(0, HERE)
sys.path.insert(0, AUTH + '/checks')
sys.path.insert(0, AUTH + '/draft')
import manifest
import regen

PY = [sys.executable, '-B']
TAKE = {'light': 'A', 'heavy': 'B'}
# the layout command of a family, and the file it writes (relative to <root>)
LAYOUT = {'grip': ('smgprod.py', [], 'clips/layout.json'), 'bullpup': ('smgprod.py', [], 'clips/layout.json'), 'top': ('smgprod.py', [], 'clips/layout.json'),
          'smg_front': ('frontprod.py', [], 'clips/layout_front.json'), 'tube': ('tube2.py', [], 'clips/layout_tube.json'),
          'break': ('breakprod.py', [], 'clips/layout_break.json'), 'front': ('prod.py', ['--out', '{root}/clips', '--guns', '{gun}'], 'clips/layout.json'),
          'masamune': ('prod.py', ['--out', '{root}/clips', '--guns', '{gun}'], 'clips/layout.json'), 'hercules': ('prod.py', ['--out', '{root}/clips', '--guns', '{gun}'], 'clips/layout.json')}
LAYOUT_KEYS = ('hide_start', 'hide_end', 'mag_out', 'seated', 'length', 'handle', 'keys', 'swap', 'loads', 'empty_loads')


class Step:
    def __init__(self, name, argv=None, fn=None, env=None, cwd=None, reads='', writes='', note='', jobs=1, group=None, ok_codes=(0,)):
        self.name, self.argv, self.fn, self.env, self.cwd, self.reads, self.writes, self.note, self.jobs, self.group, self.ok_codes = \
            name, argv, fn, env or {}, cwd, reads, writes, note, jobs, group, ok_codes


def fail(msg, code=2):
    print('ga: ' + msg, file=sys.stderr)
    raise SystemExit(code)


def find_gun(gid):
    for g in manifest.load()['guns']:
        if g['id'] == gid:
            return g
    fail(f'unknown gun {gid}: see `python manifest.py guns`')


def build_plan(gid, out, jobs, with_test, stage=None, no_build=False):
    """[Step]: everything produce does for one gun, in order. With neither out nor stage the clips are made in the shipped
    folder; with stage they are made in <stage> and the last value is the shipped root (for the replace step)."""
    g = find_gun(gid); r = g.get('reload') or {}
    if r.get('shares'):
        fail(f'{gid} shares the clips of {r["shares"]}: run ga produce {r["shares"]}')
    if not r.get('slots'):
        fail(f'{gid} has no reload entry with slots in weapons.json: nothing to produce')
    family = r['category']; take = TAKE[r['weight']]; picks = list(r['slots'])
    ckey = r.get('clips', 'rreload_clips'); fb = r.get('fallback'); fkey = (fb or {}).get('clips', 'smg_fallback_clips')
    clip_dir = manifest.path(ckey).rstrip('/')
    ship = None
    if out:
        root = os.path.abspath(out).replace('\\', '/').rstrip('/')
    else:
        if os.path.basename(clip_dir) != 'clips':
            fail(f'the clip folder {clip_dir} of the manifest is not <root>/clips: pass --out')
        root = os.path.dirname(clip_dir)
        if fb and manifest.path(fkey).rstrip('/') != root + '/fallback':
            fail(f'the fallback folder {manifest.path(fkey)} is not {root}/fallback: pass --out')
        if stage:
            ship = root; root = os.path.abspath(stage).replace('\\', '/').rstrip('/')
    work = root + '/work'
    R = AUTH + '/reload'
    genv = {'ROUND_OUT': root, 'WORK': work, 'AUTHORING': work, 'PYTHONDONTWRITEBYTECODE': '1', 'GA_INCLUDE_PARKED': os.environ.get('GA_INCLUDE_PARKED', '')}
    if family == 'top' and gid != 'warden': genv['SMG_GUN'] = gid
    steps = []
    bodies = list(manifest.bodies())

    # rest glbs first: the generators share them (written once, reused), so the parallel runs below only read them
    for body in bodies:
        f = f'{root}/rest/{body}/rest_{gid}_R__{gid}_L.glb'
        steps.append(Step(f'rest {body}', PY + [R + '/rest.py', gid, gid, '--body', body, '--out', f], env=genv, cwd=R,
                          reads=f'raised idle of {gid} (paths.raised_clips, else the game idle set in paths.gamefiles)', writes=f))
    if family in ('tube', 'break'):
        src = manifest.path('smg_ref')
        steps.append(Step('seed ref', fn=lambda: seed_ref(src, root + '/ref'), reads=f'{src}/*', writes=f'{root}/ref/*',
                          note=f'gun geometry json the {family} generators read from <root>/ref (copied, nothing else is read from the shipped folders)'))
    # clips: one generator run per pick, both bodies and hands
    for pick in picks:
        script, args = regen.command(AUTH, family, pick, [gid], ','.join(bodies), 'right,left', None, root)
        steps.append(Step(f'clips {pick}{take}', PY + [script] + args, env=genv, cwd=os.path.dirname(script), jobs=jobs, group='clips',
                          reads=f'rest glbs, weapon meshes and anims (paths.weapon_meshes, weapon_anims, rreload_gamefiles), manifest',
                          writes=f'{root}/clips/<body>/{gid}_<side>_{pick}{take}_<clip>.glb + .json, _track.json, _gate.json (+ the family sidecars)'))
    if fb:
        steps.append(Step('fallback clips', PY + [R + '/fallback.py', 'build', '--guns', gid], env=genv, cwd=R,
                          reads=f'the seated magazine track of {gid} in {root}/clips/pma, rest glbs', writes=f'{root}/fallback/<body>/{gid}_<side>_FB[loop]_reload.glb + .json, _track.json, _gate.json'))
    lscript, largs, lfile = LAYOUT[family]
    steps.append(Step('layout', PY + [R + '/' + lscript, 'layout'] + [a.format(root=root, gun=gid) for a in largs], env=genv, cwd=R,
                      reads='the _gate.json files of every clip in ' + root + '/clips', writes=f'{root}/{lfile} (+ .md tables)',
                      note=f'afterwards the {gid} entry is compared with reload.layout of weapons.json'))
    if fb:
        steps.append(Step('fallback layout', PY + [R + '/fallback.py', 'layout', '--guns', gid], env=genv, cwd=R,
                          reads=f'{root}/fallback/<body>/*_gate.json', writes=f'{root}/fallback/layout_fallback.json, gates.md',
                          note=f'afterwards compared with reload.fallback.layout'))
    # lowered-stance variants (authoring/reload/lowprod.py): every gun with a lowered entry and a reload entry; exit 3 = no discard hook in the generator (reported, not a failure)
    if g.get('lowered') and (not r.get('parked') or os.environ.get('GA_INCLUDE_PARKED') == '1'):
        steps.append(Step('lowered variants', PY + [R + '/lowprod.py', 'produce', gid, '--root', root, '--jobs', str(jobs)], env=genv, cwd=R, ok_codes=(0, 3),
                          reads=f'the shipped clips of {gid} (motion kept; else {root}/clips), {root}/rest, the lowered set (paths.low_clips), weapon meshes',
                          writes=f'{root}/lowered/clips (variant clips), solve/<pick>.json (lift.py), bs_<pick> (s bisection), layout.json, magsets/*.glb, report.json',
                          note='per pick: solve the discard offset (lift.py stop or hold), bisect the post-seat scale s, build with smgprod --lift --lowered, hidden window layout, '
                               'magazine sets (no WolvenKit); exit 3 when the generator of the gun has no hook (reason printed)'))
    # build steps: only what this gun plays
    benv = {}
    for key, folder in ((ckey, root + '/clips'),) + (((fkey, root + '/fallback'),) if fb else ()):
        benv[manifest.load()['paths'][key]['env']] = folder
    if r.get('lowered_variant'): benv[manifest.load()['paths'][r['lowered_variant']['clips']]['env']] = root + '/lowered/clips'      # the build and the checks read the variants made here
    if r.get('raised_variant'): benv[manifest.load()['paths'][r['raised_variant']['clips']]['env']] = root + '/raised/clips'
    status = g.get('status') or manifest.load()['types'][g['type']].get('status', 'release')
    tflag = ['--with-test'] if with_test else []
    if no_build:
        steps.append(Step('build', note='no build steps: --no-build (the WolvenKit archive build is skipped)'))
    elif r.get('parked'):
        steps.append(Step('build', note='no build steps: reload.parked (the gun plays the generic reload clips; its own sets are not built)'))
    elif status != 'release' and not with_test:
        steps.append(Step('build', note=f'no build steps: gun status is {status}; use --with-test'))
    else:
        steps.append(Step('build', PY + [HERE + '/build.py', 'reload', 'rreload', '--guns', gid] + tflag, env=benv, cwd=HERE,
                          reads=f'{root}/clips' + (f', {root}/fallback' if fb else '') + ', game files (paths.gamefiles, rreload_gamefiles), WolvenKit',
                          writes='WORK/sets, WORK/tmp_reload, WORK/tmp_rreload, WORK/guns-out/archive/pc/mod/<archive>.archive (+ .xl): partial, only this gun',
                          note=f'reload: the per-hand sets {gid} plays; rreload: its own arm, magazine and part sets; round trip of those'))
    areas = ['rules', 'manifest', 'draft'] + (['lowvar'] if g.get('lowered') and not r.get('parked') else [])
    if r.get('parts') and not r.get('parked'): areas.append('parts')
    if ckey == 'rreload_clips' and not r.get('parked') and r.get('magazine') is not None: areas.append('rreload')
    steps.append(Step('check', PY + [HERE + '/build.py', 'check', '--guns', gid, '--only', ','.join(areas)] + tflag, env=dict(benv, GA_CLIPS_ROOT=root), cwd=HERE,
                      reads=f'{root}/clips' + (f', {root}/fallback' if fb else '') + (', WORK/rreload/roundtrip.txt' if 'rreload' in areas else ''),
                      writes='WORK/check/report.txt, WORK/check/draft/*',
                      note='areas ' + ','.join(areas) + '; sets and roundtrip (WolvenKit, every gun) are not run'))
    return g, r, family, take, root, fb, steps, ship


def seed_ref(src, dst):
    os.makedirs(dst, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(src)):
        if os.path.isfile(f'{src}/{f}') and not os.path.exists(f'{dst}/{f}'):
            shutil.copyfile(f'{src}/{f}', f'{dst}/{f}'); n += 1
    print(f'  copied {n} files from {src}')


def show(i, s):
    print(f'{i}. {s.name}')
    if s.argv:
        e = ' '.join(f'{k}={v}' for k, v in s.env.items() if k != 'PYTHONDONTWRITEBYTECODE')
        print(f'   cmd:    {" ".join(a if " " not in a else chr(34) + a + chr(34) for a in s.argv)}' + (f'   (cwd {s.cwd})' if s.cwd else ''))
        if e: print(f'   env:    {e}')
    if s.reads: print(f'   reads:  {s.reads}')
    if s.writes: print(f'   writes: {s.writes}')
    if s.note: print(f'   note:   {s.note}')


def run_step(s, logdir, i):
    env = dict(os.environ, **s.env)
    env.pop('GA_TEST', None)      # an importing tool sets it for itself; a build must not inherit it (it would switch to test-out)
    log = f'{logdir}/{i:02d}_{s.name.replace(" ", "_")}.log'
    t = time.time()
    r = subprocess.run(s.argv, cwd=s.cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    open(log, 'w', encoding='utf-8').write(r.stdout)
    return r.returncode, time.time() - t, log, r.stdout


def split_loads(w, e):
    """The manifest keeps the shells heard at the end of the hidden part in `late_loads` and the others in `loads`; the generator
    writes all in `loads`. {loads, late_loads} of the generated entry e split the way the manifest entry w is split (last len(late) go to late)."""
    n = len(w.get('late_loads') or [])
    al = list(e.get('loads') or [])
    return {'loads': al[:len(al) - n] if n else al, 'late_loads': al[len(al) - n:] if n else []}


def layout_diff(w, e):
    """Keys of the manifest layout entry w that differ from the generated entry e. A key the generator does not write at all
    (the break layout has no `loads`: the manifest holds them by hand) is not compared: [bad keys], [keys not compared]."""
    def differs(k):
        if e is None: return True
        if k not in e: return False
        if k == 'loads': sp = split_loads(w, e); return sp['loads'] != w['loads'] or sp['late_loads'] != (w.get('late_loads') or [])
        return e[k] != w[k]
    bad = [k for k in LAYOUT_KEYS if k in w and differs(k)]
    skipped = [k for k in LAYOUT_KEYS if k in w and e is not None and k not in e]
    return bad, skipped


def compare_layout(g, r, family, root):
    """The layout the generators wrote for this gun against reload.layout / reload.fallback.layout of the manifest: [(what, ok)]."""
    out = []
    lscript, largs, lfile = LAYOUT[family]; p = f'{root}/{lfile}'
    if os.path.exists(p):
        got = json.load(open(p)).get(g['id'], {}); want = r.get('layout') or {}
        if not want:
            out.append((f'layout: the manifest has no reload.layout for {g["id"]}; the generated one is in {p}', False))
        for pk, clips in want.items():
            for clip, w in clips.items():
                e = got.get(pk, {}).get(clip)
                bad, skipped = layout_diff(w, e)
                out.append((f'layout {pk} {clip}' + (f': differs in {bad}' if bad else '') + (f' (not written by the generator, not compared: {skipped})' if skipped else ''), not bad))
    else:
        out.append((f'layout: {p} was not written', False))
    if r.get('fallback'):
        p = f'{root}/fallback/layout_fallback.json'
        e = json.load(open(p)).get(g['id']) if os.path.exists(p) else None; w = r['fallback']['layout']
        bad, skipped = layout_diff(w, e)
        out.append(('fallback layout' + (f': differs in {bad}' if bad else '') + (f' (not written by the generator, not compared: {skipped})' if skipped else ''), not bad))
    return out


def compare_lowered(g, r, root):
    """The lowered-variant layout lowprod wrote (<root>/lowered/layout.json) against reload.lowered_variant.layout of the manifest: [(what, ok)]; [] when no variants were made."""
    p = f'{root}/lowered/layout.json'
    if not os.path.exists(p): return []
    got = json.load(open(p))['layout']; lv = r.get('lowered_variant'); out = []
    if not lv: return [(f'lowered variants were made but the manifest has no reload.lowered_variant for {g["id"]}', False)]
    out.append((f'lowered wrapper {lv["wrapper"]}', lv['wrapper'] == f'gorillaakimbo_lowreload_{g["id"]}'))
    for pk, clips in lv['layout'].items():
        if 'picks' in lv and pk[:-1] not in lv['picks'] + (lv.get('stance_only') or []): continue      # per-pick wiring: the other slots keep the shipped clip and layout
        for clip, w in clips.items():
            bad, skipped = layout_diff(w, got.get(pk, {}).get(clip))
            out.append((f'lowered layout {pk} {clip}' + (f': differs in {bad}' if bad else ''), not bad))
    rv = r.get('raised_variant'); pr = f'{root}/raised/layout.json'      # the raised variants (the clips the gun plays when it is not lowered)
    if rv and rv.get('layout') and os.path.exists(pr):
        got = json.load(open(pr))['layout']
        for pk, clips in rv['layout'].items():
            if 'picks' in rv and pk[:-1] not in rv['picks']: continue
            for clip, w in clips.items():
                bad, skipped = layout_diff(w, got.get(pk, {}).get(clip))
                out.append((f'raised layout {pk} {clip}' + (f': differs in {bad}' if bad else ''), not bad))
    return out


def write_layout(g, r, family, root):
    """Copy the generated layout values over the manifest's reload.layout / reload.fallback.layout of gun g (same keys as
    compare_layout), patching only that gun's `"reload"` line of weapons.json. Returns [(where, key, old, new)]."""
    changes = []; new = json.loads(json.dumps(r))
    def upd(w, e, where):
        for k in LAYOUT_KEYS:
            if e is None or k not in w: continue
            if k == 'loads' and 'loads' in e: sp = split_loads(w, e)
            else: sp = {}
            for kk in (['loads', 'late_loads'] if k == 'loads' and 'late_loads' in w else [k]):
                v = sp.get(kk, e.get(kk))
                if kk in e or kk in sp:
                    if v != w[kk]: changes.append((where, kk, w[kk], v)); w[kk] = v
    p = f'{root}/{LAYOUT[family][2]}'
    if os.path.exists(p):
        got = json.load(open(p)).get(g['id'], {})
        for pk, clips in (new.get('layout') or {}).items():
            for clip, w in clips.items(): upd(w, got.get(pk, {}).get(clip), f'{pk} {clip}')
    p = f'{root}/fallback/layout_fallback.json'
    if new.get('fallback') and os.path.exists(p):
        upd(new['fallback']['layout'], json.load(open(p)).get(g['id']), 'fallback')
    p = f'{root}/lowered/layout.json'
    if new.get('lowered_variant') and os.path.exists(p):
        got = json.load(open(p))['layout']
        for pk, clips in new['lowered_variant']['layout'].items():
            for clip, w in clips.items(): upd(w, got.get(pk, {}).get(clip), f'lowered {pk} {clip}')
    if not changes: return changes
    mp = os.environ.get('GA_MANIFEST') or os.path.join(HERE, 'weapons.json')
    raw = open(mp, 'rb').read().decode('utf-8'); nl = chr(13) + chr(10) if chr(13) + chr(10) in raw else chr(10)
    lines = raw.split(nl); inside = False; hit = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith('"id":'): inside = ln.strip().rstrip(',') == f'"id": {json.dumps(g["id"])}'
        elif inside and ln.startswith('   "reload": '): hit = i; break
    if hit is None: fail(f'write-layout: no "reload" line for {g["id"]} in {mp}')
    ln = lines[hit]; comma = ',' if ln.rstrip().endswith(',') else ''
    body = ln.strip()[len('"reload": '):]
    if comma: body = body[:-1]
    if json.loads(body) != r or json.dumps(r, ensure_ascii=False) != body:
        fail(f'write-layout: the "reload" line of {g["id"]} is not in the one-line form the tool writes; edit it by hand')
    lines[hit] = '   "reload": ' + json.dumps(new, ensure_ascii=False) + comma
    open(mp, 'wb').write(nl.join(lines).encode('utf-8'))
    return changes


def replace_clips(stage, ship, gid, day=None):
    """Put the gun's clips of <stage>/{clips,fallback}/<body>/<gid>_* into <ship>. A file equal to the shipped one stays. A
    different one moves to <ship>/<folder>.prev-<day>/<body>/ first (a name already there gets .1, .2 ...), then the new one is
    written; a spec json has the stage folder replaced by the shipped one, as if it had been made there. Only files named
    <gid>_*: the layout tables are shared by every gun and never replaced. Returns (moved [(from, to)], added [path], same, absent
    [shipped <gid>_* files this run did not make])."""
    day = day or datetime.date.today().strftime('%Y%m%d')
    moved, added, same, made = [], [], 0, set()
    for sub in ('clips', 'fallback'):
        sd = f'{stage}/{sub}'
        if not os.path.isdir(sd): continue
        for body in sorted(os.listdir(sd)):
            if not os.path.isdir(f'{sd}/{body}'): continue
            for f in sorted(os.listdir(f'{sd}/{body}')):
                src = f'{sd}/{body}/{f}'; dst = f'{ship}/{sub}/{body}/{f}'
                if not (f.startswith(gid + '_') and os.path.isfile(src)): continue
                made.add(dst)
                data = open(src, 'rb').read()
                if f.endswith('.json'): data = data.replace(stage.encode(), ship.encode())
                if os.path.exists(dst):
                    if open(dst, 'rb').read() == data: same += 1; continue
                    aside = f'{ship}/{sub}.prev-{day}/{body}/{f}'; n = 0
                    while os.path.exists(aside):
                        n += 1; aside = f'{ship}/{sub}.prev-{day}/{body}/{f}.{n}'
                    os.makedirs(os.path.dirname(aside), exist_ok=True)
                    shutil.move(dst, aside); moved.append((dst, aside))
                else:
                    added.append(dst)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, 'wb').write(data)
    absent = []
    for sub in ('clips', 'fallback'):
        for body in ('pma', 'pwa'):
            d = f'{ship}/{sub}/{body}'
            if os.path.isdir(d):
                absent += [f'{d}/{f}' for f in sorted(os.listdir(d)) if f.startswith(gid + '_') and f'{d}/{f}' not in made]
    return moved, added, same, absent


def take_opt(argv, name):
    """Value of '--name value' (both removed from argv), else None."""
    if name not in argv: return None
    i = argv.index(name)
    if i + 1 >= len(argv): fail(f'{name} needs a value')
    v = argv[i + 1]; del argv[i:i + 2]
    return v


def run_group(steps, logdir, first):
    """Consecutive steps of one group, in parallel: [(step, (exit, seconds, log, output))]."""
    with concurrent.futures.ThreadPoolExecutor(max(1, steps[0].jobs)) as ex:
        return list(zip(steps, ex.map(lambda ab: run_step(ab[1], logdir, ab[0]), [(first + k, x) for k, x in enumerate(steps)])))


def produce(argv):
    dry = '--dry-run' in argv
    if dry: argv.remove('--dry-run')
    wt = '--with-test' in argv
    if wt: argv.remove('--with-test')
    wl = '--write-layout' in argv
    if wl: argv.remove('--write-layout')
    nb = '--no-build' in argv
    if nb: argv.remove('--no-build')
    if '--include-parked' in argv:      # variants of a parked gun's own clips (tube and break); measured, not wired
        argv.remove('--include-parked'); os.environ['GA_INCLUDE_PARKED'] = '1'
    out = take_opt(argv, '--out'); jobs = int(take_opt(argv, '--jobs') or 3)
    if len(argv) != 1 or argv[0].startswith('-'):
        fail('usage: ga.sh produce <gun> [--out <dir>] [--dry-run] [--jobs n] [--with-test] [--write-layout] [--no-build]')
    gid = argv[0]
    stage = None
    if not out:
        stage = f'{manifest.path("work").rstrip("/")}/produce_{gid}/stage-{time.strftime("%Y%m%d-%H%M%S")}'
    g, r, family, take, root, fb, steps, ship = build_plan(gid, out, jobs, wt, stage, nb)
    print(f'produce {gid}: family {family}, take {take}, picks {",".join(r["slots"])}' + (', quick-drop fallback' if fb else '')
          + f', clips made in {root}/clips' + (' (dry run: nothing is run or written)' if dry else ''))
    if dry:
        for i, s in enumerate(steps, 1): show(i, s)
        if ship:
            print(f'{len(steps) + 1}. replace\n   writes: {ship}/clips and {ship}/fallback: only {gid}_* files that differ from the stage; each replaced file moves '
                  f'to <folder>.prev-{datetime.date.today():%Y%m%d} first\n   note:   only when every step above passed and the layout equals the manifest')
        return 0
    logdir = root + '/work/produce_' + gid
    os.makedirs(logdir, exist_ok=True)
    t0 = time.time(); failed = False; differs = False; i = 0; blocked = []
    while i < len(steps) and not failed:
        s = steps[i]
        if s.group:
            n = 0
            while i + n < len(steps) and steps[i + n].group == s.group: n += 1
            done = run_group(steps[i:i + n], logdir, i + 1); i += n
        elif s.fn:
            t = time.time(); s.fn(); print(f'{s.name}: done, {time.time() - t:.0f} s', flush=True); i += 1; continue
        elif not s.argv:
            print(f'{s.name}: {s.note}'); i += 1; continue
        else:
            done = [(s, run_step(s, logdir, i + 1))]; i += 1
        for st, (code, sec, log, text) in done:
            print(f'{st.name}: exit {code}, {sec:.0f} s, log {log}', flush=True)
            if code == 3 and 3 in st.ok_codes: blocked.append(text.strip().splitlines()[-1] if text.strip() else 'no hook')
            elif code and not failed: failed = True; print(text[-1500:])
        last = done[-1][0].name
        if not failed and last == 'lowered variants':
            for what, ok in compare_lowered(g, r, root):
                print(f'   {"same as manifest" if ok else "DIFFERENT"}: {what}'); differs |= not ok
            if differs and wl:
                for where, k, a, b in write_layout(g, r, family, root): print(f'   written to weapons.json: {where} {k}: {a} -> {b}')
                manifest._m = None; g = find_gun(gid); r = g['reload']
                differs = not all(ok for _, ok in compare_layout(g, r, family, root) + compare_lowered(g, r, root))
                print(f'   layout after writing: {"same as manifest" if not differs else "STILL DIFFERENT"}')
        if not failed and last == ('fallback layout' if fb else 'layout'):
            for what, ok in compare_layout(g, r, family, root):
                print(f'   {"same as manifest" if ok else "DIFFERENT"}: {what}'); differs |= not ok
            if differs and wl:
                for where, k, a, b in write_layout(g, r, family, root): print(f'   written to weapons.json: {where} {k}: {a} -> {b}')
                manifest._m = None; g = find_gun(gid); r = g['reload']
                differs = not all(ok for _, ok in compare_layout(g, r, family, root))
                print(f'   layout after writing: {"same as manifest" if not differs else "STILL DIFFERENT"}')
    if ship and not failed and not differs:
        moved, added, same, absent = replace_clips(root, ship, gid)
        print(f'replace: {same} files equal to the shipped ones (kept), {len(moved)} replaced, {len(added)} new, {len(absent)} shipped {gid}_* files not made by this run (kept)')
        for a, b in moved: print(f'   moved {a}\n      to {b}')
        for a in added: print(f'   new {a}')
    elif ship:
        print(f'replace: not done ({"a step failed" if failed else "the layout differs from the manifest"}); the new clips stay in {root}; shipped clips unchanged')
    for b in blocked: print(f'lowered variants: NOT MADE: {b}')
    print(f'produce {gid}: {"failed" if failed else ("done, layout differs from the manifest" if differs else "done")}{" (lowered variants not made)" if blocked else ""} in {time.time() - t0:.0f} s')
    return 1 if failed or differs else 0


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == 'gun':
        import gunadd
        if rest[:1] != ['add'] or len(rest) < 2 or rest[1] in ('-h', '--help'):
            print(gunadd.__doc__); return 0 if rest[1:2] in (['-h'], ['--help']) else 2
        return gunadd.add(rest[1:])
    if cmd == 'drafts':
        import drafts; return drafts.drafts(rest)
    if cmd == 'pick':
        import drafts; return drafts.pick(rest)
    if cmd == 'ingame':
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ingame'))
        import ingame; return ingame.main(rest)
    if cmd == 'produce':
        if rest[:1] in (['-h'], ['--help']): print(__doc__); return 0
        return produce(rest)
    print(f'ga: unknown command {cmd}\n' + __doc__.split('\n\n')[0], file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
