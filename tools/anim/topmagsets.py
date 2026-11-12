"""The top-magazine reload anim sets: which to build from which clips, and their archive.xl entries.

Clips live in CLIPS/<body>/ (see build.sh). A single top-magazine gun's clip depends on the partner gun in the other
hand (its size decides where the striking gun lands): weapons.json gives each partner gun
a category per pick, and each distinct (flip, doubletap, uppercut) combination becomes one set. A set's archive.xl
entries list the partner variables it serves; unknown partners get the default combination.

usage: topmagsets.py <clips dir> sets   -> one line per set: <body> <set name> <clip glb>=<clip name> ...
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifest

# Top-magazine guns whose clips are built: weapons.json, topmag.enabled. The Midnight Borg also has a top magazine, but
# the game has no player version of it (its only records, Borg4a, are cut content named "!OBSOLETE"), so it is
# disabled there and its clips (in anim-work) are not built.
GUNS = {name: (code, model) for name, code, model, _ in manifest.topmag_guns()}
PICKS = ('flip', 'doubletap', 'uppercut')
BODIES = manifest.bodies()
# Clip names: a right gun's clips are its own reload; a left gun's play as an empty reload in the right hand's part
# of the arm graph; a pair's replace the right gun's reload.
NAMES = {'right': ('reload', 'reload_01', 'reload_02'), 'left': ('empty_reload', 'empty_reload_01', 'empty_reload_02')}
PAIR_PICKS = ('overunder', 'scissor', 'clap')
# Long shotguns get their own three clips (the SMG picks swing them across the face), one set per gun:
# <gun>_<side>_<long pick>_<partner>.glb. A partner without all three clips falls back to the size categories.
LONG = manifest.long_partners()
LONG_PICKS = ('lupper', 'axe', 'hang')
# archive.xl priorities (a lower number wins). Strict tiers, so no two sets that can both match one pair of guns share
# a number: long partner (model variable, then base variable), two top-magazine guns, size category partner (model,
# then base variable), the default set.
PRIO = {'raised': 56, 'long': 57, 'long_base': 58, 'pair': 59, 'category': 60, 'base': 61, 'default': 63}
# A partner gun with a raised pose of its own (weapons.json "raised") gets a copy of the set it would play, with the
# partner arm starting and ending in that pose: RAISEDCLIPS/<body>/topmag/<clip>__<pose>.glb (authoring/raised).
# Without those clips it stays on the shared set (the reload then ends with a jump of the partner arm).
# Its entries are keyed on the gun's model variable and sit above every other tier (PRIO raised): a gun also sets its
# type's base variable, and a long set keyed on that (long_base) would otherwise beat the gun's own category set
# (seen in game: the Hercules played the generic rifle's long clips, which end in the pistol pose).
RAISED = manifest.raised_poses()
# A top-magazine gun as the partner is the pair case: no single-gun entry for it.
TOPMAG_MODELS = {model for _, model in GUNS.values()}


def short(cat):
    return cat.replace('_', '')


def plan(clips):
    """[(body, set name, [(clip path, clip name)], [(vars, priority)])]"""
    cats = manifest.partner_categories()
    out = []
    for body in BODIES:
        for gun, (_, model) in GUNS.items():
            for side in ('left', 'right'):
                gun_var = model + ('_left' if side == 'left' else '')
                partner_var = lambda var: var + ('' if side == 'left' else '_left')
                long_sets = {}
                for var, lname in LONG.items():
                    paths = [f'{clips}/{body}/{gun}_{side}_{p}_{lname}.glb' for p in LONG_PICKS]
                    if all(os.path.exists(p) for p in paths):
                        long_sets[var] = (f'{body}_topmag_{gun}_{side}_long_{lname}', paths)
                gc = cats.get(gun)
                combos = {}
                if gc:
                    default = tuple(gc['default'][p] for p in PICKS)
                    combos[default] = [None]
                    partners = set()
                    for p in PICKS:
                        partners.update(gc[p].keys())
                    for var in sorted(partners - set(long_sets)):
                        combo = tuple(gc[p].get(var, gc['default'][p]) for p in PICKS)
                        combos.setdefault(combo, []).append(var)
                else:
                    combos[None] = [None]
                for combo, partners in combos.items():
                    if combo is None:
                        files = [f'{gun}_{side}_{p}.glb' for p in PICKS]
                        name = f'{body}_topmag_{gun}_{side}'
                    else:
                        files = [f'{gun}_{side}_{p}_{c}.glb' for p, c in zip(PICKS, combo)]
                        name = f'{body}_topmag_{gun}_{side}_' + '_'.join(short(c) for c in combo)
                    paths = [f'{clips}/{body}/{f}' for f in files]
                    if not all(os.path.exists(p) for p in paths):
                        continue
                    entries = []
                    for var in partners:
                        if var is None:
                            entries.append(([gun_var], PRIO['default']))
                        elif var not in TOPMAG_MODELS:
                            entries.append(([gun_var, partner_var(var)],
                                            PRIO['base' if var.startswith('w_base_') else 'category']))
                    out.append((body, name, list(zip(paths, NAMES[side])), entries))
                # One set per long partner name; guns that share a name (borrowed clips) share the set.
                by_name = {}
                for var, (name, paths) in long_sets.items():
                    entry = ([gun_var, partner_var(var)], PRIO['long_base' if var.startswith('w_base_') else 'long'])
                    if name in by_name:
                        by_name[name].append(entry)
                    else:
                        by_name[name] = [entry]
                        out.append((body, name, list(zip(paths, NAMES[side])), by_name[name]))
        # Pairs: <left gun><right gun>.
        for lgun, (lcode, lmodel) in GUNS.items():
            for rgun, (rcode, rmodel) in GUNS.items():
                paths = [f'{clips}/{body}/pair_{lcode}{rcode}_{p}.glb' for p in PAIR_PICKS]
                if not all(os.path.exists(p) for p in paths):
                    continue
                out.append((body, f'{body}_topmag_pair_{lcode}{rcode}', list(zip(paths, NAMES['right'])),
                            [([rmodel, lmodel + '_left'], PRIO['pair'])]))
    return _raised(out)


def raised_clip(path, pose):
    """The raised-partner version of an arm clip."""
    d, f = os.path.split(path)
    return f'{manifest.path("raised_clips")}/{os.path.basename(d)}/topmag/{f[:-4]}__{pose}.glb'


def raised_sources(clips):
    """[(body, clip path, raised pose, partner hand 'Right' or 'Left')]: the clips the raised partner sets are made
    from (authoring/raised/rmakeclips.py)."""
    out = []
    for body, name, files, entries in _shared(clips):
        for vars_, _ in entries:
            pose = RAISED.get(vars_[1][:-5] if vars_[1].endswith('_left') else vars_[1]) if len(vars_) == 2 else None
            if pose:
                out += [(body, p, pose, 'Left' if vars_[1].endswith('_left') else 'Right') for p, _ in files
                        if (body, p, pose) not in [(a, b, c) for a, b, c, _ in out]]
    return out


def _shared(clips):
    global RAISED
    keep, RAISED = RAISED, {}
    try:
        return plan(clips)
    finally:
        RAISED = keep


def _raised(sets):
    if not RAISED:
        return sets
    out = []
    for body, name, files, entries in sets:
        by_pose = {}
        for e in entries:
            v = e[0][1] if len(e[0]) == 2 else ''
            pose = RAISED.get(v[:-5] if v.endswith('_left') else v)
            if pose and all(os.path.exists(raised_clip(p, pose)) for p, _ in files):
                by_pose.setdefault(pose, []).append(e)
        moved = [e for es in by_pose.values() for e in es]
        rest = [e for e in entries if e not in moved]
        # The shared set stays in place (the same list object: sets of one long partner name share their entries).
        entries[:] = rest
        out.append((body, name, files, entries))
        for pose, es in sorted(by_pose.items()):
            out.append((body, f'{name}_raised_{pose}', [(raised_clip(p, pose), n) for p, n in files], [(v, PRIO['raised']) for v, _ in es]))
    return out


if __name__ == '__main__' and len(sys.argv) > 2 and sys.argv[2] == 'sets':
    for body, name, clips, _ in plan(sys.argv[1]):
        print(body, name, ' '.join(f'{p}={n}' for p, n in clips))
