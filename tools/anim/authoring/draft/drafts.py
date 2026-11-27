"""`ga drafts` and `ga pick`: one draft round of a family, and the owner's picks from it.

usage: ga.sh drafts <family> --round N [--out <dir>] [--take A|B] [--only id,id] [--jobs n] [--no-render] [--no-generate] [--dry-run]
                    [--compare <clips folder> [--compare-root <root the originals were made in>]] [--scores <scores.json>] [--rest-archive <dir>]
       ga.sh drafts <family> --from-vanilla [--out <dir>] [--only id,id] [--jobs n] [--no-render] [--dry-run]   (drafts translated from the game's own reloads: vdrafts.py)
       ga.sh pick <family> <id>[,id] --round N [--out <dir>] [--replace] [--allow-fail] [--dry-run]

drafts   Writes the round into <out>/<family>/round<N> (out defaults to paths.anim_work), with the generator the round was made
         with (rounds.json: generator, catalog, review tool; nothing is copied, the generator runs unchanged with ROUND_OUT set).
         Order: R4 budget exists for every take (else stop, naming the key) -> history list (history.json: a draft whose name
         matches an old rejected or picked idea prints the old draft id and its archive path; never a refusal) -> batch size warning (about 10 drafts) -> rest glbs -> generator
         (one process per chunk of ids, --jobs chunks at a time; none with --no-generate, which reuses the folder's drafts) ->
         post commands (layout) -> compare with --compare ->
         `draft` checks (draftcheck.py, every gate rule of rules.json: R1 to R14; exit 1 when a draft fails one) on every draft, <clip>_draft.json beside it -> review output (frame sheets,
         contact sheet, grid MP4, review page) unless --no-render. The page reads <out>/<family>/round<N>/scores.json (the
         reviewer's scores; --scores copies a file there); a new round without one gets an unscored file (every score 0, flagged `unscored`).
         R1 is reported, not gated: the release linear and angular impulse (cm/f, deg/f), the carrier-energy bound, the exit
         ratio and the mechanism (_draft.json R1.report). R3 (free flight at g) and R4a (fresh part with no contact) are gated. A round with `rest_archive` in rounds.json copies the archived rest glbs (the poses it was
         authored on) instead of making them; --rest-archive <dir> names another folder of <body>/rest_<gun>_R__<gun>_L.glb. Writes DRAFTS.md (with the history pairs: new draft next to the old draft of the same idea) and drafts.json (key `history`) in the round folder.
pick     Records the owner's picks: weapons.json reload.picks and reload.slots of every gun of the family (guns that share another
         gun's clips are skipped), at most 3 (the owner's rule: a reload set holds 3 variants); the ids are added to the picks already
         there, --replace sets exactly these. Slots = picks, repeated from the start up to 3. Every take of a picked draft must pass the
         draft checks (--allow-fail overrides). Writes <round folder>/PICKS.md. --dry-run prints the weapons.json change and the file.
"""
import concurrent.futures, datetime, difflib, glob, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
AUTH = os.path.dirname(HERE)
TOOLS = os.path.dirname(AUTH)
RELOAD = AUTH + '/reload'
for _p in (TOOLS, AUTH + '/checks'):
    if _p not in sys.path: sys.path.insert(0, _p)
import manifest

PY = [sys.executable, '-B']
CLIP_RE = re.compile(r'^(?P<gun>[a-z0-9]+)_(?P<side>right|left)_(?P<id>[A-Z]{1,2}\d+)(?P<take>[AB])_(?:empty_)?reload$')
SIDECARS = ('_gate.json', '_track.json', '_objects.json', '_phys.json', '_prims.json', '_inertia.json', '_ik.json', '_checks.json', '_draft.json')


def fail(msg, code=2):
    print('ga: ' + msg, file=sys.stderr)
    raise SystemExit(code)


