"""The rule manifest (tools/anim/rules.json): the owner's standard, one row per rule.

Read by: draftcheck.py (every item a clip check emits must be registered here: `registered()`), the gate area `rules` of build.sh check (`run()`),
ga produce and ga drafts (both run draftcheck), STANDARD.md (`markdown()`).

A row: id, name, statement, source (owner quote and date, or the measurement), population, limit, scope, stance (inactive = lowered, game Safe;
active = raised), enforcement {kind: gate | owner-eye | not-enforceable, ...}, warden_only, old_names.
A gate row names the check that enforces it: area (draft, pose, lowered, raised, lowvar, clips, rreload, topmag, manifest, rules, ga produce, ga pick),
items (draft items it emits) or label (text the area's check prints), limit_ref (the weapons.json checks path that holds the limit).

usage: rules.py                 validate (exit 1 on a problem)
       rules.py --markdown      print the table as markdown (STANDARD.md)
"""
import os, sys, json, re
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
ANIM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ANIM); sys.path.insert(0, os.path.join(HERE, '..'))
import manifest

KINDS = ('gate', 'owner-eye', 'not-enforceable')
FIELDS = ('id', 'name', 'statement', 'source', 'population', 'limit', 'scope', 'stance', 'enforcement')
# area -> files whose text must contain a gate row's items or label
SRC = {'draft': ['authoring/checks/draftcheck.py', 'authoring/checks/stdrules.py'], 'pose': ['authoring/pose/checks.py'], 'lowered': ['authoring/lowered/checks.py'],
       'raised': ['authoring/raised/checks.py'], 'lowvar': ['authoring/lowvar/checks.py'], 'clips': ['authoring/checks/gate.py'], 'rreload': ['authoring/reload/checks.py', 'authoring/reload/rgate.py'],
       'topmag': ['authoring/topmag/checks.py'], 'manifest': ['authoring/checks/gate.py'], 'rules': ['authoring/checks/rules.py'], 'ga produce': ['ga.py'], 'ga pick': ['authoring/draft/drafts.py']}


def path():
    return os.environ.get('GA_RULES') or os.path.join(ANIM, 'rules.json')


def load():
    return json.load(open(path(), encoding='utf-8'))['rules']


def registered():
    """{(draftcheck rule, item name)}: the items every clip check may emit. A rule id that is a draftcheck rule name (R1 ...) lists its items."""
    return {(r['id'], i) for r in load() if r['enforcement']['kind'] == 'gate' and r['enforcement'].get('area') == 'draft' and r['id'].startswith(('R', 'TM', 'H')) for i in r['enforcement'].get('items', [])}


def _text(files):
    return '\n'.join(open(os.path.join(ANIM, f), encoding='utf-8', errors='replace').read() for f in files)


def _ref(ref):
    v = manifest.load()
    for k in ref.split('.'):
        if not isinstance(v, dict) or k not in v: return None
        v = v[k]
    return v


def row(check, item, value, threshold, unit, ok, note=''):
    return {'check': check, 'item': item, 'value': value, 'threshold': threshold, 'unit': unit, 'ok': bool(ok), 'note': note}


def check_wiring():
    """V2: a gun with a lowered-stance variant plays a clip that passes R9 in every stance: its raised variant needs the same wiring (wrapper, priority, layout)."""
    bad = []
    for g in manifest.load()['guns']:
        r = g.get('reload') or {}; lv = r.get('lowered_variant'); rv = r.get('raised_variant')
        if not (lv or rv) or r.get('parked'): continue
        if lv and not rv: bad.append(f'{g["id"]}: no raised_variant')
        elif rv and not (rv.get('layout') and rv.get('clips')): bad.append(f'{g["id"]}: raised_variant built but not wired (has {sorted(rv)}; the active stance plays the shipped clips)')
        if lv and not all(k in lv for k in ('wrapper', 'priority', 'layout')): bad.append(f'{g["id"]}: lowered_variant not wired')
    return bad


def check_hashes():
    """A1, A2: the approved outputs and the frozen shipped input clips equal the committed sha256 (tools/anim/approved.json). -> [(group, bad: [str], n)]"""
    import hashlib
    J = json.load(open(os.path.join(ANIM, 'approved.json'))); out = []
    for group in ('approved', 'frozen_inputs'):
        bad = []; n = 0
        for k, want in J[group].items():
            n += 1; parts = k.split('/')
            if parts[0] == 'vanilla_finals': p = f'{manifest.path("vanilla_finals").rstrip("/")}/{parts[1]}/{parts[2]}/o/clips/' + '/'.join(parts[3:])
            else: p = manifest.load()['paths'][parts[0]]['default'].replace(chr(92), '/').rstrip('/') + '/' + '/'.join(parts[1:])      # the committed folder, not an env override (ga produce points the clip env at its own root)
            if not os.path.exists(p): bad.append(f'{k}: missing'); continue
            if hashlib.sha256(open(p, 'rb').read()).hexdigest() != want: bad.append(f'{k}: hash differs')
        out.append((group, bad, n))
    return out


