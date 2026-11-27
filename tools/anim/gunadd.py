"""ga gun add: the steps of "Add a gun" (README) run in order with the existing tools.

usage: ga.sh gun add <id> [--from <seed.json>] [--out <dir>] [--dry-run] [--apply] [--ack step,step|all] [--render]
  <id>        a gun of weapons.json (reproduction: its hand-entered fields are the seed, everything a tool derives is
              stripped and derived again) or a new id with --from.
  --from      the hand-entered fields of the gun as one json object: id, name, type, item_type, vars, audio, length and,
              for the types with arm clips, arm_set and mesh (also evolution, weapon_anim, parts, mesh_parts, game_dual,
              note, status). Fields a tool derives (lowered, raised, partner, reload) may be given: they are then the
              owner's values and are checked against the rules.
  --out       everything written: scratch manifest, tool output, sheets, <id>.proposed.json, <id>.diff.md, steps.md
              (default: <paths.authoring_work>/gun_add/<id>). weapons.json is not touched.
  --dry-run   print every step with its command, inputs and outputs and whether it needs the owner's eye; run nothing,
              write nothing.
  --apply     after the last step, add the proposed entry to weapons.json (new ids only).
  --ack       the steps whose sheet the owner has looked at (classify, weight, lowered, raised, partner), or all.
              Without it the run stops after the first step that needs the owner's eye (exit 10) and names the sheet.
  --render    also make the Blender previews of the lowered and raised poses (not part of the checks).

Steps: given, files, extents, size, weight, classify, lowered, raised, partner, entry. No step runs WolvenKit: a missing
game file stops the run (exit 3) and names the file and the command that exports it (build.sh extract, README "Game files").
Pose rule (owner, measures only): every gun with a model variable and a mesh has its own lowered pose. The length gives the preferred
family, v1d when the assembled gun is longer than checks.lowered.v1d_over_cm, else v1; it applies only if a tune passes every lowered check
(authoring/lowered/fit.py), else the other family (pose <family>_<name>, a tune that passes the checks), and, when its screen
cover in the game's raised pose is over checks.raised.limit_pct, its own C raised pose (pose C_<name>, s for both bodies); under the limit
it has no raised pose. A gun that does not follow the rule is refused (exit 2), naming the field. No category, no hand length.
Not made here: reload picks, slots and layout (ga drafts, ga pick, ga produce), the long partner clips.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
AUTH = HERE + '/authoring'
sys.path.insert(0, HERE)
import manifest
from ga import Step, show, take_opt, fail

PY = [sys.executable, '-B']
# fields a tool or a rule produces; everything else of an entry is hand-entered (given)
DERIVED = ('lowered', 'raised', 'partner', 'long_partner', 'reload')
REQUIRED = ('id', 'name', 'type', 'item_type', 'vars', 'audio', 'length')
EYE_STEPS = ('weight', 'classify', 'lowered', 'raised', 'partner')
REFUSED, MISSING, STOPPED = 2, 3, 10
BASE = os.environ.get('GA_MANIFEST') or manifest.HERE + '/weapons.json'    # the manifest read and, with --apply, edited


class Refuse(Exception):
    def __init__(self, msg, code=REFUSED):
        super().__init__(msg); self.code = code


def pose_name(family, mesh):
    return f'{family}_{mesh.split("__")[1]}'


def strip(entry):
    return {k: v for k, v in entry.items() if k not in DERIVED}


def flat(v, path=''):
    """{dotted path: leaf}; lists and scalars are leaves, dicts are walked."""
    if isinstance(v, dict) and v:
        out = {}
        for k, x in v.items():
            out.update(flat(x, f'{path}.{k}' if path else k))
        return out
    return {path: v}


def arm_type(m, g):
    return bool(m['types'][g['type']].get('arm_clips'))


class Run:
    """State of one `gun add`: the given entry, the scratch manifests, what each step found."""

    def __init__(self, gid, seed, shipped, out, ack, render, owner=None):
        self.gid, self.out, self.ack, self.render = gid, out, ack, render
        self.m = json.load(open(BASE, encoding='utf-8'))
        self.shipped = shipped                      # the entry of weapons.json, or None
        self.given = strip(seed)
        self.work = out + '/work'
        self.scratch = out + '/manifest.scratch.json'
        self.found = {}                             # step name -> result
        self.proposed = dict(self.given)
        self.lines = []                             # report lines
        self.sheets = {}
        self.large = None                           # cover over checks.raised.limit_pct (None: not measured)
        self.owner = owner or {}                    # derived fields the owner gave with --from (checked against the rules, not derived)

    def env(self, manifest_path=None):
        return {'GA_MANIFEST': manifest_path or self.scratch, 'GA_TEST': '1', 'ROUND_OUT': self.work + '/round', 'WORK': self.work,
                'AUTHORING': self.work + '/authoring', 'PYTHONDONTWRITEBYTECODE': '1'}

    def write_manifest(self, path, entry):
        m = json.loads(json.dumps(self.m)); guns = m['guns']
        for i, g in enumerate(guns):
            if g['id'] == self.gid:
                guns[i] = entry; break
        else:
            guns.append(entry)
        json.dump(m, open(path, 'w', encoding='utf-8'), indent=1)

    def gun_type(self):
        return self.m['types'][self.given['type']]

    def arm(self):
        return arm_type(self.m, self.given)

    def has_var(self):
        return bool(self.given.get('vars')) and bool(self.given.get('mesh'))


def run_tool(R, argv, name, cwd):
    """Run one tool: (exit code, output); output also kept in <out>/logs/<name>.log"""
    os.makedirs(R.out + '/logs', exist_ok=True)
    env = dict(os.environ, **R.env())
    r = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    open(f'{R.out}/logs/{name}.log', 'w', encoding='utf-8').write(r.stdout)
    return r.returncode, r.stdout


# ---- the steps ---------------------------------------------------------------------------------------------------------
def plan(R):
    """[Step]: every step in order. Each Step has .eye (needs the owner's eye), .skip (why it does not apply) and .post(R, code, text)."""
    g, gid, m = R.given, R.gid, R.m
    steps = []

    def add(name, eye=False, skip=None, post=None, **kw):
        s = Step(name, **kw); s.eye, s.skip, s.post = eye, skip, post; steps.append(s); return s

    a = R.arm(); mesh = g.get('mesh'); var = R.has_var()
    LOW, RAI, TOP, REL = AUTH + '/lowered', AUTH + '/raised', AUTH + '/topmag', AUTH + '/reload'
    add('given', fn=lambda: None, reads='the seed (--from, or the hand-entered fields of the weapons.json entry)', writes='',
        note='id, name, type, item_type, vars, audio, length (+ arm_set, mesh for the types with arm clips) are entered by hand; no tool reads them from the game', post=post_given)
    add('files', fn=lambda: None, reads='paths.weapon_meshes, weapon_anims, gamefiles', writes='',
        note='the gun\'s meshes, weapon anims and arm set are in the extracted game files; if not, the run stops (exit 3) and names them: WolvenKit is not started here',
        skip=None if a and mesh else 'a type without arm clips (or a gun without a mesh): nothing to export', post=post_files)
    add('extents', argv=PY + [LOW + '/guns.py', '--guns', gid], cwd=LOW, reads='mesh and weapon anim glbs', writes='<out>/logs/extents.log',
        note='extents and length (cm, every vertex) of the gun in weapon bone space (the length decides the lowered family: v1d over checks.lowered.v1d_over_cm)', skip=None if a and mesh else 'no mesh', post=post_extents)
    add('size', argv=PY + [RAI + '/rautotune.py', '--guns', gid, '--out', R.out + '/rautotune_game_{body}.json'], cwd=RAI,
        reads='mesh, raised pose metric (checks.raised camera)', writes='<out>/rautotune_game_<body>.json',
        note='screen cover in the game\'s raised pose; over checks.raised.limit_pct the gun gets family C',
        skip=None if var else 'no own model variable (vars empty or no mesh): the poses are the owner gun\'s', post=post_size)
    add('weight', eye=True, argv=PY + [REL + '/weight.py', R.out + '/weight.png', '--json', R.out + '/weight.json', '--guns', gid], cwd=REL,
        reads='mesh, seated magazine', writes='<out>/weight.png, weight.json',
        note='bulk of the mesh: heavy over 5.5 l or 5.4 cm mean width (rifles; shipped classes are the owner\'s). Other types: the owner decides',
        skip=None if var and g['type'] == 'rifle' else 'weight.py covers assault rifles; the owner picks light or heavy for the others', post=post_weight)
    add('classify', eye=True, argv=PY + [REL + '/classify.py', '--guns', gid, '--out', R.out + '/classify'], cwd=REL,
        reads='the gun\'s own reload (weapon anims), mesh', writes='<out>/classify/classify.json, classify.md',
        note='magazine position, exit, frames; the category is proposed from shipped guns of the same type and position, the owner chooses',
        skip=None if a and var and g['type'] != 'pistol' else 'no magazine reload to classify', post=post_classify)
    add('lowered', eye=True, argv=PY + [LOW + '/autotune.py', '--guns', gid, '--out', R.out + '/autotune.json'], cwd=LOW,
        reads='mesh, lowered families v1 and v1d (checks.lowered)', writes='<out>/autotune.json',
        note='family by the pose rule (v1d over checks.lowered.v1d_over_cm, else v1, the other one when no tune passes every lowered check) and its tune (top edge at -0.78, eye 25 cm, wrist 20 deg); runs the lowered checks per candidate: minutes',
        skip=None if var else 'no own model variable', post=post_lowered)
    add('raised', eye=True, argv=PY + [RAI + '/rautotune.py', '--guns', gid, '--family', 'C', '--out', R.out + '/rautotune_C_{body}.json'], cwd=RAI,
        reads='mesh, family C (weapons.json raised_families)', writes='<out>/rautotune_C_<body>.json',
        note='s of family C per body; only a gun over checks.raised.limit_pct gets a raised pose', skip=None if var else 'no own model variable', post=post_raised)
    add('partner', eye=True, argv=PY + [TOP + '/partner.py', 'measure', gid, '--json', R.out + '/partner.json'], cwd=TOP,
        reads='mesh parts, topmag specs of the Shingen picks', writes='<out>/partner.json',
        note='category per pick (flip, doubletap, uppercut); "NEW CATEGORY?" needs clips (gen_smg.py --cats) and the owner. Rifles: long_partner (owner)',
        skip=("no model variable of its own (vars empty): its records use another gun's variable and partner row" if not g.get('vars') else
              'long rifles use long_partner (borrow a gun of similar length or make clips with gen_long.py): owner' if g['type'] == 'rifle' and g.get('length') == 'long' else None),
        post=post_partner)
    add('entry', fn=lambda: None, reads='the steps above', writes='<out>/<id>.proposed.json, <id>.diff.md, steps.md (weapons.json only with --apply)',
        note='the proposed entry; pose rule checked on it; fields compared with weapons.json', post=post_entry)
    return steps


def post_given(R, code, text):
    miss = [k for k in REQUIRED if k not in R.given]
    if R.arm() and R.given.get('vars'):
        miss += [k for k in ('arm_set', 'mesh') if k not in R.given]
    if miss:
        raise Refuse(f'the seed lacks {", ".join(miss)}: these are entered by hand')
    return f'{len(R.given)} hand-entered fields: {", ".join(R.given)}'


def post_files(R, code, text):
    manifest._m = None; os.environ['GA_MANIFEST'] = R.scratch
    g = R.given; need = []
    mesh = g['mesh']
    if not manifest.find('weapon_meshes', f'{mesh}__base1_01.glb'): need.append(f'mesh {mesh}__base1_01.glb (paths.weapon_meshes)')
    if g['type'] in ('smg', 'rifle') and not manifest.find('weapon_anims', (g.get('weapon_anim') or mesh) + '__base1.anims.glb'):
        need.append(f'weapon anims {(g.get("weapon_anim") or mesh)}__base1.anims.glb (paths.weapon_anims)')
    arm = g.get('arm_set')
    if arm and not os.path.exists(manifest.gamefile(manifest.depot(arm), '.json')):
        need.append(f'arm set {arm} (paths.gamefiles: .anims or its .json conversion)')
    if need:
        raise Refuse('missing game files, WolvenKit is not run here: ' + '; '.join(need) + '. Export them (README "Game files", `build.sh extract`) and rerun.', MISSING)
    return 'meshes, weapon anims and arm set present'


def post_extents(R, code, text):
    if code: raise Refuse(f'guns.py failed: {text[-300:]}')
    return text.strip().splitlines()[-1].split(None, 2)[-1] if text.strip() else ''


def read_json(p):
    return json.load(open(p, encoding='utf-8'))


def post_size(R, code, text):
    if code not in (0, 1): raise Refuse(f'rautotune failed (exit {code}): {text[-300:]}')
    lim = R.m['checks']['raised']['limit_pct']; cover = {}
    for b in R.m['game_files']['bodies']:
        d = read_json(f'{R.out}/rautotune_game_{b}.json')[R.gid]
        cover[b] = d['game']['idle']['Right']['cover']
    R.found['size'] = {'cover': cover, 'limit': lim}
    R.large = max(cover.values()) > lim
    return f'cover {cover} limit {lim}: {"over, family C" if R.large else "under, game pose"}'


def type_group(R):
    return R.gun_type()['group']


def post_classify(R, code, text):
    if code: raise Refuse(f'classify.py failed: {text[-300:]}')
    row = read_json(R.out + '/classify/classify.json')[0]
    R.sheets['classify'] = R.out + '/classify/classify.md'
    rl = row.get('reload') or {}
    if 'note' not in row and (not rl or rl.get('error') or '(from the slot)' in (row.get('position') or '')):
        R.found['classify'] = {'candidates': {}, 'row': row, 'unclassified': True}
        return f'the own reload of the gun could not be classified ({rl.get("error") or "no timing"}): no category proposed, no magazine entry (shell gun or break-open); the owner decides'
    if 'note' in row:
        R.found['classify'] = {'candidates': [], 'row': row}
        return f'{row.get("position", "")}: {row["note"]}; category: owner'
    # shipped guns of this type and the same magazine position: the categories they have
    ref = R.out + '/classify_ref'
    ids = [g['id'] for g in R.m['guns'] if g['id'] != R.gid and g['type'] == R.given['type'] and (g.get('reload') or {}).get('category')
           and not g['reload'].get('shares') and g.get('mesh') and g.get('vars')]
    if ids:
        c, t = run_tool(R, PY + [REL_CLASSIFY, '--guns', ','.join(ids), '--out', ref], 'classify_ref', os.path.dirname(REL_CLASSIFY))
        if c: raise Refuse(f'classify.py (shipped guns) failed: {t[-300:]}')
    cats = {}
    pos = (row.get('position') or '').replace(' (from the slot)', '')
    wclass = (R.found.get('weight') or {}).get('class')
    for r in (read_json(ref + '/classify.json') if ids else []):
        if 'note' in r or (r.get('reload') or {}).get('error') or 'reload' not in r: continue
        if (r.get('position') or '').replace(' (from the slot)', '') != pos: continue
        sg = next(g for g in R.m['guns'] if g['id'] == r['gun'])
        if wclass and sg['reload'].get('weight') != wclass: continue      # a heavy rifle is not a light one's category
        cats.setdefault(sg['reload']['category'], []).append(r['gun'])
    cand = sorted(cats)
    R.found['classify'] = {'candidates': cats, 'row': row}
    if len(cand) == 1:
        R.found['category'] = cand[0]
        return f'position {pos}: category {cand[0]} (as {", ".join(cats[cand[0]])}); the owner confirms'
    return f'position {pos}{", " + wclass if wclass else ""}: category is for the owner: {cats if cats else "no shipped gun of this type, position and weight"}'


REL_CLASSIFY = AUTH + '/reload/classify.py'


def post_weight(R, code, text):
    if code: raise Refuse(f'weight.py failed: {text[-300:]}')
    r = read_json(R.out + '/weight.json')[0]
    R.sheets['weight'] = R.out + '/weight.png'
    R.found['weight'] = r
    return f'bulk {r["bulk_l"]} l, mean width {r["mean_width_cm"]} cm: computed {r["proposed"]}, class {r["class"]} ({r["by"]})'


def post_lowered(R, code, text):
    if code not in (0, 1): raise Refuse(f'autotune failed (exit {code}): {text[-300:]}')
    d = read_json(R.out + '/autotune.json')[R.gid]; R.found['lowered_tool'] = d
    given = R.owner.get('lowered')
    if given:
        fam, pose, tune = given.get('family'), given.get('pose'), given.get('tune')
        src = 'given by the owner'
    else:
        fam, pose, tune = (d['family'], pose_name(d['family'], R.given['mesh']), d['tune']) if d['passes'] else (None, None, d['tune'])
        src = 'autotune'
    ent = None
    if fam:
        ent = {'family': fam, 'pose': pose}
        if tune is not None and fam != 'v2': ent['tune'] = tune
    R.found['lowered'] = ent
    if ent: R.proposed['lowered'] = ent
    R.found['lowered_src'] = src
    why = '' if d['family'] == d['preferred'] else f' ({d["preferred"]} misses: ' + '; '.join(f'{n} {v} vs {l}' for n, v, l in d['failures']) + ')'
    msg = (f'length {d["length_cm"]} cm, preferred {d["preferred"]}, family {d["family"]}{why}: tune {d["tune"]} eye {d["footprint"]["eye"]} cm wrist {d["footprint"]["wrist"]} deg, passes {d["passes"]}: '
           f'{json.dumps(ent) if ent else "no passing tune"} ({src})')
    rule_lowered(R)
    return msg


def rule_lowered(R):
    """Pose rule, lowered: every gun with a model variable and a mesh has its own pose of the family the length gives."""
    d = R.found.get('lowered_tool')
    if not d: return
    ent = R.found.get('lowered'); want = d['family']
    if not ent:
        raise Refuse(f'pose rule: {R.gid} is {d["length_cm"]} cm, preferred {d["preferred"]}, and no family has a tune that passes the lowered checks '
                     f'(eye {d.get("footprint", {}).get("eye")}, wrist {d.get("footprint", {}).get("wrist")}): missing field lowered')
    bad = []
    if ent.get('family') != want: bad.append(f'lowered.family is {ent.get("family")}, the rule gives {want} for {d["length_cm"]} cm (preferred {d["preferred"]}; v1d over {R.m["checks"]["lowered"]["v1d_over_cm"]})')
    elif ent.get('pose') != pose_name(want, R.given['mesh']): bad.append(f'lowered.pose is {ent.get("pose")}, must be its own ({pose_name(want, R.given["mesh"])})')
    if 'tune' not in ent: bad.append('lowered.tune is missing')
    if bad: raise Refuse(f'pose rule: {R.gid}: ' + '; '.join(bad))


def post_raised(R, code, text):
    if code not in (0, 1): raise Refuse(f'rautotune failed (exit {code}): {text[-300:]}')
    res = {b: read_json(f'{R.out}/rautotune_C_{b}.json')[R.gid] for b in R.m['game_files']['bodies']}
    R.found['raised_tool'] = res
    given = R.owner.get('raised')
    if given:
        ent, src = given, 'given by the owner'
    elif R.large:
        ok = all(r['note'].startswith('target reached') and r['s'] > 0 for r in res.values())
        src = 'rautotune'
        ent = {'family': 'C', 'pose': pose_name('C', R.given['mesh']), 's': {b: r['s'] for b, r in res.items()}} if ok else None
    else:
        ent, src = None, 'under the cover limit: the game pose'
    R.found['raised'] = ent
    if ent: R.proposed['raised'] = ent
    notes = {b: r['note'] for b, r in res.items()}
    rule_raised(R, notes)
    return f'family C s {{{", ".join(f"{b} {r["s"]}" for b, r in res.items())}}} ({"; ".join(sorted(set(notes.values())))}): {json.dumps(ent) if ent else "no raised entry"} ({src})'


def rule_raised(R, notes=None):
    """Pose rule, raised: C with its own pose and s when the cover is over the limit, no raised pose when it is not."""
    if R.large is None: return
    ent = R.found.get('raised'); size = R.found['size']
    if not R.large:
        if ent and ent.get('family') != 'none':
            raise Refuse(f'pose rule: {R.gid} has a cover of {size["cover"]}, under {size["limit"]}: no raised pose (field raised is {ent.get("family")})')
        return
    if not ent:
        raise Refuse(f'pose rule: {R.gid} has a cover of {size["cover"]}, over {size["limit"]}, and family C does not reach its target '
                     f'({notes}): missing field raised')
    bad = []
    if ent.get('family') != 'C': bad.append(f'raised.family is {ent.get("family")}, must be C')
    if ent.get('pose') != pose_name('C', R.given['mesh']): bad.append(f'raised.pose is {ent.get("pose")}, must be its own ({pose_name("C", R.given["mesh"])})')
    for b in R.m['game_files']['bodies']:
        if not (ent.get('s') or {}).get(b): bad.append(f'raised.s.{b} is missing')
    if bad: raise Refuse(f'pose rule: {R.gid} has a cover of {size["cover"]}, over {size["limit"]}: ' + '; '.join(bad))


def post_partner(R, code, text):
    if code: raise Refuse(f'partner.py cannot measure {R.gid}: {text.strip().splitlines()[-1] if text.strip() else "no output"} (its parts come from the manifest or authoring/topmag/data/parts.json)')
    d = read_json(R.out + '/partner.json')[R.gid]
    R.sheets['partner'] = R.out + '/logs/partner.log'
    R.found['partner'] = d
    new = [k for k, v in d['fam'].items() if v['new_category']]
    if not new:
        R.proposed['partner'] = dict(d['partner'])
    return f'{json.dumps(d["partner"])}' + (f'; NEW CATEGORY for {new}: clips and the owner needed' if new else '')


def reload_entry(R):
    """The part of reload a rule produces: category (when one is unique), weight (rifles), magazine, clips, archive."""
    g = R.given; r = {}
    cl = R.found.get('classify')
    if not cl: return r
    if R.found.get('category'): r['category'] = R.found['category']
    w = R.found.get('weight')
    if w: r['weight'] = w['class']
    if g['type'] in ('smg', 'shotgun'):
        r['clips'] = 'smg_reload_clips'; r['archive'] = 'GorillaAkimboSmgShotgun'
    # shell guns (tube, break): the shipped entries of the category have magazine null
    shells = R.found.get('category') and all(next(x for x in R.m['guns'] if x['id'] == i)['reload'].get('magazine') is None
                                           for i in cl['candidates'].get(R.found['category'], []))
    if 'note' in cl['row'] or cl.get('unclassified') or shells:
        r['magazine'] = None; return r
    BS = chr(92)
    base = g['arm_set'].replace('/', BS).rsplit(BS, 1)[0]
    r['magazine'] = {'set': f'{base}{BS}{g["mesh"]}__mag_std.anims', 'weapon_set': f'{base}{BS}{g.get("weapon_anim") or g["mesh"]}__base1.anims',
                     'components': ['Magazine', 'MagazineReload']}
    if g['type'] in ('smg', 'shotgun'):
        r['magazine'].update({'builder': 'rmagset2', 'gamefiles': 'smg_reload_gamefiles'})
    return r


# a field is: given (hand entered), tool (a tool derives it), rule (derived by a rule from given fields), owner (a decision), downstream (ga drafts, pick, produce)
def field_kind(path):
    top = path.split('.')[0]
    if top in ('lowered', 'raised'): return 'tool'
    if path == 'partner.shingen': return 'tool'
    if path == 'reload.weight': return 'tool (rifles) / owner'
    if path == 'reload.category': return 'owner (proposed from classify)'
    if path.startswith('reload.magazine') or path in ('reload.clips', 'reload.archive'): return 'rule (default; some guns use rcv1 or a shared mag_std: owner verifies)'
    if path.startswith('reload'): return 'downstream (ga drafts, ga pick, ga produce)'
    if path == 'partner.borg': return 'owner (Borg is disabled: partner.py measures the Shingen only)'
    if top in ('partner', 'long_partner'): return 'owner (long partner: borrow or own clips)'
    return 'given'


def post_entry(R, code, text):
    rl = reload_entry(R)
    if rl:
        R.proposed['reload'] = rl
    rule_lowered(R); rule_raised(R)
    p = f'{R.out}/{R.gid}.proposed.json'
    json.dump(R.proposed, open(p, 'w', encoding='utf-8'), indent=1)
    msg = [f'wrote {p}']
    if R.shipped is not None:
        rows, same, diff, skipped, extra = diff_entry(R)
        open(f'{R.out}/{R.gid}.diff.md', 'w', encoding='utf-8').write(rows)
        msg.append(f'diff against weapons.json: {same} derived fields equal, {len(diff)} differ, {len(extra)} extra, {skipped} owner or downstream fields not produced here (see {R.gid}.diff.md)')
        R.found['diff'] = {'same': same, 'differ': diff, 'extra': extra, 'not_produced': skipped}
    return '; '.join(msg)


def diff_entry(R):
    want, got = flat(R.shipped), flat(R.proposed)
    paths = [p for p in list(want) + [p for p in got if p not in want]]
    L = ['| field | kind | weapons.json | proposed | result |', '|---|---|---|---|---|']
    same = skipped = 0; diff = []; extra = []
    for p in paths:
        k = field_kind(p); w, g = want.get(p, '(absent)'), got.get(p, '(absent)')
        if p not in want and k != 'given':
            L.append(f'| {p} | {k} | (absent) | {json.dumps(g)[:70]} | extra: weapons.json has no such field |'); extra.append(p); continue
        if k == 'given':
            if w != g: diff.append(p + ' (given)')
            continue
        if p not in got and p.startswith('reload.') and k.startswith('downstream'):
            skipped += 1; continue
        if p not in got and 'owner' in k:
            L.append(f'| {p} | {k} | {json.dumps(w)[:60]} | (not produced) | owner |'); skipped += 1; continue
        ok = w == g
        same += ok
        if not ok: diff.append(p)
        L.append(f'| {p} | {k} | {json.dumps(w)[:70]} | {json.dumps(g)[:70]} | {"same" if ok else "DIFFERENT"} |')
    return '\n'.join(L) + '\n', same, diff, skipped, extra


# ---- the command -------------------------------------------------------------------------------------------------------
def execute(R, steps, only_dry=False):
    t0 = time.time()
    for i, s in enumerate(steps, 1):
        if s.skip:
            R.lines.append(f'{s.name}: skipped, {s.skip}'); print(f'{i}. {s.name}: skipped, {s.skip}', flush=True); continue
        t = time.time(); code = text = None
        if s.argv:
            code, text = run_tool(R, s.argv, f'{i:02d}_{s.name}', s.cwd)
        try:
            msg = s.post(R, code, text or '')
        except Refuse as e:
            line = f'{s.name}: REFUSED, {e}'
            R.lines.append(line); print(f'{i}. {line}', flush=True); save_report(R)
            return e.code
        if s.name == 'lowered' or s.name == 'raised': refresh_proposed_manifest(R)
        if s.name == 'lowered' and R.render: render_lowered(R)
        if s.name == 'raised' and R.render and R.found.get('raised'): render_raised(R)
        line = f'{s.name}: {msg} ({time.time() - t:.0f} s)'
        R.lines.append(line); print(f'{i}. {line}', flush=True)
        if s.eye and (s.name != 'raised' or R.found.get('raised')) and not ('all' in R.ack or s.name in R.ack):
            sheet = R.sheets.get(s.name, R.out)
            R.lines.append(f'stopped after {s.name}: owner\'s eye on {sheet}; rerun with --ack {s.name}')
            print(f'   stopped: look at {sheet}, then rerun with --ack {s.name} (or --ack all)', flush=True); save_report(R)
            return STOPPED
    save_report(R)
    print(f'gun add {R.gid}: done in {time.time() - t0:.0f} s; proposal {R.out}/{R.gid}.proposed.json')
    return 0


def save_report(R):
    open(R.out + '/steps.md', 'w', encoding='utf-8').write(f'# gun add {R.gid}\n\n' + '\n'.join(f'- {l}' for l in R.lines) + '\n')


def refresh_proposed_manifest(R):
    R.write_manifest(R.out + '/manifest.proposed.json', dict(R.proposed))


def render_lowered(R):
    LOW = AUTH + '/lowered'; pm = R.out + '/manifest.proposed.json'
    if not R.found.get('lowered'): return
    pose = R.found['lowered']['pose']; env = R.env(pm)
    subprocess.run(PY + [LOW + '/makeclips.py', '--out', R.out + '/lowclips', '--poses', pose], cwd=LOW, env=dict(os.environ, **env), check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(PY + [LOW + '/render.py', '--pair', R.gid, R.gid, 'pma', R.out + '/lowered_' + R.gid, f'{R.gid} lowered', '--clips', R.out + '/lowclips'],
                   cwd=LOW, env=dict(os.environ, **env), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    R.sheets['lowered'] = R.out + f'/lowered_{R.gid}_strip.png'


def render_raised(R):
    RAI = AUTH + '/raised'; pm = R.out + '/manifest.proposed.json'
    env = dict(os.environ, **R.env(pm)); env['RAISEDCLIPS'] = R.out + '/raisedclips'
    subprocess.run(PY + [RAI + '/rmakeclips.py', '--poses', R.found['raised']['pose'], '--out', R.out + '/raisedclips'], cwd=RAI, env=env, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(PY + [RAI + '/rpreview.py', 'sheet', R.gid, '--out', R.out + '/raised_sheet'], cwd=RAI, env=env, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    R.sheets['raised'] = R.out + f'/raised_sheet/pma_{R.gid}_before_after.png'


def apply_entry(R):
    if R.shipped is not None:
        fail(f'--apply: {R.gid} is already in weapons.json; edit shipped entries by hand', 2)
    p = BASE
    s = open(p, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    body = (',' + nl + '  {' + nl + (',' + nl).join(f'   {json.dumps(k)}: {json.dumps(v)}' for k, v in R.proposed.items()) + nl + '  }')
    tail = nl + ' ]' + nl + '}'
    i = s.rstrip().rfind(tail.strip())
    j = s.rfind('}', 0, s.rfind(']'))
    s2 = s[:j + 1] + body + s[j + 1:]
    json.loads(s2)
    open(p, 'w', encoding='utf-8', newline='').write(s2)
    print(f'weapons.json: added {R.gid}')


def add(argv):
    dry = '--dry-run' in argv
    if dry: argv.remove('--dry-run')
    apply = '--apply' in argv
    if apply: argv.remove('--apply')
    render = '--render' in argv
    if render: argv.remove('--render')
    out = take_opt(argv, '--out'); seed_p = take_opt(argv, '--from'); ack = (take_opt(argv, '--ack') or '').split(',')
    if len(argv) != 1 or argv[0].startswith('-'):
        fail('usage: ga.sh gun add <id> [--from <seed.json>] [--out <dir>] [--dry-run] [--apply] [--ack step,step|all] [--render]')
    gid = argv[0]
    m = json.load(open(BASE, encoding='utf-8'))
    shipped = next((g for g in m['guns'] if g['id'] == gid), None)
    if seed_p:
        seed = json.load(open(seed_p, encoding='utf-8'))
        if seed.get('id', gid) != gid: fail(f'{seed_p}: id {seed.get("id")} is not {gid}')
        seed['id'] = gid
    elif shipped is not None:
        seed = shipped
    else:
        fail(f'{gid} is not in weapons.json: give its hand-entered fields with --from <seed.json> (see --help)')
    if 'type' not in seed or seed['type'] not in m['types']:
        fail(f'the seed has no known type (one of {", ".join(m["types"])})')
    out = os.path.abspath(out or (manifest.path('authoring_work') + '/gun_add/' + gid)).replace('\\', '/').rstrip('/')
    R = Run(gid, seed, shipped, out, ack, render, {k: seed[k] for k in DERIVED if k in seed} if seed_p else None)
    steps = plan(R)
    print(f'gun add {gid}: type {seed["type"]}, ' + ('reproduction of the weapons.json entry (derived fields stripped)' if shipped is not None and not seed_p else 'new entry')
          + (' (dry run: nothing is run or written)' if dry else f', out {out}'))
    if dry:
        for i, s in enumerate(steps, 1):
            if s.skip:
                print(f'{i}. {s.name}: skipped, {s.skip}'); continue
            show(i, s)
            print(f'   owner:  {"needs the owner\'s eye: stops with a sheet" if s.eye else "no"}')
        print('rule: the lowered family follows the length (v1d over checks.lowered.v1d_over_cm, else v1) and a raised C pose exists only over checks.raised.limit_pct; a gun that does not follow it is refused, naming the field')
        return 0
    os.makedirs(out, exist_ok=True)
    R.write_manifest(R.scratch, strip(seed))
    os.environ['GA_MANIFEST'] = R.scratch; manifest._m = None
    code = execute(R, steps)
    if code == 0 and apply: apply_entry(R)
    return code
