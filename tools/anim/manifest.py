"""Reads weapons.json, the single source of gun knowledge, and gives each tool its table.

Test content (status "test") is left out unless GA_TEST=1 (build.sh --with-test sets it). Paths come from the
manifest's paths block; each can be overridden by its environment variable.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PICKS = ('flip', 'doubletap', 'uppercut')
_m = None


def load():
    global _m
    if _m is None:
        _m = json.load(open(os.environ.get('GA_MANIFEST') or os.path.join(HERE, 'weapons.json'), encoding='utf-8'))
        _check(_m)
    return _m


def with_test():
    return os.environ.get('GA_TEST') == '1'


def path(key):
    """A path of the paths block. A relative default is relative to this folder (data kept in the repo)."""
    p = load()['paths'][key]
    v = (os.environ.get(p['env']) or p['default']).replace('\\', '/')
    if ';' not in v and not os.path.isabs(v):
        v = os.path.join(HERE, v).replace('\\', '/')
    return v


def paths(key):
    """A path entry that lists several folders, separated by ';' (searched in order)."""
    return [d.rstrip('/') for d in path(key).split(';') if d]


def find(key, name):
    """The first of the entry's folders that holds the file, or None."""
    for d in paths(key):
        if os.path.exists(d + '/' + name):
            return d + '/' + name
    return None


def depot(p):
    """manifest path (forward slashes) -> depot path (backslashes)"""
    return p.replace('/', '\\')


def gamefile(depot_path, ext=''):
    """Where an extracted game file lives: <gamefiles>/<depot path><ext> (.glb export, .json conversion)."""
    return path('gamefiles') + '/' + depot_path.replace('\\', '/') + ext


def _check(m):
    c = m['reload_clip']; f, s, fps = c['frames'], c['seconds'], float(c['fps'])
    want = {'open_end': f['open'] / fps, 'drop_end': (f['open'] + f['drop']) / fps, 'hold_end': f['pre'] / fps,
            'plain_drop': f['plain'] / fps, 'rise_length': (f['rise'][1] - f['rise'][0]) / fps}
    for k, v in want.items():
        if abs(s[k] - v) > 1e-6:
            raise SystemExit(f'weapons.json: reload_clip seconds.{k} is {s[k]}, the frames give {v:.4f}')
    ids = set()
    for g in m['guns']:
        if g['id'] in ids:
            raise SystemExit(f'weapons.json: gun id {g["id"]} twice')
        ids.add(g['id'])
        t = m['types'].get(g['type'])
        if t is None:
            raise SystemExit(f'weapons.json: gun {g["id"]} has unknown type {g["type"]}')
        if g['item_type'] not in [i['name'] for i in t['item_types']]:
            raise SystemExit(f'weapons.json: gun {g["id"]}: item type {g["item_type"]} is not one of type {g["type"]}')
        if g.get('status', 'release') not in ('release', 'test', 'disabled'):
            raise SystemExit(f'weapons.json: gun {g["id"]}: bad status')


def reload_set(body, side, old=False):
    """Name of a per-hand reload arm set; old: its name before the rename (set_names.reload_before_rename)."""
    return load()['set_names']['reload_before_rename' if old else 'reload'].format(body=body, side=side)


def mag_spec(spec_path=None):
    """The magazine flight spec with its clip paths made absolute. A clip is named relative to paths.clips
    (<body>/<clip>.glb), or to another paths entry as "<key>:<body>/<clip>.glb"; an absolute path is taken as it is."""
    spec = json.load(open(spec_path or path('mag_spec'), encoding='utf-8'))

    def full(c):
        if os.path.isabs(c):
            return c
        key, _, rel = c.rpartition(':')
        return path(key or 'clips') + '/' + rel

    for key, entries in spec.items():
        if key.startswith('_'):
            continue
        for e in entries:
            e['clips'] = [full(c) for c in e['clips']]
            if 'pose_clips' in e:
                e['pose_clips'] = [full(c) for c in e['pose_clips']]
    return spec


# ---- types ---------------------------------------------------------------------------------------------------------
def _on(status):
    return status == 'release' or (status == 'test' and with_test())


def types():
    """{key: type} of the types the mod handles in this build."""
    return {k: t for k, t in load()['types'].items() if _on(t.get('status', 'release'))}


def item_types():
    """[(item type entry, type key, type)] of the handled types, in manifest order."""
    return [(i, k, t) for k, t in types().items() for i in t['item_types']]


def item_type(name):
    for t in load()['types'].values():
        for i in t['item_types']:
            if i['name'] == name:
                return i
    raise KeyError(name)


# ---- guns ----------------------------------------------------------------------------------------------------------
def gun_vars(g):
    """Model variables of a gun; a generic entry stands for its item type's base variable."""
    if g.get('generic'):
        return [item_type(g['item_type'])['base_var']]
    return list(g['vars'])


def guns(all_=False):
    """Guns of this build, in manifest order. A gun without a status takes its type's."""
    out = []
    for g in load()['guns']:
        status = g.get('status') or load()['types'][g['type']].get('status', 'release')
        if all_ or _on(status):
            out.append(g)
    return out


def arm_guns():
    """Guns that get the mod's own arm clips and lowered stance."""
    return [g for g in guns() if load()['types'][g['type']].get('arm_clips')]


def models():
    """genxl: model variables that get the per-hand reload arm sets."""
    return [v for g in arm_guns() for v in gun_vars(g)]


def base_vars():
    """Base variables of the arm clip types (a lower archive.xl tier than a gun's own variable)."""
    return {v for g in arm_guns() if g.get('generic') for v in gun_vars(g)}


