"""Builds everything Gorilla Akimbo ships that is generated: both animation archives, their .archive.xl files,
GorillaAkimboSounds.reds and GorillaAkimboGuns.reds. Guns, types and paths come from weapons.json.

usage: build.py <command> [...] [--with-test] [--force] [--ref <folder>]
  extract   game files the build reads, from the game's archives into the gamefiles folder (WolvenKit)
  reload    per-hand reload arm sets (flick.py), then pack
  topmag    top-magazine reload sets (topmagsets.py, topmag.py), then pack
  mag       magazine sets of the top-magazine gun (magtrack.py), then pack
  lowered   lowered stance sets (lowsets.py, lowset.py), then pack
  raised    raised pose sets of the guns with a raised pose (raisedsets.py, raisedset.py), then pack; their own
            per-hand reload sets are part of reload, their top-magazine partner sets part of topmag
  xl        both .archive.xl files
  sounds    GorillaAkimboSounds.reds
  guns      GorillaAkimboGuns.reds
  tables    poses.json, tunes.json, partner_categories.json, guns.json for the authoring tools, into WORK/tables
  rreload   the rifles' own one-handed reload sets, their magazine sets, archive and .archive.xl, round trip
            (rreload.py; about 10 to 15 minutes)
  all       everything above except extract and tables
  verify    compare the outputs with a reference (git HEAD of the reference repo, or --ref <folder>)
  check     numeric checks of the shipped clips and built sets (authoring/checks/gate.py):
            check [--guns id,id] [--bodies pma,pwa] [--clips <dir>] [--only area,area]
--with-test (or GA_TEST=1) includes weapons.json content with status "test" and writes to WORK/test-out, never into
the checkout. Work files go to WORK (weapons.json paths.work), outside the repo.
"""
import concurrent.futures, glob, hashlib, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
args = sys.argv[1:]
if args[:1] == ['check']:
    sys.exit(subprocess.run([sys.executable, HERE + '/authoring/checks/gate.py'] + args[1:]).returncode)
if '--with-test' in args:
    os.environ['GA_TEST'] = '1'
FORCE = '--force' in args
REF_DIR = args[args.index('--ref') + 1] if '--ref' in args else None
if REF_DIR:
    args.remove(REF_DIR)
cmds = [a for a in args if not a.startswith('--')]
import manifest

TEST = manifest.with_test()
WK = manifest.path('wolvenkit')
GAME = manifest.path('game')
WORK = manifest.path('work') + ('/test' if TEST else '')
OUT = manifest.path('work') + '/test-out' if TEST else ROOT
OUT_ARCHIVE = OUT + '/archive/pc/mod'
OUT_SCRIPTS = OUT + '/r6/scripts/GorillaAkimbo'
SETS = WORK + '/sets'
ARCHIVES = ('GorillaAkimbo', 'GorillaAkimboLowered')
TEXTS = ('archive/pc/mod/GorillaAkimbo.archive.xl', 'archive/pc/mod/GorillaAkimboLowered.archive.xl',
         'r6/scripts/GorillaAkimbo/GorillaAkimboSounds.reds')
JOBS = int(os.environ.get('JOBS', '4'))
BACKSLASH = chr(92)
os.environ['DOTNET_ROOT'] = manifest.path('dotnet_root')
os.environ['WK_DIR'] = os.path.dirname(WK).replace('/', '\\')
os.environ['GAME'] = GAME.replace('/', '\\')
os.environ['GAMEFILES'] = manifest.path('gamefiles')


def die(msg):
    raise SystemExit('build: ' + msg)