def run(*a, **k):
    rows = []; rules = load(); ids = [r['id'] for r in rules]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    rows.append(row('rules: ids unique', dup[0] if dup else f'{len(ids)} rules', len(dup), 0, 'duplicates', not dup))
    miss = [f'{r.get("id")}: {f}' for r in rules for f in FIELDS if not r.get(f)]
    rows.append(row('rules: every rule has statement, source, population, limit, scope, stance, enforcement', miss[0] if miss else 'all', len(miss), 0, 'missing fields', not miss))
    badk = [r['id'] for r in rules if r['enforcement'].get('kind') not in KINDS or (r['enforcement']['kind'] != 'gate' and not r['enforcement'].get('why'))]
    rows.append(row('rules: enforcement kind is gate, owner-eye or not-enforceable (the last two say why)', badk[0] if badk else 'all', len(badk), 0, 'rules', not badk))
    unres = []
    for r in rules:
        e = r['enforcement']
        if e['kind'] != 'gate': continue
        if e.get('limit_ref') and _ref(e['limit_ref']) is None: unres.append(f'{r["id"]}: limit_ref {e["limit_ref"]} not in weapons.json')
        files = SRC.get(e.get('area'))
        if files is None: unres.append(f'{r["id"]}: unknown area {e.get("area")}'); continue
        txt = _text(files)
        for it in e.get('items', []):
            if it not in txt and not it.startswith('swing_'): unres.append(f'{r["id"]}: item {it} is not emitted by {files}')
            if it.startswith('swing_') and 'swing_' not in txt: unres.append(f'{r["id"]}: item {it} is not emitted by {files}')
        if not e.get('items') and not e.get('label'): unres.append(f'{r["id"]}: gate without items or label')
        if e.get('label') and e['label'] not in txt: unres.append(f'{r["id"]}: label {e["label"]!r} not found in {files}')
    rows.append(row('rules: every gate rule resolves to a check that emits it and a limit in weapons.json', unres[0] if unres else f'{sum(1 for r in rules if r["enforcement"]["kind"] == "gate")} gate rules', len(unres), 0, 'unresolved', not unres))
    bl = manifest.load()['checks']['draft'].get('baselines') or {}
    rows.append(row('rules: no baselines (no exceptions)', next(iter(bl), 'checks.draft.baselines empty'), len(bl), 0, 'baselines', not bl))
    for group, bad, n in check_hashes():
        rows.append(row(f'rules: {"A1 approved outputs" if group == "approved" else "A2 frozen shipped base clips"} equal their committed sha256', bad[0] if bad else f'{n} files', len(bad), 0, 'files', not bad))
    w = check_wiring()
    rows.append(row('rules: V2 wiring, every stance plays a variant that passes R9 (raised variant wired like the lowered one)', w[0] if w else 'all wired', len(w), 0, 'guns', not w, 'build the raised wiring (genrxl, genguns, reds), then this passes'))
    return rows


def markdown():
    rules = load()
    out = ['| ID | Rule | Statement | Source | Population and limit | Scope | Stance | Enforcement |', '|---|---|---|---|---|---|---|---|']
    esc = lambda s: str(s).replace('|', '/').replace('\n', ' ')
    for r in rules:
        e = r['enforcement']
        enf = {'gate': 'gate: ' + e.get('area', '') + (' ' + ', '.join(e['items']) if e.get('items') else (' "' + e['label'] + '"' if e.get('label') else '')) + (' (limits: ' + e['limit_ref'] + ')' if e.get('limit_ref') else ''),
               'owner-eye': 'owner-eye: ' + e.get('why', ''), 'not-enforceable': 'not yet enforceable: ' + e.get('why', '')}[e['kind']]
        lim = r['population'] + '; limit ' + r['limit'] + (' (Warden mesh only until a generic limit is measured)' if r.get('warden_only') else '')
        out.append(f'| {r["id"]} | {esc(r["name"])}{" (was " + "; ".join(r["old_names"]) + ")" if r.get("old_names") else ""} | {esc(r["statement"])} | {esc(r["source"])} | {esc(lim)} | {esc(r["scope"])} | {esc(r["stance"])} | {esc(enf)} |')
    return '\n'.join(out)


if __name__ == '__main__':
    if '--markdown' in sys.argv: print(markdown()); sys.exit(0)
    bad = 0
    for x in run():
        print(('pass ' if x['ok'] else 'FAIL ') + x['check'] + ': ' + str(x['item'])); bad += not x['ok']
    sys.exit(1 if bad else 0)