def poses():
    """lowsets (poses.json): {model variable: lowered pose}"""
    return {v: g['lowered']['pose'] for g in arm_guns() if g.get('lowered') for v in gun_vars(g)}


def tunes():
    """Lowered authoring (tunes.json): {mesh stem: {'d': [x, y, z]}}"""
    out = {}
    for g in arm_guns():
        low = g.get('lowered') or {}
        if 'tune' in low and g.get('mesh'):
            out[g['mesh']] = {'d': low['tune']}
    return out


def lowered_guns():
    """Lowered authoring (guns.py GUNS): {model variable: (mesh stem or None, family)}"""
    return {v: (g.get('mesh'), g['lowered']['family']) for g in arm_guns() if g.get('lowered') for v in gun_vars(g)}


def raised_poses():
    """{model variable: raised pose} of the guns with a raised pose of their own (family "none": the game pose)."""
    return {v: g['raised']['pose'] for g in arm_guns() if (g.get('raised') or {}).get('family', 'none') != 'none'
            for v in gun_vars(g)}


def raised_defs():
    """{raised pose: (family, {body: s})}"""
    out = {}
    for g in arm_guns():
        r = g.get('raised') or {}
        if r.get('family', 'none') == 'none':
            continue
        d = (r['family'], dict(r['s']))
        if out.setdefault(r['pose'], d) != d:
            raise SystemExit(f'weapons.json: raised pose {r["pose"]} has two definitions (gun {g["id"]})')
    return out


def raised_reload_set(body, side, pose):
    """Name of a gun's own per-hand reload arm set (it ends in the gun's raised pose)."""
    return f'{reload_set(body, side)}_{pose}'


def raised_base_set(body, side, pose):
    """Name of a gun's raised pose set (the pose clips of the game's dual-wield base set)."""
    return f'{body}_dual_wield_{side}_raised_{pose}'


def borrowed_sets():
    """genxl: [(model variable, set path template with {body} and {side})] for guns of handled types that use the
    game's dual-wield sets, have none of their own and name a gun to borrow them from (game_dual.borrow_sets)."""
    byid = {g['id']: g for g in load()['guns']}
    out = []
    for g in guns():
        t = load()['types'][g['type']]
        gd = g.get('game_dual') or {}
        if g['type'] in types() and not t.get('arm_clips') and gd.get('borrow_sets'):
            out += [(v, byid[gd['borrow_sets']]['game_dual']['sets']) for v in gun_vars(g)]
    return out


def topmag_guns(enabled_only=True):
    """[(clip name, pair code, model variable, gun)] of the top-magazine guns."""
    return [(g['topmag']['clip_name'], g['topmag']['pair_code'], gun_vars(g)[0], g) for g in guns()
            if 'topmag' in g and (g['topmag'].get('enabled') or not enabled_only)]


def partner_categories(enabled_only=True):
    """topmagsets (partner_categories.json): {top-mag gun: {pick: {partner variable: category}, 'default': {pick: category}}}"""
    out = {}
    for name, _, _, tg in topmag_guns(enabled_only):
        cats = {p: {} for p in PICKS}
        for g in guns():
            row = (g.get('partner') or {}).get(name)
            if not row:
                continue
            for v in gun_vars(g):
                for p, c in zip(PICKS, row):
                    cats[p][v] = c
        cats['default'] = dict(zip(PICKS, tg['topmag']['partner_default']))
        out[name] = cats
    return out


def long_partners():
    """topmagsets LONG: {model variable: long partner name}, the variables whose long clip set is keyed on them."""
    out = {}
    for g in guns():
        if g.get('long_partner'):
            for v in g.get('long_partner_vars', gun_vars(g)):
                out[v] = g['long_partner']
    return out


def long_audio():
    """Script: {audio set: long partner name}"""
    return {a: g['long_partner'] for g in guns() if g.get('long_partner') for a in g.get('audio', [])}


def sound_sets():
    """gensounds: [(arm set depot path, [audio sets])] of the guns with their own reload sounds."""
    return [(depot(g['arm_set']), list(g['audio'])) for g in arm_guns() if g.get('arm_set') and g.get('audio')]


def magazine():
    """The top-magazine gun whose magazine sets are built (magtrack.py), or None."""
    for _, _, _, g in topmag_guns():
        if 'magazine' in g['topmag']:
            return g['topmag']['magazine']
    return None


def entities(body):
    return [depot(e) for e in load()['game_files']['bodies'][body]]


def bodies():
    return tuple(load()['game_files']['bodies'])


def needed_game_files():
    """[(depot path, {'glb', 'json'})]: every game file the build reads and the forms it needs besides the raw file."""
    gf = load()['game_files']
    out = {}

    def add(p, *forms):
        out.setdefault(depot(p), set()).update(forms)

    for body in bodies():
        for side in ('right', 'left'):
            add(gf['reload_source'].format(body=body, side=side), 'glb')
        add(gf['lowered_base'].format(body=body), 'glb')
    mag = magazine()
    if mag:
        add(mag['vanilla_set'], 'glb')
        add(mag['weapon_set'], 'glb')
    for p, _ in sound_sets():
        add(p, 'json')
    return sorted(out.items())


if __name__ == '__main__':
    import sys
    what = sys.argv[1] if len(sys.argv) > 1 else 'guns'
    if what == 'guns':
        for g in guns(all_=True):
            st = g.get('status') or load()['types'][g['type']].get('status', 'release')
            print(f'{g["id"]:24s} {g["type"]:9s} {st:8s} {" ".join(gun_vars(g))}')
    elif what == 'path':
        print(path(sys.argv[2]))
    elif what == 'files':
        for p, forms in needed_game_files():
            print(p, ' '.join(sorted(forms)))