def run(cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode != 0:
        die(f'failed: {" ".join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}')
    return r.stdout


def py(script, *a):
    return run([sys.executable, f'{HERE}/{script}', *a])


def wk(*a):
    return run([WK, *a])


def fresh(path):
    """An empty folder for the build's own intermediate files (anything in it is from an earlier run and rebuilt)."""
    if not path.startswith(WORK + '/'):
        die('refusing to clear ' + path)
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    return path


def need(path):
    if not os.path.exists(path):
        die(f'missing {path}\n  game file not extracted: run tools/anim/build.sh extract\n  (authored clips live outside '
            f'the repo: see weapons.json paths)')
    return path


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


# ---- extract -------------------------------------------------------------------------------------------------------
def fnv1a64(s):
    h = 0xcbf29ce484222325
    for b in s.encode():
        h = ((h ^ b) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def extract():
    """Unbundles by path hash (most of these files are not in WolvenKit's name list, so a name pattern finds nothing),
    then exports glb / converts to JSON next to each file."""
    todo = [(p, forms) for p, forms in manifest.needed_game_files()
            if FORCE or not os.path.exists(manifest.gamefile(p))]
    if todo:
        tmp = fresh(WORK + '/extract')
        hashes = {str(fnv1a64(p.lower())): p for p, _ in todo}
        open(tmp + '/hashes.txt', 'w').write('\n'.join(hashes) + '\n')
        for folder in ('content', 'ep1'):
            # The exit code is not 0 when some archive lacks some hash, which is always: the files are checked below.
            run([WK, 'unbundle', f'{GAME}/archive/pc/{folder}', '-o', tmp, '--hash', tmp + '/hashes.txt'], check=False)
        for h, p in hashes.items():
            got = [f for f in (f'{tmp}/{h}.bin', tmp + '/' + p.replace('\\', '/')) if os.path.exists(f)]
            if not got:
                die(f'{p} (hash {h}) is in no archive under {GAME}/archive/pc')
            dst = manifest.gamefile(p)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(got[0], dst)
            print('extracted', dst)
    for p, forms in manifest.needed_game_files():
        f = manifest.gamefile(p)
        if 'glb' in forms and (FORCE or not os.path.exists(f + '.glb')):
            wk('export', f, '-o', os.path.dirname(f), '-gp', GAME)
            need(f + '.glb'); print('exported', f + '.glb')
        if 'json' in forms and (FORCE or not os.path.exists(f + '.json')):
            wk('convert', 's', f, '-o', os.path.dirname(f))
            need(f + '.json'); print('converted', f + '.json')
    print('game files ready in', manifest.path('gamefiles'))


# ---- anim sets -----------------------------------------------------------------------------------------------------
def import_set(glb, base_anims, keep, out):
    """glb clips into a copy of a game anim set (animimport.ps1); with keep, every other clip is renamed away."""
    name = os.path.basename(out)[:-len('.anims')]
    tmp = os.path.dirname(glb)
    anims = f'{tmp}/{name}.anims'
    shutil.copyfile(base_anims, anims)
    o = run(['pwsh', '-NoProfile', '-File', f'{HERE}/animimport.ps1', glb.replace('/', '\\'), anims.replace('/', '\\')])
    if 'import ok: True' not in o:
        die(f'import failed: {name}\n{o[-1500:]}')
    if keep:
        wk('convert', 's', anims, '-o', tmp)
        py('animrename.py', anims + '.json', *keep)
        os.makedirs(tmp + '/out', exist_ok=True)
        wk('convert', 'd', anims + '.json', '-o', tmp + '/out')
        anims = f'{tmp}/out/{name}.anims'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(need(anims), out)
    print('built', name, flush=True)


def parallel(jobs):
    with concurrent.futures.ThreadPoolExecutor(JOBS) as ex:
        for f in [ex.submit(j) for j in jobs]:
            f.result()


def source_set(key, **kw):
    return manifest.gamefile(manifest.depot(manifest.load()['game_files'][key].format(**kw)))


def reload_names():
    return [(body, side, manifest.reload_set(body, side)) for body in manifest.bodies() for side in ('right', 'left')]


def renamed():
    """{old packed path: new packed path} of the sets renamed since the reference (set_names in weapons.json)."""
    p = 'gorillaakimbo/animations/'
    return {f'{p}{manifest.reload_set(b, s, old=True)}.anims': f'{p}{manifest.reload_set(b, s)}.anims'
            for b in manifest.bodies() for s in ('right', 'left') if manifest.reload_set(b, s, old=True) != manifest.reload_set(b, s)}


def reload():
    tmp = fresh(WORK + '/tmp_reload')

    def one(body, side, name):
        src = source_set('reload_source', body=body, side=side)
        glb = f'{tmp}/{name}/{name}.glb'
        os.makedirs(os.path.dirname(glb))
        py('flick.py', need(src + '.glb'), glb, side)
        import_set(glb, need(src), None, f'{SETS}/GorillaAkimbo/{name}.anims')

    def own(body, side, name, glb_pose, glb_hands):
        # A gun with a raised pose: the same clips from its raised idle, with its equip, unequip and melee.
        src = source_set('reload_source', body=body, side=side)
        glb = f'{tmp}/{name}/{name}.glb'
        os.makedirs(os.path.dirname(glb))
        py('flick.py', need(src + '.glb'), glb, side, '--rest', need(glb_pose), '--hands', need(glb_hands))
        import_set(glb, need(src), None, f'{SETS}/GorillaAkimbo/{name}.anims')

    parallel([lambda a=a: one(*a) for a in reload_names()]
             + [lambda a=(body, side, name, glb, hands): own(*a) for body, side, kind, name, glb, hands, _ in raised_plan() if kind == 'reload'])


def raised_plan():
    from raisedsets import plan
    return plan()


def raised():
    from raisedsets import POSE_CLIPS
    tmp = fresh(WORK + '/tmp_raised')

    def one(body, side, name, clip):
        base = source_set('lowered_base', body=body)
        glb = f'{tmp}/{name}/{name}.glb'
        os.makedirs(os.path.dirname(glb))
        py('raisedset.py', need(base + '.glb'), need(clip), glb, side, ','.join(POSE_CLIPS))
        import_set(glb, need(base), [c + ('' if side == 'right' else '_l') for c in POSE_CLIPS], f'{SETS}/GorillaAkimbo/{name}.anims')

    parallel([lambda a=(body, side, name, glb): one(*a) for body, side, kind, name, glb, _, _ in raised_plan() if kind == 'base'])


def topmag_plan():
    from topmagsets import plan
    return plan(manifest.path('clips'))


def topmag():
    tmp = fresh(WORK + '/tmp_topmag')

    def one(body, name, clips):
        # A copy of the right-hand reload source set holds the clips under the game's reload clip names.
        src = source_set('reload_source', body=body, side='right')
        glb = f'{tmp}/{name}/{name}.glb'
        os.makedirs(os.path.dirname(glb))
        py('topmag.py', need(src + '.glb'), glb, *[f'{need(p)}={n}' for p, n in clips])
        import_set(glb, need(src), [n for _, n in clips], f'{SETS}/GorillaAkimbo/{name}.anims')

    parallel([lambda a=(body, name, clips): one(*a) for body, name, clips, _ in topmag_plan()])


def mag_names():
    m = manifest.magazine()
    return [f'{m["set_prefix"]}_{family}_{side}' for family in m['families'] for side in ('left', 'right')] if m else []


def mag():
    m = manifest.magazine()
    if not m:
        return
    tmp = fresh(WORK + '/tmp_mag')
    py('magtrack.py', need(manifest.path('mag_spec')), tmp + '/glb')
    vanilla = need(manifest.gamefile(manifest.depot(m['vanilla_set'])))
    keep = ['reload', 'reload_01', 'reload_02', 'empty_reload', 'empty_reload_01', 'empty_reload_02']

    def one(name):
        os.makedirs(f'{tmp}/{name}')
        glb = f'{tmp}/{name}/{name}.glb'
        shutil.copyfile(need(f'{tmp}/glb/{name}.glb'), glb)
        import_set(glb, vanilla, keep, f'{SETS}/GorillaAkimbo/{name}.anims')

    parallel([lambda n=n: one(n) for n in mag_names()])


def lowered_plan():
    from lowsets import plan
    return plan(manifest.path('low_clips'))


def lowered():
    tmp = fresh(WORK + '/tmp_lowered')

    def one(body, side, name, clip):
        base = source_set('lowered_base', body=body)
        glb = f'{tmp}/{name}/{name}.glb'
        os.makedirs(os.path.dirname(glb))
        py('lowset.py', need(base + '.glb'), need(clip), glb, side)
        keep = ['friendly_idlepose', 'safe_action', 'equip_safe']
        import_set(glb, need(base), keep if side == 'right' else [k + '_l' for k in keep],
                   f'{SETS}/GorillaAkimboLowered/{name}.anims')

    parallel([lambda a=(body, side, name, clip): one(*a) for body, side, name, clip, _ in lowered_plan()])


def expected(archive):
    if archive == 'GorillaAkimboLowered':
        return [name for _, _, name, _, _ in lowered_plan()]
    return ([n for _, _, n in reload_names()] + [name for _, name, _, _ in topmag_plan()] + mag_names()
            + [name for _, _, _, name, _, _, _ in raised_plan()])


def pack(archive):
    names = expected(archive)
    missing = [n for n in names if not os.path.exists(f'{SETS}/{archive}/{n}.anims')]
    if missing:
        die(f'{archive}: {len(missing)} of {len(names)} sets are not built yet (first: {missing[0]}); run build.sh all')
    stage = fresh(f'{WORK}/pack/{archive}')
    os.makedirs(stage + '/gorillaakimbo/animations')
    for n in names:
        shutil.copyfile(f'{SETS}/{archive}/{n}.anims', f'{stage}/gorillaakimbo/animations/{n}.anims')
    wk('pack', stage, '-o', WORK + '/pack')
    os.makedirs(OUT_ARCHIVE, exist_ok=True)
    shutil.copyfile(need(f'{WORK}/pack/{archive}.archive'), f'{OUT_ARCHIVE}/{archive}.archive')
    print(f'packed {OUT_ARCHIVE}/{archive}.archive ({len(names)} sets)')


def xl():
    os.makedirs(OUT_ARCHIVE, exist_ok=True)
    print('GorillaAkimbo.archive.xl:', py('genxl.py', OUT_ARCHIVE + '/GorillaAkimbo.archive.xl', SETS + '/GorillaAkimbo').strip())
    print('GorillaAkimboLowered.archive.xl:',
          py('genlowxl.py', OUT_ARCHIVE + '/GorillaAkimboLowered.archive.xl', manifest.path('low_clips')).strip())


def sounds():
    for p, _ in manifest.sound_sets():
        need(manifest.gamefile(p, '.json'))
    os.makedirs(OUT_SCRIPTS, exist_ok=True)
    print(py('gensounds.py', manifest.path('gamefiles'), OUT_SCRIPTS + '/GorillaAkimboSounds.reds').strip())


def guns():
    os.makedirs(OUT_SCRIPTS, exist_ok=True)
    print(py('genguns.py', OUT_SCRIPTS + '/GorillaAkimboGuns.reds').strip())


def tables():
    """The manifest's tables in the file formats the authoring tools outside the repo read."""
    out = WORK + '/tables'
    os.makedirs(out, exist_ok=True)
    for name, data in (('poses.json', manifest.poses()), ('tunes.json', manifest.tunes()),
                       ('partner_categories.json', manifest.partner_categories(enabled_only=False)),
                       ('guns.json', {v: list(t) for v, t in manifest.lowered_guns().items()})):
        json.dump(data, open(f'{out}/{name}', 'w', encoding='utf-8', newline='\n'), indent=1)
        print('wrote', f'{out}/{name}')


# ---- verify --------------------------------------------------------------------------------------------------------
def unpacked(archive_file, to):
    """{packed path: sha256} of an archive's files."""
    fresh(to)
    wk('unbundle', archive_file, '-o', to)
    return {os.path.relpath(f, to).replace('\\', '/'): sha(f)
            for f in glob.glob(to + '/**/*', recursive=True) if os.path.isfile(f)}


def verify():
    ref = WORK + '/ref'
    fresh(ref)
    if REF_DIR:
        src = REF_DIR.replace('\\', '/')
        read = lambda rel: open(f'{src}/{rel}', 'rb').read()
        print('reference: folder', src)
    else:
        repo = manifest.path('reference')
        # Blobs straight from the object store: no checkout, no line ending conversion, git state untouched.
        read = lambda rel: subprocess.run(['git', '-C', repo, 'cat-file', 'blob', 'HEAD:' + rel], capture_output=True, check=True).stdout
        print('reference: git HEAD of', repo)
    bad = 0
    ren = renamed()
    for rel in TEXTS:
        mine = open(f'{OUT}/{rel}', 'rb').read() if os.path.exists(f'{OUT}/{rel}') else None
        want = read(rel)
        same = mine == want
        note = '' if mine is not None else ' (not built)'
        if not same and mine is not None and ren:
            # The reference names the renamed sets by their old names: compare with those names replaced.
            for old, new in ren.items():
                want = want.replace(old.replace('/', BACKSLASH).encode(), new.replace('/', BACKSLASH).encode())
            same = mine == want
            note = f' (identical apart from the {len(ren)} renamed set names)' if same else ''
        bad += not same
        print(f'{"identical" if same else "DIFFERENT":10s} {rel}{note}')
    for a in ARCHIVES:
        rel = f'archive/pc/mod/{a}.archive'
        if not os.path.exists(f'{OUT}/{rel}'):
            print(f'DIFFERENT  {rel} (not built)'); bad += 1
            continue
        open(f'{ref}/{a}.archive', 'wb').write(read(rel))
        want = unpacked(f'{ref}/{a}.archive', f'{ref}/{a}')
        got = unpacked(f'{OUT}/{rel}', f'{WORK}/verify/{a}')
        moved = [(old, new) for old, new in ren.items() if old in want and old not in got and new in got and new not in want]
        for old, new in moved:
            print(f'  {"renamed, content identical" if want[old] == got[new] else "renamed, content DIFFERS"}: {old} -> {new}')
            want[new] = want.pop(old)
        same = sorted(k for k in want if got.get(k) == want[k])
        changed = sorted(k for k in want if k in got and got[k] != want[k])
        only_ref, only_new = sorted(set(want) - set(got)), sorted(set(got) - set(want))
        whole = sha(f'{ref}/{a}.archive') == sha(f'{OUT}/{rel}')
        ok = not (changed or only_ref or only_new)
        bad += not ok
        print(f'{"identical" if ok else "DIFFERENT":10s} {rel}: {len(same)} of {len(want)} packed files byte-identical'
              + (f' ({len(moved)} of them renamed)' if moved else '') + ', '
              f'{len(changed)} differ, {len(only_ref)} only in the reference, {len(only_new)} only in the build; '
              f'archive file itself {"byte-identical" if whole else "differs"}')
        for k in changed:
            print('  differs:', k)
        for k in only_ref:
            print('  only in the reference:', k)
        for k in only_new:
            print('  only in the build:', k)
    print('verify:', 'all identical' if not bad else f'{bad} outputs differ')
    return bad


STEPS = {'extract': extract, 'reload': reload, 'topmag': topmag, 'mag': mag, 'lowered': lowered, 'raised': raised, 'xl': xl,
         'sounds': sounds, 'guns': guns, 'tables': tables}
import rreload
STEPS['rreload'] = lambda: rreload.step(sys.modules[__name__])
PACKS = {'reload': 'GorillaAkimbo', 'topmag': 'GorillaAkimbo', 'mag': 'GorillaAkimbo', 'lowered': 'GorillaAkimboLowered',
         'raised': 'GorillaAkimbo'}

if __name__ == '__main__':
    if not cmds or any(c not in STEPS and c not in ('all', 'verify') for c in cmds):
        print(__doc__)
        sys.exit(2)
    if 'all' in cmds:
        cmds = ['reload', 'topmag', 'mag', 'lowered', 'raised', 'rreload', 'xl', 'sounds', 'guns'] + [c for c in cmds if c in ('verify',)]
    os.makedirs(WORK, exist_ok=True)
    print(f'work {WORK}, output {OUT}' + (', test content included' if TEST else ''))
    for c in cmds:
        if c in STEPS:
            STEPS[c]()
    for a in ARCHIVES:
        if any(PACKS.get(c) == a for c in cmds):
            pack(a)
    if 'verify' in cmds:
        sys.exit(1 if verify() else 0)
