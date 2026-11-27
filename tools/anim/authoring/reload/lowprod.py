"""Lowered-stance variants of a gun's reload clips, as one pipeline step (`ga produce` runs it; owner's standard of 2026-11-24).

A variant keeps the shipped motion, starts and ends exactly in the gun's lowered idle (friendly_idlepose of the lowered set), shows the whole gun
only around the magazine discard (R9: every gun vertex and hand joint inside the game camera frame with the margin of the shipped idle's own worst
vertex, from the arrival at the wind-up to the frame the magazine has left the frame) and has the insert off screen. The game plays the variant
in the lowered stance and the shipped clip in the raised stance (manifest reload.lowered_variant: wrapper, xl entries, magazine sets).

Rules (no per-gun numbers; limits in weapons.json checks.lowered_variant; the generator's STOP_DRIVE table gives the kind and the arrival):
  kind     a pick whose generator has STOP_DRIVE[pick] with a drive length is a 'stop' pick (the arm drives the gun along the magazine's exit line and
           stops it on the release frame: the stop position and pitch move). drop None is a 'hold' pick (the gun is held in the fingers while it
           turns: the hold position moves). A pick with no STOP_DRIVE entry has no hook: the gun is not produced (exit 3, reason printed).
  control  the clips the motion is kept from: the shipped clips of the gun (reload.clips folder) when they hold the pick, else <root>/clips.
  window   stop pick: solve from the arrival (release - STOP_DRIVE arrive), objective `up` (highest stop that meets the target), lead
           checks.lowered_variant.lead; if no stop meets the target there, from the release (the discard itself), objective `move` (smallest rigid move
           of the gun), lead 0. Hold pick: from the arrival, smallest offset. The solver is lift.py (SLSQP, 5 faces over every gun vertex and hand
           joint, both bodies, both hands, both reload clips, plus the magazine well point and the arm reach).
  overlay  h 0, a = release - arrive, e = last frame, b = e - checks.lowered_variant.return_frames (lowover.overlay, smgprod --lowered).
  s        scale of the post-seat gesture about the lowered pose: the largest found by 1.0 first, then 5 halvings of [0, 1], with the
           build's reach <= checks.rreload.reach_max and shoulder pull <= shoulder_pull_max_cm (right hand, both bodies, both reload clips).
  layout   hidden window per pick and clip: latest hide_start and earliest hide_end over both bodies and hands (smgprod.layout rule).

Every other gun (no STOP_DRIVE hook in its generator, or a generator smgprod does not drive): `produce` hands over to discard.py, a layer over the clips the generator already wrote
(spec keys, track, gate), one rule for every family: discard event = the magazine leaving the well (release to free_from), R9 = share of gun vertices in the frame at least that of the shipped idle
plus well and hand inside, smallest offset, offset held through the part's flight, lowered start and end from the lowered gun pose. The Warden keeps its own hooks (approved clips): ST38 and ST40
unchanged; the ST32 hold offset is the smallest meeting R9 and the R8 bounds (R8 measured on built clips, discard.solve_hold_r8).

Raised stance (owner, 2026-11-24: the discard is visible in every stance): `produce` also makes raised variants (same solved offsets, no lowered overlay, raised idle start and end) in <root>/raised.

usage: lowprod.py plan <gun>
       lowprod.py raised <gun> --root <root>    raised variants only (reads <root>/lowered/solve)
       lowprod.py measure <gun>     R9 on the shipped clips of the gun (what a variant would have to fix; used for a gun without a hook)
       lowprod.py produce <gun> --root <ga produce root> [--control <folder with clips/>] [--jobs n] [--picks SF13,SF35]     (writes <root>/lowered/{clips,solve,layout.json,magsets,report.json})
       exit 0 made, 1 a step failed, 3 the gun has no hook (reason printed)
"""
import os, sys, json, subprocess, shutil, concurrent.futures, glob, time
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, HERE)
import renv, common, manifest, lift

PY = [sys.executable, '-B']
BODIES = ('pma', 'pwa'); SIDES = ('right', 'left'); CLIPS = ('reload', 'empty_reload')


