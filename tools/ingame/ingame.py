"""ga ingame: scripted in-game test of one gun (or a vanilla pair) with every changed file backed up and restored.

usage: ga.sh ingame <gun> [--partner <gun>] [--item <Items.Preset_X_Default>] [--record]
                          [--build | --overlay <archive folder>] [--spec <json>] [--baseline] [--visual] [--work <dir>]
       ga.sh ingame --dry-run [<gun>]        whole run on copies of the saves and settings, no game, no MO2 (acceptance test)
       ga.sh ingame --restore <run folder>   put everything of an interrupted run back from its journal
Details in tools/ingame/README.md.
"""
import atexit, datetime, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE) + '/anim')
import guard, winio

LOCK = 'C:/Modding/gg-work/gamelock'
PROBE = 'gaingame'
SHORTCUT = 'moshortcut://Cyberpunk 2077:Cyberpunk 2077 - skip REDmod deploy'


class Env:
    """Every path the harness reads or writes. real() is the owner's machine; sandbox() is a copy under a run folder."""

    def __init__(self, base):
        b = base
        self.saves = f'{b["home"]}/Saved Games/CD Projekt Red/Cyberpunk 2077'
        self.profile = f'{b["inst"]}/profiles/3077'
        self.mods = f'{b["inst"]}/mods'
        self.overwrite = f'{b["inst"]}/overwrite'
        self.user_ini = f'{self.overwrite}/red4ext/plugins/mod_settings/user.ini'
        self.mo2_ini = f'{b["local"]}/ModOrganizer/Cyberpunk 2077/ModOrganizer.ini'
        self.mo2_exe = b['mo2_exe']
        self.lock = b['lock']
        self.sandbox = b.get('sandbox', False)
        self.out_dir = f'{self.overwrite}/bin/x64/plugins/cyber_engine_tweaks/mods/{PROBE}'

    @staticmethod
    def real():
        return Env({'home': os.path.expanduser('~').replace('\\', '/'), 'inst': 'C:/Modding/Cyberpunk 2077',
                    'local': os.environ.get('LOCALAPPDATA', '').replace('\\', '/'), 'mo2_exe': 'C:/Modding/MO2/ModOrganizer.exe', 'lock': LOCK})

    @staticmethod
    def copy_of(real, root):
        """Copies of the saves, the settings files and the modlist under root; the same Env shape pointing at them."""
        e = Env({'home': f'{root}/home', 'inst': f'{root}/inst', 'local': f'{root}/local', 'mo2_exe': '', 'lock': f'{root}/gamelock', 'sandbox': True})
        guard.copy_tree(real.saves, e.saves)
        for src, dst in ((f'{real.profile}/UserSettings.json', f'{e.profile}/UserSettings.json'),
                         (f'{real.profile}/modlist.txt', f'{e.profile}/modlist.txt'),
                         (f'{real.profile}/settings.ini', f'{e.profile}/settings.ini'),
                         (real.user_ini, e.user_ini), (real.mo2_ini, e.mo2_ini)):
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        os.makedirs(e.mods, exist_ok=True)
        return e


def log(run, msg):
    line = f'{time.strftime("%H:%M:%S")} {msg}'
    print(line, flush=True)
    if run: run.write(line + '\n'); run.flush()


