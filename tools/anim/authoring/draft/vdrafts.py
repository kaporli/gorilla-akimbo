"""`ga drafts <family> --from-vanilla`: one round of drafts translated from the game's own reloads (authoring/reload/vtop.py, vref.py).

usage: ga.sh drafts <family> --from-vanilla [--out <dir>] [--only SV03,SV04] [--jobs n] [--no-render] [--dry-run]
Family: warden's `top` (rounds.json `vanilla`). Output in <out>/<family>/vanilla:
  raised/    the drafts as the generator makes them (idle start and end), solved against the draft checks (vtop.py solve: amplitude and drive length of the first grid entry that passes)
  lowered/   the passing drafts rebuilt from the lowered idle (smgprod --lowered; the rise to the discard, the insert off screen, the return to the lowered idle)
  checks.json  per draft: gate fails, draft checks R1 to R10 (draftcheck.py), R9 on the whole gun and hand (lift.vis2), start and end against the lowered idle
  review/    game-camera MP4 per draft in the lowered stance, contact_sheet.png, grid_lowered.mp4
Order: one-handed sources first (the Lexington dual-wield reloads), then the two-handed ones; a draft that does not pass is listed with the failing rule and not reviewed.
Takes the render lock C:/Modding/gg-work/renderlock around Blender (waits 30 minutes).
"""
import os, sys, json, time, subprocess, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))); import manifest
mp = manifest.mp

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
AUTH = os.path.dirname(HERE); RELOAD = AUTH + '/reload'; CHECKS = AUTH + '/checks'
TOOLS = os.path.dirname(AUTH)
PY = [sys.executable, '-B']
LOCK = mp('C:/Modding/gg-work/renderlock')