def rules():
    return manifest.load()['checks']['lowered_variant']


def gun_entry(gid):
    g = common.gun(gid)
    return g, (g.get('reload') or {})


def status(gid):
    """(ok, kinds or reason, picks, take): whether every slot pick of the gun has a lowered hook in its generator."""
    g, r = gun_entry(gid)
    if not g.get('lowered') or not r.get('slots'): return False, f'{gid} has no lowered entry or no reload slots', [], None
    if r.get('shares'): return False, f'{gid} shares the clips of {r["shares"]}: produce {r["shares"]}', [], None
    if r.get('parked') and os.environ.get('GA_INCLUDE_PARKED') != '1': return False, f'{gid} reload is parked (plays the generic clips; no own clips)', [], None      # GA_INCLUDE_PARKED=1 (ga produce --include-parked): variants of the parked gun's own clips, measured but not wired
    take = 'A' if r['weight'] == 'light' else 'B'; picks = list(r['slots']); kinds = {}
    for p in picks: kinds[p] = lift.hook(gid, p + take) or 'layer'      # 'stop' and 'hold': the generator's own hook (Warden, approved clips); 'layer': discard.py over the clips the generator wrote (every other pick)
    return True, kinds, picks, take


def ship_root(gid, override=None):
    """Folder holding the gun's shipped clips/: the manifest default of reload.clips (`rreload_clips` when the entry has none, as ga produce and rreload read it), not the environment:
    a ga produce run points the env at its own clips."""
    if override: return override.replace(chr(92), '/').rstrip('/')
    g, r = gun_entry(gid)
    return os.path.dirname(manifest.mp(manifest.load()['paths'][r.get('clips', 'rreload_clips')]['default']).rstrip('/'))


def control_root(gid, root, override=None):
    """Folder holding clips/: the shipped clips when they hold the gun's first pick, else <root>."""
    if override: return override.replace(chr(92), '/').rstrip('/')
    g, r = gun_entry(gid); take = 'A' if r.get('weight') == 'light' else 'B'; picks = list(r.get('slots') or []); ship = ship_root(gid)
    import rreload
    if picks and os.path.exists(rreload.clip_file(f'{ship}/clips', 'pma', gid, 'right', picks[0], take, 'empty_reload')): return ship
    return root