class Run:
    def __init__(self, env, folder, spec, dry):
        self.env, self.dir, self.spec, self.dry = env, folder, spec, dry
        os.makedirs(folder, exist_ok=True)
        self.f = open(f'{folder}/run.log', 'a', encoding='utf8')
        self.q = f'{folder}/quarantine'
        self.saves = guard.SaveGuard(env.saves, f'{folder}/backup/saves', self.q)
        self.files = guard.FileGuard(f'{folder}/backup/files', self.q)
        self.deployed = []          # folders this run added to the mods folder
        self.mo2_was_running = False
        self.have_lock = False
        self.restored = False

    def say(self, m): log(self.f, m)

    def journal(self):
        j = {'env': {k: v for k, v in vars(self.env).items()}, 'dry': self.dry, 'deployed': self.deployed,
             'mo2_was_running': self.mo2_was_running, 'have_lock': self.have_lock,
             'saves': {'snap': self.saves.snap}, 'files': [list(i) for i in self.files.items]}
        with open(f'{self.dir}/journal.json', 'w') as f:
            json.dump(j, f, indent=1)

    # ---- game and MO2 control -------------------------------------------------------------------------------
    def game_running(self): return winio.running('Cyberpunk2077.exe')

    def stop_game(self):
        if self.dry or not self.game_running(): return
        winio.kill('Cyberpunk2077.exe')
        if not winio.wait_gone('Cyberpunk2077.exe', 20):
            winio.kill('Cyberpunk2077.exe', True); winio.wait_gone('Cyberpunk2077.exe', 20)

    def stop_mo2(self):
        if self.dry or not winio.running('ModOrganizer.exe'): return True
        winio.kill('ModOrganizer.exe')
        return winio.wait_gone('ModOrganizer.exe', 60)

    # ---- teardown: the only path out ---------------------------------------------------------------------------
    def teardown(self):
        if self.restored: return True
        self.say('teardown: stop game, close MO2, restore')
        self.stop_game()
        if not self.stop_mo2():
            self.say('MO2 did not close in 60 s; NOT restoring (it rewrites modlist.txt on exit). Close it, then run: ga.sh ingame --restore ' + self.dir)
            return False
        ok = True
        for d in self.deployed:
            if os.path.exists(d):
                self.say(f'deployed folder moved aside: {guard.aside(d, self.q + "/deployed")}')
        o = f'{self.env.out_dir}/out.txt'
        if os.path.isfile(o):
            os.makedirs(f'{self.dir}/evidence', exist_ok=True)
            shutil.copy2(o, f'{self.dir}/evidence/out.txt')
        r, notes = self.files.restore(); ok &= r
        for n in notes: self.say('files: ' + n)
        r, notes = self.saves.restore(); ok &= r
        for n in notes: self.say('saves: ' + n)
        self.restored = ok
        self.say('restore ' + ('verified: every file and save folder equals its snapshot' if ok else 'FAILED, see notes; backups are in ' + self.dir + '/backup'))
        if ok and self.have_lock and os.path.isdir(self.env.lock):
            guard.aside(self.env.lock, f'{self.dir}/lock')       # moved, not deleted; the lock is free
            self.have_lock = False
        if ok and self.mo2_was_running and not self.dry:
            subprocess.Popen([self.env.mo2_exe, '-i', 'Cyberpunk 2077'], cwd=os.path.dirname(self.env.mo2_exe))
        self.journal()
        return ok


def pre_checks(run):
    env = run.env
    if not run.dry and run.game_running():
        raise SystemExit('Cyberpunk2077.exe is running: the owner may be playing. Nothing touched.')
    if os.path.exists(env.lock):
        raise SystemExit(f'game lock held: {env.lock}: ' + (open(f'{env.lock}/owner.txt').read() if os.path.exists(f'{env.lock}/owner.txt') else ''))
    os.makedirs(os.path.dirname(env.lock), exist_ok=True)
    os.mkdir(env.lock)
    run.have_lock = True
    with open(f'{env.lock}/owner.txt', 'w') as f:
        f.write(f'ga ingame {run.dir} {datetime.datetime.now().isoformat()}\n')
    run.say(f'lock taken: {env.lock}')
    if not run.dry and winio.running('ModOrganizer.exe'):
        run.mo2_was_running = True
        run.say('MO2 is open: closing it (restarted at the end)')
        if not run.stop_mo2():
            raise SystemExit('MO2 did not close; close it and retry')


def backups(run):
    """Everything is copied and verified BEFORE any edit or launch."""
    e = run.env
    info = run.saves.snapshot()
    run.say(f'saves: {info["entries"]} entries hashed ({info["files"]} files), {info["copied"]} copied, {info["bytes"] // 1024} KB, verified')
    for p in (f'{e.profile}/UserSettings.json', f'{e.profile}/modlist.txt', f'{e.profile}/settings.ini', e.user_ini, e.mo2_ini,
              f'{e.out_dir}/out.txt'):
        run.files.add(p)
    run.say(f'files: {len(run.files.items)} registered, existing ones copied and verified')
    run.journal()