def sh(argv, env, cwd, log):
    r = subprocess.run(argv, env=env, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    open(log, 'w', encoding='utf-8').write(r.stdout + r.stderr); return r.returncode, r.stdout + r.stderr


def env_for(root, extra=None):
    e = dict(os.environ, ROUND_OUT=root, WORK=root + '/work', AUTHORING=root + '/work', PYTHONDONTWRITEBYTECODE='1', RAISEDCLIPS=manifest.path('raised_clips'))      # the raised idle clips the rest pose is made from: the manifest, not an environment variable
    e.pop('GA_TEST', None); e.update(extra or {}); return e


def take_lock():
    t = time.time()
    while True:
        try: os.mkdir(LOCK); return
        except FileExistsError:
            if time.time() - t > 1800: raise SystemExit('render lock held for 30 minutes')
            time.sleep(20)


def drafts_vanilla(argv):
    argv0 = list(argv); dry = '--dry-run' in argv
    if dry: argv.remove('--dry-run')
    for flagname in ('--resolve', '--rebuild'):
        if flagname in argv: argv.remove(flagname)
    norender = '--no-render' in argv
    if norender: argv.remove('--no-render')
    def opt(n, d=None):
        if n in argv: i = argv.index(n); v = argv[i + 1]; del argv[i:i + 2]; return v
        return d
    out = opt('--out'); only = opt('--only'); jobs = int(opt('--jobs') or 3)
    if len(argv) != 1: raise SystemExit('usage: ga.sh drafts <family> --from-vanilla [--out <dir>] [--only id,id] [--jobs n] [--no-render] [--dry-run]')
    family = argv[0]; reg = json.load(open(HERE + '/rounds.json')).get('vanilla', {}).get(family)
    if not reg: raise SystemExit(f'ga: no vanilla-reference round for {family} (rounds.json vanilla: {", ".join(json.load(open(HERE + "/rounds.json")).get("vanilla", {}))})')
    sys.path.insert(0, RELOAD)
    base = (os.path.abspath(out) if out else mp('C:/Modding/gg-work/migration/pvanilla')).replace('\\', '/').rstrip('/'); root = f'{base}/{family}/vanilla'
    raised, low = root + '/raised', root + '/lowered'; ids = only.split(',') if only else reg['ids']
    print(f'drafts {family} --from-vanilla: gen {reg["gen"]}, gun {reg["gun"]}, take {reg["take"]}, {len(ids)} references {",".join(ids)}, into {root}' + (' (dry run)' if dry else ''))
    if dry:
        print('  steps: rest glb, vtop.py solve (parallel groups), lowered builds (smgprod build vtop --lowered), draft checks R1 to R10 + R9 + lowered start/end, review (Blender, render lock)'); return 0
    for d in (raised, low, root + '/logs'): os.makedirs(d, exist_ok=True)
    E = env_for(raised)
    rest = f'{raised}/rest/pma/rest_{reg["gun"]}_R__{reg["gun"]}_L.glb'
    if not os.path.exists(rest):
        c, o = sh(PY + [RELOAD + '/rest.py', reg['gun'], reg['gun'], '--body', 'pma', '--out', rest], E, RELOAD, root + '/logs/rest.log')
        if c: raise SystemExit('rest.py failed: ' + o[-400:])
    t0 = time.time()
    # 1. references and solve
    pins = {k: v for k, v in json.load(open(HERE + '/vpins.json')).items() if not k.startswith('_')}
    def pinned_raised(i):
        """A pinned id (vpins.json): the raised builds from its saved options, all bodies and hands; no solve."""
        json.dump(pins[i].get('raised_opts', pins[i]['opts']), open(f'{raised}/vsolve_{i}.json', 'w'))
        sh(PY + [RELOAD + '/' + reg['gen'], 'build', i], E, RELOAD, f'{root}/logs/pin_{i}_vref.log')      # makes the vanilla reference files (raised/vref)
        sh(PY + [RELOAD + '/smgprod.py', 'build', 'vtop', '--picks', i, '--clips', 'empty_reload', '--sides', 'right,left', '--bodies', 'pma,pwa'], E, RELOAD, f'{root}/logs/pin_{i}_raised.log')
        stem = f'{raised}/clips/pma/warden_right_{i}B_empty_reload'
        sh(PY + [CHECKS + '/draftcheck.py', '--family', reg['family'], '--take', reg['take'], stem + '.json'], E, CHECKS, f'{root}/logs/pin_{i}_check.log')
        n = len(json.load(open(stem + '_gate.json'))['fails']) + len(json.load(open(stem + '_draft.json'))['fails'])
        json.dump({'id': i, 'best_fails': n, 'pinned': True}, open(f'{raised}/vsolve_{i}.result.json', 'w'))
    for i in [x for x in ids if x in pins and ('--resolve' in argv0 or not os.path.exists(f'{raised}/vsolve_{x}.result.json'))]: pinned_raised(i)
    todo = [i for i in ids if not os.path.exists(f'{raised}/vsolve_{i}.result.json') or '--resolve' in argv0]      # a solved reference is not solved again (--resolve does)
    print(f'  solve: {len(ids) - len(todo)} references already solved in {raised}, {len(todo)} to solve')
    groups = [todo[k::jobs] for k in range(jobs) if todo[k::jobs]]
    procs = [subprocess.Popen(PY + [RELOAD + '/' + reg['gen'], 'solve', ','.join(g)], env=E, cwd=RELOAD, stdout=open(f'{root}/logs/solve_{k}.log', 'w'), stderr=subprocess.STDOUT) for k, g in enumerate(groups)]
    for p in procs: p.wait()
    print(f'  solve: {time.time() - t0:.0f} s')
    res = {}
    for i in ids:
        f = f'{raised}/vsolve_{i}.result.json'; res[i] = json.load(open(f)) if os.path.exists(f) else {'best_fails': None}
    ok = [i for i in ids if res[i].get('best_fails') == 0]
    print(f'  raised drafts passing the gate and the draft checks: {len(ok)} of {len(ids)}: {",".join(ok)}')
    # 2. lowered builds of the passing ones
    import vref
    rows = {}
    for i in ids: rows[i] = {'id': i, 'ref': f'{vref.REFS[i][0]} {vref.REFS[i][1]}', 'one_handed_source': vref.ref(i)['one_handed'], 'raised_pass': i in ok, 'solve': json.load(open(f'{raised}/vsolve_{i}.json')) if os.path.exists(f'{raised}/vsolve_{i}.json') else None}
    El = env_for(low)
    LIFTS = [(0.0, 0), (0.12, 4), (0.12, 7), (0.16, 7), (0.18, 8)]      # (stop lift in metres, frames the gun waits at the stop): the discard in view until the magazine is out of the frame (R9)
    def lowered_pinned(i):
        """A pinned id: one lowered build from the saved options and s (no search over lifts and scales), all bodies and hands."""
        import vtop; o = pins[i]['opts']; B = vtop.beats(vref.ref(i), o.get('afr', vtop.AFR), o.get('sa', 0), o.get('ms', 0.5))
        os.makedirs(f'{low}/rest/pma', exist_ok=True); shutil.copyfile(rest, f'{low}/rest/pma/' + os.path.basename(rest)); shutil.copytree(f'{raised}/vref', f'{low}/vref', dirs_exist_ok=True)
        json.dump(o, open(f'{low}/vsolve_{i}.json', 'w')); lj = f'{low}/low_{i}.json'; json.dump({'h': 0, 'a': B['rel'] - 7, 'b': B['hit'] - 1, 'e': 76, 's': pins[i]['s']}, open(lj, 'w'))
        sh(PY + [RELOAD + '/smgprod.py', 'build', 'vtop', '--picks', i, '--clips', 'empty_reload', '--sides', 'right,left', '--bodies', 'pma,pwa', '--lowered', lj], El, RELOAD, f'{root}/logs/low_{i}_pinned.log')
        rows[i]['lowered_s'] = pins[i]['s']; rows[i]['lift'] = [o.get('lift'), 0]; rows[i]['pinned'] = True
    def lowered_one(i):
        if i in pins: return lowered_pinned(i)
        import vtop; sv = rows[i]['solve'] or [1.0, 1.0, vtop.AFR]; B = vtop.beats(vref.ref(i), sv[2]); best = None
        os.makedirs(f'{low}/rest/pma', exist_ok=True); shutil.copyfile(rest, f'{low}/rest/pma/' + os.path.basename(rest))
        for ly, wait in LIFTS:
            for s in (0.75, 0.6):
                json.dump(list(sv[:3]) + [ly, wait], open(f'{low}/vsolve_{i}.json', 'w')); lj = f'{low}/low_{i}.json'; json.dump({'h': 0, 'a': B['rel'] - 7, 'b': B['hit'] - 1, 'e': 76, 's': s}, open(lj, 'w'))
                sh(PY + [RELOAD + '/smgprod.py', 'build', 'vtop', '--picks', i, '--clips', 'empty_reload', '--sides', 'right', '--bodies', 'pma', '--lowered', lj], El, RELOAD, f'{root}/logs/low_{i}_{ly}_{wait}_{s}.log')
                gf = f'{low}/clips/pma/warden_right_{i}B_empty_reload_gate.json'
                fails = json.load(open(gf))['fails'] if os.path.exists(gf) else ['no gate file']
                if fails: print(f'  lowered {i} lift {ly} wait {wait} s {s}: {fails}', flush=True); continue
                v = r9(i, f'{low}/clips', El); print(f'  lowered {i} lift {ly} wait {wait} s {s}: gate pass, R9 gun {v and v["gun_worst"]} hand {v and v["hand_worst"]} vs {v and v["target"]}', flush=True)
                score = (v['pass'], v['gun_worst'] + min(v['hand_worst'], 0)) if v else (False, -99)
                if best is None or score > best[0]:
                    best = (score, ly, wait, s); keep = f'{low}/best_{i}'; shutil.rmtree(keep, ignore_errors=True); os.makedirs(keep); [shutil.copy(f'{low}/clips/pma/{f}', keep) for f in os.listdir(f'{low}/clips/pma') if f.startswith(f'warden_right_{i}B_')]
                break
            if best and best[0][0]: break
        if best:      # the best candidate's files back into clips/
            for f in os.listdir(f'{low}/best_{i}'): shutil.copy(f'{low}/best_{i}/{f}', f'{low}/clips/pma/{f}')
            json.dump(list(sv[:3]) + [best[1], best[2]], open(f'{low}/vsolve_{i}.json', 'w')); rows[i]['lowered_s'] = best[3]; rows[i]['lift'] = [best[1], best[2]]
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(jobs) as ex: list(ex.map(lowered_one, ok))
    # 3. checks on the lowered builds
    for i in ok:
        if rows[i].get('lowered_s') is None: continue
        stem = f'{low}/clips/pma/warden_right_{i}B_empty_reload'
        sh(PY + [CHECKS + '/draftcheck.py', '--family', reg['family'], '--take', reg['take'], stem + '.json'], El, CHECKS, f'{root}/logs/check_{i}.log')
        rows[i]['gate_fails'] = json.load(open(stem + '_gate.json'))['fails']; rows[i]['draft_fails'] = json.load(open(stem + '_draft.json'))['fails']
        rows[i]['r9'] = r9(i, f'{low}/clips', El)
    json.dump(rows, open(root + '/checks.json', 'w'), indent=1)
    good = [i for i in ok if rows[i].get('lowered_s') is not None and not rows[i]['gate_fails'] and not rows[i]['draft_fails']]      # reviewed: gate and R1 to R10 pass; R9 is in the table
    good.sort(key=lambda i: (not rows[i]['one_handed_source'], i))
    print(f'  lowered drafts passing gate and R1 to R10 (R9 in the table): {len(good)}: {",".join(good)}')
    md = [f'# {family} vanilla-reference round', '', '| draft | source | one-handed source | raised | lowered s | gate | draft checks | R9 gun/hand worst vs target |', '|---|---|---|---|---|---|---|---|']
    for i in ids:
        r = rows[i]; v = r.get('r9') or {}
        md.append(f"| {i} | {r['ref']} | {'yes' if r['one_handed_source'] else 'no'} | {'pass' if r['raised_pass'] else 'FAIL'} | {r.get('lowered_s', '-')} | {'; '.join(r.get('gate_fails') or []) or ('-' if r['raised_pass'] else 'see raised log')} | {'; '.join(r.get('draft_fails') or []) or '-'} | {v.get('gun_worst', '-')}/{v.get('hand_worst', '-')} vs {v.get('target', '-')} |")
    open(root + '/DRAFTS.md', 'w').write('\n'.join(md) + '\n')
    if norender or not good: print('  review: skipped'); return 0
    take_lock()
    try:
        c, o = sh(PY + [RELOAD + '/vreview.py', low + '/clips', root + '/review', '--ids', ','.join(good)], El, RELOAD, root + '/logs/review.log'); print('  review:', 'done' if c == 0 else o[-500:])
    finally:
        try: os.rmdir(LOCK)
        except OSError: pass
    return 0


def r9(i, clips, env):
    """R9 on the whole gun and the reloading hand (lift.series2, V.margin, idle target) from the release to the frame the discarded magazine has left the frame (lift.mag_gone_frame, at most the frame before the hidden window): worst margin against the target, per draft."""
    code = ("import sys, json; sys.path.insert(0, %r); import renv, lift; lift.CONTROL = %r; V = lift.V; "
            "sr = lift.series2(%r, 'pma', 'right', '%sB', 'empty_reload'); eye, hh = V.camera('pma'); mt = lift.idle_margin('pma'); "
            "L = json.load(open(%r + '/pma/warden_right_%sB_empty_reload_gate.json'))['layout']; eye_, hh_ = V.camera('pma'); f1, f2 = sr['R'], min(lift.mag_gone_frame(sr, None, eye_, hh_), (L['hide_start'] or sr['n']) - 1); "
            "g = [float(V.margin(lift.gun_world(sr, f), eye, hh).min()) for f in range(f1, f2 + 1)]; h = [float(V.margin(sr['hand'][f], eye, hh).min()) for f in range(f1, f2 + 1)]; "
            "print('R9JSON' + json.dumps({'window': [f1, f2], 'target': mt, 'gun_worst': round(min(g), 3), 'hand_worst': round(min(h), 3), 'pass': min(g) >= mt and min(h) >= mt}))" % (RELOAD, mp('C:/Modding/anim-work/smg-shotgun/production/clips'), clips, i, clips, i))
    c, o = sh(PY + ['-c', code], env, RELOAD, clips + f'/../logs_r9_{i}.log')
    ln = next((l for l in o.splitlines() if l.startswith('R9JSON')), None)
    return json.loads(ln[6:]) if ln else None