def opt(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 >= len(argv): fail(f'{name} needs a value')
        v = argv[i + 1]; del argv[i:i + 2]
        return v
    return default


def flag(argv, name):
    if name in argv: argv.remove(name); return True
    return False


def registry():
    return json.load(open(os.environ.get('GA_DRAFT_ROUNDS') or HERE + '/rounds.json', encoding='utf-8'))


def history():
    return json.load(open(HERE + '/history.json', encoding='utf-8'))['entries']


def norm(s): return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
def technique_id(name): return norm(name).replace(' ', '_')


def history_hits(family, name):
    """Rows of history.json whose match phrase is in the draft name (whole words): kind recycled for any family, the others for this family only."""
    n = ' ' + norm(name) + ' '; out = []
    for e in history():
        if e['kind'] != 'recycled' and e['family'] != family: continue
        if any(' ' + norm(m) + ' ' in n for m in e['match']): out.append(e)
    return out


def history_pairs(family, ids, names):
    """[{new id, new name, old row}] for the drafts that repeat an old idea; one per old draft (rows without a draft once per idea)."""
    out = []; seen = set()
    for i in ids:
        for e in history_hits(family, names[i]):
            key = (i, e['family'], e['round'], e['draft'], e['idea'])
            if key in seen: continue
            seen.add(key); out.append({'new': i, 'new_name': names[i], 'old_family': e['family'], 'old_round': e['round'], 'old_draft': e['draft'], 'old_name': e.get('draft_name'),
                                       'idea': e['idea'], 'kind': e['kind'], 'archive': e['archive'], 'reason': e['reason']})
    return out


def round_entry(family, rnd):
    R = registry()
    ent = (R['families'].get(family) or {}).get(str(rnd))
    if ent: return ent
    why = next((v for k, v in R['unwired'].items() if k == family or (k.startswith(family + ':') and str(rnd) in k.split(':')[1].split(','))), None)
    have = sorted((R['families'].get(family) or {}))
    fail(f'no draft round {rnd} registered for {family}' + (f': {why}' if why else (f' (registered rounds: {", ".join(have)})' if have else '')) + '. Add it to authoring/draft/rounds.json.')


def env_for(root, extra=None):
    e = dict(os.environ, ROUND_OUT=root, WORK=root + '/work', AUTHORING=root + '/work', PYTHONDONTWRITEBYTECODE='1')
    e.pop('GA_TEST', None)       # renv sets it for the tools themselves
    if extra: e.update(extra)
    return e


def sh(argv, root, log, cwd=RELOAD, extra=None):
    """Run argv, output to the log file: (exit code, seconds, text)."""
    t = time.time()
    r = subprocess.run(argv, cwd=cwd, env=env_for(root, extra), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    os.makedirs(os.path.dirname(log), exist_ok=True); open(log, 'w', encoding='utf-8').write(r.stdout)
    return r.returncode, time.time() - t, r.stdout


def catalog(ent, root, logdir):
    """{draft id: name} of the round, read from the generator's module."""
    mod, attr = ent['catalog']
    code = (f"import sys, json; sys.path.insert(0, {RELOAD!r}); import renv, {mod} as M; d = getattr(M, {attr!r}); "
            "print('GA_CATALOG' + json.dumps({k: (v[0] if isinstance(v, (tuple, list)) else v) for k, v in d.items()}))")
    code_, sec, out = sh(PY + ['-c', code], root, logdir + '/catalog.log')
    line = next((l for l in out.splitlines() if l.startswith('GA_CATALOG')), None)
    if code_ or not line: fail(f'could not read the draft list of {mod}.{attr} (log {logdir}/catalog.log):\n' + out[-800:], 1)
    return json.loads(line[len('GA_CATALOG'):])


def budget_check(family, takes, archived=False):
    """Every take needs its R4 budget before drafts are made (rule b). An archived round (rounds.json `archive`) is only reproduced:
    a take without a budget is listed, and the check reports its R4 as not measurable. -> the takes without a budget."""
    B = manifest.load()['checks']['draft']['r4_budget'].get(family) or {}
    missing = [t for t in takes if t not in B]
    if archived: return missing
    for t in takes:
        if t not in B:
            fail(f'no R4 budget for {family} take {t}: add checks.draft.r4_budget.{family}.{t} = {{"length": N, "keys": N}} to tools/anim/weapons.json '
                 f'(one timing budget per family and take, owner rule 2026-11-13) before drafts of that take are made or checked')
    return missing


def rest_archive_file(ent, override, body, g, g2):
    """The rest glb (start and end pose) the archived round was authored against, when the round names an archive folder of them
    (rounds.json `rest_archive`, under paths.anim_work; `--rest-archive <dir>` overrides). The rifle rounds 1 and 2 were authored on the
    first raised idle poses; today's rest.py makes other ones, so a reproduction needs the archived file. None: rest.py makes it."""
    d = override or (manifest.path('anim_work') + '/' + ent['rest_archive'] if ent.get('rest_archive') else None)
    if not d: return None
    f = f'{d}/{body}/rest_{g}_R__{g2}_L.glb'
    if os.path.exists(f): return f
    print(f'  rest {g} {body}: archived pose {f} not found, rest.py makes it (the drafts will not reproduce the archive)'); return None


def seed_ref(dst):
    src = manifest.path('smg_ref'); os.makedirs(dst, exist_ok=True); n = 0
    for f in sorted(os.listdir(src)):
        if os.path.isfile(f'{src}/{f}') and not os.path.exists(f'{dst}/{f}'): shutil.copyfile(f'{src}/{f}', f'{dst}/{f}'); n += 1
    print(f'  ref: copied {n} files from {src} to {dst}')


def chunks(xs, n):
    n = max(1, min(n, len(xs))); return [xs[k::n] for k in range(n) if xs[k::n]]


def build_cmds(ent, family, ids, takes_arg, jobs):
    """`ids_per_take`: the generator names a draft by id and take (round2.py: F02A F02B), so every id is passed once per take."""
    b = ent['build']; out = []
    for ch in chunks(ids, jobs):
        a = PY + [RELOAD + '/' + ent['gen']] + list(b['argv'])
        if b.get('ids_per_take'): ch = [i + t for i in ch for t in (takes_arg or ','.join(ent['takes'])).split(',')]
        a += [b['ids_flag'], ','.join(ch)] if b.get('ids_flag') else [','.join(ch)]
        if b.get('takes_flag') and takes_arg: a += [b['takes_flag'], takes_arg]
        a += list(b.get('extra') or [])
        out.append(a)
    return out


ID_RE = re.compile(r'^(?P<id>[A-Z]{1,2}\d+)(?P<take>[AB])?$')


def clips_dir(ent, root):
    """Folder holding the round's clips: <root>/clips, or <root>/<ent clips_dir> (front3.py writes <root>/round3-front/clips)."""
    return root + '/' + ((ent or {}).get('clips_dir') or 'clips')


def find_drafts(root, ids, takes, ent=None):
    """[(spec json path, stem, id, take, body)] of the drafts of a round. Layout `clips` (default): <clips dir>/<body>/<gun>_<side>_<id><take>_<clip>.glb.
    Layout `spec` (rounds.json `dir`, e.g. "{id}" or "front/{id}": the folder of each draft under <root>): the generator names no take or
    clip in the file name, so id, take and body are read from the spec (_id, _pick or _draft; _take, else the take in _draft, else the round's only take; _body)."""
    import draftcheck
    ent = ent or {}; rows = []
    if ent.get('layout') == 'spec':
        paths = [q for i in sorted(ids) for q in draftcheck.clips_in([f"{root}/{ent['dir'].format(id=i)}"])]
        for p in paths:
            stem = os.path.basename(p)[:-5]; spec = json.load(open(p)); m = ID_RE.match(spec.get('_id') or spec.get('_pick') or spec.get('_draft') or '')
            if not m: continue
            take = spec.get('_take') or m['take'] or (ent['takes'][0] if len(ent['takes']) == 1 else None)
            if take is None: fail(f'{p}: no take in the spec and the round has several ({",".join(ent["takes"])})')
            if m['id'] not in ids or take not in takes: continue
            rows.append((p.replace('\\', '/'), stem, m['id'], take, spec.get('_body', 'pma')))
        return sorted(rows, key=lambda r: (r[3], r[2], r[4], r[1]))
    for p in draftcheck.clips_in([clips_dir(ent, root)]):
        stem = os.path.basename(p)[:-5]; m = CLIP_RE.match(stem)
        if not m or m['id'] not in ids or m['take'] not in takes: continue
        rows.append((p.replace('\\', '/'), stem, m['id'], m['take'], os.path.basename(os.path.dirname(p))))
    return sorted(rows, key=lambda r: (r[3], r[2], r[4], r[1]))


def compare_base(ent, root):
    """(folder of the new clips, folder the originals' paths are relative to): the compare walks <folder>/<subfolder>/*.glb on both sides."""
    if (ent or {}).get('layout') == 'spec':
        pre = ent['dir'].split('{id}')[0].rstrip('/'); base = root + ('/' + pre if pre else ''); return base, base
    cd = (ent or {}).get('clips_dir') or 'clips'; sub = os.path.dirname(cd)
    return root + '/' + cd, root + ('/' + sub if sub else '')


# ------------------------------------------------------------------------------------------------ compare with an earlier round
def compare_round(new_clips, old_clips, root_a, root_b, stems):
    """Regen-style: every file of the originals against the new one. glb byte for byte (else cmpclips numeric), json siblings
    identical / path only (the output root swapped for root_b) / key order / number format / key set / value. A new draft
    folder holds _draft.json files too: not compared (the originals have none)."""
    import regen, cmpclips
    rows = []; kinds = {}
    for body in sorted(d for d in os.listdir(old_clips) if os.path.isdir(f'{old_clips}/{d}')):
        for og in sorted(glob.glob(f'{old_clips}/{body}/*.glb')):
            stem = os.path.basename(og)[:-4]
            if stems is not None and stem not in stems: continue
            ng = f'{new_clips}/{body}/{stem}.glb'
            if not os.path.exists(ng): rows.append((stem, 'not generated', None, {})); continue
            r = cmpclips.compare(ng, og)[0]; sib = {}
            for suf, sp in regen.siblings(og).items():
                np_ = ng[:-4] + suf
                sib[suf] = regen.classify(np_, sp, root_a, root_b) if os.path.exists(np_) else 'missing'
                kinds.setdefault(suf, {}).setdefault(sib[suf], 0); kinds[suf][sib[suf]] += 1
            for f in sorted(glob.glob(glob.escape(ng[:-4]) + '_*.json')):
                suf = f[len(ng) - 4:]
                if suf not in sib and suf != '_draft.json': sib[suf] = 'extra'; kinds.setdefault(suf, {}).setdefault('extra', 0); kinds[suf]['extra'] += 1
            rows.append((stem, r[1], (r[2], r[3]), sib))
    return rows, kinds


def compare_text(rows, kinds):
    n = len(rows); ident = sum(r[1] == 'identical' for r in rows); dev = [r for r in rows if r[1] == 'differs']
    L = [f'clips compared: {n}; glb byte-identical {ident}/{n}' + (f'; {len(dev)} differ (max {max(r[2][0] for r in dev):.4f} cm, {max(r[2][1] for r in dev):.4f} deg)' if dev else '')
         + f'; not generated {sum(r[1] == "not generated" for r in rows)}']
    for suf in sorted(kinds, key=lambda s: (s != '.json', s)):
        L.append(f'  {"spec .json" if suf == ".json" else suf:14s} ' + ', '.join(f'{k} {v}' for k, v in sorted(kinds[suf].items())))
    return L


# ------------------------------------------------------------------------------------------------ checks
def run_checks(family, drafts, root, logdir, jobs):
    """draftcheck.py per take (its --take sets the R4 budget), files split over jobs processes. -> {stem: result json}"""
    by = {}
    for p, stem, i, take, body in drafts: by.setdefault(take, []).append(p)
    cmds = []
    for take, ps in by.items():
        for ch in chunks(ps, jobs): cmds.append((take, PY + [AUTH + '/checks/draftcheck.py', '--family', family, '--take', take] + ch))
    def one(k):
        take, a = cmds[k]; code, sec, out = sh(a, root, f'{logdir}/check_{k}.log', cwd=AUTH + '/checks'); return code, sec, out
    with concurrent.futures.ThreadPoolExecutor(jobs) as ex: res = list(ex.map(one, range(len(cmds))))
    bad = [(k, r) for k, r in enumerate(res) if r[0] not in (0, 1)]
    if bad: fail(f'draftcheck failed (exit {bad[0][1][0]}, log {logdir}/check_{bad[0][0]}.log):\n' + bad[0][1][2][-800:], 1)
    out = {}
    for p, stem, i, take, body in drafts:
        f = p[:-5] + '_draft.json'
        if not os.path.exists(f): fail(f'no {f}: the check wrote nothing', 1)
        out[stem] = json.load(open(f))
    return out, sum(r[1] for r in res)


def table(drafts, results, names):
    rows = ['| draft | frames | release push (cm/f) | release spin (deg/f) | exit / gun | mechanism | rules failed |', '|---|---|---|---|---|---|---|']
    for p, stem, i, take, body in drafts:
        r = results[stem]; R1 = (r.get('rules') or {}).get('R1', {}); rep = R1.get('report') or {}
        dv = rep.get('release_linear_impulse_cm_f'); dw = rep.get('release_angular_impulse_deg_f')
        failed = sorted({x.split()[0] for x in r['fails']}) or ['none']
        ratio = rep.get('exit_over_gun'); ratio = '-' if ratio is None else f'{ratio:.2f}'
        rows.append(f"| {stem} ({body}) {names.get(i, '')} | {r.get('frames')} | {'-' if dv is None else dv} | {'-' if dw is None else dw} | {ratio} | {rep.get('mechanism') or '-'} | {' '.join(failed)} |")
    return rows


# ------------------------------------------------------------------------------------------------ review
def scores_template(ids, names, family, rnd):
    """scores.json of a new round: the review page reads it, and only the reviewer can score. Every score 0, no notes; the page's ranking
    and 'top three' are then meaningless until the file is replaced."""
    return {'_about': f'{family} round {rnd}: UNSCORED, written by ga drafts so the review page renders. The reviewer replaces the s lists (fit, clarity, weight, style, cost, 0 to 10) and the notes.',
            'unscored': True, 'weights': [0.3, 0.25, 0.2, 0.15, 0.1], 'labels': ['Fit', 'Clarity', 'Weight', 'Style', 'Cost'],
            'drafts': {i: {'s': [0, 0, 0, 0, 0], 'mechanism': names.get(i, ''), 'good': [], 'bad': []} for i in ids}}


# ------------------------------------------------------------------------------------------------ review
def review(ent, family, rnd, root, ids, take, logdir, scores):
    """Frames, dense frame sheets, contact sheet, grid MP4, page. One Blender at a time, so sequential. -> [(step, exit, seconds)]"""
    rv = ent['review']; script = RELOAD + '/' + rv['script']; mod = [rv['module']] if rv.get('module') else []; labels = rv['labels']
    steps = []; idl = ','.join(ids); tk = (take or ','.join(ent['takes']))
    if rv.get('pre'):
        m, fn = rv['pre'].split('.')
        steps.append(('pre ' + rv['pre'], PY + ['-c', f"import sys; sys.path.insert(0, {RELOAD!r}); import renv, {m}; {m}.{fn}()"]))
    fr = PY + [script] + mod + ['frames', idl] + ([rv['takes_flag'], tk] if rv.get('takes_flag') else [])
    steps.append(('frames', fr))
    for i in ids:
        for lab in labels:
            if rv.get('takes_flag') and lab not in tk.split(','): continue
            steps.append((f'dense {i}{lab}', PY + [script] + mod + ['dense', f'{i}{lab}']))
    steps.append(('sheet', PY + [script] + mod + ['sheet', idl])); steps.append(('grid', PY + [script] + mod + ['grid', idl]))
    if os.path.exists(root + '/scores.json'): steps.append(('page', PY + [script] + mod + ['page', idl]))
    else: print(f'  page: skipped, no {root}/scores.json (the reviewer\'s scores; --scores <file> copies one there)')
    out = []; extra = {k: v.format(anim_work=manifest.path('anim_work')) for k, v in (rv.get('env') or {}).items()}
    for name, a in steps:
        print(f'  review {name} ...', flush=True)
        code, sec, text = sh(a, root, f'{logdir}/review_{re.sub("[^A-Za-z0-9]+", "_", name)}.log', extra=extra)
        print(f'  review {name}: exit {code}, {sec:.0f} s', flush=True); out.append((name, code, sec))
        if code: print(text[-1200:]); break
    return out


# ------------------------------------------------------------------------------------------------ drafts
def drafts(argv):
    if not argv or argv[0] in ('-h', '--help'): print(__doc__); return 0 if argv else 2
    if flag(argv, '--from-vanilla'):
        import vdrafts; return vdrafts.drafts_vanilla(argv)
    dry = flag(argv, '--dry-run'); norender = flag(argv, '--no-render'); no_gen = flag(argv, '--no-generate')
    rnd = opt(argv, '--round'); out = opt(argv, '--out'); take = opt(argv, '--take'); only = opt(argv, '--only'); jobs = int(opt(argv, '--jobs') or 3)
    cmp_dir = opt(argv, '--compare'); cmp_root = opt(argv, '--compare-root'); scores = opt(argv, '--scores'); rest_arch = opt(argv, '--rest-archive')
    if len(argv) != 1 or argv[0].startswith('-') or not rnd or not rnd.isdigit(): fail('usage: ga.sh drafts <family> --round N [--out <dir>] [--take A|B] [--only id,id] [--jobs n] [--no-render] [--dry-run]')
    family = argv[0]; ent = round_entry(family, rnd)
    base = (os.path.abspath(out) if out else manifest.path('anim_work')).replace('\\', '/').rstrip('/')
    root = f'{base}/{family}/round{rnd}'; logdir = root + '/work/drafts_logs'
    takes = ent['takes'] if not take else [take]
    if take and take not in ent['takes']: fail(f'{family} round {rnd} has takes {",".join(ent["takes"])}, not {take}')
    print(f'drafts {family} round {rnd}: generator {ent["gen"]}, takes {",".join(takes)}, into {root}' + (' (dry run)' if dry else ''))
    nobud = budget_check(family, takes, bool(ent.get('archive')))
    print(f'  R4 budget: ' + ', '.join(f'{t} {manifest.load()["checks"]["draft"]["r4_budget"][family][t]}' for t in takes if t not in nobud)
          + (f'; no budget for take {",".join(nobud)}: archived round, R4 is reported as not measurable, no budget' if nobud else ''))
    if dry:
        print(f'  would run: {ent["gen"]} {ent["build"]} (ids from {ent["catalog"][0]}.{ent["catalog"][1]}), rest {ent["rest"]}, post {ent.get("post")}, draftcheck per take, review {(ent.get("review") or {}).get("script") or "none wired"}')
        return 0
    os.makedirs(logdir, exist_ok=True)
    if ent.get('seed_ref'): seed_ref(root + '/ref')
    names = catalog(ent, root, logdir)
    if ent.get('id_prefix'): names = {k: v for k, v in names.items() if k.startswith(ent['id_prefix'])}      # round2.py lists the picks of every rifle family
    ids = list(names)
    if only:
        want = only.split(','); miss = [w for w in want if w not in names]
        if miss: fail(f'{",".join(miss)} not in {family} round {rnd} (drafts: {",".join(names)})')
        ids = want
    # history: old drafts of the same idea (information only)
    print(f'  history (authoring/draft/history.json, {len(history())} rows): old drafts with the same idea, shown for comparison, not a refusal:')
    pairs = history_pairs(family, ids, names)
    for h in pairs:
        old = (f'{h["old_family"]} round {h["old_round"]} draft {h["old_draft"]}' + (f' "{h["old_name"]}"' if h.get('old_name') else '') + f', archive {h["archive"]}') if h['old_draft'] else 'no old draft recorded'
        print(f'    {h["new"]} "{h["new_name"]}" repeats {h["kind"]} idea "{h["idea"]}": {old}')
    if not pairs: print('    no draft of this round matches a row')
    n = len(ids)
    if not 8 <= n <= 12: print(f'  {"note" if ent.get("archive") else "WARNING"}: {n} drafts; a round is about 10 (owner rule)' + (' (archived round, reproduced as it was made)' if ent.get('archive') else ''))
    t0 = time.time(); log = []
    cmds = []
    if not no_gen:
        # rest glbs, once, so the parallel generator runs only read them
        for g, g2 in ent['rest']['pairs']:
            for body in ent['rest']['bodies']:
                f = f'{root}/rest/{body}/rest_{g}_R__{g2}_L.glb'
                arch = rest_archive_file(ent, rest_arch, body, g, g2)
                if arch:
                    os.makedirs(os.path.dirname(f), exist_ok=True); shutil.copyfile(arch, f); print(f'  rest {g} {body}: the archived pose {arch}'); continue
                code, sec, text = sh(PY + [RELOAD + '/rest.py', g, g2, '--body', body, '--out', f], root, f'{logdir}/rest_{g}_{body}.log')
                if code: fail(f'rest.py {g} {body} failed (log {logdir}/rest_{g}_{body}.log):\n{text[-600:]}', 1)
        takes_arg = ','.join(takes)
        cmds = build_cmds(ent, family, ids, takes_arg, jobs)
        print(f'  generator: {len(cmds)} process(es), ids {",".join(ids)}', flush=True)
        for k, a in enumerate(cmds): print(f'    {" ".join(a[2:])}')
        with concurrent.futures.ThreadPoolExecutor(len(cmds)) as ex:
            res = list(ex.map(lambda k: sh(cmds[k], root, f'{logdir}/build_{k}.log'), range(len(cmds))))
        for k, (code, sec, text) in enumerate(res):
            print(f'    build {k}: exit {code}, {sec:.0f} s, log {logdir}/build_{k}.log', flush=True)
            if code: print(text[-1500:]); fail('generator failed', 1)
        for k, pc in enumerate(ent.get('post') or []):
            code, sec, text = sh(PY + [RELOAD + '/' + ent['gen']] + pc, root, f'{logdir}/post_{k}.log')
            print(f'    {ent["gen"]} {" ".join(pc)}: exit {code}, {sec:.0f} s', flush=True)
            if code: print(text[-1500:]); fail('post command failed', 1)
    found = find_drafts(root, ids, takes, ent)
    if not found: fail(f'no draft clip under {compare_base(ent, root)[0]}' + ('' if no_gen else ': the generator wrote none'), 1)
    print(f'  drafts {"found (--no-generate)" if no_gen else "written"}: {len(found)} clips ({len(set(f[2] for f in found))} ids)' + ('' if no_gen else f', generation {time.time() - t0:.0f} s'))
    code_all = 0; cmp_lines = []
    if cmp_dir:
        stems = {f[1] for f in found}; new_c, base_a = compare_base(ent, root); rows, kinds = compare_round(new_c, os.path.abspath(cmp_dir).replace('\\', '/'), base_a, (cmp_root or os.path.dirname(os.path.abspath(cmp_dir))).replace('\\', '/').rstrip('/'), stems)
        cmp_lines = compare_text(rows, kinds); print('  compare with ' + cmp_dir); [print('   ' + l) for l in cmp_lines]
        bad = [r for r in rows if r[1] != 'identical' or any(v not in ('identical', 'path only') for v in r[3].values())]
        open(root + '/compare.md', 'w', encoding='utf-8').write(f'# Compare with {cmp_dir}\n\n' + '\n'.join(cmp_lines) + '\n\n' + '\n'.join(f'- {r[0]}: glb {r[1]}; ' + ', '.join(f'{k} {v}' for k, v in r[3].items() if v not in ('identical', 'path only')) for r in bad) + '\n')
        json.dump([[r[0], r[1], r[2], r[3]] for r in rows], open(root + '/compare.json', 'w'), indent=1)
        if any(r[1] != 'identical' for r in rows): code_all = 1
    # checks
    results, csec = run_checks(family, found, root, logdir, jobs)
    rows = table(found, results, names); nfail = sum(bool(results[f[1]]['fails']) for f in found)
    print(f'  draft checks (every gate rule of rules.json, R1 to R14): {len(found) - nfail} pass, {nfail} fail, {csec:.0f} s of check time')
    if nfail: code_all = 1      # a draft that fails any rule fails the command (the clips and sheets are still written)
    print('  R1 release impulse and carrier bound: reported, not gated; hand frames (loading, ejection) are not judged'); [print('  ' + r) for r in rows]
    for p, stem, i, tk, body in found:
        r = results[stem]
        if r['fails']: print(f'    FAIL {stem}: ' + '; '.join(r['fails']))
    md = [f'# {family} round {rnd}: drafts and draft checks', '', f'Generator {ent["gen"]}, takes {",".join(takes)}, {len(found)} clips. R1 release impulse is reported, not gated.', ''] + rows
    if pairs:
        md += ['', '## History: show the old draft next to the new one', '', '| new draft | old draft | idea | archive (under paths.anim_work) |', '|---|---|---|---|']
        md += [f'| {h["new"]} {h["new_name"]} | ' + (f'{h["old_family"]} round {h["old_round"]} {h["old_draft"]} {h.get("old_name") or ""}' if h['old_draft'] else 'none recorded') + f' | {h["kind"]}: {h["idea"]} | {h["archive"] or "-"} |' for h in pairs]
    open(root + '/DRAFTS.md', 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    prev = json.load(open(root + '/drafts.json')) if no_gen and os.path.exists(root + '/drafts.json') else {}
    json.dump({'family': family, 'round': int(rnd), 'generator': ent['gen'], 'ids': ids, 'takes': takes, 'history': pairs, 'commands': [' '.join(c[2:]) for c in cmds] or prev.get('commands'),
               'clips': [{'stem': f[1], 'id': f[2], 'take': f[3], 'body': f[4], 'fails': results[f[1]]['fails'], 'baselines': results[f[1]]['baselines']} for f in found],
               'generation_s': prev.get('generation_s') if no_gen else round(time.time() - t0 - csec, 1)}, open(root + '/drafts.json', 'w'), indent=1)
    if scores and not os.path.exists(root + '/scores.json'): shutil.copyfile(scores, root + '/scores.json')
    elif not os.path.exists(root + '/scores.json'):
        json.dump(scores_template(ids, names, family, rnd), open(root + '/scores.json', 'w'), indent=1)
        print(f'  scores.json: written unscored (all scores 0) so the page renders; the reviewer replaces it (--scores <file> copies one in)')
    if norender: print('  review: skipped (--no-render)')
    elif not ent.get('review'): print(f'  review: none wired for {family} round {rnd}' + (f' ({ent["review_note"]})' if ent.get('review_note') else ''))
    else:
        t1 = time.time(); rv = review(ent, family, rnd, root, ids, take, logdir, scores)
        print(f'  review: {sum(s for _, _, s in rv):.0f} s of Blender and image work, {time.time() - t1:.0f} s wall')
        if any(c for _, c, _ in rv): code_all = 1
    print(f'drafts {family} round {rnd}: done in {time.time() - t0:.0f} s' + ('' if not code_all else ' (a step failed or the compare differs)'))
    return code_all


# ------------------------------------------------------------------------------------------------ pick
def edit_manifest(text, gid, picks, slots):
    """weapons.json is hand-formatted: replace the picks and slots arrays of gun gid in place (text edit, other bytes untouched)."""
    i = text.index(f'"id": "{gid}"'); j = text.find('\n   "id": "', i + 5); j = len(text) if j < 0 else j
    blk = text[i:j]; fmt = lambda xs: '[' + ', '.join(json.dumps(x) for x in xs) + ']'
    new = re.sub(r'("picks": )\[[^\]]*\]', lambda m: m.group(1) + fmt(picks), blk, count=1)
    new = re.sub(r'("slots": )\[[^\]]*\]', lambda m: m.group(1) + fmt(slots), new, count=1)
    return text[:i] + new + text[j:]


def pick(argv):
    if not argv or argv[0] in ('-h', '--help'): print(__doc__); return 0 if argv else 2
    dry = flag(argv, '--dry-run'); replace = flag(argv, '--replace'); allow = flag(argv, '--allow-fail')
    rnd = opt(argv, '--round'); out = opt(argv, '--out')
    if len(argv) != 2 or not rnd or not rnd.isdigit(): fail('usage: ga.sh pick <family> <id>[,id] --round N [--out <dir>] [--replace] [--allow-fail] [--dry-run]')
    family, ids = argv[0], [x for x in argv[1].split(',') if x]
    if len(set(ids)) != len(ids): fail('a draft id is listed twice')
    ent = round_entry(family, rnd)
    base = (os.path.abspath(out) if out else manifest.path('anim_work')).replace('\\', '/').rstrip('/'); root = f'{base}/{family}/round{rnd}'
    man = manifest.load(); guns = [g for g in man['guns'] if (g.get('reload') or {}).get('category') == family and not g['reload'].get('shares')]
    if not guns: fail(f'no gun of family {family} has its own reload entry in weapons.json')
    found = find_drafts(root, set(ids), set('AB'), ent)
    for i in ids:
        got = [f for f in found if f[2] == i]
        if not got: fail(f'no draft {i} under {root}/clips: run ga drafts {family} --round {rnd} first')
        for p, stem, _, tk, body in got:
            d = p[:-5] + '_draft.json'
            if not os.path.exists(d): fail(f'{stem} has no _draft.json: run the draft checks first')
            r = json.load(open(d))
            if r['fails'] and not allow: fail(f'{stem} fails the draft checks ({"; ".join(r["fails"])[:300]}); --allow-fail records it anyway')
    names = catalog(ent, root, root + '/work/drafts_logs') if os.path.isdir(root + '/work') else {}
    cur = list(guns[0]['reload']['picks'])
    new = list(ids) if replace else cur + [i for i in ids if i not in cur]
    if len(new) > 3: fail(f'a set holds at most 3 picks (owner rule); {family} would hold {",".join(new)}. Use --replace to set exactly {argv[1]}')
    slots = [new[k % len(new)] for k in range(3)] if len(new) < 3 else list(new)
    path = (os.environ.get('GA_MANIFEST') or os.path.join(TOOLS, 'weapons.json'))
    raw = open(path, 'rb').read(); text = raw.decode('utf-8'); text2 = text
    for g in guns: text2 = edit_manifest(text2, g['id'], new, slots)
    nlcheck = text2.replace('\r\n', '\n')
    try: json.loads(text2)
    except ValueError as e: fail(f'the edited weapons.json would not parse: {e}', 1)
    print(f'pick {family} round {rnd}: {",".join(ids)} -> picks {new}, slots {slots}; guns {",".join(g["id"] for g in guns)}')
    diff = list(difflib.unified_diff(text.replace('\r\n', '\n').splitlines(), nlcheck.splitlines(), 'weapons.json', 'weapons.json (picks)', lineterm='', n=0))
    if diff: [print('  ' + l[:230]) for l in diff]
    else: print('  weapons.json: no change (the manifest already holds these picks)')
    nm = {g['id']: g['reload'] for g in guns}
    md = [f'# {family} round {rnd}: owner picks', '', f'Recorded {datetime.date.today().isoformat()} by ga pick: {",".join(ids)}' + (' (replacing the earlier picks)' if replace else '') + '.', '']
    for i in ids:
        got = [f for f in found if f[2] == i]; ok = all(not json.load(open(f[0][:-5] + '_draft.json'))['fails'] for f in got)
        md.append(f'- {i} {names.get(i, "")} (technique id {technique_id(names.get(i, i))}): takes {",".join(sorted({f[3] for f in got}))}, draft checks ' + ('pass' if ok else 'FAIL (allowed)'))
    md += ['', f'weapons.json guns {", ".join(g["id"] for g in guns)}: picks {new}, slots {slots}.']
    if dry:
        print('  PICKS.md would read:'); [print('    ' + l) for l in md]; print('  (dry run: nothing written)'); return 0
    if text2 != text: open(path, 'wb').write(text2.encode('utf-8'))
    open(root + '/PICKS.md', 'w', encoding='utf-8').write('\n'.join(md) + '\n'); print(f'  wrote {path if text2 != text else "(manifest unchanged)"} and {root}/PICKS.md')
    return 0