def apply_setup(run, args):
    e, sp = run.env, run.spec
    mods = sp['mods']
    changes = {('/audio/volume', 'MusicVolume'): 0}
    d = sp['display']
    mon = winio.monitors() if not run.dry else 2
    if args.get('visual'):
        run.say('visual test: monitor and HDR stay as the owner has them; music 0 only')
    elif mon >= 2:
        changes.update({('/video/display', 'OutputMonitor'): d['monitor'], ('/video/display', 'Resolution'): d['resolution'],
                        ('/video/display', 'HDRModes'): d['hdr']})
    else:
        changes[('/video/display', 'HDRModes')] = d['hdr']
        run.say('one display attached: used as is, HDR off')
    old = guard.edit_settings(f'{e.profile}/UserSettings.json', changes)
    run.say('settings: ' + ', '.join(f'{k[1]} {old[k]} -> {changes[k]}' for k in changes))
    ml = f'{e.profile}/modlist.txt'
    data = open(ml, 'rb').read()
    data = guard.set_mod(data, mods['probe'], True)
    if args.get('baseline'):
        data = guard.set_mod(data, mods['release'], False)
        data = guard.set_mod(data, mods['overlay'], False)
    elif args.get('overlay'):
        data = guard.set_mod(data, mods['overlay'], True)
    open(ml, 'wb').write(data)
    run.say(f'modlist: probe on' + (', Gorilla Akimbo off (baseline)' if args.get('baseline') else '') + (', overlay on' if args.get('overlay') and not args.get('baseline') else ''))
    src = f'{HERE}/probe/{PROBE}'
    dst = f'{e.mods}/{mods["probe"]}/bin/x64/plugins/cyber_engine_tweaks/mods/{PROBE}'
    if os.path.exists(f'{e.mods}/{mods["probe"]}'):
        raise SystemExit(f'mod folder {mods["probe"]} already exists; the harness will not overwrite it')
    run.deployed.append(f'{e.mods}/{mods["probe"]}')
    run.journal()
    shutil.copytree(src, dst)
    if args.get('overlay') and not args.get('baseline'):
        if os.path.exists(f'{e.mods}/{mods["overlay"]}'):
            raise SystemExit(f'mod folder {mods["overlay"]} already exists')
        run.deployed.append(f'{e.mods}/{mods["overlay"]}')
        shutil.copytree(args['overlay'], f'{e.mods}/{mods["overlay"]}/archive/pc/mod')
    run.journal()


# ---- probe link --------------------------------------------------------------------------------------------------
class Probe:
    def __init__(self, run):
        self.run, self.n = run, 0
        self.cmd = f'{run.env.mods}/{run.spec["mods"]["probe"]}/bin/x64/plugins/cyber_engine_tweaks/mods/{PROBE}/cmd.txt'
        self.out = f'{run.env.out_dir}/out.txt'

    def lines(self):
        try: return open(self.out, encoding='utf8', errors='replace').read().splitlines()
        except OSError: return []

    def send(self, text, timeout=30):
        self.n += 1
        tok = f'{os.getpid()}-{self.n}'
        with open(self.cmd, 'w', newline='\n') as f:
            f.write(text.rstrip('\n') + f'\n#{tok}\n')
        t = time.time()
        while time.time() - t < timeout:
            ls = self.lines()
            for i in range(len(ls) - 1, -1, -1):
                if ls[i].endswith(f'done {tok}'):
                    return [l[9:] for l in ls[:i] if l]
            time.sleep(0.3)
        raise TimeoutError(f'probe did not answer: {text.splitlines()[0]}')