def run(argv, env, log):
    r = subprocess.run(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    open(log, 'w', encoding='utf-8').write(r.stdout)
    return r.returncode


def build_env(out):
    e = dict(os.environ, ROUND_OUT=out, WORK=out + '/work', AUTHORING=out + '/work', PYTHONDONTWRITEBYTECODE='1')
    e.pop('GA_TEST', None)
    return e


def build(gid, pick, out, root, lift_json, low_json, sides=None, log=None, ctl=None):
    """smgprod build of one pick with the lift and lowered json into <out>/clips. The rest glbs are the control's (the shipped ones, which the shipped clips were made on), else <root>/rest."""
    import smgprod
    os.makedirs(out + '/work', exist_ok=True)
    for b in BODIES:
        os.makedirs(f'{out}/rest/{b}', exist_ok=True); n = f'rest_{gid}_R__{gid}_L.glb'
        src = f'{ctl}/rest/{b}/{n}' if ctl and os.path.exists(f'{ctl}/rest/{b}/{n}') else f'{root}/rest/{b}/{n}'
        if not os.path.exists(f'{out}/rest/{b}/{n}'): shutil.copyfile(src, f'{out}/rest/{b}/{n}')
    argv = PY + [HERE + '/smgprod.py', 'build', smgprod.family_of(pick), '--picks', pick, '--lift', lift_json] + (['--lowered', low_json] if low_json else []) + (['--sides', sides] if sides else [])
    return run(argv, build_env(out), log or out + '/work/build.log')


def solve(gid, pick, take, kind, ctl, root, sd):
    """(lift json path or None, note on the window)."""
    P = pick + take; wk = root + '/lowered/work'; os.makedirs(wk, exist_ok=True); env = build_env(wk); L = HERE + '/lift.py'; out = f'{sd}/{pick}.json'
    if kind == 'hold':      # the smallest hold offset meeting the R9 idle-margin target (lift.py: whole gun and hand, the approved ST32B rule) and the R8 bounds of checks.draft.r8_min on the gun series
        code = run(PY + [L, 'hold', ctl, '--gun', gid, '--pick', P, '--r8', '--out', out], env, f'{sd}/{pick}.log')
        return (None if code else out), 'hold: smallest offset meeting R9 (idle margin) and R8'
    code = run(PY + [L, 'stop', ctl, '--gun', gid, '--pick', P, '--objective', 'up', '--lead', str(rules()['lead']), '--out', out], env, f'{sd}/{pick}_arrival.log')
    note = 'stop from the arrival, objective up'
    if code:
        code = run(PY + [L, 'stop', ctl, '--gun', gid, '--pick', P, '--objective', 'move', '--lead', '0', '--from', '0', '--out', out], env, f'{sd}/{pick}_release.log')
        note = 'no stop from the arrival meets the target: stop from the release, objective move'
    return (None if code else out), note


def overlay_window(ctl, gid, pick, take):
    """h, a, b, e from the control's track (release) and gate layout (length) and the generator's arrival."""
    t = json.load(open(f'{ctl}/clips/pma/{gid}_right_{pick}{take}_empty_reload_track.json'))
    g = json.load(open(f'{ctl}/clips/pma/{gid}_right_{pick}{take}_empty_reload_gate.json'))
    lift.use(pick + take, gid); e = g['layout']['length'] - 1
    return {'h': 0, 'a': int(t['release']) - lift.ARRIVE, 'b': e - rules()['return_frames'], 'e': e}


def gate_numbers(folder):
    wr = ws = 0.0; n = 0
    for g in glob.glob(f'{folder}/clips/*/*_gate.json'):
        o = json.load(open(g)); wr = max(wr, o['reach'][0]); ws = max(ws, o['shoulder_pull_cm']); n += 1
    return n, wr, ws


def bisect_s(gid, pick, root, lift_json, win, bs, ctl=None):
    """Largest s by the plift3 bisection: 1.0 first, then halvings of [0, 1]. Returns (s, [(s, files, reach, shoulder, ok)])."""
    lim = manifest.load()['checks']['rreload']; trials = []

    def trial(s):
        out = f'{bs}/s{int(round(s * 1000)):04d}'; low = out + '.json'; os.makedirs(out, exist_ok=True); json.dump(dict(win, s=s), open(low, 'w'))
        build(gid, pick, out, root, lift_json, low, 'right', ctl=ctl); n, wr, ws = gate_numbers(out)
        ok = n == 4 and wr <= lim['reach_max'] and ws <= lim['shoulder_pull_max_cm']; trials.append((s, n, wr, ws, ok))
        return ok
    if trial(1.0): return 1.0, trials
    lo, hi = 0.0, 1.0
    for _ in range(rules()['s_halvings']):
        m = (lo + hi) / 2
        if trial(m): lo = m
        else: hi = m
    return lo, trials


def layout_of(gid, picks, take, clips):
    """{pick+take: {clip: layout}} (latest hide_start, earliest hide_end over bodies and hands) and the gate fails."""
    lay = {}; fails = []
    for pick in picks:
        for clip in CLIPS:
            e = None
            for body in BODIES:
                for side in SIDES:
                    o = json.load(open(f'{clips}/{body}/{gid}_{side}_{pick}{take}_{clip}_gate.json')); L = dict(o['layout'])
                    if o['fails']: fails.append(f'{body} {side} {pick}{take} {clip}: {o["fails"]}')
                    if e is None: e = dict(L)
                    else: e['hide_start'] = max(e['hide_start'], L['hide_start']); e['hide_end'] = min(e['hide_end'], L['hide_end'])
            lay.setdefault(pick + take, {})[clip] = e
    return lay, fails


def magsets(gid, picks, take, clips, d):
    """Magazine sets of the variant clips (python only, no WolvenKit): six slots per body and hand, every mesh matrix rebuilt from the written keys."""
    import smgprod, gungeo, rmagset2, rreload
    os.makedirs(d, exist_ok=True); rep = {}; gun = common.gun(gid)
    van, wpn, mesh = gungeo.wanim(gun, 'mag_std'), gungeo.wanim(gun, 'base1'), common.find('weapon_meshes', gun['mesh'] + '__mag_std_01.glb')
    for body in BODIES:
        for side in SIDES:
            items = []
            for clip in CLIPS:
                for k, p in enumerate(picks):
                    base = rreload.clip_file(clips, body, gid, side, p, take, clip)[:-4]; spec = json.load(open(base + '.json'))
                    items.append((base + '_track.json', clip if k == 0 else f'{clip}_0{k}', spec['_keys'], spec['_gun_map']))
            out = f'{d}/{rreload.low_mag_set(body, side, gid)}.glb'; r, _ = rmagset2.build(van, wpn, mesh, out, items)
            chk = rmagset2.check(out, wpn, mesh, items); rep[os.path.basename(out)] = {'slots': r, 'check': chk}
            print(out, 'worst rebuilt mesh error', max(c['worst_cm'] for c in chk), 'cm', flush=True)
    json.dump(rep, open(f'{d}/magsets.json', 'w'), indent=1)
    return rep


def pick_job(gid, pick, take, kind, ctl, root):
    L = root + '/lowered'; sd = L + '/solve'; os.makedirs(sd, exist_ok=True); t0 = time.time(); rep = {'pick': pick, 'kind': kind}
    lj, note = solve(gid, pick, take, kind, ctl, root, sd); rep['window_note'] = note
    if not lj: rep['error'] = 'no offset meets the visibility target'; return rep
    rep['lift'] = json.load(open(lj))[pick]; win = overlay_window(ctl, gid, pick, take); rep['overlay'] = win
    s, trials = bisect_s(gid, pick, root, lj, win, f'{L}/bs_{pick}', ctl); rep['s'] = s; rep['trials'] = trials
    low = f'{sd}/{pick}_low.json'; json.dump(dict(win, s=s), open(low, 'w'))
    rep['final_exit'] = build(gid, pick, f'{L}/p_{pick}', root, lj, low, ctl=ctl); rep['seconds'] = round(time.time() - t0)
    return rep


def raised(gid, root, ctl_arg, jobs, only=None):
    """Raised-stance variants: the same solved offsets (<root>/lowered/solve/<pick>.json: they were solved on the shipped clips, which start and end in the raised idle, against that idle's
    own margin) with no lowered overlay. Start and end are the raised idle (the generator's own); the discard is in view. Writes <root>/raised/{clips,layout.json,magsets}."""
    ok, kinds, picks, take = status(gid)
    if only: picks = [p for p in picks if p in only]
    if not ok: print(f'raised variants of {gid}: not made. {kinds}'); return 3
    root = os.path.abspath(root).replace(chr(92), '/').rstrip('/'); ctl = control_root(gid, root, ctl_arg); R = root + '/raised'; os.makedirs(R, exist_ok=True)
    def job(p):
        lj = f'{root}/lowered/solve/{p}.json'
        if not os.path.exists(lj): lj, _ = solve(gid, p, take, kinds[p], ctl, root, os.makedirs(root + '/lowered/solve', exist_ok=True) or root + '/lowered/solve')
        return p, build(gid, p, f'{R}/p_{p}', root, lj, None, ctl=ctl)
    with concurrent.futures.ThreadPoolExecutor(max(1, jobs)) as ex: res = list(ex.map(job, picks))
    print('raised builds', res, flush=True)
    if any(c for _, c in res): return 1
    clips = R + '/clips'
    for p in picks:
        for body in BODIES:
            os.makedirs(f'{clips}/{body}', exist_ok=True)
            for f in glob.glob(f'{R}/p_{p}/clips/{body}/*'):
                data = open(f, 'rb').read()
                if f.endswith('.json'): data = data.replace(f'{R}/p_{p}'.encode(), R.encode())
                open(f'{clips}/{body}/{os.path.basename(f)}', 'wb').write(data)
    lay, fails = layout_of(gid, picks, take, clips); json.dump({'layout': lay, 'fails': fails}, open(R + '/layout.json', 'w'), indent=1)
    magsets(gid, picks, take, clips, R + '/magsets')
    print(f'raised variants: {len(glob.glob(clips + "/*/*.glb"))} clips in {clips}; {len(fails)} gate fails')
    for f in fails: print('  gate fail', f)
    return 1 if fails else 0


def produce(gid, root, ctl_arg, jobs, only=None, final=True):
    ok, kinds, picks, take = status(gid)
    if only: picks = [p for p in picks if p in only]
    if ok and 'layer' in kinds.values():
        import discard
        return discard.produce(gid, root, ctl_arg, jobs, only=only, final=final)
    if not ok:
        print(f'lowered variants of {gid}: not made. {kinds}')
        return 3
    root = os.path.abspath(root).replace('\\', '/').rstrip('/'); ctl = control_root(gid, root, ctl_arg); L = root + '/lowered'; os.makedirs(L, exist_ok=True)
    print(f'lowered variants of {gid}: picks {",".join(picks)} kinds {kinds}, motion kept from {ctl}/clips', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max(1, jobs)) as ex: reps = list(ex.map(lambda p: pick_job(gid, p, take, kinds[p], ctl, root), picks))
    for r in reps: print(json.dumps({k: v for k, v in r.items() if k != 'trials'}), flush=True)
    json.dump(reps, open(L + '/report.json', 'w'), indent=1)
    if any(r.get('error') or r.get('final_exit') for r in reps): print('lowered variants: a pick failed'); return 1
    clips = L + '/clips'
    for r in reps:
        for body in BODIES:
            os.makedirs(f'{clips}/{body}', exist_ok=True)
            for f in glob.glob(f'{L}/p_{r["pick"]}/clips/{body}/*'):
                data = open(f, 'rb').read()
                if f.endswith('.json'): data = data.replace(f'{L}/p_{r["pick"]}'.encode(), L.encode())
                open(f'{clips}/{body}/{os.path.basename(f)}', 'wb').write(data)
    lay, fails = layout_of(gid, picks, take, clips); json.dump({'layout': lay, 'fails': fails}, open(L + '/layout.json', 'w'), indent=1)
    magsets(gid, picks, take, clips, L + '/magsets')
    print(f'lowered variants: {len(glob.glob(clips + "/*/*.glb"))} clips in {clips}; {len(fails)} gate fails')
    for f in fails: print('  gate fail', f)
    rc = raised(gid, root, ctl_arg, jobs, only=only)
    return 1 if fails or rc else 0


def measure(gid):
    """R9 (discard.py rule) on the shipped clips of the gun: per pick, body, hand and clip file the share of gun vertices inside the frame in the discard event against the shipped idle share, the well and the hand margin.
    Returns {'rows': [...], 'error': ...}."""
    import discard
    g, r = gun_entry(gid); take = 'A' if r['weight'] == 'light' else 'B'; ship = ship_root(gid); rows = []; err = None
    for pk in r['slots']:
        try: rows += discard.vis(f'{ship}/clips', gid, pk + take, ship)
        except Exception as e: err = f'{type(e).__name__}: {e}'[:160]; break
    return {'rows': rows, 'error': err}


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ('plan', 'produce', 'measure', 'raised', 'finalize'): raise SystemExit(__doc__)
    if a[0] == 'raised': sys.exit(raised(a[1], common.opt(a, '--root'), common.opt(a, '--control'), int(common.opt(a, '--jobs') or 3)))
    if a[0] == 'measure':
        m = measure(a[1]); print(json.dumps(m)); sys.exit(0 if not m['error'] else 1)
    if a[0] == 'plan':
        ok, k, p, t = status(a[1]); print(a[1], 'ok' if ok else 'blocked', k)
        sys.exit(0 if ok else 3)
    root = common.opt(a, '--root'); ctl = common.opt(a, '--control'); jobs = int(common.opt(a, '--jobs') or 3); pk = common.opt(a, '--picks')
    if a[0] == 'finalize':
        import discard; sys.exit(discard.finalize(a[1], root, ctl))
    sys.exit(produce(a[1], root, ctl, jobs, only=pk.split(',') if pk else None, final='--no-final' not in a))