def launch(run, probe):
    """Fresh game start through MO2; returns when V is attached in the loaded save."""
    sp, e = run.spec, run.env
    if os.path.isfile(probe.out): guard.aside(probe.out, run.q + '/out')
    subprocess.Popen([e.mo2_exe, '-i', 'Cyberpunk 2077', SHORTCUT], cwd=os.path.dirname(e.mo2_exe), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t = time.time()
    while not winio.window():
        if time.time() - t > 240: raise TimeoutError('game window did not appear in 240 s')
        time.sleep(2)
    run.say(f'game window up after {time.time() - t:.0f} s')
    time.sleep(20)
    winio.front()
    winio.screenshot(f'{run.dir}/evidence/menu.png')
    run.say('menu screenshot taken; loading the save (Continue)')
    w = winio.window()[1]
    ld = sp['load']
    for _ in range(ld['clicks']):
        winio.click(w[0] + ld['continue'][0] * w[2], w[1] + ld['continue'][1] * w[3])
        time.sleep(ld['pause'])
    t = time.time()
    while time.time() - t < sp['load_timeout']:
        try:
            r = probe.send('ready', 10)
            if any('ready=true' in l for l in r): break
        except TimeoutError: pass
        if sp['load'].get('space'): winio.key('SPACE')
        time.sleep(5)
    else:
        raise TimeoutError('V not attached before the load timeout')
    run.say(f'V attached after {time.time() - t:.0f} s')
    who = probe.send(f'lua local p=Game.GetPlayer(); log("who level="..tostring(PlayerDevelopmentSystem.GetData(p):GetProficiencyLevel(gamedataProficiencyType.Level)))')
    lv = [l for l in who if 'who level=' in l]
    run.say(lv[-1] if lv else 'who: no answer')
    ex = sp.get('expect_level')
    got = [int(float(m.group(1))) for l in lv for m in [re.search(r'level=([\d.]+)', l)] if m]
    if ex and ex not in got:
        raise RuntimeError(f'wrong save loaded (expected level {ex}): {lv}')
    s = sp['spot']
    probe.send(f'god\ntp {s["x"]} {s["y"]} {s["z"]} {s.get("yaw", 0)}', 15)
    time.sleep(4)


def rec_name(g, item):
    return item or f'Items.Preset_{g["name"].replace(" ", "")}_Default'


def battery(run, probe, pair, args):
    """One pair through the spec's ops. Returns the result rows."""
    sp = run.spec
    rows, tag, rec = [], pair['tag'], None
    shotn = 0
    def note(k, v):
        rows.append({'pair': tag, 'op': k, 'result': v}); run.say(f'{tag} {k}: {v}')
    for st in sp['setup']:
        probe.send(st.replace('{R}', pair['right']).replace('{L}', pair['left']), 15); time.sleep(1.5)
    for op in sp['battery']:
        k = op['op']
        if k == 'equip':
            probe.send(f'give {pair["right"]} 1\ngive {pair["left"]} 1\ngive Ammo.HandgunAmmo 500\ngive Ammo.RifleAmmo 500\ngive Ammo.SMGAmmo 500\ngive Ammo.ShotgunAmmo 100\nhol', 20)
            time.sleep(3)
            ok = False
            for _ in range(3):
                probe.send(f'eq {pair["right"]} 0', 15); time.sleep(3.5)
                probe.send(f'eq {pair["left"]} 3', 15); time.sleep(3.5)
                winio.front(); winio.key('D1'); time.sleep(5)
                g = probe.send('gs', 10)
                if any('dual=true' in l for l in g): ok = True; break
            note('equip', (g[-1] if g else 'no gs') + ('' if ok else ' (dual not reached)'))
            if not ok: raise RuntimeError('pair did not reach dual wield')
        elif k == 'stats':
            r = probe.send(f'mark {tag}_{op.get("tag", "stats")}\nstats {tag}_{op.get("tag", "stats")}\npstat MaxSpeed', 15)
            for l in r:
                if 'stats ' in l or 'pstat' in l: note('stats', l[:300])
        elif k == 'dummy':
            r = probe.send(f'civ {op.get("civ_radius", 15)}', 10)
            c = [l for l in r if 'civ radius' in l]
            note('civ', c[-1] if c else 'no answer')
            if c and 'n=unknown' not in c[-1] and 'n=0' not in c[-1]:
                raise RuntimeError('civilians near the test spot, no shots fired')
            probe.send(f'dummy {op.get("dist", 6)} {op.get("dz", 0)}', 10); time.sleep(1.5)
            r = probe.send('freeze', 10); note('dummy', (r or ['no answer'])[-1])
        elif k == 'fire':
            probe.send(f'refill\nmark {tag}_fire', 10)
            winio.front()
            for _ in range(op['n']):
                winio.mouse(op.get('hand', 'RMB'), op.get('ms', 120)); time.sleep(op.get('gap', 0.35))
            time.sleep(1.5)
            r = probe.send(f'shots {tag}\nmags', 10)
            note('fire', f'asked {op["n"]} by {op.get("hand", "RMB")}; ' + '; '.join(l for l in r if 'shots' in l or 'mags' in l))
        elif k == 'reload':
            winio.front()
            if op.get('stance') == 'raised':
                winio.mouse(op.get('hand', 'RMB'), 120); time.sleep(0.6)
            probe.send(f'mark {tag}_reload_{op.get("stance", "default")}', 10)
            vid = None
            if args.get('record'):
                name = f'{tag}_reload_{op.get("stance", "default")}'
                vid = winio.record_start(f'{run.dir}/evidence/{name}.mp4', op.get('secs', 6) + 1)
            winio.key('R'); time.sleep(op.get('secs', 6))
            if vid: vid.wait(timeout=30)
            r = probe.send('mags', 10); note('reload ' + op.get('stance', 'default'), '; '.join(l for l in r if 'mags' in l))
        elif k == 'shot':
            p = f'{run.dir}/evidence/{tag}_{op["name"]}.png'
            note('shot', p if winio.screenshot(p) else 'no window')
        elif k == 'wait':
            time.sleep(op['s'])
        elif k == 'key':
            winio.front(); winio.key(op['name'], op.get('hold_ms', 60)); time.sleep(op.get('wait', 2))
            if op.get('report'):
                r = probe.send('gs\nmags', 10)
                note('key ' + op['name'], '; '.join(l for l in r if 'gs ' in l or 'mags' in l))
        elif k == 'cmd':
            for l in probe.send(op['text'], op.get('timeout', 20)): note('cmd', l[:300])
    return rows


def pairs_for(args, spec):
    try:
        import manifest
        gs = {g['id']: g for g in manifest.load()['guns']}
    except Exception:
        gs = {}
    out = []
    for i, gid in enumerate(args['guns']):
        g = gs.get(gid)
        if g is None and not args.get('item'):
            raise SystemExit(f'unknown gun {gid} (not in weapons.json); give --item')
        right = rec_name(g, args.get('item') if i == 0 else None)
        pg = gs.get(args.get('partner')) if args.get('partner') else g
        left = rec_name(pg, None) if args.get('partner') else right
        out.append({'tag': f'{gid}' + (f'_{args["partner"]}' if args.get('partner') else ''), 'right': right, 'left': left})
    return out


def sim_game(run):
    """Stand-in for a game session in a dry run: does what the real game and MO2 do to the files, and nothing else."""
    e = run.env
    for n in sorted(os.listdir(e.saves)):
        p = f'{e.saves}/{n}'
        if n.startswith('AutoSave-') and os.path.isdir(p):
            with open(f'{p}/sav.dat', 'ab') as f: f.write(b'sim-overwrite')
            break
    qs = [n for n in sorted(os.listdir(e.saves)) if n.startswith('QuickSave-')]
    if qs:
        with open(f'{e.saves}/{qs[0]}/metadata.9.json', 'ab') as f: f.write(b' ')
    ar = sorted(n for n in os.listdir(e.saves) if n.startswith('AutoSave-'))
    if ar:
        shutil.rmtree(f'{e.saves}/{ar[-1]}')                   # a slot the game replaced
    os.makedirs(f'{e.saves}/AutoSave-998')
    open(f'{e.saves}/AutoSave-998/sav.dat', 'wb').write(b'junk level 1 autosave')
    open(f'{e.saves}/AutoSave-998/metadata.9.json', 'w').write('{}')
    top = [n for n in os.listdir(e.saves) if os.path.isfile(f'{e.saves}/{n}')]
    if top:
        open(f'{e.saves}/{top[0]}', 'ab').write(b'sim')
    with open(f'{e.profile}/UserSettings.json', 'a') as f: f.write('\n')
    with open(f'{e.profile}/modlist.txt', 'ab') as f: f.write(b'+sim mod\r\n')
    if os.path.isfile(f'{e.profile}/settings.ini'):
        open(f'{e.profile}/settings.ini', 'a').write('\n[sim]\n')
    if os.path.isfile(e.user_ini): open(e.user_ini, 'a').write('\n; sim\n')
    if os.path.isfile(e.mo2_ini): open(e.mo2_ini, 'a').write('\n; sim\n')
    os.makedirs(e.out_dir, exist_ok=True)
    open(f'{e.out_dir}/out.txt', 'w').write('12:00:00 init\n')


def parse(argv):
    a = {'guns': []}
    it = iter(argv)
    for x in it:
        if x in ('--dry-run', '--record', '--baseline', '--visual', '--build'): a[x[2:].replace('-', '_')] = True
        elif x in ('--partner', '--item', '--spec', '--work', '--restore', '--overlay'): a[x[2:]] = next(it)
        elif x.startswith('-'): raise SystemExit(f'unknown option {x}\n' + __doc__)
        else: a['guns'].append(x)
    return a


def restore_from(folder):
    j = json.load(open(f'{folder}/journal.json'))
    env = Env.real()
    env.__dict__.update(j['env'])
    run = Run(env, folder, {}, j['dry'])
    run.saves.snap = j['saves']['snap']
    run.files.items = [tuple(i) for i in j['files']]
    run.deployed, run.mo2_was_running, run.have_lock = j['deployed'], j['mo2_was_running'], j['have_lock']
    return 0 if run.teardown() else 1


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return 0 if argv else 2
    a = parse(argv)
    if a.get('restore'): return restore_from(a['restore'])
    spec = json.load(open(a.get('spec') or f'{HERE}/specs/battery.json', encoding='utf8'))
    dry = a.get('dry_run', False)
    if not dry and not a['guns']:
        raise SystemExit(__doc__)
    work = a.get('work') or ('C:/Modding/gg-work/migration/ingame-runs' if dry else 'C:/Modding/_tools/ingame-runs')
    stamp = time.strftime('%Y%m%d-%H%M%S')
    folder = f'{work}/{stamp}-{"dry-" if dry else ""}{(a["guns"] or ["selftest"])[0]}'
    real = Env.real()
    if dry:
        real_saves, real_files = guard.tree(real.saves), {p: guard.sha(p) for p in (f'{real.profile}/UserSettings.json', f'{real.profile}/modlist.txt') if os.path.isfile(p)}
        os.makedirs(folder, exist_ok=True)
        env = Env.copy_of(real, f'{folder}/sandbox')
        sbx_saves, sbx_files = guard.tree(env.saves), {p: guard.sha(p) for p in (f'{env.profile}/UserSettings.json', f'{env.profile}/modlist.txt')}
    else:
        env = real
    if a.get('build') and not dry:
        # the gun's own partial archives (ga produce builds only what the gun plays), in a WORK under the run folder
        os.makedirs(folder, exist_ok=True)
        r = subprocess.run(['bash', f'{os.path.dirname(HERE)}/anim/ga.sh', 'produce', a['guns'][0], '--out', f'{folder}/produce'],
                           env={**os.environ, 'WORK': f'{folder}/work'})
        if r.returncode: raise SystemExit(f'ga produce failed ({r.returncode}); nothing launched')
        a['overlay'] = f'{folder}/work/guns-out/archive/pc/mod'
    run = Run(env, folder, spec, dry)
    atexit.register(lambda: run.restored or run.teardown())
    code = 0
    try:
        pre_checks(run)
        backups(run)
        apply_setup(run, {'visual': a.get('visual'), 'baseline': a.get('baseline'), 'overlay': a.get('overlay')})
        if dry:
            run.say('dry run: no launch; simulating what the game and MO2 do to the files')
            sim_game(run)
        else:
            probe = Probe(run)
            ps = pairs_for(a, spec)
            rows = []
            os.makedirs(f'{folder}/evidence', exist_ok=True)
            if a.get('baseline'):
                for p in ps:
                    try:
                        launch(run, probe); rows += battery(run, probe, p, a)
                    finally:
                        run.stop_game(); time.sleep(5)
            else:
                launch(run, probe)
                for p in ps: rows += battery(run, probe, p, a)
            json.dump(rows, open(f'{folder}/results.json', 'w'), indent=1)
    except BaseException as ex:
        code = 1
        run.say(f'run stopped: {type(ex).__name__}: {ex}')
    ok = run.teardown()
    if dry:
        a1 = guard.tree(real.saves) == real_saves
        a2 = guard.tree(env.saves) == sbx_saves
        a3 = {p: guard.sha(p) for p in sbx_files} == sbx_files
        a4 = sbx_saves == real_saves
        run.say(f'dry run checks: real saves unchanged {a1}; sandbox saves equal the snapshot {a2}; sandbox settings/modlist equal the snapshot {a3}; '
                f'sandbox copy equals the real saves {a4}; real settings unchanged '
                f'{ {p: guard.sha(p) for p in real_files} == real_files}')
        ok = ok and a1 and a2 and a3 and a4
    return 0 if ok and not code else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
